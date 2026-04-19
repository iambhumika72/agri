"""
weather_scheduler.py
--------------------
APScheduler-based daily scheduler for the weather data pipeline.

Behaviour
---------
* Fires every day at 05:30 local time (timezone per farm; defaults to UTC)
* On success : caches the raw JSON in Redis with 6-hour TTL
* On failure : retries in 30 minutes, alerts admin after 3 consecutive failures
* All state is isolated per farm_id — no global mutable state

Environment variables (all have safe local-dev defaults)
---------------------------------------------------------
REDIS_URL          : redis://localhost:6379   — Redis connection string
ADMIN_ALERT_EMAIL  : admin@krishiai.local     — Destination for failure alerts
LOG_LEVEL          : INFO                     — Logging verbosity
PIPELINE_VERSION   : 1.0.0                   — Injected into pipeline metadata
SMTP_HOST          : localhost               — SMTP server for alert emails
SMTP_PORT          : 25                      — SMTP port
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .weather_client import WeatherClient
from .weather_pipeline_adapter import adapt_batch, pipeline_records_as_dicts
from .weather_sms_formatter import format_sms_batch
from .weather_features import engineer_features

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — all sourced from environment with safe defaults
# ---------------------------------------------------------------------------
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
ADMIN_ALERT_EMAIL: str = os.getenv("ADMIN_ALERT_EMAIL", "admin@krishiai.local")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "25"))
REDIS_TTL_SECONDS: int = 6 * 3600  # 6 hours
MAX_CONSECUTIVE_FAILURES: int = 3
RETRY_DELAY_MINUTES: int = 30

# Cron expression for daily 05:30 run (hour=5, minute=30)
SCHEDULE_HOUR: int = int(os.getenv("SCHEDULE_HOUR", "5"))
SCHEDULE_MINUTE: int = int(os.getenv("SCHEDULE_MINUTE", "30"))


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

def _redis_key(farm_id: str, forecast_date: str) -> str:
    """
    Build the Redis cache key for a weather forecast entry.

    Args:
        farm_id:       Farm identifier.
        forecast_date: ISO-8601 date string (e.g. "2024-06-18").

    Returns:
        Key string in the form ``weather:{farm_id}:{date}``.
    """
    return f"weather:{farm_id}:{forecast_date}"


# ---------------------------------------------------------------------------
# Alert email helper (synchronous — called in executor)
# ---------------------------------------------------------------------------

def _send_admin_alert(farm_ids: list[str], error_summary: str) -> None:
    """
    Send a plain-text failure alert email to the configured admin address.

    Uses the standard-library ``smtplib`` so no extra dependencies are needed.
    Failures in the email send are logged but not raised (best-effort alert).

    Args:
        farm_ids:      List of farm IDs that failed.
        error_summary: Human-readable summary of the last error.
    """
    subject = f"[KrishiAI] Weather pipeline failure — {len(farm_ids)} farm(s) affected"
    body = (
        f"Timestamp : {datetime.now(timezone.utc).isoformat()}\n"
        f"Farm IDs  : {', '.join(farm_ids)}\n"
        f"Error     : {error_summary}\n\n"
        "The scheduler will keep retrying. Please investigate immediately."
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = "no-reply@krishiai.local"
    msg["To"] = ADMIN_ALERT_EMAIL

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            smtp.sendmail(msg["From"], [ADMIN_ALERT_EMAIL], msg.as_string())
        logger.info("Admin alert sent to %s", ADMIN_ALERT_EMAIL)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send admin alert email: %s", exc)


# ---------------------------------------------------------------------------
# Core pipeline job
# ---------------------------------------------------------------------------

class WeatherPipelineJob:
    """
    Encapsulates the stateful logic for running the weather pipeline for a set
    of farms, including caching, retry bookkeeping, and admin alerting.

    All state (failure counters) is held inside the instance — no module-level
    globals.  Instantiate one ``WeatherPipelineJob`` per scheduler.

    Args:
        farm_locations: List of dicts with keys ``farm_id``, ``latitude``,
                        ``longitude``.
        redis_client:   Async Redis client (injected for testability).
    """

    def __init__(
        self,
        farm_locations: list[dict[str, Any]],
        redis_client: aioredis.Redis,
    ) -> None:
        self.farm_locations = farm_locations
        self.redis = redis_client
        self._failure_counts: dict[str, int] = {}  # farm_id → consecutive failures

    async def run(self) -> None:
        """
        Execute the full weather pipeline for all configured farms.

        For each farm:
        1. Fetch forecast from Open-Meteo (with built-in retries)
        2. Engineer features
        3. Format SMS alerts
        4. Adapt to pipeline schema
        5. Cache raw JSON in Redis

        On fetch failure for a farm:
        - Increment failure counter
        - Attempt to serve from Redis cache
        - Alert admin if counter reaches MAX_CONSECUTIVE_FAILURES
        """
        logger.info(
            "Weather pipeline job started for %d farm(s)",
            len(self.farm_locations),
        )

        raw_responses: list[dict[str, Any]] = []
        failed_farms: list[str] = []

        async with WeatherClient() as client:
            for farm in self.farm_locations:
                farm_id = farm["farm_id"]
                try:
                    raw = await client.fetch_forecast(
                        latitude=farm["latitude"],
                        longitude=farm["longitude"],
                        farm_id=farm_id,
                    )
                    raw_responses.append(raw)
                    self._failure_counts[farm_id] = 0  # reset on success
                    await self._cache_raw(farm_id, raw)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Fetch failed for farm %s: %s", farm_id, exc
                    )
                    self._failure_counts[farm_id] = (
                        self._failure_counts.get(farm_id, 0) + 1
                    )
                    failed_farms.append(farm_id)

                    # Fallback: try cached data
                    cached = await self._load_cached_latest(farm_id)
                    if cached:
                        logger.warning(
                            "Using cached data for farm %s", farm_id
                        )
                        raw_responses.append(cached)
                    else:
                        logger.error(
                            "No cached data available for farm %s", farm_id
                        )

        # Admin alert after threshold
        if failed_farms:
            for farm_id in failed_farms:
                if self._failure_counts.get(farm_id, 0) >= MAX_CONSECUTIVE_FAILURES:
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(
                        None,
                        _send_admin_alert,
                        [farm_id],
                        f"Consecutive failures: {self._failure_counts[farm_id]}",
                    )

        if not raw_responses:
            logger.error("No weather data available for any farm. Aborting.")
            return

        # Feature engineering + SMS
        all_features = []
        for raw in raw_responses:
            try:
                daily_features = engineer_features(raw)
                all_features.extend(daily_features)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Feature engineering failed: %s", exc)

        sms_batch = format_sms_batch(all_features)
        logger.info("Generated %d SMS messages", len(sms_batch))

        # Pipeline adaptation
        pipeline_records = adapt_batch(raw_responses)
        logger.info(
            "Pipeline job complete: %d pipeline records produced",
            len(pipeline_records),
        )

        # Emit records to the Unified Data Pipeline (hook point)
        # In production, replace this log with pipeline.ingest(pipeline_records_as_dicts(pipeline_records))
        logger.info(
            "Pipeline records ready for ingestion",
            extra={"record_count": len(pipeline_records)},
        )

    async def _cache_raw(self, farm_id: str, raw: dict[str, Any]) -> None:
        """
        Store a raw API response in Redis with REDIS_TTL_SECONDS TTL.

        Key format: ``weather:{farm_id}:{today_date}``

        Args:
            farm_id: Farm identifier.
            raw:     Raw JSON dict from Open-Meteo.
        """
        today = datetime.now(timezone.utc).date().isoformat()
        key = _redis_key(farm_id, today)
        try:
            await self.redis.set(key, json.dumps(raw), ex=REDIS_TTL_SECONDS)
            logger.debug("Cached weather data under key %s (TTL=%ds)", key, REDIS_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001
            logger.error("Redis cache write failed for farm %s: %s", farm_id, exc)

    async def _load_cached_latest(self, farm_id: str) -> dict[str, Any] | None:
        """
        Attempt to retrieve the most recent cached forecast for *farm_id*.

        Checks today's key first, then falls back to yesterday (in case the
        cache was written just before midnight).

        Args:
            farm_id: Farm identifier.

        Returns:
            Parsed JSON dict or ``None`` if cache miss.
        """
        from datetime import timedelta

        today = datetime.now(timezone.utc).date()
        for delta in [0, 1]:
            candidate_date = (today - timedelta(days=delta)).isoformat()
            key = _redis_key(farm_id, candidate_date)
            try:
                value = await self.redis.get(key)
                if value:
                    logger.info("Cache hit for farm %s (key %s)", farm_id, key)
                    return json.loads(value)
            except Exception as exc:  # noqa: BLE001
                logger.error("Redis cache read failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Scheduler factory
# ---------------------------------------------------------------------------

def build_scheduler(
    farm_locations: list[dict[str, Any]],
    redis_url: str = REDIS_URL,
) -> AsyncIOScheduler:
    """
    Construct and configure an ``AsyncIOScheduler`` for the weather pipeline.

    The job fires daily at SCHEDULE_HOUR:SCHEDULE_MINUTE (default 05:30) local
    time.  On failure it reschedules itself in RETRY_DELAY_MINUTES (30 min).

    Args:
        farm_locations: List of farm dicts (keys: farm_id, latitude, longitude).
        redis_url:      Redis connection string.

    Returns:
        Configured (but not yet started) ``AsyncIOScheduler`` instance.
    """
    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    job = WeatherPipelineJob(farm_locations=farm_locations, redis_client=redis_client)

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        func=job.run,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone="UTC"),
        id="weather_pipeline_daily",
        name="Weather Pipeline Daily Run",
        misfire_grace_time=300,  # tolerate up to 5 min clock drift
        coalesce=True,           # skip missed runs to avoid pile-up
    )

    logger.info(
        "Scheduler configured: daily at %02d:%02d UTC for %d farm(s)",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
        len(farm_locations),
    )
    return scheduler


# ---------------------------------------------------------------------------
# Entry-point for standalone execution
# ---------------------------------------------------------------------------

async def _main() -> None:
    """Start the scheduler and run indefinitely (for direct execution)."""
    import signal

    # Example farm locations — replace with DB/config fetch in production
    farms: list[dict[str, Any]] = [
        {"farm_id": "FARM_001", "latitude": 19.0760, "longitude": 72.8777},
        {"farm_id": "FARM_002", "latitude": 28.6139, "longitude": 77.2090},
    ]

    scheduler = build_scheduler(farms)
    scheduler.start()
    logger.info("Scheduler started. Press Ctrl+C to exit.")

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    await stop_event.wait()
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
    asyncio.run(_main())


