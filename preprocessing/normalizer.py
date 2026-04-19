from __future__ import annotations

import logging
import os
import joblib
from typing import List

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)

def fit_and_save_scaler(
    df: pd.DataFrame,
    feature_cols: List[str],
    scaler_path: str = "configs/scaler.pkl"
) -> StandardScaler:
    """Fits a StandardScaler and persists it to disk."""
    if df.empty:
        raise ValueError("Cannot fit scaler on empty DataFrame")
        
    scaler = StandardScaler()
    scaler.fit(df[feature_cols])
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(scaler_path), exist_ok=True)
    joblib.dump(scaler, scaler_path)
    
    for i, col in enumerate(feature_cols):
        log.debug(f"Scaler Feature: {col} | Mean: {scaler.mean_[i]:.4f} | Std: {scaler.scale_[i]:.4f}")
        
    log.info(f"Fitted and saved scaler to {scaler_path}")
    return scaler

def transform_features(
    df: pd.DataFrame,
    feature_cols: List[str],
    scaler_path: str = "configs/scaler.pkl"
) -> np.ndarray:
    """Transforms features using a persisted scaler."""
    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"Scaler not found at {scaler_path}. Please run fit_and_save_scaler first.")
        
    scaler = joblib.load(scaler_path)
    scaled_data = scaler.transform(df[feature_cols])
    
    return scaled_data

def encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encodes agricultural categorical variables."""
    cols_to_encode = ["crop_type", "season", "vegetation_zone", "growth_stage"]
    # Filter only existing columns
    existing_cols = [c for c in cols_to_encode if c in df.columns]
    
    if not existing_cols:
        return df
        
    df_encoded = pd.get_dummies(df, columns=existing_cols, prefix=existing_cols)
    log.info(f"Encoded categoricals {existing_cols}. New shape: {df_encoded.shape}")
    
    return df_encoded

if __name__ == "__main__":
    # Test block
    data = pd.DataFrame({
        "temp": [20, 25, 30],
        "moisture": [0.3, 0.4, 0.5],
        "crop_type": ["wheat", "corn", "wheat"]
    })
    scaler = fit_and_save_scaler(data, ["temp", "moisture"], "scratch/test_scaler.pkl")
    scaled = transform_features(data, ["temp", "moisture"], "scratch/test_scaler.pkl")
    print(scaled)
    encoded = encode_categoricals(data)
    print(encoded.columns)
