-- Durable scheduler cycles and alert deduplication. Queue transport stays in
-- Redis; PostgreSQL remains the source of operational truth.
CREATE TABLE IF NOT EXISTS sync.scheduler_cycles (
    scheduler_cycle_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cycle_key text NOT NULL UNIQUE CHECK (length(btrim(cycle_key)) > 0),
    state text NOT NULL CHECK (state IN ('dispatching', 'dispatched', 'completed', 'partial_failure')),
    registry_sha256 char(64) NOT NULL CHECK (registry_sha256 ~ '^[0-9a-f]{64}$'),
    eligible_source_ids jsonb NOT NULL CHECK (jsonb_typeof(eligible_source_ids) = 'array'),
    source_count integer NOT NULL CHECK (source_count >= 0),
    queued_count integer NOT NULL DEFAULT 0 CHECK (queued_count >= 0),
    completed_count integer NOT NULL DEFAULT 0 CHECK (completed_count >= 0),
    failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    review_required_count integer NOT NULL DEFAULT 0 CHECK (review_required_count >= 0),
    result_document jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(result_document) = 'object'),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (queued_count <= source_count),
    CHECK (completed_count + failed_count + review_required_count <= source_count),
    CHECK (
      (state IN ('dispatching', 'dispatched') AND finished_at IS NULL)
      OR (state IN ('completed', 'partial_failure') AND finished_at IS NOT NULL)
    ),
    CHECK (state NOT IN ('completed', 'partial_failure') OR completed_count + failed_count + review_required_count = source_count)
);

CREATE INDEX IF NOT EXISTS scheduler_cycles_updated
    ON sync.scheduler_cycles(updated_at DESC, scheduler_cycle_id DESC);

CREATE TABLE IF NOT EXISTS sync.scheduler_source_results (
    scheduler_source_result_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scheduler_cycle_id bigint NOT NULL REFERENCES sync.scheduler_cycles(scheduler_cycle_id) ON DELETE CASCADE,
    source_id text NOT NULL CHECK (length(btrim(source_id)) > 0),
    message_id text,
    state text NOT NULL CHECK (state IN ('queued', 'running', 'completed', 'review_required', 'failed')),
    sync_status text,
    sync_run_id bigint REFERENCES sync.source_sync_runs(sync_run_id),
    error_code text,
    result_document jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(result_document) = 'object'),
    queued_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scheduler_cycle_id, source_id)
);

CREATE INDEX IF NOT EXISTS scheduler_source_results_state
    ON sync.scheduler_source_results(state, source_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS sync.alert_deliveries (
    alert_delivery_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fingerprint char(64) NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    alert_code text NOT NULL CHECK (length(btrim(alert_code)) > 0),
    severity text NOT NULL CHECK (severity IN ('warning', 'critical')),
    subject_key text NOT NULL CHECK (length(btrim(subject_key)) > 0),
    state text NOT NULL CHECK (state IN ('open', 'resolved')),
    first_seen_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    last_notified_at timestamptz,
    notification_count integer NOT NULL DEFAULT 0 CHECK (notification_count >= 0),
    details jsonb NOT NULL CHECK (jsonb_typeof(details) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (fingerprint)
);

CREATE INDEX IF NOT EXISTS alert_deliveries_open
    ON sync.alert_deliveries(state, last_seen_at DESC, alert_delivery_id DESC);

CREATE OR REPLACE FUNCTION sync.touch_operations_row()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER scheduler_cycles_touch
BEFORE UPDATE ON sync.scheduler_cycles
FOR EACH ROW EXECUTE FUNCTION sync.touch_operations_row();

CREATE TRIGGER scheduler_source_results_touch
BEFORE UPDATE ON sync.scheduler_source_results
FOR EACH ROW EXECUTE FUNCTION sync.touch_operations_row();

CREATE TRIGGER alert_deliveries_touch
BEFORE UPDATE ON sync.alert_deliveries
FOR EACH ROW EXECUTE FUNCTION sync.touch_operations_row();
