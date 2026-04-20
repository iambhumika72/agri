import asyncio
import uuid
import logging
import random
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

# Import models and session
from iot.models import AsyncSessionLocal, IoTReadingModel
from historical_db.models import Base, Farm, Crop, YieldRecord, PestRecord, SoilHealth, SatelliteImagery
from weather_module.weather_client import WeatherClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DemoSetup")

# Constants for Ludhiana Farm
FARM_NAME = "Gurpreet Singh's Farm"
FARM_ID = uuid.UUID("f003f003-f003-f003-f003-f003f003f003") # Consistent with seed_db.py
LAT = 30.9010
LNG = 75.8573
CROP_NAME = "Wheat"
CROP_SEASON = "Rabi"
SOIL_PH = 7.8
SOIL_N = 140.0 # Medium
SOIL_P = 8.5   # Low

async def seed_real_world_demo():
    async with AsyncSessionLocal() as session:
        logger.info("Ensuring database tables exist...")
        # Since we are using an async engine from iot.models, we can run create_all
        from iot.models import async_engine
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 1. Create Farm if not exists
        stmt = select(Farm).where(Farm.farm_id == FARM_ID)
        res = await session.execute(stmt)
        farm = res.scalar_one_or_none()
        
        if not farm:
            farm = Farm(
                farm_id=FARM_ID,
                farmer_name=FARM_NAME,
                district="Ludhiana",
                state="Punjab",
                latitude=LAT,
                longitude=LNG,
                area_hectares=3.2
            )
            session.add(farm)
            logger.info(f"Created farm: {FARM_NAME}")
        else:
            logger.info(f"Farm {FARM_NAME} already exists.")

        # 2. Create Crop if not exists
        stmt = select(Crop).where(Crop.crop_name == CROP_NAME, Crop.season_type == CROP_SEASON)
        res = await session.execute(stmt)
        crop = res.scalar_one_or_none()
        
        if not crop:
            crop = Crop(
                crop_id=uuid.uuid4(),
                crop_name=CROP_NAME,
                season_type=CROP_SEASON
            )
            session.add(crop)
            logger.info(f"Created crop: {CROP_NAME}")
        
        await session.flush()
        crop_id = crop.crop_id

        # 3. Seed Yield Statistics (ICAR data: 5.0-5.2 tonnes/hectare)
        logger.info("Seeding historical yield statistics...")
        for year in [2021, 2022, 2023]:
            # Check if record exists
            stmt = select(YieldRecord).where(YieldRecord.farm_id == FARM_ID, YieldRecord.year == year)
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                yield_val = 5100 + random.randint(-100, 100) # 5.1 t/ha average
                record = YieldRecord(
                    record_id=uuid.uuid4(),
                    farm_id=FARM_ID,
                    crop_id=crop_id,
                    season=CROP_SEASON,
                    year=year,
                    yield_kg_per_hectare=yield_val,
                    harvest_date=date(year, 4, 15),
                    notes="Standard Ludhiana Wheat Yield (ICAR benchmark)"
                )
                session.add(record)

        # 4. Seed Pest History (Aphids and Yellow Rust)
        logger.info("Seeding pest history...")
        pest_data = [
            {"name": "Aphids", "severity": 2, "date": date(2024, 2, 10)},
            {"name": "Yellow Rust", "severity": 3, "date": date(2024, 3, 5)},
        ]
        for p in pest_data:
            stmt = select(PestRecord).where(PestRecord.farm_id == FARM_ID, PestRecord.pest_name == p["name"], PestRecord.detected_date == p["date"])
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                record = PestRecord(
                    pest_id=uuid.uuid4(),
                    farm_id=FARM_ID,
                    crop_id=crop_id,
                    pest_name=p["name"],
                    severity=p["severity"],
                    affected_area_pct=15.0,
                    detected_date=p["date"],
                    resolved_date=p["date"] + timedelta(days=10),
                    treatment_applied="Imidacloprid (Aphids) / Propiconazole (Rust)"
                )
                session.add(record)

        # 5. Fetch Weather and Generate IoT Simulation
        logger.info(f"Fetching real weather for Ludhiana ({LAT}, {LNG})...")
        weather_data = {}
        try:
            async with WeatherClient() as client:
                weather_data = await client.fetch_forecast(LAT, LNG, str(FARM_ID))
            logger.info("Weather data fetched successfully.")
        except Exception as e:
            logger.error(f"Weather fetch failed: {e}. Using fallback simulation.")
            weather_data = {"daily": {"temperature_2m_max": [32.0]*7, "precipitation_sum": [0.0]*7}}

        # 6. Generate IoT readings for the last 24 hours based on current weather
        logger.info("Generating realistic IoT readings...")
        current_temp = weather_data.get("daily", {}).get("temperature_2m_max", [30.0])[0]
        for i in range(24):
            ts = datetime.now(timezone.utc) - timedelta(hours=i)
            # Realistic fluctuation
            moisture = 45.0 + random.uniform(-5, 5)
            temp = current_temp + random.uniform(-3, 3)
            
            reading = IoTReadingModel(
                id=str(uuid.uuid4()),
                device_id="SN-LUD-001",
                farmer_id=str(FARM_ID),
                crop_type=CROP_NAME,
                lat=LAT,
                lng=LNG,
                timestamp=ts,
                soil_moisture=moisture,
                temperature=temp,
                humidity=60.0 + random.uniform(-10, 10),
                ph_level=SOIL_PH + random.uniform(-0.1, 0.1),
                nitrogen=SOIL_N + random.uniform(-5, 5),
                phosphorus=SOIL_P + random.uniform(-1, 1),
                potassium=150.0 + random.uniform(-10, 10),
                source="simulator",
                quality_score=0.98,
                raw_payload={"simulated": True, "weather_context": current_temp}
            )
            session.add(reading)

        # 7. Seed Satellite Imagery (Sentinel-2 Simulation)
        logger.info("Seeding Sentinel-2 imagery metadata...")
        stmt = select(SatelliteImagery).where(SatelliteImagery.farm_id == FARM_ID).order_by(SatelliteImagery.captured_at.desc()).limit(1)
        res = await session.execute(stmt)
        if not res.scalar_one_or_none():
            imagery = SatelliteImagery(
                image_id=uuid.uuid4(),
                farm_id=FARM_ID,
                captured_at=datetime.now(timezone.utc) - timedelta(days=2),
                image_path="data/satellite/ludhiana_wheat_20240419.png",
                ndvi_mean=0.72,
                ndvi_std=0.05,
                cloud_cover_pct=2.1,
                source="sentinel-2",
                metadata_json={"resolution": "10m", "bands": ["B04", "B03", "B02", "B08"]}
            )
            session.add(imagery)

        await session.commit()
        logger.info("Demo seeding complete!")

if __name__ == "__main__":
    asyncio.run(seed_real_world_demo())
