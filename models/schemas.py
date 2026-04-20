from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class IrrigationDay:
    """Represents a single day in the irrigation schedule."""
    date: datetime
    predicted_soil_moisture: float
    irrigation_needed: bool
    recommended_volume_liters: float
    confidence: float

@dataclass
class IrrigationSchedule:
    """Consolidated 7-day irrigation schedule for a farm."""
    farm_id: str
    schedule: List[IrrigationDay]
    total_water_needed_liters: float
    next_critical_date: Optional[datetime]
    confidence: float
    model_used: str
    generated_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class YieldForecast:
    """Projected yield for the upcoming/current season."""
    farm_id: str
    crop_type: str
    predicted_yield: float           # kg/hectare
    yield_lower: float
    yield_upper: float
    forecast_date: datetime
    confidence_interval: float
    trend_component: float
    seasonal_component: float
    key_drivers: List[str]
    model_used: str


@dataclass
class PriceForecast:
    """Projected market prices for a commodity."""
    state: str
    district: str
    commodity: str
    predicted_modal_price: float
    price_lower: float
    price_upper: float
    forecast_date: datetime
    confidence_interval: float
    trend_component: float
    seasonal_component: float
    model_used: str = "prophet"

@dataclass
class LSTMPrediction:
    """Raw predictions from the LSTM model."""
    predictions: List[float]
    prediction_dates: List[datetime]
    rmse_estimate: float
    model_version: str

@dataclass
class TrainingResult:
    """Summary of the LSTM training process."""
    train_loss_history: List[float]
    val_loss_history: List[float]
    best_epoch: int
    best_val_loss: float

@dataclass
class EvalResult:
    """Evaluation metrics for the forecasting models."""
    rmse: float
    mae: float
    mape: float
    r_squared: float

@dataclass
class VisionAnalysis:
    farm_id: str
    image_path: str
    health_score: int
    crop_health_status: str
    pest_detected: bool
    pest_type: str
    pest_confidence: float
    affected_area_pct: float
    growth_stage_visual: str
    stress_pattern: str
    urgency_level: str
    visual_evidence: str
    recommended_action: str
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    gemini_latency_ms: int = 0
    token_count: int = 0

@dataclass
class PatchAnalysis:
    patch_row: int
    patch_col: int
    patch_image_path: str
    alert_pixel_pct: float
    vision_analysis: VisionAnalysis

@dataclass
class PestCase:
    pest_name: str
    symptoms: str
    affected_crops: List[str]
    organic_treatment: str
    chemical_treatment: str
    severity_level: str
    treatment_window_days: int
    source: str

@dataclass
class TreatmentPlan:
    priority_score: float
    act_within_hours: int
    organic_first: bool
    treatment_steps: List[str]
    estimated_cost_inr: str

@dataclass
class PlantPestResult:
    farm_id: Optional[str]
    image_filename: str
    preprocessing_metadata: dict      # from OpenCV pipeline
    vision_analysis: VisionAnalysis   # reuse existing dataclass
    similar_cases: List[PestCase]     # reuse existing dataclass
    treatment_plan: TreatmentPlan     # reuse existing dataclass
    confidence_label: str             # human readable
    final_confidence_adjusted: float  # avg of Gemini + FAISS score
    error: Optional[str]
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

def get_confidence_label(confidence: float) -> str:
    """Returns a human-readable label for the detection confidence."""
    if confidence >= 0.85:
        return "Very High Confidence"
    elif confidence >= 0.70:
        return "High Confidence"
    elif confidence >= 0.50:
        return "Moderate Confidence — Consider Expert Advice"
    elif confidence >= 0.30:
        return "Low Confidence — Please Retake Photo"
    else:
        return "Unable to Identify — Contact Local Agriculture Officer"

if __name__ == "__main__":
    # Smoke test for schemas
    now = datetime.utcnow()
    day = IrrigationDay(now, 25.0, True, 500.0, 0.85)
    schedule = IrrigationSchedule(
        farm_id="F1",
        schedule=[day],
        total_water_needed_liters=500.0,
        next_critical_date=now,
        confidence=0.85,
        model_used="ensemble"
    )
    print(f"Created IrrigationSchedule for {schedule.farm_id} at {schedule.generated_at}")
