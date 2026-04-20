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

from .schemas import PriceForecast

log = logging.getLogger(__name__)


class PriceForecaster:
    """Prophet-based forecaster for market commodity prices."""

    def __init__(self, config_path: str = "configs/prophet_config.yaml") -> None:
        """Initializes the forecaster with custom configuration."""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            log.warning(f"Config {config_path} not found. Using defaults.")
            self.config = {
                "seasonality_mode": "multiplicative",
                "changepoint_prior_scale": 0.05,
                "holidays_prior_scale": 10.0,
                "n_changepoints": 25,
            }
        
        # Indian public holidays (2024–2026) - relevant for market closures
        holidays_data = [
            {"holiday": "Diwali", "ds": "2024-10-31", "lower_window": -2, "upper_window": 1},
            {"holiday": "Diwali", "ds": "2025-10-21", "lower_window": -2, "upper_window": 1},
            {"holiday": "Diwali", "ds": "2026-11-08", "lower_window": -2, "upper_window": 1},
            {"holiday": "Holi", "ds": "2024-03-25", "lower_window": 0, "upper_window": 1},
            {"holiday": "Holi", "ds": "2025-03-14", "lower_window": 0, "upper_window": 1},
            {"holiday": "Holi", "ds": "2026-03-03", "lower_window": 0, "upper_window": 1},
            {"holiday": "Eid", "ds": "2024-04-10", "lower_window": 0, "upper_window": 1},
            {"holiday": "Eid", "ds": "2025-03-31", "lower_window": 0, "upper_window": 1},
        ]
        self.holidays = pd.DataFrame(holidays_data)
        self.holidays["ds"] = pd.to_datetime(self.holidays["ds"])

    def _init_model(self) -> Prophet:
        """Helper to create a Prophet model."""
        return Prophet(
            seasonality_mode=self.config.get("seasonality_mode", "multiplicative"),
            changepoint_prior_scale=self.config.get("changepoint_prior_scale", 0.05),
            holidays_prior_scale=self.config.get("holidays_prior_scale", 10.0),
            n_changepoints=self.config.get("n_changepoints", 25),
            holidays=self.holidays,
        )

    def fit(
        self,
        price_df: pd.DataFrame,
        state: str,
        district: str,
        commodity: str
    ) -> None:
        """
        Fits a price forecasting model for a specific commodity in a region.
        price_df must have columns: ds (date), y (modal_price)
        """
        if len(price_df) < 5:
            log.warning("Insufficient price data for %s in %s. Model reliability will be low.", commodity, district)
            
        model = self._init_model()
        model.fit(price_df)
        
        # Save model with a unique name per region/commodity
        os.makedirs("configs/models", exist_ok=True)
        model_path = f"configs/models/price_{state}_{district}_{commodity}.pkl".lower().replace(" ", "_")
        joblib.dump(model, model_path)
        log.info("Price model for %s in %s fitted and saved to %s", commodity, district, model_path)

    def forecast(
        self,
        state: str,
        district: str,
        commodity: str,
        periods: int = 30
    ) -> PriceForecast:
        """Forecasts future prices for the given commodity and region."""
        model_path = f"configs/models/price_{state}_{district}_{commodity}.pkl".lower().replace(" ", "_")
        if not os.path.exists(model_path):
            log.error("Model not found for %s in %s at %s. Falling back to simple trend.", commodity, district, model_path)
            # In a real system, we'd have a global fallback model
            return self._calculate_fallback_forecast(state, district, commodity)

        model = joblib.load(model_path)
        future = model.make_future_dataframe(periods=periods, freq="D")
        forecast = model.predict(future)
        
        # Take the prediction for the end of the period
        res = forecast.iloc[-1]
        
        return PriceForecast(
            state=state,
            district=district,
            commodity=commodity,
            predicted_modal_price=float(res["yhat"]),
            price_lower=float(res["yhat_lower"]),
            price_upper=float(res["yhat_upper"]),
            forecast_date=res["ds"].to_pydatetime(),
            confidence_interval=float(res["yhat_upper"] - res["yhat_lower"]),
            trend_component=float(res["trend"]),
            seasonal_component=float(res.get("multiplicative_terms", 0.0)),
            model_used="prophet"
        )

    def _calculate_fallback_forecast(
        self, state: str, district: str, commodity: str
    ) -> PriceForecast:
        """Minimal fallback for missing models."""
        return PriceForecast(
            state=state,
            district=district,
            commodity=commodity,
            predicted_modal_price=0.0,
            price_lower=0.0,
            price_upper=0.0,
            forecast_date=datetime.utcnow(),
            confidence_interval=0.0,
            trend_component=0.0,
            seasonal_component=0.0,
            model_used="fallback"
        )


if __name__ == "__main__":
    # Smoke test
    logging.basicConfig(level=logging.INFO)
    forecaster = PriceForecaster()
    
    # Synthetic price data
    dates = pd.date_range(start="2023-01-01", periods=100, freq="W")
    prices = 2000 + np.cumsum(np.random.normal(10, 50, 100))
    df = pd.DataFrame({"ds": dates, "y": prices})
    
    forecaster.fit(df, "Punjab", "Ludhiana", "Wheat")
    pf = forecaster.forecast("Punjab", "Ludhiana", "Wheat")
    print(f"Predicted Price: {pf.predicted_modal_price:.2f} INR/quintal")
