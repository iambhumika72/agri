import logging
import httpx
from typing import Optional
from .schemas import IoTReading

logger = logging.getLogger(__name__)

def transform_for_pipeline(iot_reading: Optional[IoTReading], existing_features: dict) -> dict:
    """
    Takes an IoT reading and merges into feature_builder.py's expected format.
    """
    if not iot_reading:
        return {
            "soil_moisture": None,
            "soil_temperature": None,
            "air_humidity": None,
            "ph_level": None,
            "leaf_wetness": None,
            "nitrogen": None,
            "phosphorus": None,
            "potassium": None,
            "iot_quality_score": 0.0,
            "iot_source": "none",
            "iot_anomaly_detected": False,
            "iot_timestamp": None,
        }

    return {
        "soil_moisture": iot_reading.soil_moisture,
        "soil_temperature": iot_reading.temperature,
        "air_humidity": iot_reading.humidity,
        "ph_level": iot_reading.ph_level,
        "leaf_wetness": iot_reading.leaf_wetness,
        "nitrogen": iot_reading.nitrogen,
        "phosphorus": iot_reading.phosphorus,
        "potassium": iot_reading.potassium,
        "iot_quality_score": iot_reading.quality_score,
        "iot_source": iot_reading.source,
        "iot_anomaly_detected": False, # Will be set during ingestion if anomaly exists
        "iot_timestamp": iot_reading.timestamp.isoformat(),
    }

async def notify_pipeline(farmer_id: str, anomaly_type: str):
    """
    Called by ingestor when anomaly detected.
    Triggers priority re-run of forecaster for this farmer.
    POST to internal /pipeline/trigger endpoint.
    """
    logger.info(f"Notifying pipeline of anomaly for farmer {farmer_id}: {anomaly_type}")
    try:
        # Example internal POST. Real endpoint depends on pipeline config.
        async with httpx.AsyncClient() as client:
            # Assuming backend is running locally or we know the base URL.
            # Replace 'http://localhost:8000' with actual config if necessary
            # For this context, we will just log the intended action to avoid failing if not present
            logger.info("Pipeline notify trigger is a stub until `/pipeline/trigger` is implemented.")
            # await client.post("http://localhost:8000/pipeline/trigger", json={"farmer_id": farmer_id, "reason": anomaly_type})
    except Exception as e:
        logger.error(f"Failed to notify pipeline: {e}")
