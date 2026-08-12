-- Scheduler liveness is independent from whether any source is currently due.
-- A singleton heartbeat prevents an intentionally idle scheduler from being
-- mistaken for a stalled one while keeping PostgreSQL as operational truth.
CREATE TABLE IF NOT EXISTS sync.scheduler_runtime (
    runtime_key text PRIMARY KEY CHECK (runtime_key = 'primary'),
    last_heartbeat_at timestamptz NOT NULL,
    last_status text NOT NULL CHECK (last_status IN ('starting', 'idle', 'dispatching', 'recovering', 'error')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER scheduler_runtime_touch
BEFORE UPDATE ON sync.scheduler_runtime
FOR EACH ROW EXECUTE FUNCTION sync.touch_operations_row();
