"""
state.py — LangGraph state definitions for the Trace Agricultural AI System.

Each node in the pipeline reads from and writes to this shared state object.
Adding a new data source means adding a new Context dataclass here and
including it in AgriState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, List
from models.schemas import VisionAnalysis, PatchAnalysis, PestCase, TreatmentPlan


# ---------------------------------------------------------------------------
# Historical Database Context
# ---------------------------------------------------------------------------
@dataclass
class HistoricalContext:
    """
    Holds all outputs produced by the historical_db_node.

    Fields
    ------
    farm_id : str
        The farm this context belongs to.
    yield_history : list[dict]
        Raw yield records as list of dicts (from YieldRecord.to_dict()).
    pest_risk_score : float | None
        Weighted risk score in [0, 1].
        Formula: Σ(severity_i × affected_area_pct_i) / (N × 5 × 100)
        Set to None if DB is unreachable or no pest data exists.
    soil_deficiencies : list[str]
        Flags such as ["low_nitrogen", "low_potassium"].
    irrigation_efficiency : float | None
        Efficiency ratio in (0, 1]; 1.0 = exactly on baseline.
    farm_summary : dict
        LLM-ready structured summary produced by HistoricalFeatureExtractor.
    last_updated : datetime
        UTC timestamp of when this context was populated.
    """

    farm_id: str = ""
    yield_history: list[dict] = field(default_factory=list)
    pest_risk_score: Optional[float] = None
    soil_deficiencies: list[str] = field(default_factory=list)
    irrigation_efficiency: Optional[float] = None
    farm_summary: dict = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def is_degraded(self) -> bool:
        """Return True if the context was populated with degraded / missing data."""
        return (
            self.pest_risk_score is None
            and not self.yield_history
            and not self.farm_summary
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for downstream JSON encoding."""
        return {
            "farm_id": self.farm_id,
            "yield_history": self.yield_history,
            "pest_risk_score": self.pest_risk_score,
            "soil_deficiencies": self.soil_deficiencies,
            "irrigation_efficiency": self.irrigation_efficiency,
            "farm_summary": self.farm_summary,
            "last_updated": self.last_updated.isoformat(),
            "is_degraded": self.is_degraded(),
        }


# ---------------------------------------------------------------------------
# Unified pipeline state — add other data-source contexts as needed
# ---------------------------------------------------------------------------
@dataclass
class AgriState:
    """
    Top-level LangGraph state shared across all pipeline nodes.

    Each field corresponds to one data-source module:
      historical     — Historical Database node (this module)
      satellite      — NDVI / Satellite node (separate module)
      iot_sensors    — IoT Sensor node (separate module)
      weather        — Weather API node (separate module)
      farmer_sms     — Farmer SMS input node (separate module)

    Unimplemented source contexts default to None and downstream nodes
    must handle None gracefully (degraded-pipeline pattern).
    """

    # Core input
    farm_id: str = ""

    # Data source contexts
    historical: Optional[HistoricalContext] = None
    satellite: Optional[dict] = None    # placeholder until satellite module is built
    iot_sensors: Optional[dict] = None  # placeholder
    weather: Optional[dict] = None      # placeholder
    farmer_sms: Optional[dict] = None   # placeholder

    # Vision and Pest Analysis
    vision_analysis: Optional[VisionAnalysis] = None
    patch_analyses: List[PatchAnalysis] = field(default_factory=list)
    health_map_path: Optional[str] = None
    pest_cases: List[PestCase] = field(default_factory=list)
    treatment_plan: Optional[TreatmentPlan] = None

    # Forecasting results
    irrigation_schedule: Optional[Any] = None
    yield_forecast: Optional[Any] = None
    forecast_model_used: Optional[str] = None
    feature_vector: Optional[Any] = None
    aligned_df: Optional[Any] = None

    # Final Recommendation
    full_advisory: Optional[Any] = None

    # Pipeline metadata
    pipeline_run_id: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    errors: list[str] = field(default_factory=list)

    def add_error(self, source: str, message: str) -> None:
        """Record a non-fatal error from a pipeline node."""
        self.errors.append(f"[{source}] {message}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "farm_id": self.farm_id,
            "historical": self.historical.to_dict() if self.historical else None,
            "satellite": self.satellite,
            "iot_sensors": self.iot_sensors,
            "weather": self.weather,
            "farmer_sms": self.farmer_sms,
            "pipeline_run_id": self.pipeline_run_id,
            "started_at": self.started_at.isoformat(),
            "errors": self.errors,
        }


if __name__ == "__main__":
    # Smoke test: create state and serialise
    import json

    state = AgriState(
        farm_id="test-farm-001",
        historical=HistoricalContext(
            farm_id="test-farm-001",
            pest_risk_score=0.42,
            soil_deficiencies=["low_nitrogen"],
            irrigation_efficiency=0.87,
        ),
    )
    print(json.dumps(state.to_dict(), indent=2, default=str))
