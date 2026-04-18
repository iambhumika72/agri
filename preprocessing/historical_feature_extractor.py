"""
preprocessing/historical_feature_extractor.py — Derives AI-ready features from
the Historical Database for all three downstream Trace pipeline consumers.

Architecture:
  HistoricalFeatureExtractor
  ├── _forecaster_features()   → Time-Series Forecaster node
  ├── _vision_features()       → Computer Vision (pest risk) node
  ├── _llm_summary()           → Generative LLM (farmer advisory) node
  └── extract_all()            → Single dict with all three feature sets

Design notes:
- Linear regression for soil nutrient trends uses numpy polyfit(degree=1) which
  returns [slope, intercept]. Only the slope is exposed — positive = improving,
  negative = depleting.
- pest_risk_score uses a weighted formula:
    score = Σ(severity_i × affected_area_pct_i) / (N × 5 × 100)
  normalised to [0, 1] so it is directly comparable across farms.
- Irrigation efficiency = actual / recommended. Values > 1 indicate overuse;
  capped at 1.0 for efficiency score (higher = better up to baseline).
- The returned DataFrame always has (farm_id, date) MultiIndex. When a feature
  is scalar (e.g., pest_risk_score), it is broadcast across all date rows for
  that farm so the MultiIndex contract is never broken.
- All None/NaN gracefully propagate — downstream nodes must handle NaN values.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Recommended irrigation water per crop-season (litres / ha)
# ---------------------------------------------------------------------------
CROP_IRRIGATION_BASELINE_LITERS: dict[str, float] = {
    "Wheat":  450_000.0,
    "Rice":   1_200_000.0,
    "Cotton": 700_000.0,
}

# Soil nutrient deficiency thresholds (ppm or %)
SOIL_THRESHOLDS: dict[str, float] = {
    "nitrogen_ppm":    140.0,  # below → low nitrogen
    "phosphorus_ppm":   10.0,  # below → low phosphorus
    "potassium_ppm":   115.0,  # below → low potassium
}


class HistoricalFeatureExtractor:
    """
    Extracts and computes derived features from the Historical Database for
    all three downstream AI consumers in the Trace pipeline.

    Parameters
    ----------
    connector : HistoricalDBConnector
        An open (or context-managed) instance of the DB connector.
    """

    def __init__(self, connector: Any) -> None:
        self._db = connector

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_all(self, farm_id: str) -> dict[str, Any]:
        """
        Run all three feature extraction pipelines for a single farm.

        Returns
        -------
        dict with keys:
            'forecaster_features' : pd.DataFrame  (MultiIndex farm_id × date)
            'vision_features'     : pd.DataFrame  (MultiIndex farm_id × date)
            'llm_summary'         : dict           (flat JSON-ready summary)
        """
        logger.info("extract_all started for farm_id=%s", farm_id)

        forecaster_df = self._forecaster_features(farm_id)
        vision_df = self._vision_features(farm_id)
        llm_dict = self._llm_summary(farm_id)

        logger.info("extract_all completed for farm_id=%s", farm_id)
        return {
            "forecaster_features": forecaster_df,
            "vision_features": vision_df,
            "llm_summary": llm_dict,
        }

    # ------------------------------------------------------------------
    # Feature group 1: Time-Series Forecaster
    # ------------------------------------------------------------------
    def _forecaster_features(self, farm_id: str) -> pd.DataFrame:
        """
        Compute features required by the Time-Series Forecaster node.

        Columns produced:
        - rolling_yield_mean_3yr   : 3-year rolling mean yield (kg/ha)
        - rolling_yield_var_3yr    : 3-year rolling variance  (kg/ha²)
        - pest_outbreak_freq       : count of severity ≥ 3 events in last 3 seasons
        - irrigation_deficit_pct   : (actual - baseline) / baseline × 100
        - soil_n_slope             : linear slope of nitrogen_ppm over last 5 readings
        - soil_p_slope             : linear slope of phosphorus_ppm
        - soil_k_slope             : linear slope of potassium_ppm
        """
        logger.info("_forecaster_features farm_id=%s", farm_id)

        # --- Yield features ---
        # Fetch all crops for this farm (no crop filter)
        yield_df = self._fetch_all_yields(farm_id, years=5)
        if not yield_df.empty:
            yield_df = yield_df.reset_index()
            yield_df.sort_values("harvest_date", inplace=True)
            yield_df["rolling_yield_mean_3yr"] = (
                yield_df["yield_kg_per_hectare"]
                .rolling(window=3, min_periods=1)
                .mean()
            )
            yield_df["rolling_yield_var_3yr"] = (
                yield_df["yield_kg_per_hectare"]
                .rolling(window=3, min_periods=1)
                .var()
                .fillna(0)
            )
            yield_df = yield_df.rename(columns={"harvest_date": "date"})
            yield_df["farm_id"] = farm_id
        else:
            yield_df = pd.DataFrame(
                columns=["farm_id", "date", "rolling_yield_mean_3yr", "rolling_yield_var_3yr"]
            )

        # --- Pest outbreak frequency (severity ≥ 3, last 3 seasons ≈ 3 years) ---
        three_years_ago = date.today() - timedelta(days=3 * 365)
        pest_df = self._db.get_pest_history(farm_id, three_years_ago, date.today())
        if not pest_df.empty:
            pest_df_reset = pest_df.reset_index()
            outbreak_count = int(
                (pest_df_reset["severity"] >= 3).sum()
            )
        else:
            outbreak_count = 0

        # --- Irrigation deficit ---
        irr_deficit = self._compute_irrigation_deficit(farm_id)

        # --- Soil nutrient slopes (last 5 records) ---
        soil_df = self._db.get_soil_trend(farm_id, last_n_records=5)
        soil_slopes = self._compute_soil_slopes(soil_df)

        # --- Assemble into DataFrame ---
        if not yield_df.empty:
            feature_df = yield_df[
                ["farm_id", "date", "rolling_yield_mean_3yr", "rolling_yield_var_3yr"]
            ].copy()
        else:
            feature_df = pd.DataFrame(
                {"farm_id": [farm_id], "date": [pd.Timestamp(date.today())]}
            )

        feature_df["pest_outbreak_freq"] = outbreak_count
        feature_df["irrigation_deficit_pct"] = irr_deficit
        feature_df["soil_n_slope"] = soil_slopes.get("nitrogen_ppm", None)
        feature_df["soil_p_slope"] = soil_slopes.get("phosphorus_ppm", None)
        feature_df["soil_k_slope"] = soil_slopes.get("potassium_ppm", None)

        feature_df["date"] = pd.to_datetime(feature_df["date"])
        feature_df.set_index(["farm_id", "date"], inplace=True)
        return feature_df

    # ------------------------------------------------------------------
    # Feature group 2: Computer Vision node
    # ------------------------------------------------------------------
    def _vision_features(self, farm_id: str) -> pd.DataFrame:
        """
        Produce features used by the Computer Vision node for attention biasing.

        Columns produced:
        - pest_alert_date          : detected_date for severity ≥ 4 events
        - severity                 : outbreak severity at that date
        - ndvi_correlation         : placeholder (filled by satellite module)
        """
        logger.info("_vision_features farm_id=%s", farm_id)

        three_years_ago = date.today() - timedelta(days=3 * 365)
        pest_df = self._db.get_pest_history(farm_id, three_years_ago, date.today())

        if pest_df.empty:
            empty = pd.DataFrame(
                columns=["farm_id", "date", "severity", "ndvi_correlation"]
            )
            empty.set_index(["farm_id", "date"], inplace=True)
            return empty

        pest_reset = pest_df.reset_index()
        # Filter to high-severity (≥ 4) events only
        high_risk = pest_reset[pest_reset["severity"] >= 4][
            ["farm_id", "detected_date", "severity"]
        ].copy()
        high_risk.rename(columns={"detected_date": "date"}, inplace=True)
        high_risk["date"] = pd.to_datetime(high_risk["date"])
        high_risk["ndvi_correlation"] = None  # reserved for satellite module

        high_risk.set_index(["farm_id", "date"], inplace=True)
        return high_risk

    # ------------------------------------------------------------------
    # Feature group 3: Generative LLM node
    # ------------------------------------------------------------------
    def _llm_summary(self, farm_id: str) -> dict[str, Any]:
        """
        Build a structured, JSON-ready farm summary for the Generative LLM node.

        Returns
        -------
        dict with keys:
            last_season_yield_kg_ha   : float | None
            yield_vs_3yr_avg_pct      : float | None  (% above/below 3yr average)
            top_pest_risk             : str   | None   (most frequent pest name)
            soil_deficiencies         : list[str]      (e.g. ["low_nitrogen"])
            irrigation_efficiency     : float | None   (0–1)
            generated_at              : str            (ISO timestamp)
        """
        logger.info("_llm_summary farm_id=%s", farm_id)

        # --- Yield summary ---
        yield_all = self._fetch_all_yields(farm_id, years=5)
        last_yield: Optional[float] = None
        yield_vs_avg: Optional[float] = None
        if not yield_all.empty:
            yield_reset = yield_all.reset_index().sort_values("harvest_date")
            last_yield = float(yield_reset["yield_kg_per_hectare"].iloc[-1])
            if len(yield_reset) >= 2:
                three_yr_mean = float(
                    yield_reset["yield_kg_per_hectare"].iloc[:-1].tail(3).mean()
                )
                if three_yr_mean > 0:
                    yield_vs_avg = round(
                        (last_yield - three_yr_mean) / three_yr_mean * 100, 2
                    )

        # --- Top pest risk by frequency ---
        three_years_ago = date.today() - timedelta(days=3 * 365)
        pest_df = self._db.get_pest_history(farm_id, three_years_ago, date.today())
        top_pest: Optional[str] = None
        if not pest_df.empty:
            pest_reset = pest_df.reset_index()
            top_pest = str(
                pest_reset["pest_name"].value_counts().idxmax()
            )

        # --- Soil deficiencies ---
        soil_df = self._db.get_soil_trend(farm_id, last_n_records=1)
        deficiencies: list[str] = []
        if not soil_df.empty:
            latest = soil_df.reset_index().iloc[-1]
            for col, threshold in SOIL_THRESHOLDS.items():
                val = latest.get(col)
                if val is not None and not np.isnan(float(val)) and float(val) < threshold:
                    deficiencies.append(f"low_{col.replace('_ppm', '')}")

        # --- Irrigation efficiency ---
        irr_deficit = self._compute_irrigation_deficit(farm_id)
        irr_efficiency: Optional[float] = None
        if irr_deficit is not None:
            # deficit_pct: positive = overuse, negative = underuse
            # efficiency = actual / baseline, capped at 1.0
            actual_ratio = 1.0 + irr_deficit / 100.0
            irr_efficiency = round(min(1.0, 1.0 / actual_ratio if actual_ratio > 0 else 0.0), 3)

        return {
            "farm_id": farm_id,
            "last_season_yield_kg_ha": round(last_yield, 2) if last_yield else None,
            "yield_vs_3yr_avg_pct": yield_vs_avg,
            "top_pest_risk": top_pest,
            "soil_deficiencies": deficiencies,
            "irrigation_efficiency": irr_efficiency,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _fetch_all_yields(self, farm_id: str, years: int = 5) -> pd.DataFrame:
        """Fetch yield records for all crops on a farm."""
        from sqlalchemy import text

        min_year = date.today().year - years
        sql = text(
            """
            SELECT
                yr.record_id, yr.farm_id, yr.crop_id, c.crop_name,
                yr.season, yr.year, yr.yield_kg_per_hectare, yr.harvest_date
            FROM yield_records yr
            JOIN crops c ON c.crop_id = yr.crop_id
            WHERE yr.farm_id = :farm_id
              AND yr.year   >= :min_year
            ORDER BY yr.harvest_date
            """
        )
        # Use the connector's internal session
        with self._db._get_session() as session:
            result = session.execute(sql, {"farm_id": farm_id, "min_year": min_year})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        df["farm_id"] = df["farm_id"].astype(str)
        df["harvest_date"] = pd.to_datetime(df["harvest_date"])
        return df.set_index(["farm_id", "harvest_date"])

    def _compute_irrigation_deficit(self, farm_id: str) -> Optional[float]:
        """
        Return the average irrigation deficit % across the most recent full season
        compared to the crop-specific recommended baseline.
        """
        year = date.today().year
        # Try current Kharif season
        irr_df = self._db.get_irrigation_summary(farm_id, "Kharif", year - 1)
        if irr_df.empty:
            return None

        irr_reset = irr_df.reset_index()
        actual_total = float(irr_reset["water_used_liters"].sum())

        # Infer crop from context (use Rice baseline as most common Kharif crop)
        baseline = CROP_IRRIGATION_BASELINE_LITERS["Rice"]
        if baseline == 0:
            return None

        deficit_pct = round((actual_total - baseline) / baseline * 100, 2)
        return deficit_pct

    @staticmethod
    def _compute_soil_slopes(soil_df: pd.DataFrame) -> dict[str, Optional[float]]:
        """
        Compute linear regression slope for N, P, K over the provided soil DataFrame.

        Returns dict mapping column name → slope (ppm / record).
        Returns None for a column if fewer than 2 non-null readings exist.
        """
        slopes: dict[str, Optional[float]] = {}
        for col in ["nitrogen_ppm", "phosphorus_ppm", "potassium_ppm"]:
            if soil_df.empty or col not in soil_df.columns:
                slopes[col] = None
                continue

            series = soil_df[col].dropna()
            if len(series) < 2:
                slopes[col] = None
                continue

            x = np.arange(len(series), dtype=float)
            y = series.values.astype(float)
            coeffs = np.polyfit(x, y, deg=1)
            slopes[col] = round(float(coeffs[0]), 4)

        return slopes


if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    from historical_db.db_connector import HistoricalDBConnector

    # Use the first deterministic farm_id from seed data for demo
    DEMO_FARM_ID = str(__import__("uuid").uuid5(
        __import__("uuid").NAMESPACE_DNS, "farm_punjab_amarinder"
    ))

    with HistoricalDBConnector() as db:
        extractor = HistoricalFeatureExtractor(db)
        result = extractor.extract_all(DEMO_FARM_ID)
        print("=== Forecaster features ===")
        print(result["forecaster_features"])
        print("\n=== Vision features ===")
        print(result["vision_features"])
        print("\n=== LLM Summary ===")
        import json
        print(json.dumps(result["llm_summary"], indent=2, default=str))
