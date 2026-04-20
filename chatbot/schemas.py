from datetime import datetime
from typing import Literal, List, Optional
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime

class ChatRequest(BaseModel):
    farmer_id: str
    session_id: str        # UUID, frontend generates once per conversation
    message: str           # farmer's question
    lang: str = "hi"       # language code for response

class ChatResponse(BaseModel):
    session_id: str
    reply: str             # Gemini's response
    reply_lang: str        # language of response
    context_used: List[str]  # which data sources were used e.g. ["iot","weather"]
    intent: str            # detected intent e.g. "irrigation_advice"
    timestamp: datetime
    tokens_used: Optional[int]

class ConversationHistory(BaseModel):
    session_id: str
    farmer_id: str
    messages: List[ChatMessage]
    created_at: datetime
    last_active: datetime

class ContextSnapshot(BaseModel):
    # What was injected into Gemini for this message
    iot_data: Optional[dict] = None
    weather_data: Optional[dict] = None
    crop_data: Optional[dict] = None
    historical_data: Optional[dict] = None
    farmer_profile: Optional[dict] = None
    fetched_at: datetime
