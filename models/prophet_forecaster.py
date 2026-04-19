from __future__ import annotations

import logging
import os
import yaml
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional
from prophet import Prophet

from .schemas import YieldForecast, IrrigationSchedule, IrrigationDay
from preprocessing.schemas import FeatureVector

log = logging.getLogger(__name__)

class ProphetForecaster:
    """Prophet-based forecaster for seasonal yield and irrigation scheduling."""

    def __init__(self, config_path: str = "configs/prophet_config.yaml") -> None:
        """Initializes the forecaster with custom Indian seasons and holidays."""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            log.warning(f"Config {config_path} not found. Using defaults.")
            self.config = {
                "seasonality_mode": "multiplicative",
                "changepoint_prior_scale": 0.05,
                "holidays_prior_scale": 10.0,
                "n_changepoints": 25
            }
        
        # Indian public holidays (2024–2026)
        holidays_data = [
            {"holiday": "Diwali", "ds": "2024-10-31", "lower_window": -2, "upper_window": 1},
            {"holiday": "Diwali", "ds": "2025-10-21", "lower_window": -2, "upper_window": 1},
            {"holiday": "Diwali", "ds": "2026-11-08", "lower_window": -2, "upper_window": 1},
            {"holiday": "Holi", "ds": "2024-03-25", "lower_window": 0, "upper_window": 1},
            {"holiday": "Holi", "ds": "2025-03-14", "lower_window": 0, "upper_window": 1},
            {"holiday": "Holi", "ds": "2026-03-03", "lower_window": 0, "upper_window": 1},
            {"holiday": "Pongal", "ds": "2024-01-15", "lower_window": 0, "upper_window": 1},
            {"holiday": "Pongal", "ds": "2025-01-14", "lower_window": 0, "upper_window": 1},
            {"holiday": "Pongal", "ds": "2026-01-15", "lower_window": 0, "upper_window": 1},
            {"holiday": "Baisakhi", "ds": "2024-04-13", "lower_window": 0, "upper_window": 0},
            {"holiday": "Baisakhi", "ds": "2025-04-14", "lower_window": 0, "upper_window": 0},
            {"holiday": "Baisakhi", "ds": "2026-04-14", "lower_window": 0, "upper_window": 0},
            {"holiday": "Onam", "ds": "2024-09-15", "lower_window": -3, "upper_window": 1},
            {"holiday": "Onam", "ds": "2025-09-04", "lower_window": -3, "upper_window": 1},
            {"holiday": "Onam", "ds": "2026-08-27", "lower_window": -3, "upper_window": 1},
        ]
        self.holidays = pd.DataFrame(holidays_data)
        self.holidays["ds"] = pd.to_datetime(self.holidays["ds"])

    def _init_model(self) -> Prophet:
        """Helper to create a Prophet model with custom seasons."""
        model = Prophet(
            seasonality_mode=self.config.get("seasonality_mode", "multiplicative"),
            changepoint_prior_scale=self.config.get("changepoint_prior_scale", 0.05),
            holidays_prior_scale=self.config.get("holidays_prior_scale", 10.0),
            n_changepoints=self.config.get("n_changepoints", 25),
            holidays=self.holidays
        )
        # Kharif: June–October
        model.add_seasonality(name="kharif", period=365.25, fourier_order=5, condition_name="is_kharif")
        # Rabi: November–March
        model.add_seasonality(name="rabi", period=365.25, fourier_order=5, condition_name="is_rabi")
        # Zaid: April–May
        model.add_seasonality(name="zaid", period=365.25, fourier_order=5, condition_name="is_zaid")
        return model

    def _add_season_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adds binary flags for Indian agricultural seasons."""
        df["month"] = pd.to_datetime(df["ds"]).dt.month
        df["is_kharif"] = df["month"].between(6, 10)
        df["is_rabi"] = (df["month"] >= 11) | (df["month"] <= 3)
        df["is_zaid"] = df["month"].between(4, 5)
        return df

    def fit_yield_model(
        self,
        yield_df: pd.DataFrame,
        regressors: List[str] = ["ndvi_mean", "rainfall_7d", "gdd"]
    ) -> None:
        """Fits the seasonal yield model with external regressors."""
        if len(yield_df) < 2:
            log.warning("Insufficient yield data (< 2 seasons). Model will have low confidence.")
            
        df = self._add_season_flags(yield_df.copy())
        model = self._init_model()
        
        for reg in regressors:
            if reg in df.columns:
                model.add_regressor(reg)
                
        model.fit(df)
        os.makedirs("configs", exist_ok=True)
        joblib.dump(model, "configs/prophet_yield.pkl")
        log.info(f"Yield model fitted on {len(df)} seasons. Changepoints: {len(model.changepoints)}")

    def fit_irrigation_model(
        self,
        sensor_df: pd.DataFrame,
        weather_df: pd.DataFrame
    ) -> None:
        """Fits the soil moisture model for daily irrigation scheduling."""
        # Merge sensor and weather data on ds
        # Use suffixes to handle overlapping columns
        df = pd.merge(sensor_df, weather_df, on="ds", how="outer", suffixes=("", "_w")).sort_values("ds")
        df = df.ffill().bfill()
        df = self._add_season_flags(df)
        
        # Ensure y column exists
        if "soil_moisture" in df.columns:
            df = df.rename(columns={"soil_moisture": "y"})
        elif "y" not in df.columns:
            raise ValueError("Input dataframes must contain 'soil_moisture' or 'y' column.")
        
        model = self._init_model()
        regressors = ["rainfall", "evapotranspiration_est", "temperature"]
        for reg in regressors:
            if reg in df.columns:
                model.add_regressor(reg)
                
        model.fit(df)
        joblib.dump(model, "configs/prophet_irrigation.pkl")
        log.info(f"Irrigation model fitted on {len(df)} days.")

    def forecast_yield(
        self,
        farm_id: str,
        crop_type: str,
        periods: int = 1,
        future_regressors: pd.DataFrame = None
    ) -> YieldForecast:
        """Predicts future yield using the fitted model."""
        if not os.path.exists("configs/prophet_yield.pkl"):
            raise FileNotFoundError("Yield model not found. Run fit_yield_model first.")
            
        model = joblib.load("configs/prophet_yield.pkl")
        future = model.make_future_dataframe(periods=periods, freq="ME") # seasonal, month-end
        future = self._add_season_flags(future)
        
        # 1. Merge all historical regressors
        for reg in model.extra_regressors:
            if reg in model.history.columns:
                future = pd.merge(future, model.history[["ds", reg]], on="ds", how="left")
        
        # 2. Merge future regressors if provided
        if future_regressors is not None:
            for reg in future_regressors.columns:
                if reg == "ds": continue
                if reg in future.columns:
                    # Update NaNs in existing columns with future values
                    future = future.set_index("ds")
                    future[reg] = future[reg].fillna(future_regressors.set_index("ds")[reg])
                    future = future.reset_index()
                else:
                    future = pd.merge(future, future_regressors[["ds", reg]], on="ds", how="left")
        
        # 3. Fill any gaps and ensure all columns exist
        for reg in model.extra_regressors:
            if reg not in future.columns:
                future[reg] = 0.0
                    
        future = future.ffill().bfill()
        forecast = model.predict(future)
        res = forecast.iloc[-1]
        
        # Identify key drivers (simplification: largest regressor absolute values)
        drivers = []
        for col in forecast.columns:
            if col.endswith("_upper") or col.endswith("_lower"): continue
            if col in ["ndvi_mean", "rainfall_7d", "gdd"]:
                drivers.append(col)
        drivers = sorted(drivers, key=lambda x: abs(res[x]), reverse=True)[:2]

        return YieldForecast(
            farm_id=farm_id,
            crop_type=crop_type,
            predicted_yield=float(res["yhat"]),
            yield_lower=float(res["yhat_lower"]),
            yield_upper=float(res["yhat_upper"]),
            forecast_date=res["ds"].to_pydatetime(),
            confidence_interval=float(res["yhat_upper"] - res["yhat_lower"]),
            trend_component=float(res["trend"]),
            seasonal_component=float(res.get("multiplicative_terms", 0.0)),
            key_drivers=drivers,
            model_used="prophet"
        )

    def forecast_irrigation_schedule(
        self,
        farm_id: str,
        days_ahead: int = 7,
        feature_vector: FeatureVector = None,
        future_weather: pd.DataFrame = None
    ) -> IrrigationSchedule:
        """Generates a 7-day irrigation schedule."""
        if not os.path.exists("configs/prophet_irrigation.pkl"):
            raise FileNotFoundError("Irrigation model not found. Run fit_irrigation_model first.")
            
        model = joblib.load("configs/prophet_irrigation.pkl")
        future = model.make_future_dataframe(periods=days_ahead, freq="D")
        future = self._add_season_flags(future)
        
        # 1. Merge history
        for reg in model.extra_regressors:
            if reg in model.history.columns:
                future = pd.merge(future, model.history[["ds", reg]], on="ds", how="left")
                
        # 2. Merge future
        if future_weather is not None:
            for reg in future_weather.columns:
                if reg == "ds": continue
                if reg in future.columns:
                    future = future.set_index("ds")
                    future[reg] = future[reg].fillna(future_weather.set_index("ds")[reg])
                    future = future.reset_index()
                else:
                    future = pd.merge(future, future_weather[["ds", reg]], on="ds", how="left")
        
        # 3. Fallback
        for reg in model.extra_regressors:
            if reg not in future.columns:
                future[reg] = 0.0
        
        future = future.ffill().bfill()
        forecast = model.predict(future).tail(days_ahead)
        
        schedule = []
        critical_date = None
        total_volume = 0.0
        field_area = 5000.0 # m2
        
        # Incorporate feature_vector.irrigation_need_score as weight
        weight = (feature_vector.irrigation_need_score / 10.0) if feature_vector else 1.0
        
        for _, row in forecast.iterrows():
            pred_moisture = float(row["yhat"])
            precip = row.get("rainfall", 0.0)
            
            # Irrigation needed if moisture < 30% AND rainfall < 2mm
            needed = pred_moisture < 30.0 and precip < 2.0
            
            if needed and critical_date is None:
                critical_date = row["ds"].to_pydatetime()
            
            # Estimate volume: deficit_mm * area * 1.2
            # Deficit approx: (40 - moisture) / 100 * area
            deficit_mm = max(0.0, 40.0 - pred_moisture) * weight
            volume = deficit_mm * field_area * 1.2 / 1000.0 * 1000.0 # Simplified liter conversion
            
            if needed:
                total_volume += volume
                
            schedule.append(IrrigationDay(
                date=row["ds"].to_pydatetime(),
                predicted_soil_moisture=pred_moisture,
                irrigation_needed=needed,
                recommended_volume_liters=volume if needed else 0.0,
                confidence=float(1.0 - (row["yhat_upper"] - row["yhat_lower"]) / 100.0)
            ))
            
        return IrrigationSchedule(
            farm_id=farm_id,
            schedule=schedule,
            total_water_needed_liters=total_volume,
            next_critical_date=critical_date,
            confidence=float(np.mean([d.confidence for d in schedule])),
            model_used="prophet"
        )

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.INFO)
    forecaster = ProphetForecaster()
    
    # Synthetic yield data
    yield_data = pd.DataFrame({
        "ds": pd.to_datetime(["2021-06-01", "2021-11-01", "2022-06-01", "2022-11-01"]),
        "y": [3000, 3200, 3100, 3300],
        "ndvi_mean": [0.6, 0.55, 0.62, 0.58],
        "rainfall_7d": [50, 10, 45, 12],
        "gdd": [500, 400, 520, 410]
    })
    forecaster.fit_yield_model(yield_data)
    yf = forecaster.forecast_yield("F1", "Wheat")
    print(f"Yield Forecast: {yf.predicted_yield:.2f} kg/ha")
    
    # Synthetic sensor data
    sensor_data = pd.DataFrame({
        "ds": pd.date_range(start="2024-01-01", periods=60, freq="D"),
        "soil_moisture": np.random.uniform(25, 45, 60),
        "temperature": np.random.uniform(20, 35, 60),
        "rainfall": np.random.uniform(0, 10, 60),
        "evapotranspiration_est": np.random.uniform(2, 6, 60)
    })
    forecaster.fit_irrigation_model(sensor_data, sensor_data)
    ir = forecaster.forecast_irrigation_schedule("F1", days_ahead=7)
    print(f"Next Critical Date: {ir.next_critical_date}")
