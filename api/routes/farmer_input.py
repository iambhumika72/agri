"""
api/routes/farmer_input.py
============================
FastAPI router for Farmer Input endpoints.

Routes:
    POST  /farmer-input/sms              — Webhook for Twilio / Africa's Talking
    POST  /farmer-input/mobile           — Structured mobile-app submission
    GET   /farmer-input/history/{farmer_id} — Last-N records for a farmer

All requests are validated with Pydantic models.
Database access is injected via FastAPI's dependency-injection system using an
async SQLAlchemy session factory.

Dependencies:
    pip install fastapi pydantic sqlalchemy aiosqlite
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Relative imports within the agri package
from ingestion.farmer_input_ingestion import (
    AsyncSessionLocal,
    FarmerInputIngester,
    init_db,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — initialise DB on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app):
    await init_db()
    yield


router = APIRouter(prefix="/farmer-input", tags=["Farmer Input"], lifespan=_lifespan)


# ---------------------------------------------------------------------------
# DB dependency injection
# ---------------------------------------------------------------------------

async def get_db_session() -> async_sessionmaker:
    """
    FastAPI dependency that yields a session factory.

    We inject the factory (not a session) because FarmerInputIngester manages
    its own sessions internally, keeping transaction scope explicit.
    """
    return AsyncSessionLocal


SessionFactoryDep = Annotated[async_sessionmaker, Depends(get_db_session)]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SMSWebhookPayload(BaseModel):
    """
    Normalised schema that accepts both Twilio and Africa's Talking webhooks.

    Twilio fields : From, Body, MessageSid, AccountSid (optional extras ignored).
    AT fields     : from_, text, id (extra fields ignored).
    """

    # Twilio
    From: Optional[str] = Field(None, description="Sender phone number (Twilio)")
    Body: Optional[str] = Field(None, description="SMS body text (Twilio)")
    MessageSid: Optional[str] = Field(None, description="Twilio message SID")

    # Africa's Talking (aliased to avoid Python keyword conflict)
    from_: Optional[str] = Field(None, alias="from", description="Sender phone (AT)")
    text: Optional[str] = Field(None, description="SMS body text (AT)")
    id: Optional[str] = Field(None, description="Africa's Talking message ID")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @field_validator("Body", "text", mode="before")
    @classmethod
    def body_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip() == "":
            raise ValueError("SMS body must not be an empty string.")
        return v

    def to_ingestion_dict(self) -> dict:
        """Flatten to the shape expected by FarmerInputIngester.ingest_sms."""
        return {
            "From": self.From or self.from_,
            "Body": self.Body or self.text,
        }


class MobileInputPayload(BaseModel):
    """Structured observation submitted from the mobile companion app."""

    farmer_id: str = Field(..., min_length=1, max_length=64, description="Unique farmer identifier")
    location: str = Field(..., min_length=1, max_length=255, description="Village name or 'lat,lon'")
    crop_type: str = Field(..., min_length=1, max_length=64, description="Type of crop being cultivated")
    observed_issue: str = Field(
        ...,
        description="Issue category: pest | disease | drought | flood | other",
    )
    severity: str = Field(
        ...,
        pattern=r"^(low|medium|high)$",
        description="Severity level: low | medium | high",
    )
    date_observed: date = Field(..., description="Date the issue was observed (YYYY-MM-DD)")
    additional_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Free-text supplementary information",
    )

    model_config = {"extra": "ignore"}

    @field_validator("observed_issue", mode="before")
    @classmethod
    def normalize_issue(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("crop_type", mode="before")
    @classmethod
    def normalize_crop(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: str) -> str:
        return v.lower().strip()


class FarmerInputResponse(BaseModel):
    """Standard response for a successfully created farmer-input record."""

    record_id: str = Field(..., description="UUID of the persisted record")
    status: str = Field("created", description="Operation status")
    message: str = Field("Farmer input recorded successfully.")


class FarmerHistoryRecord(BaseModel):
    """Single row from farmer_inputs returned in history queries."""

    id: str
    farmer_id: str
    location_raw: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    crop_type: Optional[str] = None
    observed_issue: Optional[str] = None
    severity: Optional[str] = None
    date_observed: Optional[date] = None
    additional_notes: Optional[str] = None
    source: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class FarmerHistoryResponse(BaseModel):
    """Paginated history response."""

    farmer_id: str
    total_returned: int
    records: list[FarmerHistoryRecord]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sms",
    response_model=FarmerInputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="SMS Webhook (Twilio / Africa's Talking)",
    description=(
        "Receives an inbound SMS from a Twilio or Africa's Talking webhook. "
        "Parses the free-text body into structured fields and persists the record. "
        "Returns 422 if the message body is completely unparseable."
    ),
)
async def receive_sms(
    payload: SMSWebhookPayload,
    session_factory: SessionFactoryDep,
    x_twilio_signature: Annotated[Optional[str], Header()] = None,
) -> FarmerInputResponse:
    """
    Webhook endpoint for incoming SMS messages.

    Both Twilio and Africa's Talking can be configured to POST their callbacks
    here. The endpoint normalises the provider-specific payload and delegates
    parsing to FarmerInputIngester.

    Security note: In production, validate `x_twilio_signature` or the AT HMAC
    header against your webhook secret before processing.
    """
    ingester = FarmerInputIngester(session_factory)
    ingestion_dict = payload.to_ingestion_dict()

    record_id = await ingester.ingest_sms(ingestion_dict)
    if record_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "SMS body could not be parsed into a valid farmer-input record. "
                "The message has been saved for human review in `failed_inputs`."
            ),
        )

    return FarmerInputResponse(record_id=record_id)


@router.post(
    "/mobile",
    response_model=FarmerInputResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mobile App Structured Submission",
    description=(
        "Receives a fully structured JSON observation from the mobile companion app. "
        "All fields are Pydantic-validated before persistence."
    ),
)
async def receive_mobile_input(
    payload: MobileInputPayload,
    session_factory: SessionFactoryDep,
) -> FarmerInputResponse:
    """
    Endpoint for the mobile companion app to submit field observations.

    The payload is already structured, so no parsing heuristics are needed.
    The ingester validates business rules (e.g., known issue types) and persists.
    """
    ingester = FarmerInputIngester(session_factory)

    try:
        record_id = await ingester.ingest_mobile(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return FarmerInputResponse(record_id=record_id)


@router.get(
    "/history/{farmer_id}",
    response_model=FarmerHistoryResponse,
    summary="Fetch Farmer Submission History",
    description="Returns the last N records for a given farmer, ordered newest-first.",
)
async def get_farmer_history(
    farmer_id: str,
    session_factory: SessionFactoryDep,
    limit: int = Query(20, ge=1, le=200, description="Maximum number of records to return"),
) -> FarmerHistoryResponse:
    """
    Retrieve historical submissions for a specific farmer.

    Args:
        farmer_id: The farmer's unique identifier.
        limit:     Max records to return (1–200, default 20).

    Returns:
        FarmerHistoryResponse with a list of past records.
    """
    ingester = FarmerInputIngester(session_factory)
    records_raw = await ingester.fetch_farmer_history(farmer_id, limit=limit)

    if not records_raw:
        # Return empty list rather than 404 — no records ≠ not found
        return FarmerHistoryResponse(
            farmer_id=farmer_id,
            total_returned=0,
            records=[],
        )

    records = [FarmerHistoryRecord(**r) for r in records_raw]
    return FarmerHistoryResponse(
        farmer_id=farmer_id,
        total_returned=len(records),
        records=records,
    )



