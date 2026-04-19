from __future__ import annotations
"""models/__init__.py — Public exports for the models package."""
from .schemas import (
    IrrigationDay,
    IrrigationSchedule,
    YieldForecast,
    LSTMPrediction,
    TrainingResult,
    EvalResult,
    VisionAnalysis,
    PatchAnalysis,
    PestCase,
    TreatmentPlan,
)
from .prophet_forecaster import ProphetForecaster
from .lstm_forecaster import LSTMForecaster, CropLSTM
from .ensemble_forecaster import EnsembleForecaster
from .vision_model import VisionModel
from .pest_retriever import PestRetriever

__all__ = [
    "IrrigationDay", "IrrigationSchedule", "YieldForecast",
    "LSTMPrediction", "TrainingResult", "EvalResult",
    "ProphetForecaster", "LSTMForecaster", "CropLSTM", "EnsembleForecaster",
    "VisionAnalysis", "PatchAnalysis", "PestCase", "TreatmentPlan",
    "VisionModel", "PestRetriever",
]
