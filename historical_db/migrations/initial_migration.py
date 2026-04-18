"""
historical_db/migrations/initial_migration.py — Alembic-compatible initial migration.

Design notes:
- This is a standalone migration script that can be run directly or through Alembic.
- It creates all 6 tables in the correct dependency order (no FK violations).
- Running standalone: `python -m historical_db.migrations.initial_migration`
- Running via Alembic: `alembic upgrade head`
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alembic revision metadata
# ---------------------------------------------------------------------------
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


# ---------------------------------------------------------------------------
# Raw DDL (mirrors schema.sql exactly so both pathways are in sync)
# ---------------------------------------------------------------------------
_UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

DO $$ BEGIN
    CREATE TYPE season_type AS ENUM ('Kharif', 'Rabi', 'Zaid');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE irrigation_method AS ENUM ('drip', 'flood', 'sprinkler');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS farms (
    farm_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farmer_name      VARCHAR(120) NOT NULL,
    district         VARCHAR(100) NOT NULL,
    state            VARCHAR(100) NOT NULL,
    latitude         DOUBLE PRECISION NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
    longitude        DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    area_hectares    DOUBLE PRECISION NOT NULL CHECK (area_hectares > 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farms_state_district ON farms (state, district);

CREATE TABLE IF NOT EXISTS crops (
    crop_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_name      VARCHAR(100) NOT NULL,
    crop_variety   VARCHAR(100),
    season_type    season_type NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_crop_name_variety UNIQUE (crop_name, crop_variety)
);

CREATE INDEX IF NOT EXISTS idx_crops_season ON crops (season_type);

CREATE TABLE IF NOT EXISTS yield_records (
    record_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id              UUID NOT NULL REFERENCES farms(farm_id)  ON DELETE CASCADE,
    crop_id              UUID NOT NULL REFERENCES crops(crop_id)  ON DELETE RESTRICT,
    season               season_type NOT NULL,
    year                 SMALLINT NOT NULL CHECK (year BETWEEN 1950 AND 2100),
    yield_kg_per_hectare DOUBLE PRECISION NOT NULL CHECK (yield_kg_per_hectare >= 0),
    harvest_date         DATE NOT NULL,
    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_yield_farm_year    ON yield_records (farm_id, year);
CREATE INDEX IF NOT EXISTS idx_yield_crop_season  ON yield_records (crop_id, season);
CREATE INDEX IF NOT EXISTS idx_yield_harvest_date ON yield_records (harvest_date);

CREATE TABLE IF NOT EXISTS pest_records (
    pest_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id              UUID NOT NULL REFERENCES farms(farm_id)  ON DELETE CASCADE,
    crop_id              UUID NOT NULL REFERENCES crops(crop_id)  ON DELETE RESTRICT,
    pest_name            VARCHAR(120) NOT NULL,
    severity             SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
    affected_area_pct    DOUBLE PRECISION NOT NULL CHECK (affected_area_pct BETWEEN 0 AND 100),
    detected_date        DATE NOT NULL,
    resolved_date        DATE,
    treatment_applied    TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_resolved_after_detected CHECK (
        resolved_date IS NULL OR resolved_date >= detected_date
    )
);

CREATE INDEX IF NOT EXISTS idx_pest_farm_detected ON pest_records (farm_id, detected_date);
CREATE INDEX IF NOT EXISTS idx_pest_severity      ON pest_records (severity);
CREATE INDEX IF NOT EXISTS idx_pest_crop          ON pest_records (crop_id);

CREATE TABLE IF NOT EXISTS irrigation_logs (
    log_id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id           UUID NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    log_date          DATE NOT NULL,
    water_used_liters DOUBLE PRECISION NOT NULL CHECK (water_used_liters >= 0),
    method            irrigation_method NOT NULL,
    duration_minutes  INTEGER NOT NULL CHECK (duration_minutes >= 0),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_irrigation_farm_date ON irrigation_logs (farm_id, log_date);
CREATE INDEX IF NOT EXISTS idx_irrigation_method    ON irrigation_logs (method);

CREATE TABLE IF NOT EXISTS soil_health (
    soil_id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id             UUID NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    recorded_date       DATE NOT NULL,
    ph_level            DOUBLE PRECISION CHECK (ph_level BETWEEN 0 AND 14),
    nitrogen_ppm        DOUBLE PRECISION CHECK (nitrogen_ppm >= 0),
    phosphorus_ppm      DOUBLE PRECISION CHECK (phosphorus_ppm >= 0),
    potassium_ppm       DOUBLE PRECISION CHECK (potassium_ppm >= 0),
    organic_matter_pct  DOUBLE PRECISION CHECK (organic_matter_pct BETWEEN 0 AND 100),
    moisture_pct        DOUBLE PRECISION CHECK (moisture_pct BETWEEN 0 AND 100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_soil_farm_date ON soil_health (farm_id, recorded_date);

CREATE OR REPLACE VIEW farm_latest_soil AS
SELECT DISTINCT ON (farm_id)
    soil_id, farm_id, recorded_date,
    ph_level, nitrogen_ppm, phosphorus_ppm, potassium_ppm,
    organic_matter_pct, moisture_pct
FROM soil_health
ORDER BY farm_id, recorded_date DESC;
"""

_DOWNGRADE_SQL = """
DROP VIEW  IF EXISTS farm_latest_soil;
DROP TABLE IF EXISTS soil_health;
DROP TABLE IF EXISTS irrigation_logs;
DROP TABLE IF EXISTS pest_records;
DROP TABLE IF EXISTS yield_records;
DROP TABLE IF EXISTS crops;
DROP TABLE IF EXISTS farms;
DROP TYPE  IF EXISTS irrigation_method;
DROP TYPE  IF EXISTS season_type;
"""


# ---------------------------------------------------------------------------
# Alembic hook functions
# ---------------------------------------------------------------------------
def upgrade(op=None) -> None:  # type: ignore[no-untyped-def]
    """Apply the migration forward."""
    if op is not None:
        # Running inside Alembic context
        op.execute(_UPGRADE_SQL)
    else:
        _run_standalone(upgrade=True)


def downgrade(op=None) -> None:  # type: ignore[no-untyped-def]
    """Reverse the migration."""
    if op is not None:
        op.execute(_DOWNGRADE_SQL)
    else:
        _run_standalone(upgrade=False)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------
def _run_standalone(upgrade: bool = True) -> None:
    """Run the migration directly using the standard env vars."""
    import sqlalchemy

    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {missing}")

    env = {k: os.environ[k] for k in required}
    dsn = (
        f"postgresql+psycopg2://{env['DB_USER']}:{env['DB_PASSWORD']}"
        f"@{env['DB_HOST']}:{env['DB_PORT']}/{env['DB_NAME']}"
    )
    engine = sqlalchemy.create_engine(dsn)
    sql = _UPGRADE_SQL if upgrade else _DOWNGRADE_SQL
    direction = "upgrade" if upgrade else "downgrade"
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text(sql))
    logger.info("Initial migration %s completed.", direction)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    action = sys.argv[1] if len(sys.argv) > 1 else "upgrade"
    if action == "downgrade":
        downgrade()
    else:
        upgrade()
