import os
import json
import logging
from typing import Optional, List
import redis.asyncio as redis
from .schemas import IoTReading

logger = logging.getLogger(__name__)

IOT_LATEST    = "iot:latest:{farmer_id}:{crop_type}"    # TTL: 10min
IOT_STATS     = "iot:stats:{farmer_id}"                 # TTL: 1hr  
IOT_ANOMALY   = "iot:anomaly:{farmer_id}"               # TTL: 24hr
IOT_SIM_STATE = "iot:simulator:state"                   # TTL: none (persistent)

redis_client: Optional[redis.Redis] = None

async def init_redis():
    global redis_client
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        redis_client = client
        logger.info(f"Connected to Redis at {redis_url}")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis. Running without cache. Error: {e}")
        redis_client = None

def get_redis() -> Optional[redis.Redis]:
    return redis_client

async def cache_latest_reading(farmer_id: str, crop_type: str, reading: IoTReading):
    client = get_redis()
    if not client:
        return
    key = IOT_LATEST.format(farmer_id=farmer_id, crop_type=crop_type)
    try:
        ttl = int(os.environ.get("IOT_CACHE_TTL_SECONDS", "600"))
        await client.setex(key, ttl, reading.model_dump_json())
    except Exception as e:
        logger.warning(f"Redis cache_latest_reading failed: {e}")

async def get_cached_latest(farmer_id: str, crop_type: str) -> Optional[IoTReading]:
    client = get_redis()
    if not client:
        return None
    key = IOT_LATEST.format(farmer_id=farmer_id, crop_type=crop_type)
    try:
        data = await client.get(key)
        if data:
            return IoTReading.model_validate_json(data)
    except Exception as e:
        logger.warning(f"Redis get_cached_latest failed: {e}")
    return None

async def cache_stats(farmer_id: str, stats: dict):
    client = get_redis()
    if not client:
        return
    key = IOT_STATS.format(farmer_id=farmer_id)
    try:
        await client.setex(key, 3600, json.dumps(stats))
    except Exception as e:
        logger.warning(f"Redis cache_stats failed: {e}")

async def get_cached_stats(farmer_id: str) -> Optional[dict]:
    client = get_redis()
    if not client:
        return None
    key = IOT_STATS.format(farmer_id=farmer_id)
    try:
        data = await client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Redis get_cached_stats failed: {e}")
    return None

async def set_anomaly_flag(farmer_id: str, anomaly_data: dict):
    client = get_redis()
    if not client:
        return
    key = IOT_ANOMALY.format(farmer_id=farmer_id)
    try:
        await client.lpush(key, json.dumps(anomaly_data))
        await client.expire(key, 86400)
    except Exception as e:
        logger.warning(f"Redis set_anomaly_flag failed: {e}")

async def get_anomaly_flags(farmer_id: str) -> List[dict]:
    client = get_redis()
    if not client:
        return []
    key = IOT_ANOMALY.format(farmer_id=farmer_id)
    try:
        data = await client.lrange(key, 0, -1)
        return [json.loads(d) for d in data]
    except Exception as e:
        logger.warning(f"Redis get_anomaly_flags failed: {e}")
    return []

async def set_sim_state(state: dict):
    client = get_redis()
    if not client:
        return
    try:
        await client.set(IOT_SIM_STATE, json.dumps(state))
    except Exception as e:
        logger.warning(f"Redis set_sim_state failed: {e}")

async def get_sim_state() -> Optional[dict]:
    client = get_redis()
    if not client:
        return None
    try:
        data = await client.get(IOT_SIM_STATE)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Redis get_sim_state failed: {e}")
    return None

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
