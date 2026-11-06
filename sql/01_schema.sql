-- 01_schema.sql
-- Star schema for the simulated supplier POS data (all data is simulated).
-- Grain of fact_pos: one row per item x store x week.

DROP TABLE IF EXISTS fact_pos;
DROP TABLE IF EXISTS planogram;
DROP TABLE IF EXISTS dim_promo;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_store;
DROP TABLE IF EXISTS dim_item;

CREATE TABLE dim_item (
    item_id     INTEGER PRIMARY KEY,
    item_name   TEXT NOT NULL,
    category    TEXT NOT NULL,
    brand       TEXT NOT NULL,
    base_price  REAL NOT NULL,
    unit_cost   REAL NOT NULL
);

CREATE TABLE dim_store (
    store_id    INTEGER PRIMARY KEY,
    store_name  TEXT NOT NULL,
    region      TEXT NOT NULL,
    format      TEXT NOT NULL,
    cluster     TEXT NOT NULL            -- A / B / C, drives planogram space
);

CREATE TABLE dim_date (
    week_start  TEXT PRIMARY KEY,        -- Sunday, ISO date
    week_num    INTEGER NOT NULL,        -- 1..156
    month       TEXT NOT NULL,           -- YYYY-MM (month of the week's midpoint)
    year        INTEGER NOT NULL
);

CREATE TABLE dim_promo (
    promo_id     INTEGER PRIMARY KEY,
    item_id      INTEGER NOT NULL REFERENCES dim_item(item_id),
    start_week   TEXT NOT NULL,
    weeks        INTEGER NOT NULL,
    promo_type   TEXT NOT NULL,          -- TPR / Feature / Display
    discount_pct REAL NOT NULL
);

CREATE TABLE planogram (
    cluster    TEXT NOT NULL,
    item_id    INTEGER NOT NULL REFERENCES dim_item(item_id),
    facings    INTEGER NOT NULL,
    linear_ft  REAL NOT NULL,
    PRIMARY KEY (cluster, item_id)
);

CREATE TABLE fact_pos (
    week_start    TEXT    NOT NULL REFERENCES dim_date(week_start),
    item_id       INTEGER NOT NULL REFERENCES dim_item(item_id),
    store_id      INTEGER NOT NULL REFERENCES dim_store(store_id),
    units         INTEGER NOT NULL,
    net_sales     REAL    NOT NULL,
    cost          REAL    NOT NULL,
    in_stock_days INTEGER NOT NULL,      -- 0..7
    promo_flag    INTEGER NOT NULL,
    PRIMARY KEY (week_start, item_id, store_id)
);

CREATE INDEX ix_fact_item  ON fact_pos(item_id);
CREATE INDEX ix_fact_store ON fact_pos(store_id);
