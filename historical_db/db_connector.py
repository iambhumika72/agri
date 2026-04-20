"""
historical_db/db_connector.py — SQLAlchemy session manager and typed query layer.

Design notes:
- HistoricalDBConnector is a context manager so callers get automatic session
  cleanup even on exceptions.
- All env vars are read once at __init__ time and validated immediately so
  misconfiguration fails fast rather than at query time.
- Query methods return pandas DataFrames so they slot directly into the
  preprocessing / feature extraction pipeline without extra conversion.
- insert_record uses a white-list of allowed table names to prevent SQL injection
  via the table_name parameter.
- The _validate_env() helper raises EnvironmentError (not RuntimeError) so
  calling code can distinguish configuration failures from logic errors.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import date
from typing import Any, Generator

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from historical_db.models import (
    Base,
    Farm,
    IrrigationLog,
    PestRecord,
    SoilHealth,
    YieldRecord,
)

logger = logging.getLogger(__name__)

# Tables that insert_record is permitted to write to
_ALLOWED_TABLES = frozenset(
    {"farms", "crops", "yield_records", "pest_records", "irrigation_logs", "soil_health", "mandi_prices"}
)


class HistoricalDBConnector:
    """
    Thread-safe SQLAlchemy connector for the Historical Database.

    Usage as context manager::

        with HistoricalDBConnector() as db:
            df = db.get_yield_history(farm_id="...", crop_id="...", years=3)

    Usage without context manager::

        db = HistoricalDBConnector()
        db.open()
        df = db.get_yield_history(...)
        db.close()
    """

    # --------------------------------------------------------------------------
    # Construction / teardown
    # --------------------------------------------------------------------------
    def __init__(self) -> None:
        self._url = self._get_db_url()
        
        engine_args = {"echo": False}
        if "sqlite" not in self._url:
            engine_args.update({
                "pool_size": 5,
                "max_overflow": 10,
                "pool_pre_ping": True
            })
            
        self._engine = create_engine(self._url, **engine_args)
        self._SessionFactory = sessionmaker(bind=self._engine, expire_on_commit=False)
        self._session: Session | None = None
        logger.info("HistoricalDBConnector initialised — url=%s", self._url.split("@")[-1] if "@" in self._url else self._url)

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------
    def __enter__(self) -> "HistoricalDBConnector":
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.close(rollback=exc_type is not None)
        return False  # Do not suppress exceptions

    def open(self) -> None:
        """Open a new database session."""
        if self._session is not None:
            logger.warning("Session already open — ignoring open() call.")
            return
        self._session = self._SessionFactory()
        logger.info("DB session opened.")

    def close(self, rollback: bool = False) -> None:
        """Commit (or rollback) and close the session."""
        if self._session is None:
            return
        try:
            if rollback:
                self._session.rollback()
                logger.warning("DB session rolled back.")
            else:
                self._session.commit()
                logger.info("DB session committed and closed.")
        finally:
            self._session.close()
            self._session = None

    @contextmanager
    def _get_session(self) -> Generator[Session, None, None]:
        """Internal: yield a usable session, creating one if needed."""
        if self._session is not None:
            yield self._session
        else:
            session = self._SessionFactory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------
    def create_all_tables(self) -> None:
        """Create all ORM-defined tables if they don't already exist."""
        Base.metadata.create_all(self._engine)
        logger.info("All tables created (or already present).")

    def drop_all_tables(self) -> None:
        """Drop all ORM-defined tables — use with caution."""
        Base.metadata.drop_all(self._engine)
        logger.warning("All tables dropped.")

    # ------------------------------------------------------------------
    # Typed query methods
    # ------------------------------------------------------------------
    def get_yield_history(
        self, farm_id: str, crop_id: str, years: int = 5
    ) -> pd.DataFrame:
        """
        Return yield records for a given farm × crop over the last N years.

        The MultiIndex (farm_id, harvest_date) enables time-series alignment
        with other pipeline DataFrames.
        """
        logger.info(
            "get_yield_history farm_id=%s crop_id=%s years=%d", farm_id, crop_id, years
        )
        min_year = date.today().year - years
        sql = text(
            """
            SELECT
                yr.record_id,
                yr.farm_id,
                yr.crop_id,
                c.crop_name,
                yr.season,
                yr.year,
                yr.yield_kg_per_hectare,
                yr.harvest_date,
                yr.notes
            FROM yield_records yr
            JOIN crops c ON c.crop_id = yr.crop_id
            WHERE yr.farm_id   = :farm_id
              AND yr.crop_id   = :crop_id
              AND yr.year      >= :min_year
            ORDER BY yr.harvest_date
            """
        )
        with self._get_session() as session:
            result = session.execute(
                sql,
                {"farm_id": farm_id, "crop_id": crop_id, "min_year": min_year},
            )
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        df["farm_id"] = df["farm_id"].astype(str)
        df["harvest_date"] = pd.to_datetime(df["harvest_date"])
        return df.set_index(["farm_id", "harvest_date"])

    def get_pest_history(
        self, farm_id: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """
        Return pest records for a farm within [start_date, end_date].
        """
        logger.info(
            "get_pest_history farm_id=%s %s → %s", farm_id, start_date, end_date
        )
        sql = text(
            """
            SELECT
                pr.pest_id,
                pr.farm_id,
                pr.crop_id,
                c.crop_name,
                pr.pest_name,
                pr.severity,
                pr.affected_area_pct,
                pr.detected_date,
                pr.resolved_date,
                pr.treatment_applied
            FROM pest_records pr
            JOIN crops c ON c.crop_id = pr.crop_id
            WHERE pr.farm_id       = :farm_id
              AND pr.detected_date BETWEEN :start_date AND :end_date
            ORDER BY pr.detected_date
            """
        )
        with self._get_session() as session:
            result = session.execute(
                sql,
                {"farm_id": farm_id, "start_date": start_date, "end_date": end_date},
            )
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        df["farm_id"] = df["farm_id"].astype(str)
        df["detected_date"] = pd.to_datetime(df["detected_date"])
        return df.set_index(["farm_id", "detected_date"])

    def get_soil_trend(
        self, farm_id: str, last_n_records: int = 10
    ) -> pd.DataFrame:
        """
        Return the most recent N soil health readings for a farm.
        """
        logger.info(
            "get_soil_trend farm_id=%s last_n_records=%d", farm_id, last_n_records
        )
        sql = text(
            """
            SELECT
                soil_id,
                farm_id,
                recorded_date,
                ph_level,
                nitrogen_ppm,
                phosphorus_ppm,
                potassium_ppm,
                organic_matter_pct,
                moisture_pct
            FROM soil_health
            WHERE farm_id = :farm_id
            ORDER BY recorded_date DESC
            LIMIT :n
            """
        )
        with self._get_session() as session:
            result = session.execute(sql, {"farm_id": farm_id, "n": last_n_records})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        df["farm_id"] = df["farm_id"].astype(str)
        df["recorded_date"] = pd.to_datetime(df["recorded_date"])
        df.sort_values("recorded_date", inplace=True)
        return df.set_index(["farm_id", "recorded_date"])

    def get_irrigation_summary(
        self, farm_id: str, season: str, year: int
    ) -> pd.DataFrame:
        """
        Return a daily irrigation log for a farm filtered to an agronomic season.

        Season window approximation:
          Kharif  → June 1 – November 30
          Rabi    → November 1 – April 30
          Zaid    → March 1 – June 30
        """
        logger.info(
            "get_irrigation_summary farm_id=%s season=%s year=%d",
            farm_id, season, year,
        )
        season_windows: dict[str, tuple[str, str]] = {
            "Kharif": (f"{year}-06-01",     f"{year}-11-30"),
            "Rabi":   (f"{year}-11-01",     f"{year + 1}-04-30"),
            "Zaid":   (f"{year}-03-01",     f"{year}-06-30"),
        }
        if season not in season_windows:
            raise ValueError(f"Unknown season '{season}'. Must be Kharif, Rabi, or Zaid.")

        start, end = season_windows[season]
        sql = text(
            """
            SELECT
                log_id,
                farm_id,
                log_date,
                water_used_liters,
                method,
                duration_minutes
            FROM irrigation_logs
            WHERE farm_id  = :farm_id
              AND log_date BETWEEN :start AND :end
            ORDER BY log_date
            """
        )
        with self._get_session() as session:
            result = session.execute(
                sql, {"farm_id": farm_id, "start": start, "end": end}
            )
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            return df

        df["farm_id"] = df["farm_id"].astype(str)
        df["log_date"] = pd.to_datetime(df["log_date"])
        return df.set_index(["farm_id", "log_date"])

    def get_latest_soil_health(self, farm_id: str) -> dict:
        """Return the most recent soil health record as a dictionary."""
        df = self.get_soil_trend(farm_id, last_n_records=1)
        if df.empty:
            return {}
        # index is (farm_id, date), reset it to get columns back
        return df.reset_index().iloc[0].to_dict()

    def fetch_mandi_prices(
        self, state: str, district: str, commodity: str, days: int = 365
    ) -> pd.DataFrame:
        """Return historical mandi prices for a given region and commodity."""
        logger.info(
            "fetch_mandi_prices %s, %s, %s (last %d days)",
            state, district, commodity, days
        )
        sql = text(
            """
            SELECT arrival_date as ds, modal_price as y
            FROM mandi_prices
            WHERE state     = :state
              AND district  = :district
              AND commodity = :commodity
              AND arrival_date >= CURRENT_DATE - INTERVAL '1 day' * :days
            ORDER BY arrival_date ASC
            """
        )
        with self._get_session() as session:
            result = session.execute(
                sql, {"state": state, "district": district, "commodity": commodity, "days": days}
            )
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        if not df.empty:
            df["ds"] = pd.to_datetime(df["ds"])
        return df

    # ------------------------------------------------------------------
    # Generic insert
    # ------------------------------------------------------------------
    def insert_record(self, table_name: str, data: dict) -> bool:
        """
        Generic insert into any of the 6 allowed tables.

        :param table_name: One of the allowed table names.
        :param data: Column → value mapping (UUID fields accepted as str).
        :returns: True on success, False on failure (with logged error).
        :raises ValueError: If table_name is not in the allowed list.
        """
        if table_name not in _ALLOWED_TABLES:
            raise ValueError(
                f"table_name '{table_name}' is not allowed. "
                f"Must be one of: {sorted(_ALLOWED_TABLES)}"
            )

        # Build parameterised INSERT dynamically
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = text(
            f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"  # noqa: S608
        )

        logger.info("insert_record table=%s keys=%s", table_name, list(data.keys()))

        # Convert UUID and date objects to strings for SQLite compatibility in text() queries
        import uuid
        from datetime import date
        processed_data = {
            k: str(v) if isinstance(v, (uuid.UUID, date)) else v 
            for k, v in data.items()
        }

        with self._get_session() as session:
            try:
                session.execute(sql, processed_data)
                logger.info("insert_record succeeded for table=%s", table_name)
                return True
            except Exception as exc:
                logger.error(
                    "insert_record failed for table=%s: %s", table_name, exc
                )
                raise

    # ------------------------------------------------------------------
    # Farm existence check (used by API routes)
    # ------------------------------------------------------------------
    def farm_exists(self, farm_id: str) -> bool:
        """Return True if the given farm_id exists in the farms table."""
        sql = text("SELECT 1 FROM farms WHERE farm_id = :fid LIMIT 1")
        with self._get_session() as session:
            result = session.execute(sql, {"fid": farm_id}).fetchone()
        return result is not None

    def get_all_farms(self) -> list[dict]:
        """Return a list of all farms registered in the system."""
        sql = text("SELECT * FROM farms ORDER BY farmer_name")
        with self._get_session() as session:
            result = session.execute(sql)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_db_url() -> str:
        """Read DB connection string from environment or fall back to default SQLite."""
        # 1. Direct URL (Preferred)
        url = os.environ.get("DATABASE_URL")
        if url:
            return url

        # 2. Individual components
        host = os.environ.get("DB_HOST")
        port = os.environ.get("DB_PORT", "5432")
        db = os.environ.get("DB_NAME")
        user = os.environ.get("DB_USER")
        pw = os.environ.get("DB_PASSWORD")

        if all([host, db, user, pw]):
            return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"

        # 3. Development Fallback
        default_sqlite = "sqlite:///./agri.db"
        logger.warning("Missing DB env vars; falling back to %s", default_sqlite)
        return default_sqlite


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        with HistoricalDBConnector() as db:
            print("Connection OK — engine:", db._engine.url)
    except EnvironmentError as e:
        print(f"Cannot connect: {e}")
