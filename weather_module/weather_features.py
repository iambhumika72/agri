"""
weather_features.py
-------------------
Feature engineering layer for raw Open-Meteo API responses.

Transforms the raw JSON payload into a flat, typed feature dictionary
per day — suitable for direct ingestion by the Unified Data Pipeline
and the Time-Series Forecaster.

WMO weather interpretation codes that indicate precipitation:
  Drizzle         : 51, 53, 55
  Freezing drizzle: 56, 57
  Rain            : 61, 63, 65
  Freezing rain   : 66, 67
  Snow            : 71–77
  Snow grains     : 77
  Rain showers    : 80–82
  Snow showers    : 85, 86
  Thunderstorm    : 95, 96, 99
"""

import logging
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WMO codes that represent some form of precipitation / rain
# ---------------------------------------------------------------------------
RAIN_WMO_CODES: frozenset[int] = frozenset(
    [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99]
)

# Thresholds
FROST_TEMP_C: float = 4.0       # °C — temp_min below which frost risk is flagged
HEAT_STRESS_TEMP_C: float = 38.0  # °C — temp_max above which heat stress is flagged


# ---------------------------------------------------------------------------
# Pydantic model for a single day's engineered features
# ---------------------------------------------------------------------------
class DailyWeatherFeatures(BaseModel):
    """
    Engineered weather features for a single day at a specific farm.

    All numeric fields represent physical quantities in SI-adjacent units
    (°C, mm, km/h) to match the downstream pipeline's feature schema.
    """

    farm_id: str = Field(..., description="Opaque farm identifier")
    forecast_date: date = Field(..., description="Forecast date (UTC)")

    # Derived temperature features
    temp_mean_c: float = Field(..., description="Mean air temperature (°C)")
    temp_range_c: float = Field(..., description="Diurnal temperature range (°C)")

    # Precipitation
    precip_mm: float = Field(..., ge=0, description="Total daily precipitation (mm)")
    rain_probability: float = Field(..., ge=0.0, le=1.0, description="Rain probability [0–1]")

    # Wind
    wind_kmh: float = Field(..., ge=0, description="Max wind speed (km/h)")

    # Evapotranspiration / irrigation demand
    et0_mm: float = Field(..., ge=0, description="FAO-56 reference ET₀ (mm)")

    # Risk signals
    drought_risk_score: float = Field(
        ..., ge=0.0, le=1.0, description="Rolling 7-day drought risk [0–1]"
    )
    is_frost_risk: bool = Field(..., description="True if min temp < 4 °C")
    is_heat_stress: bool = Field(..., description="True if max temp > 38 °C")

    # Soil moisture
    soil_moisture_avg: float = Field(
        ..., ge=0.0, description="Mean hourly soil moisture (m³/m³) for the day"
    )


# ---------------------------------------------------------------------------
# Feature engineering functions
# ---------------------------------------------------------------------------

def _safe_mean(values: list[float | None]) -> float:
    """Return the mean of *values*, ignoring None entries; returns 0.0 if empty."""
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else 0.0


def _compute_drought_risk(
    precip_series: list[float],
    et0_series: list[float],
) -> list[float]:
    """
    Compute a drought risk score per day using a rolling 7-day water-balance ratio.

    Algorithm
    ---------
    For day *i*, accumulate all available prior days in the 7-day window:

        deficit  = max(0, ET₀ - precip)
        balance  = sum(deficit) / max(sum(ET₀), ε)

    Score is clamped to [0, 1].  A score of **1.0** means severe drought
    (zero precipitation against high ET₀); **0.0** means surplus water.

    Args:
        precip_series: Daily precipitation values (mm).
        et0_series:    Daily ET₀ values (mm).

    Returns:
        List of drought risk scores, one per day.
    """
    scores: list[float] = []
    n = len(precip_series)
    for i in range(n):
        window_start = max(0, i - 6)  # up to 7-day rolling window
        window_precip = precip_series[window_start : i + 1]
        window_et0 = et0_series[window_start : i + 1]

        total_et0 = sum(window_et0)
        if total_et0 < 1e-6:
            scores.append(0.0)
            continue

        deficit = sum(max(0.0, e - p) for p, e in zip(window_precip, window_et0))
        score = min(1.0, deficit / total_et0)
        scores.append(round(score, 4))
    return scores


