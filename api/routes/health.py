from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter
from ..schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["system"])

@router.get("/", response_model=HealthResponse)
async def get_health():
    """Returns the system health status and dependency check."""
    
    # Mock dependency check for now
    # In production, check Redis, Database, SentinelAPI connectivity
    dependencies = {
        "copernicus_hub": "available",
        "google_earth_engine": "available",
        "open_meteo": "available",
        "redis": "available"
    }
    
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow(),
        "dependencies": dependencies
    }
