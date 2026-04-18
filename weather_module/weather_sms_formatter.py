"""
weather_sms_formatter.py
------------------------
Generate concise, field-appropriate SMS alerts from daily weather features.

Constraints
-----------
* Maximum 160 characters per message (single GSM SMS segment)
* Language must be simple enough for voice IVR delivery to illiterate farmers
* Priority: frost risk > heat stress > drought risk > rain (heavy > light)

Format templates
----------------
Alert  : "Farm {id} | {date}: {alert}. Rain: {X}mm. Temp: {low}-{hi}C."
No alert: "Farm {id} | Good conditions. Water {X}mm today."
"""

import logging
from datetime import date

from weather_features import DailyWeatherFeatures

logger = logging.getLogger(__name__)

SMS_MAX_CHARS: int = 160

# Drought risk thresholds
DROUGHT_HIGH_THRESHOLD: float = 0.7
DROUGHT_MEDIUM_THRESHOLD: float = 0.4

# Rain thresholds for advisory language (mm/day)
HEAVY_RAIN_MM: float = 25.0
MODERATE_RAIN_MM: float = 5.0


def _format_date(d: date) -> str:
    """
    Format date as 'D Mon' e.g. '18 Apr' — short and universally understood.

    Cross-platform: avoids ``%-d`` (Linux-only) in favour of ``lstrip``
    so the formatter works on Windows and Linux alike.
    """
    return d.strftime("%d %b").lstrip("0").strip()


def _pick_top_alert(feat: DailyWeatherFeatures) -> str | None:
    """
    Select the highest-priority alert for the day.

    Priority order: frost risk > heat stress > high drought > moderate drought > heavy rain.

    Args:
        feat: Engineered features for the day.

    Returns:
        A short alert string (fits within the SMS template budget), or None.
    """
    if feat.is_frost_risk:
        return "FROST ALERT! Cover crops tonight"
    if feat.is_heat_stress:
        return "HEAT STRESS! Water plants now"
    if feat.drought_risk_score >= DROUGHT_HIGH_THRESHOLD:
        return "Drought risk HIGH. Irrigate today"
    if feat.drought_risk_score >= DROUGHT_MEDIUM_THRESHOLD:
        return "Low rain. Check soil moisture"
    if feat.precip_mm >= HEAVY_RAIN_MM:
        return "Heavy rain. Drain fields if needed"
    return None


def _truncate(text: str, max_len: int) -> str:
    """
    Truncate *text* to *max_len* characters, adding ellipsis if needed.

    Args:
        text:    Input string.
        max_len: Maximum allowed length.

    Returns:
        String of length ≤ *max_len*.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_sms(feat: DailyWeatherFeatures) -> str:
    """
    Generate a single SMS message (≤ 160 chars) for one farm on one day.

    The message follows one of two templates:

    **Alert template**::

        "Farm {id} | {date}: {alert}. Rain: {X}mm. Temp: {lo}-{hi}C."

    **No-alert template**::

        "Farm {id} | Good conditions. Water {X}mm today."

    Args:
        feat: Engineered weather features for the day.

    Returns:
        SMS string of at most 160 characters.

    Raises:
        AssertionError: (in debug mode) if the generated message exceeds 160 chars.
    """
    farm_short = feat.farm_id[:8]  # keep farm ID concise
    date_str = _format_date(feat.forecast_date)
    precip = round(feat.precip_mm, 1)
    temp_lo = round(feat.temp_mean_c - feat.temp_range_c / 2, 1)
    temp_hi = round(feat.temp_mean_c + feat.temp_range_c / 2, 1)
    et0 = round(feat.et0_mm, 1)

    alert = _pick_top_alert(feat)

    if alert:
        sms = (
            f"Farm {farm_short} | {date_str}: {alert}. "
            f"Rain: {precip}mm. Temp: {temp_lo}-{temp_hi}C."
        )
    else:
        sms = (
            f"Farm {farm_short} | Good conditions. "
            f"Water {et0}mm today. Temp: {temp_lo}-{temp_hi}C."
        )

    sms = _truncate(sms, SMS_MAX_CHARS)

    logger.debug(
        "SMS generated",
        extra={
            "farm_id": feat.farm_id,
            "date": str(feat.forecast_date),
            "length": len(sms),
            "has_alert": alert is not None,
        },
    )

    assert len(sms) <= SMS_MAX_CHARS, (
        f"SMS length {len(sms)} exceeds {SMS_MAX_CHARS} chars: {sms!r}"
    )
    return sms


def format_sms_batch(features: list[DailyWeatherFeatures]) -> list[dict[str, str]]:
    """
    Generate SMS messages for a list of daily feature records.

    Intended for scheduling scenarios where all 7 days are formatted at once
    or a batch of farm records needs to be formatted in one call.

    Args:
        features: List of ``DailyWeatherFeatures``, potentially spanning
                  multiple farms and/or days.

    Returns:
        List of dicts with keys ``farm_id``, ``date``, ``sms``.
    """
    results: list[dict[str, str]] = []
    for feat in features:
        try:
            sms = format_sms(feat)
            results.append(
                {
                    "farm_id": feat.farm_id,
                    "date": feat.forecast_date.isoformat(),
                    "sms": sms,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to format SMS for farm %s on %s: %s",
                feat.farm_id,
                feat.forecast_date,
                exc,
            )
    return results
