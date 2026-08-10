-- TASK-0005 hardening is additive so a database that applied 0001 remains
-- auditable and the checksum for its original migration never changes.

ALTER TABLE inventory.source_adapter_runs
    ADD COLUMN registry_snapshot jsonb;

-- 0001 made evidence rows immutable. A controlled migration is the sole
-- exception needed to move its registry evidence from the project identity
-- row to the immutable run that consumed it.
ALTER TABLE inventory.source_adapter_runs DISABLE TRIGGER immutable_source_adapter_runs;

UPDATE inventory.source_adapter_runs AS run
SET registry_snapshot = project.registry_record
FROM inventory.source_revisions AS revision
JOIN inventory.source_projects AS project
  ON project.source_project_id = revision.source_project_id
WHERE run.source_revision_id = revision.source_revision_id;

ALTER TABLE inventory.source_adapter_runs ENABLE TRIGGER immutable_source_adapter_runs;

ALTER TABLE inventory.source_adapter_runs
    ALTER COLUMN registry_snapshot SET NOT NULL,
    ADD CONSTRAINT source_adapter_runs_registry_snapshot_object
        CHECK (jsonb_typeof(registry_snapshot) = 'object');

-- A project is intentionally a stable source/repository identity only. URL,
-- status, rights, fixed Commit, and the complete registry document belong to
-- the immutable run snapshot above and can therefore evolve by revision.
ALTER TABLE inventory.source_projects
    DROP COLUMN registry_record,
    DROP COLUMN repository_url,
    DROP COLUMN family_id,
    DROP COLUMN source_status;

-- TASK-0003 derives a Generation Example id from the stable source case key.
-- The same case may legitimately recur in a later immutable revision, so the
-- identifier is only unique within its source case version rather than across
-- the entire lifetime of the source project.
ALTER TABLE inventory.generation_examples
    DROP CONSTRAINT IF EXISTS generation_examples_generation_example_id_key,
    ADD CONSTRAINT generation_examples_case_version_generation_example_id_key
        UNIQUE (source_case_version_id, generation_example_id);

CREATE OR REPLACE FUNCTION inventory.require_case_version_domain()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    case_project_id bigint;
    revision_project_id bigint;
    run_revision_id bigint;
    file_revision_id bigint;
BEGIN
    SELECT source_project_id INTO case_project_id
    FROM inventory.source_cases
    WHERE source_case_id = NEW.source_case_id;

    SELECT source_project_id INTO revision_project_id
    FROM inventory.source_revisions
    WHERE source_revision_id = NEW.source_revision_id;

    SELECT source_revision_id INTO run_revision_id
    FROM inventory.source_adapter_runs
    WHERE source_adapter_run_id = NEW.source_adapter_run_id;

    SELECT source_revision_id INTO file_revision_id
    FROM inventory.source_files
    WHERE source_file_id = NEW.source_file_id;

    IF case_project_id IS NULL
       OR revision_project_id IS NULL
       OR run_revision_id IS NULL
       OR file_revision_id IS NULL
       OR case_project_id <> revision_project_id
       OR run_revision_id <> NEW.source_revision_id
       OR file_revision_id <> NEW.source_revision_id THEN
        RAISE EXCEPTION 'source case version must use one project and one revision domain'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION inventory.require_child_source_file_revision()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    case_revision_id bigint;
    file_revision_id bigint;
BEGIN
    SELECT source_revision_id INTO case_revision_id
    FROM inventory.source_case_versions
    WHERE source_case_version_id = NEW.source_case_version_id;

    SELECT source_revision_id INTO file_revision_id
    FROM inventory.source_files
    WHERE source_file_id = NEW.source_file_id;

    IF case_revision_id IS NULL
       OR file_revision_id IS NULL
       OR case_revision_id <> file_revision_id THEN
        RAISE EXCEPTION 'child evidence source file must belong to its case revision'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION inventory.require_generation_prompt_domain()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    prompt_case_version_id bigint;
BEGIN
    SELECT source_case_version_id INTO prompt_case_version_id
    FROM inventory.prompt_records
    WHERE prompt_record_id = NEW.prompt_record_id;

    IF prompt_case_version_id IS NULL
       OR prompt_case_version_id <> NEW.source_case_version_id THEN
        RAISE EXCEPTION 'generation prompt must belong to the same source case version'
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER source_case_versions_domain
BEFORE INSERT OR UPDATE ON inventory.source_case_versions
FOR EACH ROW EXECUTE FUNCTION inventory.require_case_version_domain();

CREATE TRIGGER prompt_records_source_file_revision
BEFORE INSERT OR UPDATE ON inventory.prompt_records
FOR EACH ROW EXECUTE FUNCTION inventory.require_child_source_file_revision();

CREATE TRIGGER asset_sources_source_file_revision
BEFORE INSERT OR UPDATE ON inventory.asset_sources
FOR EACH ROW EXECUTE FUNCTION inventory.require_child_source_file_revision();

CREATE TRIGGER generation_examples_prompt_domain
BEFORE INSERT OR UPDATE ON inventory.generation_examples
FOR EACH ROW EXECUTE FUNCTION inventory.require_generation_prompt_domain();
