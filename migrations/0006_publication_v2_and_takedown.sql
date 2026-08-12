-- Public v2 is additive and leaves Publication/API/Web v1 current untouched.
CREATE TABLE IF NOT EXISTS content.publication_versions_v2 (
    publication_version_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state text NOT NULL CHECK (state IN ('building', 'ready', 'active', 'superseded', 'failed')),
    content_digest char(64) CHECK (content_digest IS NULL OR content_digest ~ '^[0-9a-f]{64}$'),
    included_count integer NOT NULL DEFAULT 0 CHECK (included_count >= 0),
    excluded_count integer NOT NULL DEFAULT 0 CHECK (excluded_count >= 0),
    reason_counts jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(reason_counts) = 'object'),
    created_by text NOT NULL CHECK (length(btrim(created_by)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK (
        (state = 'building' AND content_digest IS NULL AND completed_at IS NULL)
        OR (state IN ('ready', 'active', 'superseded') AND content_digest IS NOT NULL AND completed_at IS NOT NULL)
        OR state = 'failed'
    )
);

CREATE TABLE IF NOT EXISTS content.publication_build_requests_v2 (
    publication_build_request_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) > 0),
    request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    publication_version_v2_id bigint NOT NULL REFERENCES content.publication_versions_v2(publication_version_v2_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_publication_version_v2
    ON content.publication_versions_v2 ((true)) WHERE state='active';

CREATE TABLE IF NOT EXISTS content.publication_revision_selections_v2 (
    publication_revision_selection_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_v2_id bigint NOT NULL REFERENCES content.publication_versions_v2(publication_version_v2_id) ON DELETE CASCADE,
    source_project_id bigint NOT NULL REFERENCES inventory.source_projects(source_project_id),
    source_revision_id bigint NOT NULL REFERENCES inventory.source_revisions(source_revision_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (publication_version_v2_id, source_project_id)
);

CREATE TABLE IF NOT EXISTS content.publication_entries_v2 (
    publication_entry_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_v2_id bigint NOT NULL REFERENCES content.publication_versions_v2(publication_version_v2_id) ON DELETE CASCADE,
    public_case_key char(64) NOT NULL CHECK (public_case_key ~ '^[0-9a-f]{64}$'),
    source_case_version_id bigint NOT NULL REFERENCES inventory.source_case_versions(source_case_version_id),
    rights_review_batch_id bigint NOT NULL REFERENCES content.rights_review_batches_v2(rights_review_batch_id),
    snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    snapshot_digest char(64) NOT NULL CHECK (snapshot_digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (publication_version_v2_id, public_case_key),
    UNIQUE (publication_version_v2_id, source_case_version_id)
);

CREATE TABLE IF NOT EXISTS content.publication_assets_v2 (
    publication_asset_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_v2_id bigint NOT NULL,
    public_case_key char(64) NOT NULL CHECK (public_case_key ~ '^[0-9a-f]{64}$'),
    generation_output_id bigint NOT NULL REFERENCES inventory.generation_outputs(generation_output_id),
    content_sha256 char(64) NOT NULL REFERENCES inventory.assets(content_sha256),
    object_bucket text,
    object_key text,
    media_type text NOT NULL CHECK (media_type LIKE 'image/%'),
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    display_policy text NOT NULL CHECK (display_policy IN ('mirror_allowed', 'attribution_required', 'link_only')),
    public_display_role text NOT NULL CHECK (public_display_role IN ('public_primary', 'public_gallery')),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (publication_version_v2_id, public_case_key)
      REFERENCES content.publication_entries_v2(publication_version_v2_id, public_case_key) ON DELETE CASCADE,
    UNIQUE (publication_version_v2_id, generation_output_id),
    CHECK (
      (display_policy IN ('mirror_allowed', 'attribution_required') AND object_bucket IS NOT NULL AND object_key IS NOT NULL)
      OR (display_policy='link_only' AND object_bucket IS NULL AND object_key IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS content.publication_current_v2 (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    publication_version_v2_id bigint NOT NULL REFERENCES content.publication_versions_v2(publication_version_v2_id),
    activated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.publication_outbox_v2 (
    publication_outbox_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_v2_id bigint NOT NULL REFERENCES content.publication_versions_v2(publication_version_v2_id),
    event_type text NOT NULL CHECK (event_type IN ('publication_v2_activated', 'publication_v2_rolled_back')),
    event_document jsonb NOT NULL CHECK (jsonb_typeof(event_document) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS content.takedown_requests_v2 (
    takedown_request_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE CHECK (length(btrim(idempotency_key)) > 0),
    request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    scope_type text NOT NULL CHECK (scope_type IN ('asset', 'prompt', 'case', 'source')),
    scope_key text NOT NULL CHECK (length(btrim(scope_key)) > 0),
    action text NOT NULL CHECK (action IN ('remove', 'restore')),
    reason_code text NOT NULL CHECK (length(btrim(reason_code)) > 0),
    evidence_url text NOT NULL CHECK (length(btrim(evidence_url)) > 0),
    note text NOT NULL CHECK (length(btrim(note)) > 0),
    requested_by text NOT NULL CHECK (length(btrim(requested_by)) > 0),
    requested_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (scope_type <> 'asset' OR scope_key ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS takedown_requests_v2_effective
    ON content.takedown_requests_v2(scope_type, scope_key, requested_at DESC, takedown_request_v2_id DESC);

CREATE TABLE IF NOT EXISTS content.publication_exclusions_v2 (
    publication_exclusion_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_v2_id bigint NOT NULL REFERENCES content.publication_versions_v2(publication_version_v2_id) ON DELETE CASCADE,
    source_case_version_id bigint NOT NULL REFERENCES inventory.source_case_versions(source_case_version_id),
    reason_code text NOT NULL CHECK (reason_code IN (
      'candidate_invalid', 'review_pending', 'review_review_required',
      'review_internal_only', 'review_blocked', 'takedown_asset',
      'takedown_asset_primary', 'takedown_prompt', 'takedown_case', 'takedown_source'
    )),
    takedown_request_v2_id bigint REFERENCES content.takedown_requests_v2(takedown_request_v2_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (publication_version_v2_id, source_case_version_id)
);

CREATE TABLE IF NOT EXISTS content.publication_takedown_applications_v2 (
    publication_takedown_application_v2_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    publication_version_v2_id bigint NOT NULL,
    public_case_key char(64) NOT NULL CHECK (public_case_key ~ '^[0-9a-f]{64}$'),
    takedown_request_v2_id bigint NOT NULL REFERENCES content.takedown_requests_v2(takedown_request_v2_id),
    effect_type text NOT NULL CHECK (effect_type='asset_removed'),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (publication_version_v2_id, public_case_key)
      REFERENCES content.publication_entries_v2(publication_version_v2_id, public_case_key) ON DELETE CASCADE,
    UNIQUE (publication_version_v2_id, public_case_key, takedown_request_v2_id)
);

CREATE OR REPLACE FUNCTION content.enforce_publication_version_v2_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        IF OLD.state <> 'building' THEN
            RAISE EXCEPTION 'completed publication v2 versions cannot be deleted' USING ERRCODE='integrity_constraint_violation';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.state='building' AND NEW.state IN ('building', 'ready', 'failed') THEN RETURN NEW; END IF;
    IF OLD.state='ready' AND NEW.state='active' AND (to_jsonb(NEW)-'state')=(to_jsonb(OLD)-'state') THEN RETURN NEW; END IF;
    IF OLD.state='active' AND NEW.state='superseded' AND (to_jsonb(NEW)-'state')=(to_jsonb(OLD)-'state') THEN RETURN NEW; END IF;
    IF OLD.state='superseded' AND NEW.state='active' AND (to_jsonb(NEW)-'state')=(to_jsonb(OLD)-'state') THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'completed publication v2 version is immutable except pointer transitions' USING ERRCODE='integrity_constraint_violation';
END;
$$;

CREATE OR REPLACE FUNCTION content.require_building_publication_v2_child()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_state text;
BEGIN
    SELECT state INTO version_state FROM content.publication_versions_v2 WHERE publication_version_v2_id=NEW.publication_version_v2_id;
    IF version_state IS NULL OR version_state <> 'building' THEN
        RAISE EXCEPTION 'publication v2 children require a building version' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_building_publication_v2_asset()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_state text;
BEGIN
    SELECT state INTO version_state FROM content.publication_versions_v2 WHERE publication_version_v2_id=NEW.publication_version_v2_id;
    IF version_state IS NULL OR version_state <> 'building' THEN
        RAISE EXCEPTION 'publication v2 assets require a building version' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_publication_v2_selection_domain()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE revision_project_id bigint;
BEGIN
    SELECT source_project_id INTO revision_project_id FROM inventory.source_revisions WHERE source_revision_id=NEW.source_revision_id;
    IF revision_project_id IS NULL OR revision_project_id <> NEW.source_project_id THEN
        RAISE EXCEPTION 'publication v2 revision selection crosses source project domain' USING ERRCODE='foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_publication_v2_entry_authority()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE batch_case_version_id bigint; selected_count integer;
BEGIN
    SELECT source_case_version_id INTO batch_case_version_id FROM content.rights_review_batches_v2 WHERE rights_review_batch_id=NEW.rights_review_batch_id;
    IF batch_case_version_id IS NULL OR batch_case_version_id <> NEW.source_case_version_id THEN
        RAISE EXCEPTION 'publication v2 entry review authority crosses source case' USING ERRCODE='foreign_key_violation';
    END IF;
    SELECT count(*) INTO selected_count
    FROM inventory.source_case_versions version
    JOIN inventory.source_revisions revision ON revision.source_revision_id=version.source_revision_id
    JOIN content.publication_revision_selections_v2 selection
      ON selection.publication_version_v2_id=NEW.publication_version_v2_id
     AND selection.source_project_id=revision.source_project_id
     AND selection.source_revision_id=revision.source_revision_id
    WHERE version.source_case_version_id=NEW.source_case_version_id;
    IF selected_count <> 1 THEN
        RAISE EXCEPTION 'publication v2 entry is absent from its explicit revision selection' USING ERRCODE='integrity_constraint_violation';
    END IF;
    IF NEW.snapshot->>'schema_version' <> 'public-case-publication-entry/v2'
       OR NEW.snapshot->>'public_case_key' <> NEW.public_case_key
       OR (NEW.snapshot->>'source_case_version_id')::bigint <> NEW.source_case_version_id
       OR (NEW.snapshot->>'rights_review_batch_id')::bigint <> NEW.rights_review_batch_id THEN
        RAISE EXCEPTION 'publication v2 entry columns do not match its frozen snapshot' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_publication_v2_asset_authority()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE matched_output jsonb; inventory_asset record;
BEGIN
    SELECT output_item INTO matched_output
    FROM content.publication_entries_v2 entry
    CROSS JOIN LATERAL jsonb_array_elements(entry.snapshot->'generation_members') member
    CROSS JOIN LATERAL jsonb_array_elements(member->'public_outputs') output_item
    WHERE entry.publication_version_v2_id=NEW.publication_version_v2_id
      AND entry.public_case_key=NEW.public_case_key
      AND (output_item->>'generation_output_id')::bigint=NEW.generation_output_id;
    IF matched_output IS NULL
       OR matched_output->>'content_sha256' <> NEW.content_sha256
       OR matched_output->>'media_type' <> NEW.media_type
       OR (matched_output->>'byte_size')::bigint <> NEW.byte_size
       OR matched_output->>'public_display_role' <> NEW.public_display_role
       OR matched_output->'rights'->>'display_policy' <> NEW.display_policy THEN
        RAISE EXCEPTION 'publication v2 private asset manifest does not match its public snapshot' USING ERRCODE='integrity_constraint_violation';
    END IF;
    SELECT asset.content_sha256, asset.object_bucket, asset.object_key, asset.media_type, asset.byte_size
      INTO inventory_asset
    FROM inventory.generation_outputs generation_output
    JOIN inventory.asset_sources source ON source.asset_source_id=generation_output.asset_source_id
    JOIN inventory.assets asset ON asset.content_sha256=source.content_sha256
    WHERE generation_output.generation_output_id=NEW.generation_output_id;
    IF inventory_asset IS NULL
       OR inventory_asset.content_sha256 <> NEW.content_sha256
       OR inventory_asset.media_type <> NEW.media_type
       OR inventory_asset.byte_size <> NEW.byte_size
       OR (
          NEW.display_policy IN ('mirror_allowed', 'attribution_required')
          AND (inventory_asset.object_bucket <> NEW.object_bucket OR inventory_asset.object_key <> NEW.object_key)
       ) THEN
        RAISE EXCEPTION 'publication v2 private asset manifest does not match immutable inventory' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_takedown_v2_not_future()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.requested_at > statement_timestamp() THEN
        RAISE EXCEPTION 'takedown request cannot be future dated' USING ERRCODE='check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_publication_v2_exclusion_authority()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE selected_count integer; takedown_scope text; takedown_key text; takedown_action text;
        case_source_id text; case_native_key text; prompt_native_id text; matched_count integer;
BEGIN
    SELECT count(*) INTO selected_count
    FROM inventory.source_case_versions version
    JOIN inventory.source_revisions revision ON revision.source_revision_id=version.source_revision_id
    JOIN content.publication_revision_selections_v2 selection
      ON selection.publication_version_v2_id=NEW.publication_version_v2_id
     AND selection.source_project_id=revision.source_project_id
     AND selection.source_revision_id=revision.source_revision_id
    WHERE version.source_case_version_id=NEW.source_case_version_id;
    IF selected_count <> 1 THEN
        RAISE EXCEPTION 'publication v2 exclusion is absent from its explicit revision selection' USING ERRCODE='integrity_constraint_violation';
    END IF;
    IF NEW.reason_code LIKE 'takedown_%' THEN
        SELECT scope_type, scope_key, action INTO takedown_scope, takedown_key, takedown_action
        FROM content.takedown_requests_v2 WHERE takedown_request_v2_id=NEW.takedown_request_v2_id;
        IF takedown_scope IS NULL OR takedown_action <> 'remove'
           OR NEW.reason_code NOT IN ('takedown_' || takedown_scope, 'takedown_asset_primary') THEN
            RAISE EXCEPTION 'publication v2 takedown exclusion lacks matching authority' USING ERRCODE='integrity_constraint_violation';
        END IF;
        SELECT project.source_id, source_case.source_case_key, prompt.prompt_id
          INTO case_source_id, case_native_key, prompt_native_id
        FROM inventory.source_case_versions version
        JOIN inventory.source_cases source_case ON source_case.source_case_id=version.source_case_id
        JOIN inventory.source_revisions revision ON revision.source_revision_id=version.source_revision_id
        JOIN inventory.source_projects project ON project.source_project_id=revision.source_project_id
        JOIN inventory.prompt_records prompt ON prompt.source_case_version_id=version.source_case_version_id
        WHERE version.source_case_version_id=NEW.source_case_version_id;
        IF (takedown_scope='source' AND takedown_key <> case_source_id)
           OR (takedown_scope='case' AND takedown_key <> case_source_id || ':' || case_native_key)
           OR (takedown_scope='prompt' AND takedown_key <> case_source_id || ':' || prompt_native_id) THEN
            RAISE EXCEPTION 'publication v2 takedown scope does not match excluded source case' USING ERRCODE='integrity_constraint_violation';
        END IF;
        IF takedown_scope='asset' THEN
            SELECT count(*) INTO matched_count
            FROM inventory.generation_examples generation
            JOIN inventory.generation_outputs generation_output ON generation_output.generation_example_row_id=generation.generation_example_row_id
            JOIN inventory.asset_sources source ON source.asset_source_id=generation_output.asset_source_id
            JOIN content.rights_review_output_decisions_v2 decision ON decision.generation_output_id=generation_output.generation_output_id
            JOIN content.rights_review_batches_v2 batch ON batch.rights_review_batch_id=decision.rights_review_batch_id
            WHERE generation.source_case_version_id=NEW.source_case_version_id
              AND batch.source_case_version_id=NEW.source_case_version_id
              AND source.content_sha256=takedown_key
              AND decision.public_display_role='public_primary';
            IF matched_count < 1 OR NEW.reason_code <> 'takedown_asset_primary' THEN
                RAISE EXCEPTION 'publication v2 asset exclusion is not an approved public primary' USING ERRCODE='integrity_constraint_violation';
            END IF;
        END IF;
    ELSIF NEW.takedown_request_v2_id IS NOT NULL THEN
        RAISE EXCEPTION 'non-takedown exclusion must not reference a takedown request' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_publication_v2_takedown_application_authority()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE scope_name text; scope_value text; scope_action text; matched_count integer;
BEGIN
    SELECT scope_type, scope_key, action INTO scope_name, scope_value, scope_action
    FROM content.takedown_requests_v2 WHERE takedown_request_v2_id=NEW.takedown_request_v2_id;
    IF scope_name IS NULL OR scope_name <> 'asset' OR scope_action <> 'remove' THEN
        RAISE EXCEPTION 'publication v2 asset removal lacks asset takedown authority' USING ERRCODE='integrity_constraint_violation';
    END IF;
    SELECT count(*) INTO matched_count
    FROM content.publication_entries_v2 entry
    JOIN inventory.generation_examples generation ON generation.source_case_version_id=entry.source_case_version_id
    JOIN inventory.generation_outputs generation_output ON generation_output.generation_example_row_id=generation.generation_example_row_id
    JOIN inventory.asset_sources source ON source.asset_source_id=generation_output.asset_source_id
    JOIN content.rights_review_output_decisions_v2 decision
      ON decision.rights_review_batch_id=entry.rights_review_batch_id
     AND decision.generation_output_id=generation_output.generation_output_id
    WHERE entry.publication_version_v2_id=NEW.publication_version_v2_id
      AND entry.public_case_key=NEW.public_case_key
      AND source.content_sha256=scope_value
      AND decision.public_display_role='public_gallery'
      AND NOT jsonb_path_exists(entry.snapshot, '$.generation_members[*].public_outputs[*] ? (@.content_sha256 == $hash)', jsonb_build_object('hash', scope_value));
    IF matched_count <> 1 THEN
        RAISE EXCEPTION 'publication v2 asset removal does not match one omitted public gallery output' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_current_active_version_v2()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_state text;
BEGIN
    SELECT state INTO version_state FROM content.publication_versions_v2 WHERE publication_version_v2_id=NEW.publication_version_v2_id;
    IF version_state IS NULL OR version_state <> 'active' THEN
        RAISE EXCEPTION 'current publication v2 pointer must reference an active version' USING ERRCODE='foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION content.require_publication_build_request_v2_building()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE version_state text;
BEGIN
    SELECT state INTO version_state FROM content.publication_versions_v2 WHERE publication_version_v2_id=NEW.publication_version_v2_id;
    IF version_state IS NULL OR version_state <> 'building' THEN
        RAISE EXCEPTION 'publication v2 build request must bind a building version' USING ERRCODE='integrity_constraint_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER publication_versions_v2_transition BEFORE UPDATE OR DELETE ON content.publication_versions_v2
FOR EACH ROW EXECUTE FUNCTION content.enforce_publication_version_v2_transition();
CREATE TRIGGER publication_revision_selections_v2_only_building BEFORE INSERT ON content.publication_revision_selections_v2
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_v2_child();
CREATE TRIGGER publication_revision_selections_v2_domain BEFORE INSERT ON content.publication_revision_selections_v2
FOR EACH ROW EXECUTE FUNCTION content.require_publication_v2_selection_domain();
CREATE TRIGGER publication_entries_v2_only_building BEFORE INSERT ON content.publication_entries_v2
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_v2_child();
CREATE TRIGGER publication_entries_v2_authority BEFORE INSERT ON content.publication_entries_v2
FOR EACH ROW EXECUTE FUNCTION content.require_publication_v2_entry_authority();
CREATE TRIGGER publication_assets_v2_only_building BEFORE INSERT ON content.publication_assets_v2
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_v2_asset();
CREATE TRIGGER publication_assets_v2_authority BEFORE INSERT ON content.publication_assets_v2
FOR EACH ROW EXECUTE FUNCTION content.require_publication_v2_asset_authority();
CREATE TRIGGER publication_exclusions_v2_only_building BEFORE INSERT ON content.publication_exclusions_v2
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_v2_asset();
CREATE TRIGGER publication_exclusions_v2_authority BEFORE INSERT ON content.publication_exclusions_v2
FOR EACH ROW EXECUTE FUNCTION content.require_publication_v2_exclusion_authority();
CREATE TRIGGER publication_takedown_applications_v2_only_building BEFORE INSERT ON content.publication_takedown_applications_v2
FOR EACH ROW EXECUTE FUNCTION content.require_building_publication_v2_asset();
CREATE TRIGGER publication_takedown_applications_v2_authority BEFORE INSERT ON content.publication_takedown_applications_v2
FOR EACH ROW EXECUTE FUNCTION content.require_publication_v2_takedown_application_authority();
CREATE TRIGGER immutable_publication_revision_selections_v2 BEFORE UPDATE OR DELETE ON content.publication_revision_selections_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_publication_build_requests_v2 BEFORE UPDATE OR DELETE ON content.publication_build_requests_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER publication_build_requests_v2_building BEFORE INSERT ON content.publication_build_requests_v2
FOR EACH ROW EXECUTE FUNCTION content.require_publication_build_request_v2_building();
CREATE TRIGGER immutable_publication_entries_v2 BEFORE UPDATE OR DELETE ON content.publication_entries_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_publication_assets_v2 BEFORE UPDATE OR DELETE ON content.publication_assets_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_publication_exclusions_v2 BEFORE UPDATE OR DELETE ON content.publication_exclusions_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_publication_takedown_applications_v2 BEFORE UPDATE OR DELETE ON content.publication_takedown_applications_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER current_publication_v2_active_only BEFORE INSERT OR UPDATE ON content.publication_current_v2
FOR EACH ROW EXECUTE FUNCTION content.require_current_active_version_v2();
CREATE TRIGGER immutable_publication_outbox_v2 BEFORE UPDATE OR DELETE ON content.publication_outbox_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER immutable_takedown_requests_v2 BEFORE UPDATE OR DELETE ON content.takedown_requests_v2
FOR EACH ROW EXECUTE FUNCTION content.reject_immutable_mutation();
CREATE TRIGGER takedown_requests_v2_not_future BEFORE INSERT ON content.takedown_requests_v2
FOR EACH ROW EXECUTE FUNCTION content.require_takedown_v2_not_future();
