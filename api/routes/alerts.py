from __future__ import annotations

"""
api/routes/alerts.py
=====================
Alert delivery endpoints for AgriSense.
Serves real-time agronomic alerts triggered by satellite change detection
and sensor threshold breaches.
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


class AlertSummary(BaseModel):
    farm_id: str
    total_alerts: int
    critical_count: int
    recent_alerts: List[AlertResponse]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{farm_id}", response_model=AlertSummary)
async def get_farm_alerts(
    farm_id: str,
    days: int = Query(default=7, ge=1, le=30, description="Number of past days to retrieve alerts for"),
):
    """
    Returns all active alerts for a farm over the last N days.
    In production, this reads from a Redis/Postgres event store.
    Currently returns synthesized alerts based on farm context.
    """
    log.info("Fetching alerts for farm=%s over last %d days", farm_id, days)

    # Generate representative alerts based on typical farm conditions
    # In production, replace with: alerts = await alert_store.get_alerts(farm_id, days)
    now = datetime.utcnow()
    alerts = [
        AlertResponse(
            alert_id=f"{farm_id}-DROUGHT-001",
            farm_id=farm_id,
            alert_type="drought",
            severity="medium",
            message="Soil moisture dropped below 25% threshold for 3 consecutive days.",
            recommendation="Irrigate 12,000 liters within the next 24 hours. Check drip lines.",
            triggered_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=2),
        ),
    ]

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
    )
