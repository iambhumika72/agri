import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .schemas import IoTReading
from .models import IoTReadingModel
from .cache import cache_latest_reading, cache_stats, get_cached_stats, set_anomaly_flag
from .feature_adapter import notify_pipeline
import json

logger = logging.getLogger(__name__)

async def ingest_reading(reading: IoTReading, db: AsyncSession) -> IoTReading:
    # 1. Validate ranges
    if reading.temperature is not None and (reading.temperature < -20 or reading.temperature > 80):
        logger.warning(f"Invalid temperature {reading.temperature} for device {reading.device_id}")
        reading.temperature = None
    if reading.soil_moisture is not None and (reading.soil_moisture < 0 or reading.soil_moisture > 100):
        logger.warning(f"Invalid moisture {reading.soil_moisture} for device {reading.device_id}")
        reading.soil_moisture = None
        
    # 2. Detect anomalies (simple threshold for demonstration)
    anomaly_detected = False
    anomaly_type = None
    if reading.temperature is not None and reading.temperature > 40:
        anomaly_detected = True
        anomaly_type = "high_temperature"
        
    if anomaly_detected:
        await set_anomaly_flag(reading.farmer_id, {
            "type": anomaly_type,
            "timestamp": reading.timestamp.isoformat(),
            "device": reading.device_id
        })
        await notify_pipeline(reading.farmer_id, anomaly_type)
        
    # 3. Write to PostgreSQL (or SQLite async)
    raw_payload_dict = reading.model_dump(mode="json")
    
    db_model = IoTReadingModel(
        device_id=reading.device_id,
        farmer_id=reading.farmer_id,
        crop_type=reading.crop_type,
        lat=reading.lat,
        lng=reading.lng,
        timestamp=reading.timestamp,
        soil_moisture=reading.soil_moisture,
        temperature=reading.temperature,
        humidity=reading.humidity,
        ph_level=reading.ph_level,
        leaf_wetness=reading.leaf_wetness,
        nitrogen=reading.nitrogen,
        phosphorus=reading.phosphorus,
        potassium=reading.potassium,
        source=reading.source,
        quality_score=reading.quality_score,
        raw_payload=raw_payload_dict
    )
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    
    # 4. Update Redis cache key
    await cache_latest_reading(reading.farmer_id, reading.crop_type, reading)
    
    # 5. Update Redis stats (mock rolling avg logic)
    stats = await get_cached_stats(reading.farmer_id) or {}
    stats["avg_temp"] = reading.temperature if reading.temperature else stats.get("avg_temp", 0)
    stats["avg_moisture"] = reading.soil_moisture if reading.soil_moisture else stats.get("avg_moisture", 0)
    await cache_stats(reading.farmer_id, stats)
    
    return reading

async def get_latest_reading(farmer_id: str, crop_type: str, db: AsyncSession) -> IoTReading | None:
    from .cache import get_cached_latest
    # 1. Try Redis cache first
    cached = await get_cached_latest(farmer_id, crop_type)
    if cached:
        return cached
        
    # 2. Fallback to Database
    stmt = select(IoTReadingModel).where(
        IoTReadingModel.farmer_id == farmer_id,
        IoTReadingModel.crop_type == crop_type
    ).order_by(IoTReadingModel.timestamp.desc()).limit(1)
    
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if not record:
        return None
        
    reading = IoTReading(
        device_id=record.device_id,
        farmer_id=record.farmer_id,
        crop_type=record.crop_type,
        lat=record.lat,
        lng=record.lng,
        timestamp=record.timestamp,
        soil_moisture=record.soil_moisture,
        temperature=record.temperature,
        humidity=record.humidity,
        ph_level=record.ph_level,
        leaf_wetness=record.leaf_wetness,
        nitrogen=record.nitrogen,
        phosphorus=record.phosphorus,
        potassium=record.potassium,
        source=record.source,
        quality_score=record.quality_score
    )
    # Cache it to populate redis
    await cache_latest_reading(farmer_id, crop_type, reading)
    return reading

async def get_readings_range(
    farmer_id: str, 
    crop_type: str,
    start: datetime, 
    end: datetime,
    db: AsyncSession
) -> list[IoTReading]:
    stmt = select(IoTReadingModel).where(
        IoTReadingModel.farmer_id == farmer_id,
        IoTReadingModel.crop_type == crop_type,
        IoTReadingModel.timestamp >= start,
        IoTReadingModel.timestamp <= end
    ).order_by(IoTReadingModel.timestamp.desc())
    
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    readings = []
    for r in records:
        readings.append(IoTReading(
            device_id=r.device_id,
            farmer_id=r.farmer_id,
            crop_type=r.crop_type,
            lat=r.lat,
            lng=r.lng,
            timestamp=r.timestamp,
            soil_moisture=r.soil_moisture,
            temperature=r.temperature,
            humidity=r.humidity,
            ph_level=r.ph_level,
            leaf_wetness=r.leaf_wetness,
            nitrogen=r.nitrogen,
            phosphorus=r.phosphorus,
            potassium=r.potassium,
            source=r.source,
            quality_score=r.quality_score
        ))
    return readings
