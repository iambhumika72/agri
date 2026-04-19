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
