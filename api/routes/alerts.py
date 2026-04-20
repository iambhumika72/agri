from __future__ import annotations

"""
api/routes/alerts.py
=====================
Alert delivery endpoints for AgriSense.
Serves real-time agronomic alerts triggered by satellite change detection,
vision-based pest detection, and sensor threshold breaches.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    alert_id: str
    farm_id: str
    alert_type: str   # "drought" | "pest" | "flood" | "frost" | "change_detection"
    severity: str     # "low" | "medium" | "high" | "critical"
    message: str
    recommendation: str
    triggered_at: datetime
    expires_at: datetime
    source: str = "static"  # "pipeline" | "manual" | "static"


class AlertSummary(BaseModel):
    farm_id: str
    total_alerts: int
    critical_count: int
    recent_alerts: List[AlertResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vision_to_alerts(farm_id: str, vision_analysis, now: datetime) -> List[AlertResponse]:
    """
    Convert a VisionAnalysis dataclass OR satellite_vision_node dict into
    AlertResponse objects, if conditions warrant.
    """
    alerts = []

    if vision_analysis is None:
        return alerts

    # Normalise to attribute access
    if isinstance(vision_analysis, dict):
        pest_detected = vision_analysis.get("pest_detected", False)
        pest_type = vision_analysis.get("pest_type") or vision_analysis.get("likely_cause", "unknown")
        affected_pct = vision_analysis.get("affected_area_pct") or vision_analysis.get("stressed_zone_pct", 0.0)
        urgency = vision_analysis.get("urgency_level", "monitor")
        health_score = vision_analysis.get("health_score", 75)
        recommended_action = vision_analysis.get("recommended_action") or vision_analysis.get("agronomist_note", "")
    else:
        pest_detected = getattr(vision_analysis, "pest_detected", False)
        pest_type = getattr(vision_analysis, "pest_type", "unknown")
        affected_pct = getattr(vision_analysis, "affected_area_pct", 0.0)
        urgency = getattr(vision_analysis, "urgency_level", "monitor")
        health_score = getattr(vision_analysis, "health_score", 75)
        recommended_action = getattr(vision_analysis, "recommended_action", "")

    # Map urgency → severity
    urgency_severity = {
        "immediate": "critical",
        "within_3_days": "high",
        "within_week": "medium",
        "monitor": "low",
        "none": "low",
    }
    severity = urgency_severity.get(urgency, "low")

    # Pest alert
    if pest_detected and pest_type not in ("healthy", "unknown", None):
        alerts.append(AlertResponse(
            alert_id=f"{farm_id}-PEST-{now.strftime('%Y%m%d%H%M%S')}",
            farm_id=farm_id,
            alert_type="pest",
            severity=severity,
            message=(
                f"Pest detected via satellite vision: {pest_type}. "
                f"Approximately {affected_pct:.1f}% of the field shows symptoms."
            ),
            recommendation=recommended_action or f"Apply appropriate treatment for {pest_type} within the recommended window.",
            triggered_at=now,
            expires_at=now + timedelta(days=3),
            source="pipeline",
        ))

    # Low health score alert (non-pest stress)
    if not pest_detected and health_score < 40:
        stress_type = "drought" if "drought" in (pest_type or "") else "crop_stress"
        alerts.append(AlertResponse(
            alert_id=f"{farm_id}-STRESS-{now.strftime('%Y%m%d%H%M%S')}",
            farm_id=farm_id,
            alert_type=stress_type,
            severity="medium" if health_score > 25 else "high",
            message=(
                f"Crop health score is critically low ({health_score}/100). "
                f"{affected_pct:.1f}% of visible field shows stress indicators."
            ),
            recommendation=recommended_action or "Inspect field conditions and check soil moisture and nutrient levels.",
            triggered_at=now,
            expires_at=now + timedelta(days=2),
            source="pipeline",
        ))

    return alerts


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{farm_id}", response_model=AlertSummary)
async def get_farm_alerts(
    farm_id: str,
    days: int = Query(default=7, ge=1, le=30, description="Number of past days to retrieve alerts for"),
    run_pipeline: bool = Query(default=False, description="Run live pipeline to generate real-time alerts from vision analysis"),
    language: str = Query(default="en", description="ISO 639-1 language code for alert translation"),
):
    """
    Returns all active alerts for a farm over the last N days.

    When `run_pipeline=true`, executes the AgriSense pipeline to generate
    real-time alerts grounded in current satellite vision analysis and pest detection.
    Otherwise, returns synthesized representative alerts (demo / low-cost mode).
    """
    log.info("Fetching alerts for farm=%s over last %d days (pipeline=%s)", farm_id, days, run_pipeline)

    now = datetime.utcnow()
    alerts: List[AlertResponse] = []

    if run_pipeline:
        try:
            from nodes.orchestrator import AgriSensePipeline
            pipeline = AgriSensePipeline()
            final_state = await pipeline.run(farm_id=farm_id)

            # Extract vision analysis from state (dataclass or dict)
            if isinstance(final_state, dict):
                vision_analysis = final_state.get("vision_analysis")
            else:
                vision_analysis = getattr(final_state, "vision_analysis", None)

            pipeline_alerts = _vision_to_alerts(farm_id, vision_analysis, now)
            alerts.extend(pipeline_alerts)

            # Add historical pest risk alert if available
            if isinstance(final_state, dict):
                hist = final_state.get("historical")
            else:
                hist = getattr(final_state, "historical", None)

            if hist is not None:
                pest_risk = getattr(hist, "pest_risk_score", None) if not isinstance(hist, dict) else hist.get("pest_risk_score")
                if pest_risk is not None and pest_risk > 0.5:
                    alerts.append(AlertResponse(
                        alert_id=f"{farm_id}-HIST-PEST-{now.strftime('%Y%m%d%H%M%S')}",
                        farm_id=farm_id,
                        alert_type="pest",
                        severity="high" if pest_risk > 0.7 else "medium",
                        message=f"Historical pest risk score is elevated ({pest_risk:.2f}/1.0). Past seasons show recurring pest pressure.",
                        recommendation="Consider preventive spraying and field scouting based on historical outbreak patterns.",
                        triggered_at=now,
                        expires_at=now + timedelta(days=7),
                        source="pipeline",
                    ))

        except EnvironmentError as e:
            log.warning("Pipeline skipped (no API key): %s", e)
        except Exception as e:
            log.error("Pipeline alert generation failed: %s", str(e), exc_info=True)

    # Always include a baseline drought alert as a representative example
    # (In production: replace with real event-store query)
    if not alerts:
        alerts.append(AlertResponse(
            alert_id=f"{farm_id}-DROUGHT-001",
            farm_id=farm_id,
            alert_type="drought",
            severity="medium",
            message="Soil moisture dropped below 25% threshold for 3 consecutive days.",
            recommendation="Irrigate 12,000 liters within the next 24 hours. Check drip lines.",
            triggered_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=2),
            source="static",
        ))
    
    # Translate alerts if language is not English
    if language != "en":
        try:
            from generative.multilingual import translate_alert_message, is_supported
            if is_supported(language):
                translated_alerts = []
                for alert in alerts:
                    t_msg, t_rec = translate_alert_message(
                        alert.message, alert.recommendation, language
                    )
                    translated_alerts.append(alert.model_copy(update={
                        "message": t_msg,
                        "recommendation": t_rec,
                    }))
                alerts = translated_alerts
        except Exception as e:
            log.warning("Alert translation failed: %s — returning English.", e)

    return AlertSummary(
        farm_id=farm_id,
        total_alerts=len(alerts),
        critical_count=sum(1 for a in alerts if a.severity == "critical"),
        recent_alerts=alerts,
    )


@router.post("/trigger", response_model=AlertResponse)
async def trigger_manual_alert(
    farm_id: str,
    alert_type: str,
    message: str,
    severity: str = "medium",
    language: str = "en",
):
    """
    Manually triggers an alert for a farm.
    Used by field agents or automated pipeline triggers.
    """
    if severity not in ("low", "medium", "high", "critical"):
        raise HTTPException(status_code=400, detail="Invalid severity. Use: low, medium, high, critical")

    now = datetime.utcnow()
    alert_id = f"{farm_id}-{alert_type.upper()}-{now.strftime('%Y%m%d%H%M%S')}"

    log.info("Manual alert triggered: %s | farm=%s | severity=%s", alert_id, farm_id, severity)

    return AlertResponse(
        alert_id=alert_id,
        farm_id=farm_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        recommendation="Contact your AgriSense advisor for immediate guidance.",
        triggered_at=now,
        expires_at=now + timedelta(days=3),
        source="manual",
    )
    
    # After creating the alert, translate if needed
    if language != "en":
        from generative.multilingual import translate_alert_message, is_supported
        if is_supported(language):
            t_msg, t_rec = translate_alert_message(
                alert.message, alert.recommendation, language
            )
            alert = alert.model_copy(update={"message": t_msg, "recommendation": t_rec})
    return alert
