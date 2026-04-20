from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def get_weather_data(farmer_id: str, db: AsyncSession) -> Optional[dict]:
    # Placeholder: would typically query weather module or cache
    return None

async def get_crop_data(farmer_id: str, db: AsyncSession) -> Optional[dict]:
    try:
        # Approximate query using existing tables
        stmt = text("""
            SELECT c.crop_name, c.season_type 
            FROM crops c
            JOIN yield_records y ON c.crop_id = y.crop_id
            WHERE y.farm_id = :fid
            LIMIT 1
        """)
        res = await db.execute(stmt, {"fid": farmer_id})
        row = res.fetchone()
        if row:
            return {
                "crops": [row[0]],
                "primary_crop": row[0],
                "season": row[1],
            }
    except Exception as e:
        logger.warning(f"Failed to fetch crop data: {e}")
    return None

async def get_historical_data(farmer_id: str, db: AsyncSession) -> Optional[dict]:
    try:
        # Fetch latest yield
        yield_stmt = text("""
            SELECT yield_kg_per_hectare 
            FROM yield_records 
            WHERE farm_id = :fid 
            ORDER BY harvest_date DESC LIMIT 1
        """)
        yield_res = await db.execute(yield_stmt, {"fid": farmer_id})
        yield_row = yield_res.fetchone()
        
        # Fetch pests
        pest_stmt = text("""
            SELECT pest_name, severity, detected_date 
            FROM pest_records 
            WHERE farm_id = :fid 
            ORDER BY detected_date DESC
        """)
        pest_res = await db.execute(pest_stmt, {"fid": farmer_id})
        pest_rows = pest_res.fetchall()
        
        return {
            "last_yield": f"{yield_row[0]} kg/hectare" if yield_row else "N/A",
            "common_pests": [row[0] for row in pest_rows],
            "pest_history": [{"name": row[0], "severity": row[1], "date": str(row[2])} for row in pest_rows],
            "notes": "Historical data reflects ICAR district averages for Ludhiana."
        }
    except Exception as e:
        logger.warning(f"Failed to fetch historical data: {e}")
    return None

async def get_farmer_profile(farmer_id: str, db: AsyncSession) -> Optional[dict]:
    try:
        stmt = text("""
            SELECT farmer_name, state, area_hectares 
            FROM farms 
            WHERE farm_id = :fid LIMIT 1
        """)
        res = await db.execute(stmt, {"fid": farmer_id})
        row = res.fetchone()
        if row:
            return {
                "name": row[0],
                "region": row[1],
                "land_size": f"{row[2]} hectares",
                "lang": "hi"
            }
    except Exception as e:
        logger.warning(f"Failed to fetch farmer profile: {e}")
    return None
