import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .schemas import ChatMessage
from .models import ChatSession, ChatMessageModel

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Manages last 10 messages per session.
    Redis-first with SQLite fallback.
    """
    
    REDIS_KEY = "chat:history:{session_id}"  # TTL: 2 hours
    MAX_MESSAGES = 10
    
    async def get_history(self, session_id: str, db: AsyncSession, redis=None) -> list[ChatMessage]:
        # 1. Try Redis
        if redis:
            try:
                key = self.REDIS_KEY.format(session_id=session_id)
                data = await redis.lrange(key, 0, -1)
                if data:
                    return [ChatMessage(**json.loads(d)) for d in data]
            except Exception as e:
                logger.warning(f"Redis get_history failed: {e}")

        # 2. Fallback SQLite
        try:
            stmt = select(ChatMessageModel).where(
                ChatMessageModel.session_id == session_id
            ).order_by(ChatMessageModel.timestamp.desc()).limit(self.MAX_MESSAGES)
            res = await db.execute(stmt)
            records = list(res.scalars().all())
            records.reverse()
            return [
                ChatMessage(
                    role=r.role,
                    content=r.content,
                    timestamp=r.timestamp
                ) for r in records
            ]
        except Exception as e:
            logger.error(f"DB get_history failed: {e}")
            return []

    async def add_message(
        self,
        session_id: str,
        farmer_id: str,
        role: str,
        content: str,
        db: AsyncSession,
        redis=None,
        intent: str = None,
        context_snapshot: dict = None,
        tokens_used: int = None
    ):
        now = datetime.now(timezone.utc)
        
        # 1. Ensure ChatSession exists
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        res = await db.execute(stmt)
        session_obj = res.scalar_one_or_none()
        
        if not session_obj:
            session_obj = ChatSession(
                farmer_id=farmer_id,
                session_id=session_id,
                created_at=now,
                last_active=now,
                message_count=1
            )
            db.add(session_obj)
        else:
            session_obj.last_active = now
            session_obj.message_count += 1
            
        # 2. Write to SQLite
        msg_model = ChatMessageModel(
            session_id=session_id,
            farmer_id=farmer_id,
            role=role,
            content=content,
            intent=intent,
            context_snapshot=context_snapshot,
            tokens_used=tokens_used,
            timestamp=now
        )
        db.add(msg_model)
        await db.commit()
        
        # 3. Update Redis
        if redis:
            try:
                key = self.REDIS_KEY.format(session_id=session_id)
                msg_dict = {
                    "role": role,
                    "content": content,
                    "timestamp": now.isoformat()
                }
                await redis.rpush(key, json.dumps(msg_dict))
                # Trim to MAX_MESSAGES
                await redis.ltrim(key, -self.MAX_MESSAGES, -1)
                await redis.expire(key, 7200) # 2 hours
            except Exception as e:
                logger.warning(f"Redis add_message failed: {e}")

    async def get_formatted_for_gemini(self, session_id: str, db: AsyncSession, redis=None) -> list[dict]:
        history = await self.get_history(session_id, db, redis)
        
        formatted = []
        last_role = None
        
        for msg in history:
            gemini_role = "model" if msg.role == "assistant" else "user"
            
            # Deduplicate consecutive same-role messages
            if gemini_role == last_role:
                formatted[-1]["parts"][0]["text"] += f"\n\n{msg.content}"
            else:
                formatted.append({
                    "role": gemini_role,
                    "parts": [{"text": msg.content}]
                })
                last_role = gemini_role
                
        # Ensure it starts with 'user'
        if formatted and formatted[0]["role"] == "model":
            formatted.pop(0)
            
        return formatted
