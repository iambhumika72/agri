import uuid
from datetime import date, datetime, timedelta
import logging
from historical_db.db_connector import HistoricalDBConnector
from historical_db.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SeedDB")

def seed():
    with HistoricalDBConnector() as db:
        # Create tables
        Base.metadata.create_all(db._engine)
        logger.info("Database tables ensured.")
        
        # 1. Create a few farms
        farm_ids = ["farm-001", "farm-002", "farm-003"]
        farm_data = [
            {"farm_id": uuid.UUID("f001f001-f001-f001-f001-f001f001f001"), "farmer_name": "Ramesh Kumar", "district": "Lucknow", "state": "UP", "latitude": 26.8467, "longitude": 80.9462, "area_hectares": 2.5},
            {"farm_id": uuid.UUID("f002f002-f002-f002-f002-f002f002f002"), "farmer_name": "Sunita Devi", "district": "Satara", "state": "Maharashtra", "latitude": 17.9497, "longitude": 73.8930, "area_hectares": 1.8},
            {"farm_id": uuid.UUID("f003f003-f003-f003-f003-f003f003f003"), "farmer_name": "Gurpreet Singh", "district": "Ludhiana", "state": "Punjab", "latitude": 30.9009, "longitude": 80.8572, "area_hectares": 3.2},
        ]
        
        # Mapping for the UI to use simpler IDs if needed, but let's use real UUIDs
        # I'll also add them with string IDs if the DB allows (it's UUID col though)
        
        for farm in farm_data:
            if not db.farm_exists(str(farm["farm_id"])):
                db.insert_record("farms", farm)
                logger.info(f"Added farm: {farm['farmer_name']}")
        
        # 2. Add some crops
        crop_id = uuid.uuid4()
        db.insert_record("crops", {"crop_id": crop_id, "crop_name": "Wheat", "season_type": "Rabi"})
        
        # 3. Add yield records for farm-001
        f1_id = farm_data[0]["farm_id"]
        for i in range(1, 4):
            db.insert_record("yield_records", {
                "record_id": uuid.uuid4(),
                "farm_id": f1_id,
                "crop_id": crop_id,
                "season": "Rabi",
                "year": 2023 - i,
                "yield_kg_per_hectare": 2000 + (i * 100),
                "harvest_date": date(2023 - i, 4, 15)
            })
            
        # 4. Add soil health records
        db.insert_record("soil_health", {
            "soil_id": uuid.uuid4(),
            "farm_id": f1_id,
            "recorded_date": date.today(),
            "nitrogen_ppm": 120.5,
            "phosphorus_ppm": 12.0,
            "potassium_ppm": 110.0,
            "ph_level": 6.8,
            "organic_matter_pct": 1.2
        })
        
        logger.info("Database seeding complete!")

if __name__ == "__main__":
    seed()


if __name__ == "__main__":
    seed()
