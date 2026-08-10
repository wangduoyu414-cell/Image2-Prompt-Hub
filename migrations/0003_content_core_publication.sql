-- TASK-0013 is intentionally additive: immutable Source/Evidence remains in
-- inventory, while Content Core owns its review decisions and public snapshots.
CREATE SCHEMA IF NOT EXISTS content;

CREATE TABLE IF NOT EXISTS content.canonical_cases (
    canonical_case_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_key char(64) NOT NULL UNIQUE CHECK (canonical_key ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.canonical_memberships (
    canonical_membership_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_case_id bigint NOT NULL REFERENCES content.canonical_cases(canonical_case_id),
    generation_example_row_id bigint NOT NULL REFERENCES inventory.generation_examples(generation_example_row_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (generation_example_row_id),
    UNIQUE (canonical_case_id, generation_example_row_id)
);

CREATE TABLE IF NOT EXISTS content.taxonomy_assignments (
    taxonomy_assignment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    canonical_case_id bigint NOT NULL REFERENCES content.canonical_cases(canonical_case_id),
    taxonomy_version text NOT NULL CHECK (length(btrim(taxonomy_version)) > 0),
    classifier_version text NOT NULL CHECK (length(btrim(classifier_version)) > 0),
    tag_value text NOT NULL CHECK (length(btrim(tag_value)) > 0),
    tag_source text NOT NULL CHECK (tag_source IN ('source_tag', 'system_facet', 'editor', 'blocked')),
    confidence numeric(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (canonical_case_id, taxonomy_version, classifier_version, tag_value, tag_source)
);

CREATE TABLE IF NOT EXISTS content.rights_review_events (
    rights_review_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_example_row_id bigint NOT NULL REFERENCES inventory.generation_examples(generation_example_row_id),
    repository_license text NOT NULL CHECK (length(btrim(repository_license)) > 0),
    prompt_rights text NOT NULL CHECK (prompt_rights IN ('approved', 'unknown', 'internal_only', 'blocked')),
    asset_rights text NOT NULL CHECK (asset_rights IN ('approved', 'unknown', 'internal_only', 'blocked')),
    author text NOT NULL CHECK (length(btrim(author)) > 0),
    original_url text NOT NULL CHECK (length(btrim(original_url)) > 0),
    evidence_url text NOT NULL CHECK (length(btrim(evidence_url)) > 0),
    reviewer text NOT NULL CHECK (length(btrim(reviewer)) > 0),
    reviewed_at timestamptz NOT NULL,
    display_policy text NOT NULL CHECK (display_policy IN ('mirror_allowed', 'attribution_required', 'link_only', 'internal_only', 'blocked')),
    review_note text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rights_review_events_latest
    ON content.rights_review_events(generation_example_row_id, reviewed_at DESC, rights_review_event_id DESC);

CREATE TABLE IF NOT EXISTS content.publication_versions (
    publication_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state text NOT NULL CHECK (state IN ('building', 'ready', 'active', 'superseded', 'failed')),
    content_digest char(64) CHECK (content_digest IS NULL OR content_digest ~ '^[0-9a-f]{64}$'),
    included_count integer NOT NULL DEFAULT 0 CHECK (included_count >= 0),
    excluded_count integer NOT NULL DEFAULT 0 CHECK (excluded_count >= 0),
    reason_counts jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(reason_counts) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (
        (state = 'building' AND content_digest IS NULL AND completed_at IS NULL)
        OR (state IN ('ready', 'active', 'superseded') AND content_digest IS NOT NULL AND completed_at IS NOT NULL)
        OR state = 'failed'
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_publication_version
    ON content.publication_versions ((true)) WHERE state = 'active';

CREATE TABLE IF NOT EXISTS content.publication_entries (
    publication_entry_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_id bigint NOT NULL REFERENCES content.publication_versions(publication_version_id) ON DELETE CASCADE,
    canonical_case_id bigint NOT NULL REFERENCES content.canonical_cases(canonical_case_id),
    generation_example_row_id bigint NOT NULL REFERENCES inventory.generation_examples(generation_example_row_id),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    snapshot_digest char(64) NOT NULL CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (publication_version_id, generation_example_row_id)
);

CREATE TABLE IF NOT EXISTS content.publication_current (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    publication_version_id bigint NOT NULL REFERENCES content.publication_versions(publication_version_id),
    activated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.publication_outbox (
    publication_outbox_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_id bigint NOT NULL REFERENCES content.publication_versions(publication_version_id),
    event_type text NOT NULL CHECK (event_type IN ('publication_activated', 'publication_rolled_back')),
    event_document jsonb NOT NULL CHECK (jsonb_typeof(event_document) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION content.reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'content immutable table % rejects %', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE OR REPLACE FUNCTION content.enforce_publication_version_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state <> 'building' THEN
            RAISE EXCEPTION 'completed publication versions cannot be deleted'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.state = 'building' THEN
        IF NEW.state NOT IN ('building', 'ready', 'failed') THEN
            RAISE EXCEPTION 'building publication version has an invalid state transition'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.state = 'ready' AND NEW.state = 'active'
       AND (to_jsonb(NEW) - 'state') = (to_jsonb(OLD) - 'state') THEN
        RETURN NEW;
    END IF;
    IF OLD.state = 'active' AND NEW.state = 'superseded'
       AND (to_jsonb(NEW) - 'state') = (to_jsonb(OLD) - 'state') THEN
        RETURN NEW;
    END IF;
    IF OLD.state = 'superseded' AND NEW.state = 'active'
       AND (to_jsonb(NEW) - 'state') = (to_jsonb(OLD) - 'state') THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'completed publication version is immutable except atomic pointer state transitions'
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE OR REPLACE FUNCTION content.require_building_publication_entry()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    version_state text;
    display_policy text;
BEGIN
    SELECT state INTO version_state
    FROM content.publication_versions
    WHERE publication_version_id = NEW.publication_version_id;
    IF version_state IS NULL OR version_state <> 'building' THEN
        RAISE EXCEPTION 'publication entries may only be inserted into a building version'
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

CREATE OR REPLACE FUNCTION content.require_review_not_future()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.reviewed_at > statement_timestamp() THEN
        RAISE EXCEPTION 'rights review event cannot be future dated'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_current_active_version()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    version_state text;
BEGIN
    SELECT state INTO version_state
    FROM content.publication_versions
    WHERE publication_version_id = NEW.publication_version_id;
    IF version_state IS NULL OR version_state <> 'active' THEN
        RAISE EXCEPTION 'current publication pointer must reference an active completed version'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER immutable_canonical_cases
BEFORE UPDATE OR DELETE ON content.canonical_cases
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_canonical_memberships
BEFORE UPDATE OR DELETE ON content.canonical_memberships
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_taxonomy_assignments
BEFORE UPDATE OR DELETE ON content.taxonomy_assignments
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_rights_review_events
BEFORE UPDATE OR DELETE ON content.rights_review_events
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER rights_review_not_future
BEFORE INSERT ON content.rights_review_events
FOR EACH ROW EXECUTE FUNCTION content.require_review_not_future();
CREATE TRIGGER publication_versions_transition
BEFORE UPDATE OR DELETE ON content.publication_versions
FOR EACH ROW EXECUTE FUNCTION content.enforce_publication_version_transition();
CREATE TRIGGER publication_entries_only_building
BEFORE INSERT ON content.publication_entries
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_entry();
CREATE TRIGGER immutable_publication_entries
BEFORE UPDATE OR DELETE ON content.publication_entries
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER current_publication_active_only
BEFORE INSERT OR UPDATE ON content.publication_current
FOR EACH ROW EXECUTE FUNCTION content.require_current_active_version();
CREATE TRIGGER immutable_publication_outbox
BEFORE UPDATE OR DELETE ON content.publication_outbox
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
