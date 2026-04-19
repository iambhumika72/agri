"""
weather_pipeline_adapter.py
---------------------------
Adapts engineered weather features into records conforming to the
KrishiAI Unified Data Pipeline schema.

Pipeline schema (per record)::

    {
        "source"    : "weather",
        "farm_id"   : "<str>",
        "timestamp" : "<ISO-8601 date string>",
        "features"  : { <flat feature dict> },
        "metadata"  : {
            "crop_season" : "kharif" | "rabi" | "zaid",
            "pipeline_version": "<str>"
        }
    }

Crop season definitions (Indian agriculture calendar):
    kharif : June–October   (monsoon; rice, cotton, maize)
    rabi   : November–March (winter; wheat, mustard, chickpea)
    zaid   : April–May      (summer; watermelon, cucumber)
"""

import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from .weather_features import DailyWeatherFeatures, engineer_features

logger = logging.getLogger(__name__)

PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "1.0.0")

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
CropSeason = Literal["kharif", "rabi", "zaid"]

# Month → season mapping (1-indexed)
_MONTH_TO_SEASON: dict[int, CropSeason] = {
    1: "rabi",
    2: "rabi",
    3: "rabi",
    4: "zaid",
    5: "zaid",
    6: "kharif",
    7: "kharif",
    8: "kharif",
    9: "kharif",
    10: "kharif",
    11: "rabi",
    12: "rabi",
}


# ---------------------------------------------------------------------------
# Pydantic schema for a pipeline-ready record
# ---------------------------------------------------------------------------
class PipelineRecord(BaseModel):
    """
    A single pipeline-ready record conforming to the Unified Data Pipeline schema.
    """

    source: Literal["weather"] = "weather"
    farm_id: str = Field(..., description="Opaque farm identifier")
    timestamp: str = Field(..., description="ISO-8601 date string for the forecast day")
    features: dict[str, Any] = Field(..., description="Flat feature dictionary")
    metadata: dict[str, Any] = Field(default_factory=dict)


class FarmLocation(BaseModel):
    """
    Minimal farm descriptor used as input to the batch adapter.
    """

    farm_id: str = Field(..., description="Opaque farm identifier")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tag_crop_season(forecast_date: date) -> CropSeason:
    """
    Return the Indian agricultural crop season for *forecast_date*.

    Seasons:
        kharif — June through October  (monsoon / kharif crops)
        rabi   — November through March (winter / rabi crops)
        zaid   — April through May      (summer / zaid crops)

    Args:
        forecast_date: Calendar date to classify.

    Returns:
        One of ``"kharif"``, ``"rabi"``, or ``"zaid"``.
    """
    season = _MONTH_TO_SEASON[forecast_date.month]
    logger.debug("Tagged %s as season=%s", forecast_date, season)
    return season


def features_to_dict(feat: DailyWeatherFeatures) -> dict[str, Any]:
    """
    Serialise a ``DailyWeatherFeatures`` instance to a plain dict,
    excluding ``farm_id`` and ``forecast_date`` (they live at record level).

    Args:
        feat: Engineered feature object.

    Returns:
        Flat dict of feature name → value.
    """
    raw = feat.model_dump(exclude={"farm_id", "forecast_date"})
    return raw


def adapt_single(feat: DailyWeatherFeatures) -> PipelineRecord:
    """
    Convert one ``DailyWeatherFeatures`` to a ``PipelineRecord``.

    Args:
        feat: A single day's engineered weather features.

    Returns:
        Pipeline-ready record.
    """
    season = tag_crop_season(feat.forecast_date)
    return PipelineRecord(
        farm_id=feat.farm_id,
        timestamp=feat.forecast_date.isoformat(),
        features=features_to_dict(feat),
        metadata={
            "crop_season": season,
            "pipeline_version": PIPELINE_VERSION,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# Public batch entry-point
# ---------------------------------------------------------------------------

def adapt_batch(
    raw_responses: list[dict[str, Any]],
) -> list[PipelineRecord]:
    """
    Transform a batch of raw Open-Meteo API responses into pipeline-ready records.

    This is the primary integration point between the weather data source and
    the Unified Data Pipeline.  Each raw response represents one farm's 7-day
    forecast.  The function performs feature engineering and schema adaptation
    for all farms in one call.

    Args:
        raw_responses: List of raw JSON payloads — one per farm — as returned
                       by ``WeatherClient.fetch_forecast``.  Each dict must
                       contain the ``farm_id`` annotation injected by the client.

    Returns:
        Flat list of ``PipelineRecord`` objects ordered by (farm_id, date).
        Total records = len(raw_responses) × 7 (forecast days).

    Example::

        records = adapt_batch([raw_farm_a, raw_farm_b])
        pipeline.ingest(records)
    """
    all_records: list[PipelineRecord] = []

    for raw in raw_responses:
        farm_id = raw.get("farm_id", "UNKNOWN")
        try:
            daily_features = engineer_features(raw)
            for feat in daily_features:
                record = adapt_single(feat)
                all_records.append(record)
            logger.info(
                "Adapted %d records for farm %s",
                len(daily_features),
                farm_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to adapt weather data for farm %s: %s",
                farm_id,
                exc,
            )
            # Partial failure: skip this farm, let other farms proceed
            continue

    logger.info(
        "Batch adaptation complete: %d total records from %d farms",
        len(all_records),
        len(raw_responses),
    )
    return all_records


def pipeline_records_as_dicts(records: list[PipelineRecord]) -> list[dict[str, Any]]:
    """
    Serialise ``PipelineRecord`` objects to plain dicts for JSON transport.

    Args:
        records: List of adapted pipeline records.

    Returns:
        JSON-serialisable list of dicts.
    """
    return [r.model_dump() for r in records]
