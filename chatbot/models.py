import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Index, ForeignKey, Text
from sqlalchemy.types import JSON
from iot.models import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String(100), index=True, nullable=False)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_active = Column(DateTime(timezone=True), default=datetime.utcnow)
    message_count = Column(Integer, default=0)
    lang = Column(String(10), default="hi")

class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"), index=True, nullable=False)
    farmer_id = Column(String(100), index=True, nullable=False)
    role = Column(String(20), nullable=False) # "user" or "assistant"
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_chat_msg_session_time", "session_id", "timestamp"),
    )
