-- TASK-0020 adds case-level review batches without changing immutable inventory
-- evidence, legacy generation-level rights events, or Publication v1.
CREATE TABLE IF NOT EXISTS content.rights_review_batches_v2 (
    rights_review_batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_case_version_id bigint NOT NULL REFERENCES inventory.source_case_versions(source_case_version_id),
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) > 0 AND length(idempotency_key) <= 200),
    request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    expected_latest_batch_id bigint REFERENCES content.rights_review_batches_v2(rights_review_batch_id),
    repository_license text NOT NULL CHECK (length(btrim(repository_license)) > 0),
    prompt_rights text NOT NULL CHECK (prompt_rights IN ('approved', 'unknown', 'internal_only', 'blocked')),
    author text NOT NULL CHECK (length(btrim(author)) > 0),
    original_url text NOT NULL CHECK (length(btrim(original_url)) > 0),
    evidence_url text NOT NULL CHECK (length(btrim(evidence_url)) > 0),
    reviewer text NOT NULL CHECK (length(btrim(reviewer)) > 0),
    reviewed_at timestamptz NOT NULL,
    review_note text NOT NULL CHECK (length(btrim(review_note)) > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS rights_review_batches_v2_latest
    ON content.rights_review_batches_v2(source_case_version_id, reviewed_at DESC, rights_review_batch_id DESC);

CREATE TABLE IF NOT EXISTS content.rights_review_output_decisions_v2 (
    rights_review_output_decision_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rights_review_batch_id bigint NOT NULL REFERENCES content.rights_review_batches_v2(rights_review_batch_id),
    generation_output_id bigint NOT NULL REFERENCES inventory.generation_outputs(generation_output_id),
    asset_rights text NOT NULL CHECK (asset_rights IN ('approved', 'unknown', 'internal_only', 'blocked')),
    display_policy text NOT NULL CHECK (display_policy IN ('mirror_allowed', 'attribution_required', 'link_only', 'internal_only', 'blocked')),
    public_display_role text NOT NULL CHECK (public_display_role IN ('public_primary', 'public_gallery', 'hidden')),
    decision_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (rights_review_batch_id, generation_output_id),
    CHECK (
        public_display_role = 'hidden'
        OR (
            asset_rights = 'approved'
            AND display_policy IN ('mirror_allowed', 'attribution_required', 'link_only')
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS one_public_primary_per_review_batch_v2
    ON content.rights_review_output_decisions_v2(rights_review_batch_id)
    WHERE public_display_role = 'public_primary';

CREATE OR REPLACE FUNCTION content.require_review_batch_v2_authority()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    latest_id bigint;
    latest_reviewed_at timestamptz;
    expected_case_id bigint;
    target_project_id bigint;
    target_run_id bigint;
    latest_run_id bigint;
BEGIN
    IF NEW.reviewed_at > now() THEN
        RAISE EXCEPTION 'rights review reviewed_at cannot be in the future'
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT revision.source_project_id, version.source_adapter_run_id
    INTO target_project_id, target_run_id
    FROM inventory.source_case_versions AS version
    JOIN inventory.source_revisions AS revision
      ON revision.source_revision_id=version.source_revision_id
    WHERE version.source_case_version_id=NEW.source_case_version_id;

    IF target_project_id IS NULL OR target_run_id IS NULL THEN
        RAISE EXCEPTION 'rights review target source case version does not exist'
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('image2-ready-review-project-v2:' || target_project_id::text, 0));
    PERFORM pg_advisory_xact_lock(hashtextextended('image2-rights-review-v2:' || NEW.source_case_version_id::text, 0));

    SELECT max(run.source_adapter_run_id)
    INTO latest_run_id
    FROM inventory.source_adapter_runs AS run
    JOIN inventory.source_revisions AS revision
      ON revision.source_revision_id=run.source_revision_id
    WHERE revision.source_project_id=target_project_id AND run.state='ready';

    IF target_run_id IS DISTINCT FROM latest_run_id THEN
        RAISE EXCEPTION 'rights review target is not the latest ready source revision'
            USING ERRCODE = 'serialization_failure';
    END IF;

    SELECT rights_review_batch_id, reviewed_at
    INTO latest_id, latest_reviewed_at
    FROM content.rights_review_batches_v2
    WHERE source_case_version_id = NEW.source_case_version_id
    ORDER BY reviewed_at DESC, rights_review_batch_id DESC
    LIMIT 1;

    IF latest_id IS DISTINCT FROM NEW.expected_latest_batch_id THEN
        RAISE EXCEPTION 'rights review expected latest batch is stale'
            USING ERRCODE = 'serialization_failure';
    END IF;
    IF latest_reviewed_at IS NOT NULL AND NEW.reviewed_at < latest_reviewed_at THEN
        RAISE EXCEPTION 'rights review reviewed_at precedes the latest batch'
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.expected_latest_batch_id IS NOT NULL THEN
        SELECT source_case_version_id INTO expected_case_id
        FROM content.rights_review_batches_v2
        WHERE rights_review_batch_id = NEW.expected_latest_batch_id;
        IF expected_case_id IS NULL OR expected_case_id <> NEW.source_case_version_id THEN
            RAISE EXCEPTION 'rights review expected latest batch crosses source case versions'
                USING ERRCODE = 'foreign_key_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.serialize_ready_run_against_review_v2()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_project_id bigint;
BEGIN
    SELECT source_project_id INTO target_project_id
    FROM inventory.source_revisions
    WHERE source_revision_id=NEW.source_revision_id;
    IF target_project_id IS NULL THEN
        RAISE EXCEPTION 'ready adapter run revision does not exist'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('image2-ready-review-project-v2:' || target_project_id::text, 0));
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_review_output_v2_same_case()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    batch_case_id bigint;
    output_case_id bigint;
BEGIN
    SELECT source_case_version_id INTO batch_case_id
    FROM content.rights_review_batches_v2
    WHERE rights_review_batch_id = NEW.rights_review_batch_id;

    SELECT generation.source_case_version_id INTO output_case_id
    FROM inventory.generation_outputs AS output
    JOIN inventory.generation_examples AS generation
      ON generation.generation_example_row_id = output.generation_example_row_id
    WHERE output.generation_output_id = NEW.generation_output_id;

    IF batch_case_id IS NULL OR output_case_id IS NULL OR batch_case_id <> output_case_id THEN
        RAISE EXCEPTION 'rights review output decision crosses source case versions'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_complete_review_batch_v2()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_count integer;
    actual_count integer;
BEGIN
    SELECT count(*) INTO expected_count
    FROM inventory.generation_examples AS generation
    JOIN inventory.generation_outputs AS output
      ON output.generation_example_row_id = generation.generation_example_row_id
    WHERE generation.source_case_version_id = NEW.source_case_version_id;

    SELECT count(*) INTO actual_count
    FROM content.rights_review_output_decisions_v2
    WHERE rights_review_batch_id = NEW.rights_review_batch_id;

    IF expected_count = 0 OR actual_count <> expected_count THEN
        RAISE EXCEPTION 'rights review batch must cover the exact source case output set'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER rights_review_batch_v2_authority
BEFORE INSERT ON content.rights_review_batches_v2
FOR EACH ROW EXECUTE FUNCTION content.require_review_batch_v2_authority();

CREATE TRIGGER serialize_ready_run_against_review_v2
BEFORE INSERT ON inventory.source_adapter_runs
FOR EACH ROW EXECUTE FUNCTION content.serialize_ready_run_against_review_v2();

CREATE TRIGGER rights_review_output_v2_same_case
BEFORE INSERT ON content.rights_review_output_decisions_v2
FOR EACH ROW EXECUTE FUNCTION content.require_review_output_v2_same_case();

CREATE CONSTRAINT TRIGGER rights_review_batch_v2_complete
AFTER INSERT ON content.rights_review_batches_v2
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION content.require_complete_review_batch_v2();

CREATE TRIGGER immutable_rights_review_batches_v2
BEFORE UPDATE OR DELETE ON content.rights_review_batches_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();

CREATE TRIGGER immutable_rights_review_output_decisions_v2
BEFORE UPDATE OR DELETE ON content.rights_review_output_decisions_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
