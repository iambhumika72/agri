"""
ingestion/farmer_input_ingestion.py
====================================
Farmer Input Ingestion Module for the Agri Generative AI Platform.

Handles two input channels:
  1. SMS via Twilio / Africa's Talking (AT) webhook callbacks.
  2. Structured JSON POSTed from a mobile companion app.

Parsed records are persisted to the `farmer_inputs` table.
Unparseable raw SMS bodies are stored in `failed_inputs` for human review.

Dependencies:
    pip install sqlalchemy aiosqlite asyncpg pydantic python-dateutil pyyaml
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, date
from typing import Optional

import yaml
from dateutil import parser as dateutil_parser
from sqlalchemy import (
    Column,
    String,
    Float,
    Date,
    DateTime,
    Text,
    Enum as SAEnum,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ---------------------------------------------------------------------------
# Load config
# ---------------------------------------------------------------------------
_CONFIG_PATH = "configs/farmer_input_config.yaml"


def _load_config(path: str = _CONFIG_PATH) -> dict:
    """Load YAML configuration, falling back to sensible defaults."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        logger.warning("Config file %s not found; using defaults.", path)
        return {}


CONFIG = _load_config()
DB_URL: str = CONFIG.get("database", {}).get(
    "url", "sqlite+aiosqlite:///./agri.db"
)
SUPPORTED_CROPS: list[str] = CONFIG.get("crops", [])
SUPPORTED_ISSUES: list[str] = CONFIG.get("issues", [])
VILLAGE_COORDS: dict[str, dict] = CONFIG.get("village_coords", {})


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class FarmerInputRecord(Base):
    """Parsed and validated farmer input stored in `farmer_inputs`."""

    __tablename__ = "farmer_inputs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    farmer_id = Column(String(64), nullable=False, index=True)
    location_raw = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    crop_type = Column(String(64), nullable=True)
    observed_issue = Column(
        SAEnum("pest", "disease", "drought", "flood", "other", name="issue_enum"),
        nullable=True,
    )
    severity = Column(
        SAEnum("low", "medium", "high", name="severity_enum"),
        nullable=True,
    )
    date_observed = Column(Date, nullable=True)
    additional_notes = Column(Text, nullable=True)
    source = Column(String(16), nullable=False)   # "sms" | "mobile"
    raw_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FailedInputRecord(Base):
    """Raw SMS bodies that could not be parsed, stored in `failed_inputs`."""

    __tablename__ = "failed_inputs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_number = Column(String(32), nullable=True)
    raw_body = Column(Text, nullable=False)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Async engine / session factory
