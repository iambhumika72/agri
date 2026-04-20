-- historical_db/migrations/004_mandi_prices.sql
-- =============================================================================
-- Migration to add mandi_prices table for tracking Agmarknet commodity prices.
-- =============================================================================

CREATE TABLE IF NOT EXISTS mandi_prices (
    price_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state            VARCHAR(100) NOT NULL,
    district         VARCHAR(100) NOT NULL,
    market           VARCHAR(100) NOT NULL,
    commodity        VARCHAR(100) NOT NULL,
    variety          VARCHAR(100) NOT NULL,
    arrival_date     DATE NOT NULL,
    min_price        DOUBLE PRECISION NOT NULL CHECK (min_price >= 0),
    max_price        DOUBLE PRECISION NOT NULL CHECK (max_price >= 0),
    modal_price      DOUBLE PRECISION NOT NULL CHECK (modal_price >= 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Primary lookup for price forecasting: location + commodity
CREATE INDEX IF NOT EXISTS idx_mandi_lookup ON mandi_prices (state, district, commodity);

-- Historical trend index
CREATE INDEX IF NOT EXISTS idx_mandi_date ON mandi_prices (arrival_date);
