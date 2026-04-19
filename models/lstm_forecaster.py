from __future__ import annotations

import logging
import os
import yaml
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from .schemas import LSTMPrediction, TrainingResult, EvalResult

log = logging.getLogger(__name__)

class CropLSTM(nn.Module):
    """Stacked LSTM model for non-linear agricultural time-series forecasting."""
    def __init__(
        self,
        input_size: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        output_size: int = 1,
        dropout: float = 0.2
    ) -> None:
        super().__init__()
        self.batch_norm = nn.BatchNorm1d(input_size)
        self.lstm = nn.LSTM(
            input_size, 
            hidden_size, 
            num_layers, 
            batch_first=True, 
            dropout=dropout if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: [batch, sequence_len, input_size]
        # Reshape for batch_norm: [batch * seq_len, input_size]
        b, s, f = x.shape
        x = x.view(-1, f)
        x = self.batch_norm(x)
        x = x.view(b, s, f)
        
        out, _ = self.lstm(x)
        # Use only the last timestep hidden state
        out = out[:, -1, :]
        out = self.fc(self.dropout(out))
        return out

class LSTMForecaster:
    """Orchestrator for training and inference of the CropLSTM model."""

    def __init__(
        self,
        sequence_len: int = 30,
        forecast_horizon: int = 7,
        feature_cols: Optional[List[str]] = None,
        model_path: str = "configs/lstm_model.pt",
        config_path: str = "configs/lstm_config.yaml"
    ) -> None:
        self.sequence_len = sequence_len
        self.forecast_horizon = forecast_horizon
        self.model_path = model_path
        self.feature_cols = feature_cols or [
            "soil_moisture", "ndvi_mean", "temperature", "humidity", 
            "rainfall", "gdd", "drought_index", "lag_1d", "lag_7d"
        ]
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
                "hidden_size": 64,
                "num_layers": 2,
                "dropout": 0.2,
                "patience": 10,
                "model_version": "1.0.0"
            }
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

    def prepare_sequences(
        self,
        df: pd.DataFrame,
        target_col: str = "soil_moisture"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Creates sliding window sequences for LSTM training."""
        # Ensure only relevant columns are used
        data = df[self.feature_cols].values
        target = df[target_col].values
        
        X, y = [], []
        for i in range(len(data) - self.sequence_len):
            X.append(data[i:i + self.sequence_len])
            y.append(target[i + self.sequence_len])
            
        return np.array(X), np.array(y).reshape(-1, 1)

    def train(
        self,
        aligned_df: pd.DataFrame,
        target_col: str = "soil_moisture"
    ) -> TrainingResult:
        """Trains the LSTM model with early stopping."""
        df = aligned_df.ffill().bfill()
        X, y = self.prepare_sequences(df, target_col)
        
        # Train/Val split (temporal)
        split_idx = int(0.8 * len(X))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        train_ds = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
        val_ds = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val))
        
        train_loader = DataLoader(train_ds, batch_size=self.config["batch_size"], shuffle=False)
        val_loader = DataLoader(val_ds, batch_size=self.config["batch_size"], shuffle=False)
        
        self.model = CropLSTM(
            input_size=len(self.feature_cols),
            hidden_size=self.config["hidden_size"],
            num_layers=self.config["num_layers"],
            dropout=self.config["dropout"]
        ).to(self.device)
        
        optimizer = optim.Adam(self.model.parameters(), lr=self.config["learning_rate"])
        criterion = nn.MSELoss()
        
        train_hist, val_hist = [], []
        best_val_loss = float("inf")
        patience_counter = 0
        best_epoch = 0
        
        for epoch in range(self.config["epochs"]):
            self.model.train()
            total_train_loss = 0
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                optimizer.zero_grad()
                pred = self.model(batch_X)
                loss = criterion(pred, batch_y)
                loss.backward()
                optimizer.step()
                total_train_loss += loss.item()
            
            avg_train_loss = total_train_loss / len(train_loader)
            train_hist.append(avg_train_loss)
            
            self.model.eval()
            total_val_loss = 0
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                    pred = self.model(batch_X)
                    loss = criterion(pred, batch_y)
                    total_val_loss += loss.item()
            
            avg_val_loss = total_val_loss / len(val_loader)
            val_hist.append(avg_val_loss)
            
            if (epoch + 1) % 5 == 0:
                log.info(f"Epoch {epoch+1}/{self.config['epochs']} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")
            
            # Early Stopping
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                best_epoch = epoch
                patience_counter = 0
                os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
                torch.save(self.model.state_dict(), self.model_path)
            else:
                patience_counter += 1
                if patience_counter >= self.config["patience"]:
                    log.info(f"Early stopping at epoch {epoch+1}")
                    break
        
        return TrainingResult(
            train_loss_history=train_hist,
            val_loss_history=val_hist,
            best_epoch=best_epoch,
            best_val_loss=best_val_loss
        )
        # Save rmse estimate (sqrt of best val_loss) to config for future use
        import yaml as _yaml
        rmse_est = float(best_val_loss ** 0.5)
        try:
            cfg_path = self.model_path.replace(".pt", "_metrics.yaml")
            with open(cfg_path, "w") as _f:
                _yaml.dump({"rmse_estimate": rmse_est, "best_epoch": best_epoch}, _f)
        except Exception:
            pass

    def predict(
        self,
        recent_df: pd.DataFrame,
        target_col: str = "soil_moisture"
    ) -> LSTMPrediction:
        """Performs recursive multi-step forecasting."""
        if self.model is None:
            self.model = CropLSTM(input_size=len(self.feature_cols)).to(self.device)
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
        
        self.model.eval()
        df = recent_df.ffill().bfill()
        
        # Get last sequence
        last_seq = df[self.feature_cols].values[-self.sequence_len:]
        curr_X = torch.FloatTensor(last_seq).unsqueeze(0).to(self.device)
        
        predictions = []
        with torch.no_grad():
            for _ in range(self.forecast_horizon):
                pred = self.model(curr_X)
                pred_val = pred.item()
                predictions.append(pred_val)
                
                # Recursive update: push prediction into seq, drop oldest
                # Assuming target_col is the first column in feature_cols for simplicity
                # Real implementation should find index of target_col
                target_idx = self.feature_cols.index(target_col)
                new_row = curr_X[:, -1, :].clone()
                new_row[0, target_idx] = pred_val
                
                curr_X = torch.cat([curr_X[:, 1:, :], new_row.unsqueeze(1)], dim=1)
        
        last_date = pd.to_datetime(df.index[-1])
        prediction_dates = [last_date + timedelta(days=i+1) for i in range(self.forecast_horizon)]
        
        # Load persisted rmse_estimate if available
        rmse_est = self.config.get("rmse_estimate", 0.0)
        metrics_path = self.model_path.replace(".pt", "_metrics.yaml")
        if os.path.exists(metrics_path):
            import yaml as _yaml
            try:
                with open(metrics_path, "r") as _f:
                    _m = _yaml.safe_load(_f)
                    rmse_est = float(_m.get("rmse_estimate", 0.0))
            except Exception:
                pass
        
        return LSTMPrediction(
            predictions=predictions,
            prediction_dates=prediction_dates,
            rmse_estimate=rmse_est,
            model_version=self.config.get("model_version", "1.0.0")
        )

    def evaluate(
        self,
        test_df: pd.DataFrame,
        target_col: str = "soil_moisture"
    ) -> EvalResult:
        """Computes RMSE, MAE, MAPE, and R2 on a test set."""
        X, y_true = self.prepare_sequences(test_df, target_col)
        self.model.eval()
        with torch.no_grad():
            y_pred = self.model(torch.FloatTensor(X).to(self.device)).cpu().numpy()
            
        rmse = np.sqrt(np.mean((y_true - y_pred)**2))
        mae = np.mean(np.abs(y_true - y_pred))
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
        
        ss_res = np.sum((y_true - y_pred)**2)
        ss_tot = np.sum((y_true - np.mean(y_true))**2)
        r2 = 1 - (ss_res / ss_tot)
        
        log.info(f"Evaluation: RMSE={rmse:.4f}, MAE={mae:.4f}, R2={r2:.4f}")
        return EvalResult(rmse=float(rmse), mae=float(mae), mape=float(mape), r_squared=float(r2))

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.INFO)
    dummy_data = pd.DataFrame(
        np.random.rand(100, 9), 
        columns=["soil_moisture", "ndvi_mean", "temperature", "humidity", "rainfall", "gdd", "drought_index", "lag_1d", "lag_7d"]
    )
    dummy_data.index = pd.date_range("2024-01-01", periods=100)
    
    forecaster = LSTMForecaster(sequence_len=10)
    res = forecaster.train(dummy_data)
    print(f"Best Val Loss: {res.best_val_loss:.4f}")
    
    pred = forecaster.predict(dummy_data.tail(10))
    print(f"Predictions: {pred.predictions}")
