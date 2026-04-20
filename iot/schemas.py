from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field

class IoTReadingBase(BaseModel):
    device_id: str = Field(..., description="Unique sensor ID e.g., 'DEVICE-FARM001-SOIL'")
    farmer_id: str = Field(..., description="Links to user in your auth system")
    crop_type: str = Field(..., description="e.g., 'wheat', 'tomato'")
    lat: float = Field(..., description="GPS coords of sensor/farm")
    lng: float = Field(..., description="GPS coords of sensor/farm")
    
    # Sensor fields
    soil_moisture: Optional[float] = Field(None, description="% (0-100)")
    temperature: Optional[float] = Field(None, description="Celsius")
    humidity: Optional[float] = Field(None, description="% (0-100)")
    ph_level: Optional[float] = Field(None, description="0-14 scale")
    leaf_wetness: Optional[float] = Field(None, description="% (0-100)")
    nitrogen: Optional[float] = Field(None, description="mg/kg")
    phosphorus: Optional[float] = Field(None, description="mg/kg")
    potassium: Optional[float] = Field(None, description="mg/kg")

    source: Literal["simulator", "hardware", "manual"]
    quality_score: float = Field(..., description="0.0-1.0, simulator=0.7, hardware=1.0, manual=0.5")

class IoTReadingCreate(IoTReadingBase):
    """Input payload for creating a reading. Timestamp is set server-side."""
    pass

class IoTReading(IoTReadingBase):
    """Full reading representation used in the system."""
    timestamp: datetime = Field(..., description="UTC always")

class IoTReadingResponse(IoTReading):
    """Output payload with DB fields."""
    id: str
    created_at: datetime

class IoTLatestResponse(BaseModel):
    """Latest reading for a specific farmer and crop."""
    farmer_id: str
    crop_type: str
    latest_reading: Optional[IoTReadingResponse]

class IoTStatsResponse(BaseModel):
    """Aggregated stats: 24hr avg per field."""
    farmer_id: str
    averages: dict[str, float]
    anomaly_count_24h: int

class BulkIoTReading(BaseModel):
    """List of IoTReadingCreate for batch upload."""
    readings: List[IoTReadingCreate] = Field(..., max_length=100)
