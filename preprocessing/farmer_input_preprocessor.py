"""
preprocessing/farmer_input_preprocessor.py
============================================
Farmer Input Preprocessing Module for the Agri Generative AI Platform.

Loads raw FarmerInputRecord rows from the database, applies:
  - Location normalisation   → (lat, lon) from village names
  - One-hot encoding         → crop_type, observed_issue
  - Ordinal mapping          → severity  (low=1, medium=2, high=3)
  - Timestamp alignment      → reindex to the shared pipeline time-series index
  - Null imputation          → fill missing numeric fields with sensible defaults

Returns a clean pandas DataFrame ready for feature engineering / model ingestion.

Dependencies:
    pip install pandas sqlalchemy aiosqlite pyyaml
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------
_CONFIG_PATH = "configs/farmer_input_config.yaml"


def _load_config(path: str = _CONFIG_PATH) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except FileNotFoundError:
        logger.warning("Config not found at %s; using defaults.", path)
        return {}


CONFIG = _load_config()

VILLAGE_COORDS: dict[str, dict] = CONFIG.get("village_coords", {})
SUPPORTED_CROPS: list[str] = CONFIG.get("crops", [])
SUPPORTED_ISSUES: list[str] = CONFIG.get("issues", [])
TS_FREQUENCY: str = CONFIG.get("timeseries", {}).get("frequency", "D")  # "D" = daily


# ---------------------------------------------------------------------------
# Severity map
# ---------------------------------------------------------------------------
SEVERITY_MAP: dict[str, int] = {"low": 1, "medium": 2, "high": 3}


# ---------------------------------------------------------------------------
# FarmerInputPreprocessor
# ---------------------------------------------------------------------------

class FarmerInputPreprocessor:
    """
    Preprocessing pipeline for farmer-reported field observations.

    Typical usage::

        preprocessor = FarmerInputPreprocessor(session_factory)
        df = await preprocessor.run(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

    The returned DataFrame has:
        - A DatetimeIndex aligned to `ts_frequency` (default: daily).
        - Numeric latitude / longitude columns.
        - One-hot columns for crop_type and observed_issue.
        - A numeric `severity_numeric` column (1–3).
        - All original metadata columns retained.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        ts_frequency: str = TS_FREQUENCY,
        village_coords: Optional[dict] = None,
        supported_crops: Optional[list] = None,
        supported_issues: Optional[list] = None,
    ) -> None:
        """
        Args:
            session_factory: Async SQLAlchemy session factory.
            ts_frequency:    Pandas offset alias for the shared time-series index.
            village_coords:  Mapping of village name (lower) → {lat, lon}.
            supported_crops: All possible crop type labels.
            supported_issues:All possible observed issue labels.
        """
        self.session_factory = session_factory
        self.ts_frequency = ts_frequency
        self.village_coords = village_coords or VILLAGE_COORDS
        self.supported_crops = supported_crops or SUPPORTED_CROPS
        self.supported_issues = supported_issues or SUPPORTED_ISSUES

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        farmer_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Execute the full preprocessing pipeline and return a clean DataFrame.

        Args:
            start_date: Filter records from this date (inclusive).
            end_date:   Filter records up to this date (inclusive).
            farmer_id:  If provided, restrict to a single farmer.

        Returns:
            Preprocessed pandas DataFrame indexed by date_observed.
        """
        raw_df = await self._load_records(start_date, end_date, farmer_id)
        if raw_df.empty:
            logger.info("No records found for the given filter criteria.")
            return raw_df

        df = self._normalize_locations(raw_df)
        df = self._map_severity(df)
        df = self._one_hot_encode(df)
        df = self._align_timestamps(df, start_date, end_date)
        df = self._impute_nulls(df)

        logger.info(
            "Preprocessing complete: %d rows, %d features.", len(df), len(df.columns)
        )
        return df

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def normalize_location_string(self, location_raw: Optional[str]) -> tuple[Optional[float], Optional[float]]:
        """
        Attempt to resolve a raw location string to (lat, lon).

        Resolution order:
          1. Already-numeric "lat,lon" string.
          2. Village-name lookup (case-insensitive).
          3. Return (None, None) if unresolvable.
        """
        if not location_raw:
            return None, None

        # Try "lat,lon" format
        parts = str(location_raw).split(",")
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass

        # Village lookup
        coords = self.village_coords.get(location_raw.lower().strip())
        if coords:
            return coords.get("lat"), coords.get("lon")

        return None, None

    def _normalize_locations(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fill missing latitude / longitude values using `location_raw` lookups.

        Operates on the existing `latitude` and `longitude` columns,
        only overwriting NaN values.
        """
        df = df.copy()

        def _fill_coords(row: pd.Series) -> pd.Series:
            if pd.isna(row.get("latitude")) or pd.isna(row.get("longitude")):
                lat, lon = self.normalize_location_string(row.get("location_raw"))
                row["latitude"] = lat
                row["longitude"] = lon
            return row

        df = df.apply(_fill_coords, axis=1)
        logger.debug("Location normalisation applied.")
        return df

    def _map_severity(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add `severity_numeric` column: low=1, medium=2, high=3.
        Rows with unrecognised/null severity receive NaN.
        """
        df = df.copy()
        df["severity_numeric"] = df["severity"].map(SEVERITY_MAP)
        return df

    def _one_hot_encode(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        One-hot encode `crop_type` and `observed_issue`.

        Uses `supported_crops` and `supported_issues` to ensure a fixed,
        consistent column set regardless of which values appear in the batch.
        Produces columns:
            crop_{name}      for each supported crop
            issue_{name}     for each supported issue
        """
        df = df.copy()

        # --- crop_type ---
        crop_dummies = pd.get_dummies(df["crop_type"], prefix="crop")
        for crop in self.supported_crops:
            col = f"crop_{crop}"
            if col not in crop_dummies.columns:
                crop_dummies[col] = 0
        crop_dummies = crop_dummies[[f"crop_{c}" for c in self.supported_crops]]

        # --- observed_issue ---
        issue_dummies = pd.get_dummies(df["observed_issue"], prefix="issue")
        for issue in self.supported_issues:
            col = f"issue_{issue}"
            if col not in issue_dummies.columns:
                issue_dummies[col] = 0
        issue_dummies = issue_dummies[[f"issue_{i}" for i in self.supported_issues]]

        df = pd.concat([df, crop_dummies, issue_dummies], axis=1)
        logger.debug("One-hot encoding applied for crop_type and observed_issue.")
        return df

    def _align_timestamps(
        self,
        df: pd.DataFrame,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> pd.DataFrame:
        """
        Re-index the DataFrame to a regular DatetimeIndex.

        Steps:
          1. Parse `date_observed` → DatetimeIndex.
          2. Build a complete date range between min/max dates (or overrides).
          3. Group by date, aggregate numeric columns by mean, string columns
             by first occurrence.
          4. Reindex to the full date range, forward-fill string categoricals.

        This ensures the farmer-input feature matrix aligns with satellite,
        IoT, and weather data sources that share the same time-series index.
        """
        df = df.copy()
        df["date_observed"] = pd.to_datetime(df["date_observed"], errors="coerce")
        df = df.dropna(subset=["date_observed"])
        df = df.set_index("date_observed")
        df.index = df.index.normalize()  # truncate to day boundary

        # Build the full shared index
        idx_start = (
            pd.Timestamp(start_date) if start_date else df.index.min()
        )
        idx_end = (
            pd.Timestamp(end_date) if end_date else df.index.max()
        )
        full_index = pd.date_range(start=idx_start, end=idx_end, freq=self.ts_frequency)

        # Separate numeric vs. non-numeric columns for aggregation
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        str_cols = [c for c in df.columns if c not in numeric_cols]

        # Aggregate by date
        agg_dict = {c: "mean" for c in numeric_cols}
        agg_dict.update({c: "first" for c in str_cols})
        df_agg = df.groupby(df.index).agg(agg_dict)

        # Reindex to full range; forward-fill categoricals, leave numerics NaN
        df_reindexed = df_agg.reindex(full_index)
        df_reindexed[str_cols] = df_reindexed[str_cols].ffill()

        logger.debug(
            "Timestamp aligned: %d periods at frequency '%s'.",
            len(full_index),
            self.ts_frequency,
        )
        return df_reindexed

    @staticmethod
    def _impute_nulls(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply conservative null imputation.

        - Numeric NaN → 0 (absence of observation = no reading).
        - String NaN  → "unknown".
        """
        numeric_cols = df.select_dtypes(include="number").columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        str_cols = df.select_dtypes(include=["object", "string"]).columns
        df[str_cols] = df[str_cols].fillna("unknown")
        return df

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_records(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
        farmer_id: Optional[str],
    ) -> pd.DataFrame:
        """
        Fetch raw records from `farmer_inputs` and return as DataFrame.
        """
        conditions = []
        params: dict = {}

        if start_date:
            conditions.append("date_observed >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("date_observed <= :end_date")
            params["end_date"] = end_date
        if farmer_id:
            conditions.append("farmer_id = :farmer_id")
            params["farmer_id"] = farmer_id

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM farmer_inputs {where_clause} ORDER BY date_observed ASC"  # noqa: S608

        async with self.session_factory() as session:
            result = await session.execute(text(query), params)
            rows = result.mappings().all()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])
        logger.info("Loaded %d raw farmer-input records.", len(df))
        return df
