from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from typing import List, Optional
from datetime import datetime, timezone
import os

from sqlalchemy.ext.asyncio import AsyncSession
from .schemas import IoTReadingCreate, IoTReadingResponse, IoTLatestResponse, IoTStatsResponse, BulkIoTReading, IoTReading
from .models import AsyncSessionLocal, IoTReadingModel
from .ingestor import ingest_reading, get_latest_reading, get_readings_range
from .cache import get_cached_stats, get_sim_state
from .simulator import iot_simulator
from .hardware_bridge import hardware_bridge

router = APIRouter(prefix="/iot", tags=["IoT"])

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def attach_headers(response: Response):
    source = os.getenv("IOT_SOURCE", "simulator")
    response.headers["X-IoT-Source"] = source

@router.post("/reading", response_model=IoTReadingResponse)
async def create_reading(reading_in: IoTReadingCreate, response: Response, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    reading = IoTReading(**reading_in.model_dump(), timestamp=datetime.now(timezone.utc))
    await ingest_reading(reading, db)
    
    # Quick fetch of the newly created to get ID and created_at
    from sqlalchemy import select
    stmt = select(IoTReadingModel).where(
        IoTReadingModel.device_id == reading.device_id,
        IoTReadingModel.timestamp == reading.timestamp
    ).order_by(IoTReadingModel.created_at.desc()).limit(1)
    
    res = await db.execute(stmt)
    db_model = res.scalar_one_or_none()
    
    if db_model:
        return IoTReadingResponse(
            **reading.model_dump(),
            id=db_model.id,
            created_at=db_model.created_at
        )
    raise HTTPException(status_code=500, detail="Failed to save reading")

@router.post("/readings/bulk")
async def create_bulk_readings(bulk_in: BulkIoTReading, response: Response, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    for reading_in in bulk_in.readings:
        reading = IoTReading(**reading_in.model_dump(), timestamp=datetime.now(timezone.utc))
        await ingest_reading(reading, db)
    return {"message": f"Successfully ingested {len(bulk_in.readings)} readings"}

@router.get("/latest/{farmer_id}", response_model=List[IoTLatestResponse])
async def get_latest_all_crops(farmer_id: str, response: Response, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    # This might require querying distinct crops or having a predefined list.
    # For now, we fetch latest for the known farmer (this would ideally group by crop in SQL)
    from sqlalchemy import select
    stmt = select(IoTReadingModel.crop_type).where(IoTReadingModel.farmer_id == farmer_id).distinct()
    res = await db.execute(stmt)
    crops = res.scalars().all()
    
    results = []
    for crop in crops:
        reading = await get_latest_reading(farmer_id, crop, db)
        # Fetch db fields for response
        if reading:
            s_stmt = select(IoTReadingModel).where(
                IoTReadingModel.farmer_id == farmer_id,
                IoTReadingModel.crop_type == crop
            ).order_by(IoTReadingModel.timestamp.desc()).limit(1)
            s_res = await db.execute(s_stmt)
            db_model = s_res.scalar_one_or_none()
            if db_model:
                reading_resp = IoTReadingResponse(**reading.model_dump(), id=db_model.id, created_at=db_model.created_at)
                results.append(IoTLatestResponse(farmer_id=farmer_id, crop_type=crop, latest_reading=reading_resp))
    return results

@router.get("/latest/{farmer_id}/{crop_type}", response_model=IoTLatestResponse)
async def get_latest_crop(farmer_id: str, crop_type: str, response: Response, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    reading = await get_latest_reading(farmer_id, crop_type, db)
    
    if reading:
        from sqlalchemy import select
        stmt = select(IoTReadingModel).where(
            IoTReadingModel.farmer_id == farmer_id,
            IoTReadingModel.crop_type == crop_type
        ).order_by(IoTReadingModel.timestamp.desc()).limit(1)
        res = await db.execute(stmt)
        db_model = res.scalar_one_or_none()
        if db_model:
            reading_resp = IoTReadingResponse(**reading.model_dump(), id=db_model.id, created_at=db_model.created_at)
            
            # calculate age
            age = (datetime.now(timezone.utc) - reading.timestamp).total_seconds()
            response.headers["X-Data-Age-Seconds"] = str(int(age))
            response.headers["X-Cache-Hit"] = "true" # Simplified, we would track this in get_latest_reading
            
            return IoTLatestResponse(farmer_id=farmer_id, crop_type=crop_type, latest_reading=reading_resp)
            
    return IoTLatestResponse(farmer_id=farmer_id, crop_type=crop_type, latest_reading=None)

@router.get("/history/{farmer_id}/{crop_type}", response_model=List[IoTReadingResponse])
async def get_history(farmer_id: str, crop_type: str, start: datetime, end: datetime, response: Response, limit: int = 100, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    from sqlalchemy import select
    stmt = select(IoTReadingModel).where(
        IoTReadingModel.farmer_id == farmer_id,
        IoTReadingModel.crop_type == crop_type,
        IoTReadingModel.timestamp >= start,
        IoTReadingModel.timestamp <= end
    ).order_by(IoTReadingModel.timestamp.desc()).limit(limit)
    res = await db.execute(stmt)
    records = res.scalars().all()
    
    return [
        IoTReadingResponse(
            **IoTReading(**r.raw_payload, timestamp=r.timestamp).model_dump(),
            id=r.id,
            created_at=r.created_at
        ) for r in records
    ]

@router.get("/stats/{farmer_id}", response_model=IoTStatsResponse)
async def get_stats(farmer_id: str, response: Response):
    attach_headers(response)
    stats = await get_cached_stats(farmer_id) or {}
    from .cache import get_anomaly_flags
    anomalies = await get_anomaly_flags(farmer_id)
    return IoTStatsResponse(farmer_id=farmer_id, averages=stats, anomaly_count_24h=len(anomalies))

@router.get("/simulator/status")
async def get_sim_status(response: Response):
    attach_headers(response)
    return {
        "running": iot_simulator.is_running,
    }

@router.post("/simulator/trigger")
async def trigger_sim(response: Response):
    attach_headers(response)
    await iot_simulator._run_simulation_cycle()
    return {"status": "triggered"}

@router.get("/devices/{farmer_id}")
async def list_devices(farmer_id: str, response: Response, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    from sqlalchemy import select
    stmt = select(IoTReadingModel.device_id).where(IoTReadingModel.farmer_id == farmer_id).distinct()
    res = await db.execute(stmt)
    devices = res.scalars().all()
    return {"farmer_id": farmer_id, "devices": devices}

@router.get("/health")
async def health(response: Response, db: AsyncSession = Depends(get_db)):
    attach_headers(response)
    from sqlalchemy import select
    stmt = select(IoTReadingModel.timestamp).order_by(IoTReadingModel.timestamp.desc()).limit(1)
    res = await db.execute(stmt)
    last_timestamp = res.scalar_one_or_none()
    
    return {
        "source": os.getenv("IOT_SOURCE", "simulator"),
        "last_ingest_time": last_timestamp.isoformat() if last_timestamp else None,
        "status": "healthy"
    }