def _infer_rain_probability(weathercode: int) -> float:
    """
    Infer rain probability (0 or 1) from a WMO weather interpretation code.

    While Open-Meteo does not provide probabilistic precipitation forecasts in
    the free tier, the deterministic weather code gives a reliable binary signal.
    Downstream models can treat this as a hard 0/1 feature or smooth it.

    Args:
        weathercode: WMO code for the day (integer).

    Returns:
        1.0 if the code implies precipitation, else 0.0.
    """
    return 1.0 if int(weathercode) in RAIN_WMO_CODES else 0.0


def _extract_daily_soil_moisture(
    hourly_times: list[str],
    hourly_soil_moisture: list[float | None],
    target_date: date,
) -> float:
    """
    Average the hourly soil-moisture readings that belong to *target_date*.

    Args:
        hourly_times:         ISO-8601 datetime strings from the hourly block.
        hourly_soil_moisture: Corresponding soil-moisture values (m³/m³).
        target_date:          The calendar date to filter on.

    Returns:
        Mean soil moisture for the day; 0.0 if no data available.
    """
    values: list[float] = []
    for ts, sm in zip(hourly_times, hourly_soil_moisture):
        try:
            dt = datetime.fromisoformat(ts)
            if dt.date() == target_date:
                if sm is not None:
                    values.append(sm)
        except ValueError:
            logger.warning("Could not parse hourly timestamp: %s", ts)
    return round(_safe_mean(values), 6)


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def engineer_features(raw_response: dict[str, Any]) -> list[DailyWeatherFeatures]:
    """
    Transform a raw Open-Meteo API response into a list of
    ``DailyWeatherFeatures`` objects — one per forecast day.

    Args:
        raw_response: Full JSON payload returned by ``WeatherClient.fetch_forecast``.
                      Must contain ``farm_id``, ``daily``, and ``hourly`` keys.

    Returns:
        Ordered list of feature objects (index 0 = today, index 6 = day+6).

    Raises:
        KeyError: If required fields are missing from the response.
        ValueError: If data arrays have mismatched lengths.
    """
    farm_id: str = raw_response["farm_id"]
    daily: dict[str, Any] = raw_response["daily"]
    hourly: dict[str, Any] = raw_response["hourly"]

    dates: list[str] = daily["time"]
    temp_max: list[float] = daily["temperature_2m_max"]
    temp_min: list[float] = daily["temperature_2m_min"]
    precip: list[float] = daily["precipitation_sum"]
    wind: list[float] = daily["windspeed_10m_max"]
    et0: list[float] = daily["et0_fao_evapotranspiration"]
    wcodes: list[int] = daily["weathercode"]

    hourly_times: list[str] = hourly["time"]
    hourly_soil_moist: list[float | None] = hourly["soil_moisture_0_to_1cm"]

    # Validate array lengths
    n = len(dates)
    if not all(len(arr) == n for arr in [temp_max, temp_min, precip, wind, et0, wcodes]):
        raise ValueError("Daily weather arrays have mismatched lengths.")

    # Precompute drought risk across the full 7-day window
    drought_scores = _compute_drought_risk(precip, et0)

    features: list[DailyWeatherFeatures] = []
    for i, date_str in enumerate(dates):
        forecast_date = date.fromisoformat(date_str)

        tmax = temp_max[i] if temp_max[i] is not None else 0.0
        tmin = temp_min[i] if temp_min[i] is not None else 0.0

        soil_avg = _extract_daily_soil_moisture(hourly_times, hourly_soil_moist, forecast_date)

        feat = DailyWeatherFeatures(
            farm_id=farm_id,
            forecast_date=forecast_date,
            temp_mean_c=round((tmax + tmin) / 2, 2),
            temp_range_c=round(tmax - tmin, 2),
            precip_mm=round(float(precip[i] or 0.0), 2),
            rain_probability=_infer_rain_probability(wcodes[i]),
            wind_kmh=round(float(wind[i] or 0.0), 2),
            et0_mm=round(float(et0[i] or 0.0), 2),
            drought_risk_score=drought_scores[i],
            is_frost_risk=tmin < FROST_TEMP_C,
            is_heat_stress=tmax > HEAT_STRESS_TEMP_C,
            soil_moisture_avg=soil_avg,
        )
        features.append(feat)
        logger.debug(
            "Engineered features for day %s",
            date_str,
            extra={"farm_id": farm_id, "features": feat.model_dump()},
        )

    logger.info(
        "Feature engineering complete",
        extra={"farm_id": farm_id, "days_processed": len(features)},
    )
    return features
