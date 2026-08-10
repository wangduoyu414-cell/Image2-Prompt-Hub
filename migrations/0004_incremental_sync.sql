-- TASK-0016 adds mutable synchronization control state without changing any
-- static source-admission or immutable inventory evidence tables.
CREATE SCHEMA IF NOT EXISTS sync;

CREATE TABLE IF NOT EXISTS sync.source_sync_runs (
    sync_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id text NOT NULL CHECK (length(btrim(source_id)) > 0),
    previous_revision_sha char(40) CHECK (previous_revision_sha IS NULL OR previous_revision_sha ~ '^[0-9a-f]{40}$'),
    candidate_revision_sha char(40) NOT NULL CHECK (candidate_revision_sha ~ '^[0-9a-f]{40}$'),
    idempotency_key char(64) NOT NULL UNIQUE CHECK (idempotency_key ~ '^[0-9a-f]{64}$'),
    state text NOT NULL CHECK (state IN ('detected', 'no_change', 'extracting', 'imported', 'gated', 'review_required', 'ready', 'completed', 'failed')),
    authority jsonb NOT NULL CHECK (jsonb_typeof(authority) = 'object'),
    diff_document jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(diff_document) = 'object'),
    metrics jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metrics) = 'object'),
    package_idempotency_key text,
    source_adapter_run_id bigint REFERENCES inventory.source_adapter_runs(source_adapter_run_id),
    publication_version_id bigint REFERENCES content.publication_versions(publication_version_id),
    reason_code text,
    error_code text,
    result_document jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(result_document) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (source_id, candidate_revision_sha)
);

CREATE INDEX IF NOT EXISTS source_sync_runs_source_updated
    ON sync.source_sync_runs(source_id, updated_at DESC, sync_run_id DESC);
CREATE INDEX IF NOT EXISTS source_sync_runs_state
    ON sync.source_sync_runs(state, source_id);

CREATE TABLE IF NOT EXISTS sync.case_tombstone_events (
    case_tombstone_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sync_run_id bigint NOT NULL REFERENCES sync.source_sync_runs(sync_run_id),
    source_id text NOT NULL CHECK (length(btrim(source_id)) > 0),
    source_case_key text NOT NULL CHECK (length(btrim(source_case_key)) > 0),
    previous_revision_sha char(40) CHECK (previous_revision_sha IS NULL OR previous_revision_sha ~ '^[0-9a-f]{40}$'),
    candidate_revision_sha char(40) NOT NULL CHECK (candidate_revision_sha ~ '^[0-9a-f]{40}$'),
    event_type text NOT NULL CHECK (event_type IN ('removed', 'restored')),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sync_run_id, source_case_key, event_type)
);

CREATE INDEX IF NOT EXISTS case_tombstone_events_source_case
    ON sync.case_tombstone_events(source_id, source_case_key, created_at DESC);

CREATE TABLE IF NOT EXISTS content.publication_revision_selections (
    publication_revision_selection_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_id bigint NOT NULL REFERENCES content.publication_versions(publication_version_id) ON DELETE CASCADE,
    source_project_id bigint NOT NULL REFERENCES inventory.source_projects(source_project_id),
    source_revision_id bigint NOT NULL REFERENCES inventory.source_revisions(source_revision_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (publication_version_id, source_project_id),
    UNIQUE (publication_version_id, source_revision_id)
);

CREATE OR REPLACE FUNCTION sync.touch_source_sync_run()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    IF NEW.state = 'completed' AND NEW.completed_at IS NULL THEN
        NEW.completed_at := now();
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION sync.reject_tombstone_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'sync tombstone event rejects %', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE OR REPLACE FUNCTION content.require_building_publication_selection()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    version_state text;
    revision_project_id bigint;
BEGIN
    SELECT state INTO version_state
    FROM content.publication_versions
    WHERE publication_version_id = NEW.publication_version_id;
    IF version_state IS NULL OR version_state <> 'building' THEN
        RAISE EXCEPTION 'publication revision selections may only be inserted into a building version'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    SELECT source_project_id INTO revision_project_id
    FROM inventory.source_revisions
    WHERE source_revision_id = NEW.source_revision_id;
    IF revision_project_id IS NULL OR revision_project_id <> NEW.source_project_id THEN
        RAISE EXCEPTION 'publication revision selection crosses source project domains'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

-- Replace the original building-only gate so every new immutable publication
-- entry is also bound to the version's explicitly frozen source revisions.
CREATE OR REPLACE FUNCTION content.require_building_publication_entry()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    version_state text;
    display_policy text;
    entry_revision_id bigint;
BEGIN
    SELECT state INTO version_state
    FROM content.publication_versions
    WHERE publication_version_id = NEW.publication_version_id;
    IF version_state IS NULL OR version_state <> 'building' THEN
        RAISE EXCEPTION 'publication entries may only be inserted into a building version'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    SELECT source_revision_id INTO entry_revision_id
    FROM inventory.generation_examples AS generation
    JOIN inventory.source_case_versions AS case_version
      ON case_version.source_case_version_id = generation.source_case_version_id
    WHERE generation.generation_example_row_id = NEW.generation_example_row_id;
    IF entry_revision_id IS NULL OR NOT EXISTS (
        SELECT 1
        FROM content.publication_revision_selections
        WHERE publication_version_id = NEW.publication_version_id
          AND source_revision_id = entry_revision_id
    ) THEN
        RAISE EXCEPTION 'publication entry is absent from the explicit revision selection'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    display_policy := NEW.snapshot->'rights'->>'display_policy';
    IF display_policy = 'link_only'
       AND (
           jsonb_path_exists(NEW.snapshot, '$.outputs[*].object_key')
           OR jsonb_path_exists(NEW.snapshot, '$.outputs[*].object_bucket')
           OR jsonb_path_exists(NEW.snapshot, '$.inputs[*].object_key')
           OR jsonb_path_exists(NEW.snapshot, '$.inputs[*].object_bucket')
       ) THEN
        RAISE EXCEPTION 'link_only publication snapshot must not contain a mirrorable object path'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER source_sync_runs_touch
BEFORE UPDATE ON sync.source_sync_runs
FOR EACH ROW EXECUTE FUNCTION sync.touch_source_sync_run();
CREATE TRIGGER immutable_case_tombstone_events
BEFORE UPDATE OR DELETE ON sync.case_tombstone_events
FOR EACH ROW EXECUTE FUNCTION sync.reject_tombstone_mutation();
CREATE TRIGGER publication_revision_selections_only_building
BEFORE INSERT ON content.publication_revision_selections
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_selection();
CREATE TRIGGER immutable_publication_revision_selections
BEFORE UPDATE OR DELETE ON content.publication_revision_selections
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
