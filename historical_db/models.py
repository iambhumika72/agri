"""
historical_db/models.py — SQLAlchemy ORM models for Trace Historical Database.

Design notes:
- All PKs use UUID so records can be generated offline and merged without collision.
- `to_dict()` performs shallow serialisation; UUID and date objects are cast to
  str/isoformat so the output is directly JSON-serialisable without extra encoders.
- Relationships are defined with lazy="select" (default) so they work with both
  sync and async session patterns; change to lazy="joined" for read-heavy paths.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship


# ---------------------------------------------------------------------------
# Shared Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Shared declarative base — all models inherit from this."""
    __allow_unmapped__ = True  # permits plain Python type hints alongside Mapped[]
    pass


# ---------------------------------------------------------------------------
# ENUM helpers (mirrors schema.sql enums)
# ---------------------------------------------------------------------------
SeasonTypeEnum = Enum("Kharif", "Rabi", "Zaid", name="season_type")
IrrigationMethodEnum = Enum("drip", "flood", "sprinkler", name="irrigation_method")


# ---------------------------------------------------------------------------
# Farm
# ---------------------------------------------------------------------------
class Farm(Base):
    """Represents a physical farm registered in the system."""

    __tablename__ = "farms"

    farm_id: uuid.UUID = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farmer_name: str = Column(String(120), nullable=False)
    district: str = Column(String(100), nullable=False)
    state: str = Column(String(100), nullable=False)
    latitude: float = Column(Double, nullable=False)
    longitude: float = Column(Double, nullable=False)
    area_hectares: float = Column(Double, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90",   name="chk_farm_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="chk_farm_lon"),
        CheckConstraint("area_hectares > 0",              name="chk_farm_area"),
        Index("idx_farms_state_district", "state", "district"),
    )

    # Relationships
    yield_records: Mapped[List["YieldRecord"]] = relationship(
        "YieldRecord", back_populates="farm", cascade="all, delete-orphan"
    )
    pest_records: Mapped[List["PestRecord"]] = relationship(
        "PestRecord", back_populates="farm", cascade="all, delete-orphan"
    )
    irrigation_logs: Mapped[List["IrrigationLog"]] = relationship(
        "IrrigationLog", back_populates="farm", cascade="all, delete-orphan"
    )
    soil_health_records: Mapped[List["SoilHealth"]] = relationship(
        "SoilHealth", back_populates="farm", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "farm_id": str(self.farm_id),
            "farmer_name": self.farmer_name,
            "district": self.district,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "area_hectares": self.area_hectares,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Crop
# ---------------------------------------------------------------------------
class Crop(Base):
    """Crop master reference table."""

    __tablename__ = "crops"

    crop_id: uuid.UUID = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    crop_name: str = Column(String(100), nullable=False)
    crop_variety: Optional[str] = Column(String(100))
    season_type: str = Column(SeasonTypeEnum, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("crop_name", "crop_variety", name="uq_crop_name_variety"),
        Index("idx_crops_season", "season_type"),
    )

    yield_records: Mapped[List["YieldRecord"]] = relationship(
        "YieldRecord", back_populates="crop"
    )
    pest_records: Mapped[List["PestRecord"]] = relationship(
        "PestRecord", back_populates="crop"
    )

    def to_dict(self) -> dict:
        return {
            "crop_id": str(self.crop_id),
            "crop_name": self.crop_name,
            "crop_variety": self.crop_variety,
            "season_type": self.season_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# YieldRecord
# ---------------------------------------------------------------------------
class YieldRecord(Base):
    """Per-season yield observation for a farm × crop pair."""

    __tablename__ = "yield_records"

    record_id: uuid.UUID = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: uuid.UUID = Column(
        Uuid(as_uuid=True), ForeignKey("farms.farm_id", ondelete="CASCADE"), nullable=False
    )
    crop_id: uuid.UUID = Column(
        Uuid(as_uuid=True), ForeignKey("crops.crop_id", ondelete="RESTRICT"), nullable=False
    )
    season: str = Column(SeasonTypeEnum, nullable=False)
    year: int = Column(SmallInteger, nullable=False)
    yield_kg_per_hectare: float = Column(Double, nullable=False)
    harvest_date: date = Column(Date, nullable=False)
    notes: Optional[str] = Column(Text)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("year BETWEEN 1950 AND 2100",          name="chk_yield_year"),
        CheckConstraint("yield_kg_per_hectare >= 0",           name="chk_yield_kg"),
        Index("idx_yield_farm_year",    "farm_id", "year"),
        Index("idx_yield_crop_season",  "crop_id", "season"),
        Index("idx_yield_harvest_date", "harvest_date"),
    )

    farm: Mapped["Farm"] = relationship("Farm", back_populates="yield_records")
    crop: Mapped["Crop"] = relationship("Crop", back_populates="yield_records")

    def to_dict(self) -> dict:
        return {
            "record_id": str(self.record_id),
            "farm_id": str(self.farm_id),
            "crop_id": str(self.crop_id),
            "season": self.season,
            "year": self.year,
            "yield_kg_per_hectare": self.yield_kg_per_hectare,
            "harvest_date": self.harvest_date.isoformat() if self.harvest_date else None,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# PestRecord
# ---------------------------------------------------------------------------
class PestRecord(Base):
    """Pest outbreak event recorded at a farm."""

    __tablename__ = "pest_records"

    pest_id: uuid.UUID = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: uuid.UUID = Column(
        Uuid(as_uuid=True), ForeignKey("farms.farm_id", ondelete="CASCADE"), nullable=False
    )
    crop_id: uuid.UUID = Column(
        Uuid(as_uuid=True), ForeignKey("crops.crop_id", ondelete="RESTRICT"), nullable=False
    )
    pest_name: str = Column(String(120), nullable=False)
    severity: int = Column(SmallInteger, nullable=False)
    affected_area_pct: float = Column(Double, nullable=False)
    detected_date: date = Column(Date, nullable=False)
    resolved_date: Optional[date] = Column(Date)
    treatment_applied: Optional[str] = Column(Text)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 5",               name="chk_pest_severity"),
        CheckConstraint("affected_area_pct BETWEEN 0 AND 100",    name="chk_pest_area_pct"),
        CheckConstraint(
            "resolved_date IS NULL OR resolved_date >= detected_date",
            name="chk_resolved_after_detected",
        ),
        Index("idx_pest_farm_detected", "farm_id", "detected_date"),
        Index("idx_pest_severity",      "severity"),
        Index("idx_pest_crop",          "crop_id"),
    )

    farm: Mapped["Farm"] = relationship("Farm", back_populates="pest_records")
    crop: Mapped["Crop"] = relationship("Crop", back_populates="pest_records")

    def to_dict(self) -> dict:
        return {
            "pest_id": str(self.pest_id),
            "farm_id": str(self.farm_id),
            "crop_id": str(self.crop_id),
            "pest_name": self.pest_name,
            "severity": self.severity,
            "affected_area_pct": self.affected_area_pct,
            "detected_date": self.detected_date.isoformat() if self.detected_date else None,
            "resolved_date": self.resolved_date.isoformat() if self.resolved_date else None,
            "treatment_applied": self.treatment_applied,
        }


# ---------------------------------------------------------------------------
# IrrigationLog
# ---------------------------------------------------------------------------
class IrrigationLog(Base):
    """Daily irrigation event for a farm."""

    __tablename__ = "irrigation_logs"

    log_id: uuid.UUID = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: uuid.UUID = Column(
        Uuid(as_uuid=True), ForeignKey("farms.farm_id", ondelete="CASCADE"), nullable=False
    )
    log_date: date = Column(Date, nullable=False)
    water_used_liters: float = Column(Double, nullable=False)
    method: str = Column(IrrigationMethodEnum, nullable=False)
    duration_minutes: int = Column(Integer, nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("water_used_liters >= 0",  name="chk_irr_water"),
        CheckConstraint("duration_minutes >= 0",   name="chk_irr_duration"),
        Index("idx_irrigation_farm_date", "farm_id", "log_date"),
        Index("idx_irrigation_method",    "method"),
    )

    farm: Mapped["Farm"] = relationship("Farm", back_populates="irrigation_logs")

    def to_dict(self) -> dict:
        return {
            "log_id": str(self.log_id),
            "farm_id": str(self.farm_id),
            "log_date": self.log_date.isoformat() if self.log_date else None,
            "water_used_liters": self.water_used_liters,
            "method": self.method,
            "duration_minutes": self.duration_minutes,
        }


# ---------------------------------------------------------------------------
# SoilHealth
# ---------------------------------------------------------------------------
class SoilHealth(Base):
    """Soil health sample for a farm on a specific date."""

    __tablename__ = "soil_health"

    soil_id: uuid.UUID = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: uuid.UUID = Column(
        Uuid(as_uuid=True), ForeignKey("farms.farm_id", ondelete="CASCADE"), nullable=False
    )
    recorded_date: date = Column(Date, nullable=False)
    ph_level: Optional[float] = Column(Double)
    nitrogen_ppm: Optional[float] = Column(Double)
    phosphorus_ppm: Optional[float] = Column(Double)
    potassium_ppm: Optional[float] = Column(Double)
    organic_matter_pct: Optional[float] = Column(Double)
    moisture_pct: Optional[float] = Column(Double)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("ph_level BETWEEN 0 AND 14",          name="chk_soil_ph"),
        CheckConstraint("nitrogen_ppm >= 0",                  name="chk_soil_n"),
        CheckConstraint("phosphorus_ppm >= 0",                name="chk_soil_p"),
        CheckConstraint("potassium_ppm >= 0",                 name="chk_soil_k"),
        CheckConstraint("organic_matter_pct BETWEEN 0 AND 100", name="chk_soil_om"),
        CheckConstraint("moisture_pct BETWEEN 0 AND 100",    name="chk_soil_moist"),
        Index("idx_soil_farm_date", "farm_id", "recorded_date"),
    )

    farm: Mapped["Farm"] = relationship("Farm", back_populates="soil_health_records")

    def to_dict(self) -> dict:
        return {
            "soil_id": str(self.soil_id),
            "farm_id": str(self.farm_id),
            "recorded_date": self.recorded_date.isoformat() if self.recorded_date else None,
            "ph_level": self.ph_level,
            "nitrogen_ppm": self.nitrogen_ppm,
            "phosphorus_ppm": self.phosphorus_ppm,
            "potassium_ppm": self.potassium_ppm,
            "organic_matter_pct": self.organic_matter_pct,
            "moisture_pct": self.moisture_pct,
        }


if __name__ == "__main__":
    # Quick smoke-test: create all tables against an in-memory SQLite DB
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:", echo=True)
    Base.metadata.create_all(engine)
    print("All tables created successfully.")
