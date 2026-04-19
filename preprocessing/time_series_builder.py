from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd

from .schemas import SensorReading

log = logging.getLogger(__name__)

def build_ndvi_timeseries(
    ndvi_history: List[Tuple[datetime, float, float]],  # (date, mean, std)
    freq: str = "5D"
) -> pd.DataFrame:
    """Builds NDVI timeseries with resampling and interpolation."""
    if not ndvi_history:
        return pd.DataFrame(columns=["ds", "y", "y_lower", "y_upper", "stale"])
    
    df = pd.DataFrame(ndvi_history, columns=["ds", "y", "std"])
    df["ds"] = pd.to_datetime(df["ds"])
    df = df.set_index("ds").sort_index()
    
    # Resample and interpolate
    resampled = df.resample(freq).mean()
    resampled["y"] = resampled["y"].interpolate(method="linear")
    resampled["std"] = resampled["std"].interpolate(method="linear")
    
    # Add bounds
    resampled["y_lower"] = resampled["y"] - resampled["std"]
    resampled["y_upper"] = resampled["y"] + resampled["std"]
    
    # Flag stale observations (if gap > freq)
    resampled["stale"] = df.resample(freq).asfreq()["y"].isna()
    
    return resampled.reset_index()

def build_yield_timeseries(
    yield_history: List[Tuple[str, float]],  # (season_label, yield)
    season_labels: List[str]
) -> pd.DataFrame:
    """Builds season-indexed yield timeseries with lag features."""
    if not yield_history:
        return pd.DataFrame(columns=["ds", "y", "season", "crop_type"])
        
    df = pd.DataFrame(yield_history, columns=["season_label", "y"])
    
    # Infer ds from season label (e.g., "Kharif 2023")
    def _parse_season_date(label: str) -> datetime:
        parts = label.split()
        season = parts[0].lower()
        year = int(parts[1])
        # Start dates: Kharif: June, Rabi: Nov, Zaid: April
        month = {"kharif": 6, "rabi": 11, "zaid": 4}.get(season, 1)
        return datetime(year, month, 1)
        
    df["ds"] = df["season_label"].apply(_parse_season_date)
    df = df.sort_values("ds")
    
    # Normalize y to z-scores
    mean_y = df["y"].mean()
    std_y = df["y"].std()
    if std_y > 0:
        df["y"] = (df["y"] - mean_y) / std_y
    
    # Add lag features
    df["y_lag1"] = df["y"].shift(1)
    df["y_lag2"] = df["y"].shift(2)
    
    # Add rolling mean
    df["rolling_mean_3"] = df["y"].rolling(window=3, min_periods=1).mean()
    
    return df

def build_sensor_timeseries(
    sensor_history: List[SensorReading],
    target_col: str = "soil_moisture"
) -> pd.DataFrame:
    """Builds daily sensor timeseries with rolling and lag features."""
    if not sensor_history:
        return pd.DataFrame()
        
    data = []
    for r in sensor_history:
        data.append({
            "ds": r.timestamp,
            "soil_moisture": r.soil_moisture,
            "temperature": r.air_temperature,
            "humidity": r.humidity,
            "rainfall": r.rainfall_mm
        })
        
    df = pd.DataFrame(data)
    df["ds"] = pd.to_datetime(df["ds"]).dt.floor("D")
    df = df.set_index("ds").sort_index()
    
    # Resample to daily frequency
    df = df.resample("D").mean()
    
    # Fill missing
    df = df.ffill().bfill()
    
    # Time features
    df["day_of_week"] = df.index.dayofweek
    df["day_of_year"] = df.index.dayofyear
    df["week_of_year"] = df.index.isocalendar().week.astype(int)
    
    # Rolling features
    df["3d_rolling_mean"] = df[target_col].rolling(window=3, min_periods=1).mean()
    df["7d_rolling_mean"] = df[target_col].rolling(window=7, min_periods=1).mean()
    df["7d_rolling_std"] = df[target_col].rolling(window=7, min_periods=1).std().fillna(0)
    
    # Lag features
    df["lag_1d"] = df[target_col].shift(1)
    df["lag_3d"] = df[target_col].shift(3)
    df["lag_7d"] = df[target_col].shift(7)
    
    return df.reset_index().fillna(0)

def align_multimodal_timeseries(
    ndvi_df: pd.DataFrame,
    sensor_df: pd.DataFrame,
    weather_df: pd.DataFrame # Forecasted or historical
) -> pd.DataFrame:
    """Merges NDVI, sensor, and weather data onto a daily UTC index."""
    # Ensure ds is datetime and set as index
    for df in [ndvi_df, sensor_df, weather_df]:
        if not df.empty:
            df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None).dt.tz_localize("UTC")
            
    ndvi_df = ndvi_df.set_index("ds") if not ndvi_df.empty else pd.DataFrame()
    sensor_df = sensor_df.set_index("ds") if not sensor_df.empty else pd.DataFrame()
    weather_df = weather_df.set_index("ds") if not weather_df.empty else pd.DataFrame()
    
    # Outer join
    aligned = sensor_df.join([ndvi_df, weather_df], how="outer")
    
    # Forward-fill satellite data (5-day updates) to daily
    if "y" in aligned.columns:
        aligned["y"] = aligned["y"].ffill()
        if "y_lower" in aligned.columns:
            aligned["y_lower"] = aligned["y_lower"].ffill()
            aligned["y_upper"] = aligned["y_upper"].ffill()
            
    log.info(f"Aligned multimodal timeseries: shape={aligned.shape}, range={aligned.index.min()} to {aligned.index.max()}")
    
    return aligned.sort_index()

if __name__ == "__main__":
    # Test block
    dates = [datetime.utcnow() - timedelta(days=i*5) for i in range(10)]
    ndvi = [(d, 0.5, 0.05) for d in dates]
    df = build_ndvi_timeseries(ndvi)
    print(df.head())
