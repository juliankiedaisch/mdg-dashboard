-- Add scheduled sync jobs table for per-source automatic syncing.
-- Supports daily and weekly frequencies with configurable time/day.

CREATE TABLE IF NOT EXISTS assistant_scheduled_sync (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id       INTEGER NOT NULL,
    frequency       VARCHAR(20) NOT NULL,          -- 'daily' or 'weekly'
    time_of_day     VARCHAR(5) NOT NULL,            -- 'HH:MM'
    day_of_week     INTEGER,                        -- 0=Mon..6=Sun, NULL for daily
    active          BOOLEAN NOT NULL DEFAULT 1,
    last_run_at     TIMESTAMP,
    last_run_status VARCHAR(50),
    last_run_message TEXT,
    next_run_at     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scheduled_sync_source ON assistant_scheduled_sync(source_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_sync_active ON assistant_scheduled_sync(active);
CREATE INDEX IF NOT EXISTS idx_scheduled_sync_next_run ON assistant_scheduled_sync(next_run_at);
