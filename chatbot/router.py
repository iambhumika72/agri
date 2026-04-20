import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import List

from iot.models import AsyncSessionLocal
from iot.cache import get_redis
from .schemas import ChatRequest, ChatResponse, VoiceChatResponse, ChatMessage, ConversationHistory
from .models import ChatSession, ChatMessageModel
from .memory_manager import MemoryManager
from .context_builder import ContextBuilder
from .intent_detector import detect_intent, get_intent_instruction, detect_language
from .gemini_client import gemini_client
from .voice_handler import transcribe_audio, generate_audio
from fastapi import File, UploadFile, Form

router = APIRouter()

memory_manager = MemoryManager()
context_builder = ContextBuilder()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def _process_chat_logic(
    farmer_id: str,
    session_id: str,
    message: str,
    requested_lang: str,
    db: AsyncSession,
    redis_client
) -> tuple[str, str, list[str], str, int]:
    
    # 1. Detect Intent and Lang
    lang = detect_language(message) if not requested_lang else requested_lang
    intent = detect_intent(message)
    intent_instruction = get_intent_instruction(intent)
    
    # 2. Build Context
    context_data, sources_used = await context_builder.build_context(farmer_id, db, redis_client)
    context_text = context_builder.format_context_as_text(context_data)
    
    # 3. Get Memory
    history = await memory_manager.get_formatted_for_gemini(session_id, db, redis_client)
    
    # 4. Build System Prompt
    system_prompt = gemini_client.build_system_prompt(context_text, intent, lang, intent_instruction)
    
    # 5. Gemini Chat
    reply, tokens_used = await gemini_client.chat(
        message=message,
        history=history,
        system_prompt=system_prompt,
        farmer_id=farmer_id
    )
    
    # 6. Save User Message
    await memory_manager.add_message(
        session_id=session_id,
        farmer_id=farmer_id,
        role="user",
        content=message,
        db=db,
        redis=redis_client,
        intent=intent,
        context_snapshot=context_data,
        tokens_used=0
    )
    
    # 7. Save Assistant Message
    await memory_manager.add_message(
        session_id=session_id,
        farmer_id=farmer_id,
        role="assistant",
        content=reply,
        db=db,
        redis=redis_client,
        intent=intent,
        context_snapshot=context_data,
        tokens_used=tokens_used
    )
    
    return reply, lang, sources_used, intent, tokens_used

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    redis_client = get_redis()
    reply, lang, sources_used, intent, tokens_used = await _process_chat_logic(
        request.farmer_id, request.session_id, request.message, request.lang, db, redis_client
    )
    
    return ChatResponse(
        session_id=request.session_id,
        reply=reply,
        reply_lang=lang,
        context_used=sources_used,
        intent=intent,
        timestamp=datetime.now(timezone.utc),
        tokens_used=tokens_used
    )

@router.post("/voice-chat", response_model=VoiceChatResponse)
async def voice_chat(
    file: UploadFile = File(...),
    farmer_id: str = Form(...),
    session_id: str = Form(...),
    lang: str = Form("hi"),
    db: AsyncSession = Depends(get_db)
):
    redis_client = get_redis()
    
    # 1. Transcribe Audio
    try:
        audio_bytes = await file.read()
        transcribed_text = await transcribe_audio(audio_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # 2. Process Chat Logic
    reply, out_lang, sources_used, intent, tokens_used = await _process_chat_logic(
        farmer_id, session_id, transcribed_text, lang, db, redis_client
    )
    
    # 3. Generate Audio
    audio_base64 = await generate_audio(reply, lang=out_lang)
    
    return VoiceChatResponse(
        session_id=session_id,
        reply=reply,
        reply_lang=out_lang,
        context_used=sources_used,
        intent=intent,
        timestamp=datetime.now(timezone.utc),
        tokens_used=tokens_used,
        audio_base64=audio_base64
    )

@router.get("/history/{session_id}", response_model=List[ChatMessage])
async def get_history(session_id: str, farmer_id: str, db: AsyncSession = Depends(get_db)):
    # Auth check
    stmt = select(ChatSession).where(ChatSession.session_id == session_id, ChatSession.farmer_id == farmer_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Session does not belong to farmer")
        
    redis_client = get_redis()
    history = await memory_manager.get_history(session_id, db, redis_client)
    return history

@router.get("/sessions/{farmer_id}")
async def list_sessions(farmer_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ChatSession).where(ChatSession.farmer_id == farmer_id).order_by(ChatSession.last_active.desc()).limit(20)
    res = await db.execute(stmt)
    sessions = res.scalars().all()
    return [{"session_id": s.session_id, "created_at": s.created_at, "last_active": s.last_active, "message_count": s.message_count} for s in sessions]

@router.delete("/session/{session_id}")
async def clear_session(session_id: str, db: AsyncSession = Depends(get_db)):
    # Delete from DB
    stmt = select(ChatSession).where(ChatSession.session_id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if session:
        await db.delete(session)
        # Cascade should delete messages or we do it explicitly if needed
        msg_stmt = select(ChatMessageModel).where(ChatMessageModel.session_id == session_id)
        msg_res = await db.execute(msg_stmt)
        msgs = msg_res.scalars().all()
        for msg in msgs:
            await db.delete(msg)
        await db.commit()
        
    # Delete from Redis
    redis_client = get_redis()
    if redis_client:
        await redis_client.delete(memory_manager.REDIS_KEY.format(session_id=session_id))
        
    return {"status": "cleared"}

@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    # Check Gemini
    gemini_status = "ok" if await gemini_client.health_check() else "error"
    
    # Check Redis
    redis_client = get_redis()
    redis_status = "ok" if redis_client else "unavailable"
    
    # Check DB
    db_status = "ok"
    try:
        await db.execute(select(1))
    except Exception:
        db_status = "error"
        
    return {
        "gemini_status": gemini_status,
        "redis_status": redis_status,
        "db_status": db_status,
        "model": gemini_client.model_name
    }
