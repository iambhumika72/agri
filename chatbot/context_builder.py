import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from iot.ingestor import get_latest_reading
from iot.models import IoTReadingModel
from .repository import get_weather_data, get_crop_data, get_historical_data, get_farmer_profile

logger = logging.getLogger(__name__)

class ContextBuilder:
    async def build_context(self, farmer_id: str, db: AsyncSession, redis=None) -> tuple[dict, list[str]]:
        results = await asyncio.gather(
            self._fetch_iot_data(farmer_id, db, redis),
            self._fetch_weather_data(farmer_id, db),
            self._fetch_crop_data(farmer_id, db),
            self._fetch_historical_data(farmer_id, db),
            self._fetch_farmer_profile(farmer_id, db),
            return_exceptions=True
        )
        
        context = {}
        sources_used = []
        
        for key, result in zip(
            ["iot", "weather", "crop", "historical", "farmer_profile"],
            results
        ):
            if isinstance(result, Exception):
                logger.warning(f"Context fetch failed for {key}: {result}")
            elif result:
                context[key] = result
                sources_used.append(key)
        
        return context, sources_used

    async def _fetch_iot_data(self, farmer_id: str, db: AsyncSession, redis=None) -> dict | None:
        try:
            # We fetch the most recent reading overall for this farmer, regardless of crop_type
            stmt = select(IoTReadingModel).where(
                IoTReadingModel.farmer_id == farmer_id
            ).order_by(IoTReadingModel.timestamp.desc()).limit(1)
            res = await db.execute(stmt)
            record = res.scalar_one_or_none()
            
            if record:
                return {
                    "soil_moisture": f"{record.soil_moisture:.1f}%" if record.soil_moisture else "N/A",
                    "temperature": f"{record.temperature:.1f}°C" if record.temperature else "N/A",
                    "humidity": f"{record.humidity:.1f}%" if record.humidity else "N/A",
                    "ph_level": f"{record.ph_level:.1f}" if record.ph_level else "N/A",
                    "leaf_wetness": f"{record.leaf_wetness:.1f}%" if record.leaf_wetness else "N/A",
                    "last_updated": record.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "source": record.source
                }
        except Exception as e:
            logger.warning(f"Failed to fetch IoT data: {e}")
        return None

    async def _fetch_weather_data(self, farmer_id: str, db: AsyncSession) -> dict | None:
        return await get_weather_data(farmer_id, db)

    async def _fetch_crop_data(self, farmer_id: str, db: AsyncSession) -> dict | None:
        return await get_crop_data(farmer_id, db)

    async def _fetch_historical_data(self, farmer_id: str, db: AsyncSession) -> dict | None:
        return await get_historical_data(farmer_id, db)

    async def _fetch_farmer_profile(self, farmer_id: str, db: AsyncSession) -> dict | None:
        return await get_farmer_profile(farmer_id, db)

    def format_context_as_text(self, context: dict) -> str:
        blocks = []
        
        prof = context.get("farmer_profile")
        crop = context.get("crop_data")
        if prof or crop:
            lines = ["=== FARMER FIELD DATA ==="]
            if prof:
                lines.append(f"Farmer: {prof.get('name', 'Unknown')} | Region: {prof.get('region', 'Unknown')} | Land: {prof.get('land_size', 'Unknown')}")
            if crop:
                lines.append(f"Crops: {', '.join(crop.get('crops', []))}")
            blocks.append("\n".join(lines))
            
        iot = context.get("iot")
        if iot:
            lines = [
                "=== CURRENT FIELD CONDITIONS (IoT) ===",
                f"Soil Moisture: {iot.get('soil_moisture')} | Temperature: {iot.get('temperature')} | Humidity: {iot.get('humidity')}",
                f"pH Level: {iot.get('ph_level')} | Leaf Wetness: {iot.get('leaf_wetness')}",
                f"Last Updated: {iot.get('last_updated')}"
            ]
            blocks.append("\n".join(lines))
            
        wea = context.get("weather")
        if wea:
            lines = ["=== WEATHER ==="]
            lines.append(f"Current: {wea.get('current_temp')}, {wea.get('humidity')} humidity, {wea.get('rainfall_chance')} rain chance")
            lines.append(f"3-Day Forecast: {wea.get('forecast_3day')}")
            blocks.append("\n".join(lines))
            
        hist = context.get("historical")
        if hist:
            lines = ["=== CROP HISTORY & YIELD POTENTIAL ==="]
            lines.append(f"Last Season Yield: {hist.get('last_yield')}")
            lines.append(f"Yield Potential (ICAR District Average): 5.1 tonnes/hectare")
            
            if hist.get("common_pests"):
                lines.append(f"Historical Pests in Region: {', '.join(hist.get('common_pests'))}")
            
            pest_hist = hist.get("pest_history", [])
            if pest_hist:
                lines.append("Recent Outbreaks:")
                for p in pest_hist[:2]:
                    lines.append(f"  - {p['name']} (Severity: {p['severity']}/5) on {p['date']}")
            
            if hist.get("notes"):
                lines.append(f"Notes: {hist.get('notes')}")
            blocks.append("\n".join(lines))
            
        return "\n\n".join(blocks)
