CREATE SCHEMA IF NOT EXISTS inventory;

CREATE TABLE IF NOT EXISTS inventory.schema_migrations (
    version text PRIMARY KEY,
    checksum_sha256 char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inventory.source_projects (
    source_project_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id text NOT NULL UNIQUE,
    repository_id text NOT NULL,
    repository_url text NOT NULL,
    family_id text NOT NULL,
    source_status text NOT NULL,
    registry_record jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory.source_revisions (
    source_revision_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_project_id bigint NOT NULL REFERENCES inventory.source_projects(source_project_id),
    revision_sha char(40) NOT NULL CHECK (revision_sha ~ '^[0-9a-f]{40}$'),
    UNIQUE (source_project_id, revision_sha)
);

CREATE TABLE IF NOT EXISTS inventory.source_files (
    source_file_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_revision_id bigint NOT NULL REFERENCES inventory.source_revisions(source_revision_id),
    source_path text NOT NULL,
    source_url text NOT NULL,
    UNIQUE (source_revision_id, source_path, source_url)
);

CREATE TABLE IF NOT EXISTS inventory.source_adapter_runs (
    source_adapter_run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_revision_id bigint NOT NULL REFERENCES inventory.source_revisions(source_revision_id),
    adapter_id text NOT NULL,
    adapter_version text NOT NULL,
    contract_version text NOT NULL,
    package_idempotency_key text NOT NULL UNIQUE,
    manifest_stable_sha256 char(64) NOT NULL CHECK (manifest_stable_sha256 ~ '^[0-9a-f]{64}$'),
    semantic_digest char(64) NOT NULL CHECK (semantic_digest ~ '^[0-9a-f]{64}$'),
    coverage jsonb NOT NULL,
    metrics jsonb NOT NULL,
    manifest jsonb NOT NULL,
    state text NOT NULL CHECK (state = 'ready')
);

CREATE TABLE IF NOT EXISTS inventory.source_parse_errors (
    source_parse_error_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_adapter_run_id bigint NOT NULL REFERENCES inventory.source_adapter_runs(source_adapter_run_id),
    source_case_key text NOT NULL,
    error_document jsonb NOT NULL,
    UNIQUE (source_adapter_run_id, source_case_key)
);

CREATE TABLE IF NOT EXISTS inventory.source_cases (
    source_case_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_project_id bigint NOT NULL REFERENCES inventory.source_projects(source_project_id),
    source_case_key text NOT NULL,
    UNIQUE (source_project_id, source_case_key)
);

CREATE TABLE IF NOT EXISTS inventory.source_case_versions (
    source_case_version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_case_id bigint NOT NULL REFERENCES inventory.source_cases(source_case_id),
    source_revision_id bigint NOT NULL REFERENCES inventory.source_revisions(source_revision_id),
    source_adapter_run_id bigint NOT NULL REFERENCES inventory.source_adapter_runs(source_adapter_run_id),
    source_file_id bigint NOT NULL REFERENCES inventory.source_files(source_file_id),
    source_locator jsonb NOT NULL,
    adapter_record jsonb NOT NULL,
    generation_document jsonb NOT NULL,
    contract_state text NOT NULL CHECK (contract_state = 'contract_valid'),
    UNIQUE (source_case_id, source_revision_id)
);

CREATE TABLE IF NOT EXISTS inventory.prompt_records (
    prompt_record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_case_version_id bigint NOT NULL REFERENCES inventory.source_case_versions(source_case_version_id),
    prompt_id text NOT NULL,
    raw_text text NOT NULL,
    language text NOT NULL,
    source_file_id bigint NOT NULL REFERENCES inventory.source_files(source_file_id),
    source_location jsonb NOT NULL,
    raw_text_sha256 char(64) NOT NULL CHECK (raw_text_sha256 ~ '^[0-9a-f]{64}$'),
    UNIQUE (source_case_version_id, prompt_id)
);

CREATE TABLE IF NOT EXISTS inventory.assets (
    content_sha256 char(64) PRIMARY KEY CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    object_key text NOT NULL UNIQUE,
    object_bucket text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size > 512),
    media_type text NOT NULL,
    integrity_state text NOT NULL CHECK (integrity_state = 'verified')
);

CREATE TABLE IF NOT EXISTS inventory.asset_sources (
    asset_source_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_case_version_id bigint NOT NULL REFERENCES inventory.source_case_versions(source_case_version_id),
    asset_ref_id text NOT NULL,
    source_file_id bigint NOT NULL REFERENCES inventory.source_files(source_file_id),
    content_sha256 char(64) NOT NULL REFERENCES inventory.assets(content_sha256),
    role text NOT NULL,
    source_location jsonb NOT NULL,
    UNIQUE (source_case_version_id, asset_ref_id)
);

CREATE TABLE IF NOT EXISTS inventory.generation_examples (
    generation_example_row_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_example_id text NOT NULL UNIQUE,
    source_case_version_id bigint NOT NULL REFERENCES inventory.source_case_versions(source_case_version_id),
    prompt_record_id bigint NOT NULL REFERENCES inventory.prompt_records(prompt_record_id),
    source_claim jsonb NOT NULL,
    contract_state text NOT NULL CHECK (contract_state = 'contract_valid')
);

CREATE TABLE IF NOT EXISTS inventory.generation_inputs (
    generation_input_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_example_row_id bigint NOT NULL REFERENCES inventory.generation_examples(generation_example_row_id),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    asset_source_id bigint NOT NULL REFERENCES inventory.asset_sources(asset_source_id),
    UNIQUE (generation_example_row_id, ordinal)
);

CREATE TABLE IF NOT EXISTS inventory.generation_outputs (
    generation_output_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_example_row_id bigint NOT NULL REFERENCES inventory.generation_examples(generation_example_row_id),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    asset_source_id bigint NOT NULL REFERENCES inventory.asset_sources(asset_source_id),
    UNIQUE (generation_example_row_id, ordinal)
);

CREATE TABLE IF NOT EXISTS inventory.pairing_evidence (
    pairing_evidence_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_example_row_id bigint NOT NULL REFERENCES inventory.generation_examples(generation_example_row_id),
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    method text NOT NULL,
    status text NOT NULL CHECK (status = 'strong'),
    evidence jsonb NOT NULL,
    UNIQUE (generation_example_row_id, ordinal)
);

CREATE TABLE IF NOT EXISTS inventory.rights_records (
    rights_record_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_case_version_id bigint NOT NULL UNIQUE REFERENCES inventory.source_case_versions(source_case_version_id),
    prompt_rights_status text NOT NULL,
    asset_rights_status text NOT NULL,
    evidence_urls jsonb NOT NULL,
    note text
);

CREATE OR REPLACE FUNCTION inventory.reject_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'inventory immutable evidence table % rejects %', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE OR REPLACE FUNCTION inventory.require_same_case_asset_source()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    generation_case_version bigint;
    asset_case_version bigint;
BEGIN
    SELECT source_case_version_id INTO generation_case_version
    FROM inventory.generation_examples
    WHERE generation_example_row_id = NEW.generation_example_row_id;
    SELECT source_case_version_id INTO asset_case_version
    FROM inventory.asset_sources
    WHERE asset_source_id = NEW.asset_source_id;
    IF generation_case_version IS NULL OR asset_case_version IS NULL OR generation_case_version <> asset_case_version THEN
        RAISE EXCEPTION 'generation asset source must belong to the same source case version'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER generation_inputs_same_case
BEFORE INSERT OR UPDATE ON inventory.generation_inputs
FOR EACH ROW EXECUTE FUNCTION inventory.require_same_case_asset_source();

CREATE TRIGGER generation_outputs_same_case
BEFORE INSERT OR UPDATE ON inventory.generation_outputs
FOR EACH ROW EXECUTE FUNCTION inventory.require_same_case_asset_source();

CREATE TRIGGER immutable_source_projects BEFORE UPDATE OR DELETE ON inventory.source_projects FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_source_revisions BEFORE UPDATE OR DELETE ON inventory.source_revisions FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_source_files BEFORE UPDATE OR DELETE ON inventory.source_files FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_source_adapter_runs BEFORE UPDATE OR DELETE ON inventory.source_adapter_runs FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_source_parse_errors BEFORE UPDATE OR DELETE ON inventory.source_parse_errors FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_source_cases BEFORE UPDATE OR DELETE ON inventory.source_cases FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_source_case_versions BEFORE UPDATE OR DELETE ON inventory.source_case_versions FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_prompt_records BEFORE UPDATE OR DELETE ON inventory.prompt_records FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_assets BEFORE UPDATE OR DELETE ON inventory.assets FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_asset_sources BEFORE UPDATE OR DELETE ON inventory.asset_sources FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_generation_examples BEFORE UPDATE OR DELETE ON inventory.generation_examples FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_generation_inputs BEFORE UPDATE OR DELETE ON inventory.generation_inputs FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_generation_outputs BEFORE UPDATE OR DELETE ON inventory.generation_outputs FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_pairing_evidence BEFORE UPDATE OR DELETE ON inventory.pairing_evidence FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
CREATE TRIGGER immutable_rights_records BEFORE UPDATE OR DELETE ON inventory.rights_records FOR EACH ROW EXECUTE FUNCTION inventory.reject_evidence_mutation();
