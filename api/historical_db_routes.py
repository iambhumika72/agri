"""
api/historical_db_routes.py — FastAPI APIRouter for Historical Database endpoints.

Compatibility note (FastAPI 0.104 / Pydantic 2):
- Annotated[Any, Depends(get_db)] is the canonical dependency pattern.
  The `db` parameter must come AFTER all Query/Path params in the signature
  (Python enforces that non-default args don't follow default args).
  Since DBDep = Annotated[Any, Depends(get_db)] carries no Python-level default,
  it must be the last parameter.  Use a sentinel default `= None` for DBDep
  so Python's argument-ordering rules are satisfied; FastAPI will always inject
  the actual connector and the None default is never observed.

Design notes:
- The POST /history/ingest endpoint accepts a discriminated union payload via the
  `table` field so a single route handles all 6 table schemas cleanly.
- 404 responses use a consistent {"detail": "..."} body matching FastAPI defaults.
- Date fields in query params are typed as `date` so FastAPI auto-validates the
  ISO-8601 format (e.g. 2023-07-01) and returns 422 on invalid input.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["Historical Database"])


# ---------------------------------------------------------------------------
# Dependency: DB connector
# ---------------------------------------------------------------------------
def get_db():  # type: ignore[return]
    """FastAPI dependency that yields an open HistoricalDBConnector."""
    from historical_db.db_connector import HistoricalDBConnector

    db = HistoricalDBConnector()
    db.open()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class YieldRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    record_id: UUID
    farm_id: UUID
    crop_id: UUID
    crop_name: Optional[str] = None
    season: str
    year: int
    yield_kg_per_hectare: float
    harvest_date: date
    notes: Optional[str] = None


class PestRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pest_id: UUID
    farm_id: UUID
    crop_id: UUID
    pest_name: str
    severity: int
    affected_area_pct: float
    detected_date: date
    resolved_date: Optional[date] = None
    treatment_applied: Optional[str] = None


class SoilHealthOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    soil_id: UUID
    farm_id: UUID
    recorded_date: date
    ph_level: Optional[float] = None
    nitrogen_ppm: Optional[float] = None
    phosphorus_ppm: Optional[float] = None
    potassium_ppm: Optional[float] = None
    organic_matter_pct: Optional[float] = None
    moisture_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# Ingest request schemas (one per table)
# ---------------------------------------------------------------------------
class FarmIngest(BaseModel):
    table: Literal["farms"]
    farmer_name: str
    district: str
    state: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    area_hectares: float = Field(..., gt=0)


class CropIngest(BaseModel):
    table: Literal["crops"]
    crop_name: str
    crop_variety: Optional[str] = None
    season_type: Literal["Kharif", "Rabi", "Zaid"]


class YieldIngest(BaseModel):
    table: Literal["yield_records"]
    farm_id: UUID
    crop_id: UUID
    season: Literal["Kharif", "Rabi", "Zaid"]
    year: int = Field(..., ge=1950, le=2100)
    yield_kg_per_hectare: float = Field(..., ge=0)
    harvest_date: date
    notes: Optional[str] = None


class PestIngest(BaseModel):
    table: Literal["pest_records"]
    farm_id: UUID
    crop_id: UUID
    pest_name: str
    severity: int = Field(..., ge=1, le=5)
    affected_area_pct: float = Field(..., ge=0, le=100)
    detected_date: date
    resolved_date: Optional[date] = None
    treatment_applied: Optional[str] = None

    @field_validator("resolved_date")
    @classmethod
    def resolved_after_detected(
        cls, v: Optional[date], info: Any
    ) -> Optional[date]:
        detected = info.data.get("detected_date")
        if v is not None and detected is not None and v < detected:
            raise ValueError("resolved_date must be on or after detected_date")
        return v


class IrrigationIngest(BaseModel):
    table: Literal["irrigation_logs"]
    farm_id: UUID
    log_date: date
    water_used_liters: float = Field(..., ge=0)
    method: Literal["drip", "flood", "sprinkler"]
    duration_minutes: int = Field(..., ge=0)


class SoilIngest(BaseModel):
    table: Literal["soil_health"]
    farm_id: UUID
    recorded_date: date
    ph_level: Optional[float] = Field(default=None, ge=0, le=14)
    nitrogen_ppm: Optional[float] = Field(default=None, ge=0)
    phosphorus_ppm: Optional[float] = Field(default=None, ge=0)
    potassium_ppm: Optional[float] = Field(default=None, ge=0)
    organic_matter_pct: Optional[float] = Field(default=None, ge=0, le=100)
    moisture_pct: Optional[float] = Field(default=None, ge=0, le=100)


# Discriminated union — FastAPI/Pydantic resolves the correct model via `table`
IngestPayload = Annotated[
    Union[
        FarmIngest,
        CropIngest,
        YieldIngest,
        PestIngest,
        IrrigationIngest,
        SoilIngest,
    ],
    Field(discriminator="table"),
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get(
    "/farms",
    response_model=list[dict],
    summary="List all farms",
)
def list_all_farms(
    db: Any = Depends(get_db),
) -> list[dict]:
    """Returns a list of all farms for selection in the UI."""
    return db.get_all_farms()


@router.get(
    "/yield/{farm_id}",
    response_model=list[YieldRecordOut],
    summary="Get yield history for a farm",
)
def get_yield_history(
    farm_id: str,
    crop_id: str = Query(..., description="UUID of the crop"),
    years: int = Query(default=5, ge=1, le=20, description="Number of years to look back"),
    db: Any = Depends(get_db),
) -> list[YieldRecordOut]:
    logger.info("GET /yield/%s crop_id=%s years=%d", farm_id, crop_id, years)

    if not db.farm_exists(farm_id):
        raise HTTPException(status_code=404, detail=f"Farm '{farm_id}' not found.")

    df = db.get_yield_history(farm_id=farm_id, crop_id=crop_id, years=years)
    if df.empty:
        return []

    df_reset = df.reset_index()
    return [YieldRecordOut(**row) for row in df_reset.to_dict(orient="records")]


@router.get(
    "/pests/{farm_id}",
    response_model=list[PestRecordOut],
    summary="Get pest timeline for a farm",
)
def get_pest_history(
    farm_id: str,
    start_date: date = Query(..., description="Start of date range (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End of date range (YYYY-MM-DD)"),
    db: Any = Depends(get_db),
) -> list[PestRecordOut]:
    logger.info("GET /pests/%s %s → %s", farm_id, start_date, end_date)

    if not db.farm_exists(farm_id):
        raise HTTPException(status_code=404, detail=f"Farm '{farm_id}' not found.")

    if end_date < start_date:
        raise HTTPException(
            status_code=422, detail="end_date must be on or after start_date."
        )

    df = db.get_pest_history(farm_id=farm_id, start_date=start_date, end_date=end_date)
    if df.empty:
        return []

    df_reset = df.reset_index()
    # Replace NaN/NaT with None so Pydantic doesn't receive float nan for date fields
    records = df_reset.astype(object).where(df_reset.notna(), other=None).to_dict(orient="records")
    return [PestRecordOut(**row) for row in records]


@router.get(
    "/soil/{farm_id}",
    response_model=list[SoilHealthOut],
    summary="Get soil health trend for a farm",
)
def get_soil_trend(
    farm_id: str,
    last_n: int = Query(default=10, ge=1, le=100, description="Number of records to return"),
    db: Any = Depends(get_db),
) -> list[SoilHealthOut]:
    logger.info("GET /soil/%s last_n=%d", farm_id, last_n)

    if not db.farm_exists(farm_id):
        raise HTTPException(status_code=404, detail=f"Farm '{farm_id}' not found.")

    df = db.get_soil_trend(farm_id=farm_id, last_n_records=last_n)
    if df.empty:
        return []

    df_reset = df.reset_index()
    return [SoilHealthOut(**row) for row in df_reset.to_dict(orient="records")]


@router.get(
    "/summary/{farm_id}",
    response_model=dict,
    summary="Get LLM-ready farm summary",
)
def get_farm_summary(
    farm_id: str,
    db: Any = Depends(get_db),
) -> dict:
    logger.info("GET /summary/%s", farm_id)

    if not db.farm_exists(farm_id):
        raise HTTPException(status_code=404, detail=f"Farm '{farm_id}' not found.")

    from preprocessing.historical_feature_extractor import HistoricalFeatureExtractor

    extractor = HistoricalFeatureExtractor(db)
    return extractor._llm_summary(farm_id)


@router.post(
    "/ingest",
    status_code=201,
    summary="Ingest a record into any historical table",
)
def ingest_record(
    payload: Annotated[
        Union[
            FarmIngest,
            CropIngest,
            YieldIngest,
            PestIngest,
            IrrigationIngest,
            SoilIngest,
        ],
        Body(discriminator="table"),
    ],
    db: Any = Depends(get_db),
) -> dict:
    logger.info("POST /ingest table=%s", payload.table)

    table_name = payload.table
    # Exclude the discriminator field before inserting
    data = payload.model_dump(exclude={"table"})
    # Convert UUID objects and date objects to str for generic insert
    data = {
        k: str(v) if isinstance(v, UUID) else (v.isoformat() if isinstance(v, date) else v)
        for k, v in data.items()
        if v is not None
    }
    # Auto-generate primary key UUID if caller omitted it (SQLite has no server-side uuid_generate_v4)
    import uuid as _uuid
    pk_map = {
        "farms": "farm_id", "crops": "crop_id",
        "yield_records": "record_id", "pest_records": "pest_id",
        "irrigation_logs": "log_id", "soil_health": "soil_id",
    }
    pk_col = pk_map.get(table_name)
    if pk_col and pk_col not in data:
        data[pk_col] = str(_uuid.uuid4())

    try:
        db.insert_record(table_name, data)
    except Exception as exc:
        logger.error("POST /ingest failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Insert failed: {exc}")

    return {"status": "created", "table": table_name}


if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    app = FastAPI(title="Trace Historical DB — Dev Server")
    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
