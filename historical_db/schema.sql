-- =============================================================================
-- Trace Agricultural AI System — Historical Database Schema
-- PostgreSQL with time-series optimised indexes
-- =============================================================================

-- ---------------------------------------------------------------------------
-- ENUM types
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE season_type AS ENUM ('Kharif', 'Rabi', 'Zaid');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE irrigation_method AS ENUM ('drip', 'flood', 'sprinkler');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- Extension: uuid-ossp for UUID generation
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Table: farms
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Table: crops
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crops (
    crop_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crop_name      VARCHAR(100) NOT NULL,
    crop_variety   VARCHAR(100),
    season_type    season_type NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_crop_name_variety UNIQUE (crop_name, crop_variety)
);

CREATE INDEX IF NOT EXISTS idx_crops_season ON crops (season_type);

-- ---------------------------------------------------------------------------
-- Table: yield_records
-- ---------------------------------------------------------------------------
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

-- Primary time-series query pattern: farm × year
CREATE INDEX IF NOT EXISTS idx_yield_farm_year       ON yield_records (farm_id, year);
CREATE INDEX IF NOT EXISTS idx_yield_crop_season     ON yield_records (crop_id, season);
CREATE INDEX IF NOT EXISTS idx_yield_harvest_date    ON yield_records (harvest_date);

-- ---------------------------------------------------------------------------
-- Table: pest_records
-- ---------------------------------------------------------------------------
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

-- Primary time-series query pattern: farm × detection window
CREATE INDEX IF NOT EXISTS idx_pest_farm_detected ON pest_records (farm_id, detected_date);
CREATE INDEX IF NOT EXISTS idx_pest_severity       ON pest_records (severity);
CREATE INDEX IF NOT EXISTS idx_pest_crop           ON pest_records (crop_id);

-- ---------------------------------------------------------------------------
-- Table: irrigation_logs
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Table: soil_health
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- Utility view: farm_latest_soil — handy for the LLM summary endpoint
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW farm_latest_soil AS
SELECT DISTINCT ON (farm_id)
    soil_id, farm_id, recorded_date,
    ph_level, nitrogen_ppm, phosphorus_ppm, potassium_ppm,
    organic_matter_pct, moisture_pct
FROM soil_health
ORDER BY farm_id, recorded_date DESC;