# ---------------------------------------------------------------------------
_engine = create_async_engine(DB_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    bind=_engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised.")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Regex patterns for free-text SMS parsing
_RE_FARMER_ID = re.compile(
    r"\b(?:farmer[_\s]?id|id|fid)[:\s=]+([A-Za-z0-9_\-]+)", re.IGNORECASE
)
_RE_LOCATION = re.compile(
    r"\b(?:location|loc|village|vill|village name)[:\s=]+([A-Za-z0-9\s,\.]+?)(?=\s*(?:crop|issue|severity|date|notes?|id|$)|[,;\n])",
    re.IGNORECASE,
)
_RE_LATLON = re.compile(
    r"\b(?:lat|latitude)[:\s=]+([\-0-9\.]+)[,\s]+(?:lon|lng|longitude)[:\s=]+([\-0-9\.]+)",
    re.IGNORECASE,
)
_RE_CROP = re.compile(
    r"\b(?:crop|crop[_\s]?type)[:\s=]+([A-Za-z\s]+?)(?:,|$|\n|;)",
    re.IGNORECASE,
)
_RE_SEVERITY = re.compile(
    r"\b(?:severity|sev)[:\s=]+(low|medium|high)\b", re.IGNORECASE
)
_RE_DATE = re.compile(
    r"\b(?:date|date[_\s]?observed|on)[:\s=]+(\d{1,4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,4}|\d{1,2}\s+\w+\s+\d{4})",
    re.IGNORECASE,
)
_RE_NOTES = re.compile(
    r"\b(?:notes?|additional[_\s]?notes?|info)[:\s=]+(.+?)(?:$|\n)",
    re.IGNORECASE | re.DOTALL,
)


def _match_keyword(text: str, keywords: list[str]) -> Optional[str]:
    """
    Return the first keyword found in `text` (case-insensitive),
    or None if nothing matches.
    """
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            return kw
    return None


def parse_sms(body: str) -> dict:
    """
    Parse a free-text SMS body into a structured dict.

    Tries regex patterns first; falls back to keyword matching for
    crop_type and observed_issue.

    Returns a dict with keys matching FarmerInputRecord columns.
    Raises ValueError if the minimum required fields are absent.
    """
    result: dict = {}

    # --- farmer_id ---
    m = _RE_FARMER_ID.search(body)
    result["farmer_id"] = m.group(1).strip() if m else None

    # --- location (lat/lon or village name) ---
    result["location_raw"] = None  # always present, even if unparseable
    m_ll = _RE_LATLON.search(body)
    if m_ll:
        result["latitude"] = float(m_ll.group(1))
        result["longitude"] = float(m_ll.group(2))
        result["location_raw"] = f"{result['latitude']},{result['longitude']}"
    else:
        m_loc = _RE_LOCATION.search(body)
        if m_loc:
            village = m_loc.group(1).strip().rstrip(",;")
            result["location_raw"] = village
            coords = VILLAGE_COORDS.get(village.lower())
            if coords:
                result["latitude"] = coords["lat"]
                result["longitude"] = coords["lon"]

    # --- crop_type ---
    m = _RE_CROP.search(body)
    if m:
        raw_crop = m.group(1).strip().lower()
        # Match against supported crops, or keep raw value
        matched_crop = _match_keyword(raw_crop, SUPPORTED_CROPS) or raw_crop
        result["crop_type"] = matched_crop
    else:
        result["crop_type"] = _match_keyword(body, SUPPORTED_CROPS)

    # --- observed_issue ---
    result["observed_issue"] = _match_keyword(body, SUPPORTED_ISSUES)

    # --- severity ---
    m = _RE_SEVERITY.search(body)
    if m:
        result["severity"] = m.group(1).lower()
    else:
        # keyword fallback
        for sev in ("high", "medium", "low"):
            if sev in body.lower():
                result["severity"] = sev
                break

    # --- date_observed ---
    m = _RE_DATE.search(body)
    if m:
        try:
            result["date_observed"] = dateutil_parser.parse(m.group(1)).date()
        except (ValueError, OverflowError):
            result["date_observed"] = None
    else:
        result["date_observed"] = None

    # --- additional_notes ---
    m = _RE_NOTES.search(body)
    result["additional_notes"] = m.group(1).strip() if m else None

    # Validate minimum fields
    if not result.get("farmer_id"):
        raise ValueError("farmer_id could not be extracted from SMS body.")
    if not result.get("observed_issue"):
        raise ValueError("observed_issue could not be identified from SMS body.")

    return result


# ---------------------------------------------------------------------------
# FarmerInputIngester
# ---------------------------------------------------------------------------

class FarmerInputIngester:
    """
    Ingests farmer-reported field observations from two channels:

    * SMS webhook payloads (Twilio or Africa's Talking format).
    * Structured JSON from the mobile companion app.

    Usage::

        ingester = FarmerInputIngester()
        await ingester.ingest_sms(sms_payload)
        await ingester.ingest_mobile(mobile_payload)
    """

    def __init__(self, session_factory=None) -> None:
        """
        Args:
            session_factory: An async SQLAlchemy session factory.
                             Defaults to the module-level AsyncSessionLocal.
        """
        self.session_factory = session_factory or AsyncSessionLocal

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest_sms(self, payload: dict) -> Optional[str]:
        """
        Process an incoming SMS webhook payload (Twilio or Africa's Talking).

        Twilio shape  → {"From": "+91...", "Body": "Farmer ID: F001 ..."}
        AT shape      → {"from": "+91...", "text": "Farmer ID: F001 ..."}

        Returns:
            The UUID of the saved FarmerInputRecord, or None on failure.
        """
        source_number, body = self._extract_sms_fields(payload)
        if not body:
            logger.error("SMS payload missing body: %s", payload)
            return None

        try:
            parsed = parse_sms(body)
        except ValueError as exc:
            logger.warning("Failed to parse SMS from %s: %s", source_number, exc)
            await self._save_failed(source_number, body, reason=str(exc))
            return None

        record = FarmerInputRecord(
            farmer_id=parsed["farmer_id"],
            location_raw=parsed.get("location_raw"),
            latitude=parsed.get("latitude"),
            longitude=parsed.get("longitude"),
            crop_type=parsed.get("crop_type"),
            observed_issue=parsed.get("observed_issue"),
            severity=parsed.get("severity"),
            date_observed=parsed.get("date_observed"),
            additional_notes=parsed.get("additional_notes"),
            source="sms",
            raw_message=body,
        )
        record_id = await self._persist(record)
        logger.info("SMS ingested — record_id=%s farmer_id=%s", record_id, parsed["farmer_id"])
        return record_id

    async def ingest_mobile(self, payload: dict) -> str:
        """
        Process a structured JSON payload from the mobile app.

        Expected keys: farmer_id, location (village or "lat,lon"),
        crop_type, observed_issue, severity, date_observed, additional_notes.

        Returns:
            The UUID of the saved FarmerInputRecord.

        Raises:
            ValueError: If required fields are missing.
        """
        farmer_id: Optional[str] = payload.get("farmer_id")
        if not farmer_id:
            raise ValueError("farmer_id is required in mobile payload.")

        # Resolve location
        lat, lon, location_raw = self._resolve_location(
            payload.get("location", "")
        )

        # Validate observed_issue
        issue = (payload.get("observed_issue") or "").lower()
        if issue not in SUPPORTED_ISSUES:
            issue = "other"

        # Validate severity
        severity = (payload.get("severity") or "").lower()
        if severity not in ("low", "medium", "high"):
            severity = None

        # Parse date
        raw_date = payload.get("date_observed")
        date_observed: Optional[date] = None
        if raw_date:
            try:
                date_observed = dateutil_parser.parse(str(raw_date)).date()
            except (ValueError, OverflowError):
                date_observed = None

        record = FarmerInputRecord(
            farmer_id=farmer_id,
            location_raw=location_raw,
            latitude=lat,
            longitude=lon,
            crop_type=(payload.get("crop_type") or "").lower() or None,
            observed_issue=issue or None,
            severity=severity,
            date_observed=date_observed,
            additional_notes=payload.get("additional_notes"),
            source="mobile",
            raw_message=None,
        )
        record_id = await self._persist(record)
        logger.info(
            "Mobile record ingested — record_id=%s farmer_id=%s",
            record_id,
            farmer_id,
        )
        return record_id

    async def fetch_farmer_history(
        self, farmer_id: str, limit: int = 20
    ) -> list[dict]:
        """
        Retrieve the last `limit` records for a given farmer, newest first.

        Returns:
            List of dicts with all FarmerInputRecord columns.
        """
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM farmer_inputs
                    WHERE farmer_id = :fid
                    ORDER BY created_at DESC
                    LIMIT :lim
                    """
                ),
                {"fid": farmer_id, "lim": limit},
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sms_fields(payload: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Normalise Twilio and Africa's Talking webhook shapes.

        Returns:
            (source_number, message_body)
        """
        # Twilio uses 'From' / 'Body'; AT uses 'from' / 'text'
        source_number = payload.get("From") or payload.get("from")
        body = payload.get("Body") or payload.get("text")
        return source_number, body

    @staticmethod
    def _resolve_location(location_str: str) -> tuple[Optional[float], Optional[float], str]:
        """
        Resolve a location string to (lat, lon, location_raw).

        Tries:
          1. "lat,lon" numeric format.
          2. Village-name lookup in VILLAGE_COORDS.
          3. Returns (None, None, location_str) as fallback.
        """
        location_str = (location_str or "").strip()
        if not location_str:
            return None, None, ""

        # Try numeric lat,lon
        parts = location_str.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                return lat, lon, location_str
            except ValueError:
                pass

        # Village lookup
        coords = VILLAGE_COORDS.get(location_str.lower())
        if coords:
            return coords["lat"], coords["lon"], location_str

        return None, None, location_str

    async def _persist(self, record: FarmerInputRecord) -> str:
        """Save a FarmerInputRecord and return its ID."""
        async with self.session_factory() as session:
            async with session.begin():
                session.add(record)
            await session.refresh(record)
        return record.id

    async def _save_failed(
        self, source_number: Optional[str], body: str, reason: str
    ) -> None:
        """Save a FailedInputRecord for human review."""
        failed = FailedInputRecord(
            source_number=source_number,
            raw_body=body,
            reason=reason,
        )
        async with self.session_factory() as session:
            async with session.begin():
                session.add(failed)
        logger.debug("Saved failed input for review (source=%s).", source_number)
