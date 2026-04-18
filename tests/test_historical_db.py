"""
tests/test_historical_db.py — Pytest suite for the Historical Database module.

Uses an in-memory SQLite DB with a SQLite-compatible schema (no PostgreSQL types).
A SQLiteConnector class mirrors HistoricalDBConnector's public API for testing.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any, Generator

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import (
    Column, Date, DateTime, Double, Float, Integer, MetaData,
    SmallInteger, String, Table, Text, create_engine, event, text,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Patch env vars before any import that touches HistoricalDBConnector.__init__
# ---------------------------------------------------------------------------
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "5432"
os.environ["DB_NAME"] = "trace_test"
os.environ["DB_USER"] = "trace"
os.environ["DB_PASSWORD"] = "trace_secret"


# ===========================================================================
# SQLite-compatible schema (no PostgreSQL UUID/ENUM types)
# ===========================================================================
_meta = MetaData()

Table("farms", _meta,
    Column("farm_id",       String(36), primary_key=True),
    Column("farmer_name",   String(120), nullable=False),
    Column("district",      String(100), nullable=False),
    Column("state",         String(100), nullable=False),
    Column("latitude",      Double),
    Column("longitude",     Double),
    Column("area_hectares", Double),
    Column("created_at",    DateTime),
)
Table("crops", _meta,
    Column("crop_id",      String(36), primary_key=True),
    Column("crop_name",    String(100), nullable=False),
    Column("crop_variety", String(100)),
    Column("season_type",  String(20), nullable=False),
    Column("created_at",   DateTime),
)
Table("yield_records", _meta,
    Column("record_id",            String(36), primary_key=True),
    Column("farm_id",              String(36), nullable=False),
    Column("crop_id",              String(36), nullable=False),
    Column("season",               String(20), nullable=False),
    Column("year",                 SmallInteger, nullable=False),
    Column("yield_kg_per_hectare", Double, nullable=False),
    Column("harvest_date",         Date, nullable=False),
    Column("notes",                Text),
    Column("created_at",           DateTime),
)
Table("pest_records", _meta,
    Column("pest_id",           String(36), primary_key=True),
    Column("farm_id",           String(36), nullable=False),
    Column("crop_id",           String(36), nullable=False),
    Column("pest_name",         String(120), nullable=False),
    Column("severity",          SmallInteger, nullable=False),
    Column("affected_area_pct", Double, nullable=False),
    Column("detected_date",     Date, nullable=False),
    Column("resolved_date",     Date),
    Column("treatment_applied", Text),
    Column("created_at",        DateTime),
)
Table("irrigation_logs", _meta,
    Column("log_id",            String(36), primary_key=True),
    Column("farm_id",           String(36), nullable=False),
    Column("log_date",          Date, nullable=False),
    Column("water_used_liters", Double, nullable=False),
    Column("method",            String(20), nullable=False),
    Column("duration_minutes",  Integer, nullable=False),
    Column("created_at",        DateTime),
)
Table("soil_health", _meta,
    Column("soil_id",             String(36), primary_key=True),
    Column("farm_id",             String(36), nullable=False),
    Column("recorded_date",       Date, nullable=False),
    Column("ph_level",            Float),
    Column("nitrogen_ppm",        Float),
    Column("phosphorus_ppm",      Float),
    Column("potassium_ppm",       Float),
    Column("organic_matter_pct",  Float),
    Column("moisture_pct",        Float),
    Column("created_at",          DateTime),
)


# ===========================================================================
# SQLiteConnector — mirrors HistoricalDBConnector's public API for tests
# ===========================================================================
class SQLiteConnector:
    """Test-only connector backed by SQLite. No PostgreSQL-specific SQL."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine
        self._SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
        self._session: Any = None

    def __enter__(self) -> "SQLiteConnector":
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.close(rollback=exc_type is not None)
        return False

    def open(self) -> None:
        self._session = self._SessionFactory()

    def close(self, rollback: bool = False) -> None:
        if self._session:
            if rollback:
                self._session.rollback()
            else:
                self._session.commit()
            self._session.close()
            self._session = None

    @contextmanager  # type: ignore[misc]
    def _get_session(self):  # type: ignore[return]
        if self._session is not None:
            yield self._session
        else:
            s = self._SessionFactory()
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

    def farm_exists(self, farm_id: str) -> bool:
        with self._get_session() as s:
            r = s.execute(
                text("SELECT 1 FROM farms WHERE farm_id = :fid LIMIT 1"),
                {"fid": farm_id},
            ).fetchone()
        return r is not None

    def insert_record(self, table_name: str, data: dict) -> bool:
        _ALLOWED = {"farms","crops","yield_records","pest_records","irrigation_logs","soil_health"}
        if table_name not in _ALLOWED:
            raise ValueError(f"Not allowed: {table_name}")
        cols = ", ".join(data.keys())
        ph = ", ".join(f":{k}" for k in data.keys())
        with self._get_session() as s:
            s.execute(text(f"INSERT INTO {table_name} ({cols}) VALUES ({ph})"), data)  # noqa: S608
        return True

    def get_yield_history(self, farm_id: str, crop_id: str, years: int = 5) -> pd.DataFrame:
        min_yr = date.today().year - years
        sql = text(
            "SELECT yr.record_id, yr.farm_id, yr.crop_id, c.crop_name,"
            " yr.season, yr.year, yr.yield_kg_per_hectare, yr.harvest_date, yr.notes"
            " FROM yield_records yr JOIN crops c ON c.crop_id = yr.crop_id"
            " WHERE yr.farm_id = :fid AND yr.crop_id = :cid AND yr.year >= :min_yr"
            " ORDER BY yr.harvest_date"
        )
        with self._get_session() as s:
            r = s.execute(sql, {"fid": farm_id, "cid": crop_id, "min_yr": min_yr})
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        if df.empty:
            return df
        df["farm_id"] = df["farm_id"].astype(str)
        df["harvest_date"] = pd.to_datetime(df["harvest_date"])
        return df.set_index(["farm_id", "harvest_date"])

    def get_pest_history(self, farm_id: str, start_date: date, end_date: date) -> pd.DataFrame:
        sql = text(
            "SELECT pr.pest_id, pr.farm_id, pr.crop_id, c.crop_name, pr.pest_name,"
            " pr.severity, pr.affected_area_pct, pr.detected_date, pr.resolved_date, pr.treatment_applied"
            " FROM pest_records pr JOIN crops c ON c.crop_id = pr.crop_id"
            " WHERE pr.farm_id = :fid AND pr.detected_date BETWEEN :sd AND :ed"
            " ORDER BY pr.detected_date"
        )
        with self._get_session() as s:
            r = s.execute(
                sql,
                {"fid": farm_id, "sd": start_date.isoformat(), "ed": end_date.isoformat()},
            )
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        if df.empty:
            return df
        df["farm_id"] = df["farm_id"].astype(str)
        df["detected_date"] = pd.to_datetime(df["detected_date"])
        return df.set_index(["farm_id", "detected_date"])

    def get_soil_trend(self, farm_id: str, last_n_records: int = 10) -> pd.DataFrame:
        sql = text(
            "SELECT soil_id, farm_id, recorded_date, ph_level, nitrogen_ppm,"
            " phosphorus_ppm, potassium_ppm, organic_matter_pct, moisture_pct"
            " FROM soil_health WHERE farm_id = :fid ORDER BY recorded_date DESC LIMIT :n"
        )
        with self._get_session() as s:
            r = s.execute(sql, {"fid": farm_id, "n": last_n_records})
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        if df.empty:
            return df
        df["farm_id"] = df["farm_id"].astype(str)
        df["recorded_date"] = pd.to_datetime(df["recorded_date"])
        df.sort_values("recorded_date", inplace=True)
        return df.set_index(["farm_id", "recorded_date"])

    def get_irrigation_summary(self, farm_id: str, season: str, year: int) -> pd.DataFrame:
        windows = {
            "Kharif": (f"{year}-06-01",   f"{year}-11-30"),
            "Rabi":   (f"{year}-11-01",   f"{year+1}-04-30"),
            "Zaid":   (f"{year}-03-01",   f"{year}-06-30"),
        }
        start, end = windows[season]
        sql = text(
            "SELECT log_id, farm_id, log_date, water_used_liters, method, duration_minutes"
            " FROM irrigation_logs WHERE farm_id = :fid AND log_date BETWEEN :s AND :e ORDER BY log_date"
        )
        with self._get_session() as s:
            r = s.execute(sql, {"fid": farm_id, "s": start, "e": end})
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        if df.empty:
            return df
        df["farm_id"] = df["farm_id"].astype(str)
        df["log_date"] = pd.to_datetime(df["log_date"])
        return df.set_index(["farm_id", "log_date"])


