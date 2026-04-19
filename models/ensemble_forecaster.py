from __future__ import annotations

import logging
import os
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Optional

from .schemas import IrrigationSchedule, IrrigationDay, YieldForecast, LSTMPrediction
from preprocessing.schemas import FeatureVector
from .prophet_forecaster import ProphetForecaster
from .lstm_forecaster import LSTMForecaster

log = logging.getLogger(__name__)

class EnsembleForecaster:
    """Combines statistical and deep learning forecasts with dynamic weighting."""

    def __init__(
        self,
        prophet: ProphetForecaster,
        lstm: LSTMForecaster,
        prophet_weight: float = 0.5,
        lstm_weight: float = 0.5
    ) -> None:
        self.prophet = prophet
        self.lstm = lstm
        self.prophet_weight = prophet_weight
        self.lstm_weight = lstm_weight

    def blend_irrigation_forecast(
        self,
        prophet_schedule: IrrigationSchedule,
        lstm_prediction: LSTMPrediction,
        feature_vector: FeatureVector
    ) -> IrrigationSchedule:
        """Blends Prophet and LSTM moisture forecasts for a final 7-day schedule."""
        
        # Dynamic weight adjustment
        p_weight = self.prophet_weight
        l_weight = self.lstm_weight
        
        if feature_vector.drought_index > 0.7:
            l_weight += 0.2
            log.info("Drought detected: Increasing LSTM weight for non-linear patterns.")
            
        if feature_vector.rain_probability_7d > 0.6:
            p_weight += 0.2
            log.info("High rain probability: Increasing Prophet weight for seasonal alignment.")
            
        # Normalize weights
        total_w = p_weight + l_weight
        p_weight /= total_w
        l_weight /= total_w
        
        blended_days = []
        total_volume = 0.0
        critical_date = None
        field_area = 5000.0
        
        for i, p_day in enumerate(prophet_schedule.schedule):
            l_val = lstm_prediction.predictions[i]
            blended_moisture = (p_day.predicted_soil_moisture * p_weight) + (l_val * l_weight)
            
            # Recalculate irrigation needed (same logic: moisture < 30%)
            # We'll use the prophet_schedule's day as a template but update moisture
            # Assuming rainfall info is consistent between models
            needed = blended_moisture < 30.0 and p_day.recommended_volume_liters > 0 # Simple proxy
            
            if needed and critical_date is None:
                critical_date = p_day.date
                
            # Volume adjustment
            deficit_mm = max(0.0, 40.0 - blended_moisture)
            volume = (deficit_mm * field_area * 1.2) / 1000.0 * 1000.0 # liters
            
            if needed:
                total_volume += volume
                
            blended_days.append(IrrigationDay(
                date=p_day.date,
                predicted_soil_moisture=blended_moisture,
                irrigation_needed=needed,
                recommended_volume_liters=volume if needed else 0.0,
                confidence=(p_day.confidence * p_weight) + (0.85 * l_weight) # LSTM constant proxy
            ))
            
        return IrrigationSchedule(
            farm_id=prophet_schedule.farm_id,
            schedule=blended_days,
            total_water_needed_liters=total_volume,
            next_critical_date=critical_date,
            confidence=float(np.mean([d.confidence for d in blended_days])),
            model_used="ensemble"
        )

    def blend_yield_forecast(
        self,
        prophet_yield: YieldForecast,
        lstm_yield: LSTMPrediction,
        feature_vector: FeatureVector
    ) -> YieldForecast:
        """Merges Prophet yield forecast with LSTM's most recent projection."""
        
        # Weighted average of Prophet predicted_yield and LSTM's last step
        lstm_val = lstm_yield.predictions[-1]
        blended_yield = (prophet_yield.predicted_yield * self.prophet_weight) + (lstm_val * self.lstm_weight)
        
        # Propagate uncertainty: widen CI if models disagree by > 15%
        disagreement = abs(prophet_yield.predicted_yield - lstm_val) / prophet_yield.predicted_yield
        ci_factor = 1.0
        if disagreement > 0.15:
            ci_factor = 1.5
            log.warning(f"Models disagree by {disagreement:.1%}: Widening confidence intervals.")
            
        return YieldForecast(
            farm_id=prophet_yield.farm_id,
            crop_type=prophet_yield.crop_type,
            predicted_yield=blended_yield,
            yield_lower=prophet_yield.yield_lower * ci_factor,
            yield_upper=prophet_yield.yield_upper * ci_factor,
            forecast_date=prophet_yield.forecast_date,
            confidence_interval=(prophet_yield.yield_upper - prophet_yield.yield_lower) * ci_factor,
            trend_component=prophet_yield.trend_component,
            seasonal_component=prophet_yield.seasonal_component,
            key_drivers=prophet_yield.key_drivers,
            model_used="ensemble"
        )

    def select_model(
        self,
        aligned_df: pd.DataFrame
    ) -> str:
        """Decision logic for which model(s) to use based on data volume."""
        n_rows = len(aligned_df)
        lstm_exists = os.path.exists(self.lstm.model_path)
        
        if n_rows < 30:
            log.info(f"Data volume too low ({n_rows} rows) for LSTM. Using Prophet.")
            return "prophet"
            
        if not lstm_exists:
            log.info("LSTM model file missing. Falling back to Prophet.")
            return "prophet"
            
        log.info(f"Data volume sufficient ({n_rows} rows) and models present. Using ensemble.")
        return "ensemble"

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.INFO)
    p = ProphetForecaster()
    l = LSTMForecaster()
    e = EnsembleForecaster(p, l)
    
    df = pd.DataFrame(np.random.rand(50, 10))
    print(f"Selected Model: {e.select_model(df)}")
