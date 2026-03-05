-- Enable uuid extension (required for generated UUIDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Event store table
CREATE TABLE IF NOT EXISTS events (
  event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  aggregate_id VARCHAR(255) NOT NULL,
  aggregate_type VARCHAR(255) NOT NULL,
  event_type VARCHAR(255) NOT NULL,
  event_data JSONB NOT NULL,
  event_number INTEGER NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (aggregate_id, event_number)
);

CREATE INDEX IF NOT EXISTS idx_events_aggregate_id ON events (aggregate_id);

-- Snapshots table
CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  aggregate_id VARCHAR(255) NOT NULL UNIQUE,
  snapshot_data JSONB NOT NULL,
  last_event_number INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_aggregate_id ON snapshots (aggregate_id);

-- Projection: account_summaries
CREATE TABLE IF NOT EXISTS account_summaries (
  account_id VARCHAR(255) PRIMARY KEY,
  owner_name VARCHAR(255) NOT NULL,
  balance DECIMAL(19,4) NOT NULL DEFAULT 0,
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',
  status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
  version BIGINT NOT NULL DEFAULT 0
);

-- Projection: transaction_history
CREATE TABLE IF NOT EXISTS transaction_history (
  transaction_id VARCHAR(255) PRIMARY KEY,
  account_id VARCHAR(255) NOT NULL,
  type VARCHAR(50) NOT NULL,
  amount DECIMAL(19,4) NOT NULL,
  description TEXT,
  timestamp TIMESTAMPTZ NOT NULL
);
 
