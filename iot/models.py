import os
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Float, String, DateTime, Index
)
from sqlalchemy.types import JSON
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from historical_db.models import Base

class IoTReadingModel(Base):
    __tablename__ = "iot_readings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(100), nullable=False)
    farmer_id = Column(String(100), nullable=False)
    crop_type = Column(String(100), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    
    soil_moisture = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    ph_level = Column(Float, nullable=True)
    leaf_wetness = Column(Float, nullable=True)
    nitrogen = Column(Float, nullable=True)
    phosphorus = Column(Float, nullable=True)
    potassium = Column(Float, nullable=True)
    
    source = Column(String(50), nullable=False) # simulator/hardware/manual
    quality_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    raw_payload = Column(JSON, nullable=True)

    __table_args__ = (
        Index("idx_iot_farmer_timestamp", "farmer_id", "timestamp"),
        Index("idx_iot_farmer_crop_timestamp", "farmer_id", "crop_type", "timestamp"),
        Index("idx_iot_device_timestamp", "device_id", "timestamp"),
    )

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/agrisense.db")
if DATABASE_URL.startswith("sqlite://") and not DATABASE_URL.startswith("sqlite+aiosqlite://"):
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)

async_engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

async def init_iot_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
