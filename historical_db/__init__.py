"""
historical_db — Historical Database package for Trace Agricultural AI System.

Exports core components for easy import from the package root.
"""

from historical_db.models import (
    Base,
    Farm,
    Crop,
    YieldRecord,
    PestRecord,
    IrrigationLog,
    SoilHealth,
)
from historical_db.db_connector import HistoricalDBConnector

__all__ = [
    "Base",
    "Farm",
    "Crop",
    "YieldRecord",
    "PestRecord",
    "IrrigationLog",
    "SoilHealth",
    "HistoricalDBConnector",
]
