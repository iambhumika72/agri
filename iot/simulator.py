import logging
import os
import asyncio
from datetime import datetime, timezone
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .schemas import IoTReading
from .models import AsyncSessionLocal
from .ingestor import ingest_reading

logger = logging.getLogger(__name__)

CROP_PROFILES = {
    "wheat":   {"soil_moisture": (40,65), "temp": (15,28), "ph": (6.0,7.5)},
    "tomato":  {"soil_moisture": (60,80), "temp": (18,30), "ph": (5.5,7.0)},
    "rice":    {"soil_moisture": (70,90), "temp": (22,35), "ph": (5.5,6.5)},
    "maize":   {"soil_moisture": (50,70), "temp": (18,32), "ph": (5.8,7.0)},
    "potato":  {"soil_moisture": (65,80), "temp": (14,22), "ph": (4.8,6.0)},
    "default": {"soil_moisture": (50,70), "temp": (18,30), "ph": (6.0,7.0)},
}

class IoTDataSource:
    async def get_current_readings(self, farmer_id: str) -> list[IoTReading]:
        raise NotImplementedError
    
    async def start(self): 
        raise NotImplementedError
    
    async def stop(self): 
        raise NotImplementedError

class IoTSimulator(IoTDataSource):
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def get_current_readings(self, farmer_id: str) -> list[IoTReading]:
        return [self._generate_mock_reading(farmer_id, "default")]

    async def start(self):
        if not self.is_running:
            interval = int(os.environ.get("IOT_SIMULATE_INTERVAL_MINUTES", "5"))
            self.scheduler.add_job(self._run_simulation_cycle, 'interval', minutes=interval)
            self.scheduler.start()
            self.is_running = True
            logger.info(f"IoTSimulator started. Running every {interval} minutes.")

    async def stop(self):
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("IoTSimulator stopped.")

    async def _run_simulation_cycle(self):
        logger.info("[SIMULATOR] Running simulation cycle...")
        mock_farmers = [("FARMER-001", "wheat"), ("FARMER-002", "tomato")]
        for farmer_id, crop in mock_farmers:
            reading = self._generate_mock_reading(farmer_id, crop)
            async with AsyncSessionLocal() as session:
                try:
                    await ingest_reading(reading, session)
                    logger.info(f"[SIMULATOR] Generated reading for {farmer_id} - {crop}")
                except Exception as e:
                    logger.error(f"[SIMULATOR] Error ingesting reading for {farmer_id}: {e}")

    def _generate_mock_reading(self, farmer_id: str, crop_type: str) -> IoTReading:
        profile = CROP_PROFILES.get(crop_type, CROP_PROFILES["default"])
        
        is_anomaly = random.random() < 0.05
        temp = random.uniform(*profile["temp"])
        if is_anomaly:
            temp += random.uniform(10, 20)
            
        return IoTReading(
            device_id=f"DEVICE-{farmer_id}-{crop_type.upper()}-SIM",
            farmer_id=farmer_id,
            crop_type=crop_type,
            lat=random.uniform(20.0, 30.0), # Realistic coords roughly
            lng=random.uniform(70.0, 80.0),
            timestamp=datetime.now(timezone.utc),
            soil_moisture=random.uniform(*profile["soil_moisture"]),
            temperature=temp,
            humidity=random.uniform(30, 80),
            ph_level=random.uniform(*profile["ph"]),
            leaf_wetness=random.uniform(0, 100),
            nitrogen=random.uniform(10, 50),
            phosphorus=random.uniform(10, 50),
            potassium=random.uniform(10, 50),
            source="simulator",
            quality_score=0.7
        )

iot_simulator = IoTSimulator()