def _make_connector(engine: Any) -> SQLiteConnector:
    return SQLiteConnector(engine)


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # all connections share one in-memory DB
    )

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    _meta.create_all(engine)
    yield engine
    _meta.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def db_session(sqlite_engine) -> Generator:
    S = sessionmaker(bind=sqlite_engine)
    session = S()
    yield session
    session.close()


@pytest.fixture(scope="module")
def seeded_farm_id() -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "test_farm_alpha"))


@pytest.fixture(scope="module")
def seeded_crop_id() -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "test_crop_wheat"))


@pytest.fixture(scope="module")
def seed_data(db_session, seeded_farm_id, seeded_crop_id):
    db_session.execute(
        text("INSERT INTO farms (farm_id, farmer_name, district, state, latitude, longitude, area_hectares)"
             " VALUES (:fid, 'Test Farmer', 'Test District', 'Test State', 28.6, 77.2, 3.0)"),
        {"fid": seeded_farm_id},
    )
    db_session.execute(
        text("INSERT INTO crops (crop_id, crop_name, crop_variety, season_type)"
             " VALUES (:cid, 'Wheat', 'HD-2967', 'Rabi')"),
        {"cid": seeded_crop_id},
    )
    # 3 yield records
    for i, yr in enumerate([2022, 2023, 2024]):
        db_session.execute(
            text("INSERT INTO yield_records"
                 " (record_id, farm_id, crop_id, season, year, yield_kg_per_hectare, harvest_date)"
                 " VALUES (:rid, :fid, :cid, 'Rabi', :yr, :yld, :hd)"),
            {"rid": str(uuid.uuid4()), "fid": seeded_farm_id, "cid": seeded_crop_id,
             "yr": yr, "yld": 4000.0 + i * 200, "hd": f"{yr}-04-15"},
        )
    # 4 pest records: weighted_sum=425, N=4, max=2000, score=0.2125
    pests = [
        ("aphids",    3, 20.0, "2023-07-10", "2023-07-25"),
        ("bollworm",  5, 45.0, "2023-08-05", "2023-08-20"),
        ("stem borer",2, 10.0, "2024-02-01", "2024-02-15"),
        ("aphids",    4, 30.0, "2024-03-10", None),
    ]
    for pest_name, sev, area, det, res in pests:
        db_session.execute(
            text("INSERT INTO pest_records"
                 " (pest_id, farm_id, crop_id, pest_name, severity, affected_area_pct, detected_date, resolved_date)"
                 " VALUES (:pid, :fid, :cid, :pn, :sv, :ar, :dd, :rd)"),
            {"pid": str(uuid.uuid4()), "fid": seeded_farm_id, "cid": seeded_crop_id,
             "pn": pest_name, "sv": sev, "ar": area, "dd": det, "rd": res},
        )
    # 5 soil records
    for i in range(5):
        db_session.execute(
            text("INSERT INTO soil_health"
                 " (soil_id, farm_id, recorded_date, ph_level, nitrogen_ppm,"
                 "  phosphorus_ppm, potassium_ppm, organic_matter_pct, moisture_pct)"
                 " VALUES (:sid, :fid, :rd, 7.5, :n, :p, :k, 0.5, 20.0)"),
            {"sid": str(uuid.uuid4()), "fid": seeded_farm_id,
             "rd": (date(2023, 6, 1) + timedelta(days=60 * i)).isoformat(),
             "n": 200.0 - i * 5, "p": 15.0 + i, "k": 180.0},
        )
    # 10 irrigation logs
    for week in range(10):
        db_session.execute(
            text("INSERT INTO irrigation_logs"
                 " (log_id, farm_id, log_date, water_used_liters, method, duration_minutes)"
                 " VALUES (:lid, :fid, :ld, 50000.0, 'flood', 180)"),
            {"lid": str(uuid.uuid4()), "fid": seeded_farm_id,
             "ld": (date(2023, 6, 1) + timedelta(weeks=week)).isoformat()},
        )
    db_session.commit()
    return {"farm_id": seeded_farm_id, "crop_id": seeded_crop_id}


