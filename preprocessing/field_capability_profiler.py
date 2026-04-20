"""
preprocessing/field_capability_profiler.py
==========================================
Generates a crop-agnostic FieldCapabilityProfile by aggregating 
satellite, weather, soil, and historical pest data.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from .schemas import (
    FieldCapabilityProfile,
    SatelliteAnalysis,
    WeatherForecast,
)

log = logging.getLogger(__name__)


class FieldCapabilityProfiler:
    """Aggregates multi-source data into a crop-agnostic field profile."""

    def generate_profile(
        self,
        farm_id: str,
        satellite: SatelliteAnalysis,
        weather: WeatherForecast,
        soil: Optional[dict] = None,
        pest_history: Optional[List[dict]] = None,
    ) -> FieldCapabilityProfile:
        """
        Derives the field capability using current and historical signals.
        
        Args:
            farm_id: Unique identifier for the farm.
            satellite: Processed satellite indices (NDVI, NDWI).
            weather: 7-day weather forecast data.
            soil: Dictionary containing soil health metrics (pH, organic matter).
            pest_history: List of historical pest occurrences.
            
        Returns:
            A FieldCapabilityProfile representing the field's agricultural potential.
        """
        log.info("Generating field capability profile for farm_id=%s", farm_id)

        # 1. Vegetation signals (Satellite)
        avg_ndvi = satellite.ndvi_mean
        # Stability is high if standard deviation is low relative to mean
        ndvi_stability = 1.0 - (satellite.ndvi_std / max(avg_ndvi, 0.1))
        moisture_index = satellite.ndwi_mean

        # 2. Climatic Suitability (Weather)
        # Scoring logic: 20-30°C is optimal range for most crops
        forecast_temps = weather.forecast_temp_max
        if forecast_temps:
            avg_temp = sum(forecast_temps) / len(forecast_temps)
            temp_suitability = 1.0 - min(abs(avg_temp - 25) / 15.0, 1.0)
        else:
            temp_suitability = 0.5

        forecast_rain = weather.forecast_rainfall
        if forecast_rain:
            total_precip = sum(forecast_rain)
            # 50mm/week is a healthy baseline for suitability scoring
            precip_suitability = min(total_precip / 50.0, 1.0)
        else:
            precip_suitability = 0.5
        
        # 3. Soil Health
        ph = soil.get("ph_level", 6.5) if soil else 6.5
        om = soil.get("organic_matter_pct", 2.0) if soil else 2.0
        
        # 4. Pest Pressure (Historical)
        pest_pressure = 0.0
        dominant_pests = []
        if pest_history:
            high_severity_count = sum(1 for p in pest_history if p.get("severity", 1) >= 4)
            # Higher pressure if multiple high-severity events in history
            pest_pressure = min(high_severity_count / 5.0, 1.0)
            dominant_pests = list({p.get("pest_name") for p in pest_history if p.get("pest_name")})
            dominant_pests = dominant_pests[:3]

        # 5. Composite Score Calculation
        # Weights for the diverse factors
        weights = {
            "ndvi": 0.35,
            "climate": 0.25,
            "soil": 0.20,
            "pest": 0.20
        }
        
        # Normalise factors to 0-1
        om_factor = min(om / 5.0, 1.0)
        climate_factor = (0.5 * temp_suitability + 0.5 * precip_suitability)
        pest_factor = 1.0 - pest_pressure
        
        score = (
            weights["ndvi"] * max(avg_ndvi, 0.0) +
            weights["climate"] * climate_factor +
            weights["soil"] * om_factor +
            weights["pest"] * pest_factor
        )

        log.debug("Field capability score for %s: %.2f", farm_id, score)

        return FieldCapabilityProfile(
            farm_id=farm_id,
            timestamp=datetime.utcnow(),
            avg_ndvi=float(avg_ndvi),
            ndvi_stability=float(max(ndvi_stability, 0.0)),
            moisture_index=float(moisture_index),
            temp_suitability=float(temp_suitability),
            precip_suitability=float(precip_suitability),
            soil_moisture_index=0.5, # Default / placeholder
            ph_level=float(ph),
            organic_matter=float(om),
            historical_pest_pressure=float(pest_pressure),
            dominant_pest_types=dominant_pests,
            overall_capability_score=float(min(max(score, 0.0), 1.0))
        )