# ===========================================================================
# TEST SUITE
# ===========================================================================

class TestSchemaCreation:
    def test_all_tables_exist(self, sqlite_engine):
        from sqlalchemy import inspect
        tables = set(inspect(sqlite_engine).get_table_names())
        expected = {"farms","crops","yield_records","pest_records","irrigation_logs","soil_health"}
        assert expected.issubset(tables)

    def test_farms_columns(self, sqlite_engine):
        from sqlalchemy import inspect
        cols = {c["name"] for c in inspect(sqlite_engine).get_columns("farms")}
        assert {"farm_id","farmer_name","district","state","latitude","longitude","area_hectares"}.issubset(cols)

    def test_yield_records_columns(self, sqlite_engine):
        from sqlalchemy import inspect
        cols = {c["name"] for c in inspect(sqlite_engine).get_columns("yield_records")}
        assert {"record_id","farm_id","crop_id","season","year","yield_kg_per_hectare","harvest_date"}.issubset(cols)


class TestGetYieldHistory:
    def test_returns_dataframe(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_yield_history(seed_data["farm_id"], seed_data["crop_id"], years=10)
        assert isinstance(df, pd.DataFrame)

    def test_returns_expected_row_count(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_yield_history(seed_data["farm_id"], seed_data["crop_id"], years=10)
        assert len(df) == 3

    def test_expected_columns_present(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_yield_history(seed_data["farm_id"], seed_data["crop_id"], years=10)
        df_r = df.reset_index()
        assert "yield_kg_per_hectare" in df_r.columns
        assert "season" in df_r.columns

    def test_multiindex(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_yield_history(seed_data["farm_id"], seed_data["crop_id"], years=10)
        assert df.index.names == ["farm_id", "harvest_date"]

    def test_returns_empty_for_unknown_farm(self, sqlite_engine):
        conn = _make_connector(sqlite_engine)
        df = conn.get_yield_history(str(uuid.uuid4()), str(uuid.uuid4()), years=5)
        assert df.empty


class TestGetPestHistory:
    def test_date_range_filter(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_pest_history(seed_data["farm_id"], date(2023,7,1), date(2023,12,31))
        df_r = df.reset_index()
        assert all(df_r["detected_date"] >= pd.Timestamp("2023-07-01"))
        assert all(df_r["detected_date"] <= pd.Timestamp("2023-12-31"))

    def test_all_records_returned_for_wide_range(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_pest_history(seed_data["farm_id"], date(2020,1,1), date(2030,12,31))
        assert len(df) == 4

    def test_returns_empty_outside_range(self, sqlite_engine, seed_data):
        conn = _make_connector(sqlite_engine)
        df = conn.get_pest_history(seed_data["farm_id"], date(2010,1,1), date(2010,12,31))
        assert df.empty


class TestPestRiskScore:
    """Pest risk score: Σ(severity×area) / (N×5×100)."""

    def _score(self, engine, farm_id):
        conn = _make_connector(engine)
        df = conn.get_pest_history(farm_id, date(2020,1,1), date(2030,12,31))
        if df.empty:
            return None
        dr = df.reset_index()
        n = len(dr)
        ws = float((dr["severity"] * dr["affected_area_pct"]).sum())
        return round(ws / (n * 5.0 * 100.0), 4)

    def test_score_is_in_unit_interval(self, sqlite_engine, seed_data):
        score = self._score(sqlite_engine, seed_data["farm_id"])
        assert score is not None and 0.0 <= score <= 1.0

    def test_score_correct_formula(self, sqlite_engine, seed_data):
        # 3×20 + 5×45 + 2×10 + 4×30 = 425; N=4; max=2000 → 0.2125
        score = self._score(sqlite_engine, seed_data["farm_id"])
        assert score == pytest.approx(0.2125, rel=1e-3)

    def test_none_returned_for_unknown_farm(self, sqlite_engine):
        score = self._score(sqlite_engine, str(uuid.uuid4()))
        assert score is None


class TestExtractAll:
    def _ext(self, engine, farm_id):
        from preprocessing.historical_feature_extractor import HistoricalFeatureExtractor
        conn = _make_connector(engine)
        return HistoricalFeatureExtractor(conn).extract_all(farm_id)

    def test_returns_three_keys(self, sqlite_engine, seed_data):
        r = self._ext(sqlite_engine, seed_data["farm_id"])
        assert "forecaster_features" in r
        assert "vision_features" in r
        assert "llm_summary" in r

    def test_forecaster_features_is_dataframe(self, sqlite_engine, seed_data):
        r = self._ext(sqlite_engine, seed_data["farm_id"])
        assert isinstance(r["forecaster_features"], pd.DataFrame)

    def test_llm_summary_has_expected_keys(self, sqlite_engine, seed_data):
        r = self._ext(sqlite_engine, seed_data["farm_id"])
        expected = {"farm_id","last_season_yield_kg_ha","yield_vs_3yr_avg_pct",
                    "top_pest_risk","soil_deficiencies","irrigation_efficiency","generated_at"}
        assert expected.issubset(r["llm_summary"].keys())

    def test_soil_deficiencies_is_list(self, sqlite_engine, seed_data):
        r = self._ext(sqlite_engine, seed_data["farm_id"])
        assert isinstance(r["llm_summary"]["soil_deficiencies"], list)


# ===========================================================================
# FastAPI route tests
# ===========================================================================
@pytest.fixture(scope="module")
def test_client(sqlite_engine, seed_data):
    from fastapi import FastAPI
    from api.historical_db_routes import router, get_db

    app = FastAPI()
    app.include_router(router)

    # Capture engine in closure
    _engine = sqlite_engine

    def _override_get_db():
        conn = _make_connector(_engine)
        conn.open()
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as client:
        yield client, seed_data


class TestFastAPIRoutes:
    def test_yield_history_200(self, test_client):
        client, data = test_client
        resp = client.get(
            f"/history/yield/{data['farm_id']}",
            params={"crop_id": data["crop_id"], "years": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and len(body) == 3
        assert "yield_kg_per_hectare" in body[0]

    def test_yield_history_404_unknown_farm(self, test_client):
        client, _ = test_client
        resp = client.get(
            f"/history/yield/{uuid.uuid4()}",
            params={"crop_id": str(uuid.uuid4()), "years": 5},
        )
        assert resp.status_code == 404

    def test_pest_history_200(self, test_client):
        client, data = test_client
        resp = client.get(
            f"/history/pests/{data['farm_id']}",
            params={"start_date": "2020-01-01", "end_date": "2030-12-31"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and len(body) == 4

    def test_soil_history_200(self, test_client):
        client, data = test_client
        resp = client.get(f"/history/soil/{data['farm_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list) and "nitrogen_ppm" in body[0]

    def test_ingest_valid_yield_201(self, test_client, seed_data):
        client, data = test_client
        payload = {
            "table": "yield_records",
            "farm_id": data["farm_id"],
            "crop_id": data["crop_id"],
            "season": "Rabi",
            "year": 2025,
            "yield_kg_per_hectare": 4500.0,
            "harvest_date": "2025-04-15",
        }
        resp = client.post("/history/ingest", json=payload)
        assert resp.status_code == 201
        assert resp.json()["table"] == "yield_records"

    def test_ingest_invalid_payload_422(self, test_client):
        client, _ = test_client
        payload = {"table": "yield_records", "year": -1}  # missing required fields
        resp = client.post("/history/ingest", json=payload)
        assert resp.status_code == 422

    def test_ingest_invalid_table_422(self, test_client):
        client, _ = test_client
        payload = {"table": "hackers_table", "data": "bad"}
        resp = client.post("/history/ingest", json=payload)
        assert resp.status_code == 422


if __name__ == "__main__":
    import sys
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"] + sys.argv[1:]))
