#!/usr/bin/env python3
"""Isolated PostgreSQL proof for Publication v2 lifecycle and fail-closed state."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(r"C:\Users\admin\.codex\runtime\image2\task-0025-publication-v2")


class ValidationFailure(RuntimeError):
    pass


def _run(arguments: list[str], *, environment: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _json_command(arguments: list[str], environment: dict[str, str]) -> dict[str, Any]:
    completed = _run([sys.executable, "-B", *arguments], environment=environment)
    if completed.returncode != 0:
        raise ValidationFailure(f"{' '.join(arguments)}: {(completed.stderr or completed.stdout)[-1500:]}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationFailure("command did not emit JSON") from exc


def _seed_publishable_case(database_url: str) -> dict[str, Any]:
    revision_sha = "a" * 40
    prompt_text = "Create a verified multi-image publication v2 test case."
    primary_hash = hashlib.sha256(b"publication-v2-primary").hexdigest()
    gallery_hash = hashlib.sha256(b"publication-v2-gallery").hexdigest()
    with psycopg.connect(database_url) as conn:
        project_id = int(
            conn.execute(
                "INSERT INTO inventory.source_projects(source_id, repository_id) VALUES ('synthetic-source','github:synthetic/source') RETURNING source_project_id"
            ).fetchone()[0]
        )
        revision_id = int(
            conn.execute(
                "INSERT INTO inventory.source_revisions(source_project_id, revision_sha) VALUES (%s,%s) RETURNING source_revision_id",
                (project_id, revision_sha),
            ).fetchone()[0]
        )
        prompt_file_id = int(
            conn.execute(
                "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s,'cases/case-1.json','https://example.invalid/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/cases/case-1.json') RETURNING source_file_id",
                (revision_id,),
            ).fetchone()[0]
        )
        primary_file_id = int(
            conn.execute(
                "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s,'assets/primary.png','https://example.invalid/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/assets/primary.png') RETURNING source_file_id",
                (revision_id,),
            ).fetchone()[0]
        )
        gallery_file_id = int(
            conn.execute(
                "INSERT INTO inventory.source_files(source_revision_id, source_path, source_url) VALUES (%s,'assets/gallery.png','https://example.invalid/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/assets/gallery.png') RETURNING source_file_id",
                (revision_id,),
            ).fetchone()[0]
        )
        run_id = int(
            conn.execute(
                """
                INSERT INTO inventory.source_adapter_runs
                  (source_revision_id, adapter_id, adapter_version, contract_version, package_idempotency_key,
                   manifest_stable_sha256, semantic_digest, coverage, metrics, manifest, state, registry_snapshot)
                VALUES (%s,'synthetic-v2','1','generation-example/v1','synthetic-v2-package',%s,%s,%s,%s,%s,'ready',%s)
                RETURNING source_adapter_run_id
                """,
                (
                    revision_id,
                    "1" * 64,
                    "2" * 64,
                    Jsonb({"complete": True}),
                    Jsonb({"cases": 1}),
                    Jsonb({"files": 3}),
                    Jsonb({"source_id": "synthetic-source", "revision_sha": revision_sha}),
                ),
            ).fetchone()[0]
        )
        case_id = int(
            conn.execute(
                "INSERT INTO inventory.source_cases(source_project_id, source_case_key) VALUES (%s,'case-1') RETURNING source_case_id",
                (project_id,),
            ).fetchone()[0]
        )
        case_version_id = int(
            conn.execute(
                """
                INSERT INTO inventory.source_case_versions
                  (source_case_id, source_revision_id, source_adapter_run_id, source_file_id,
                   source_locator, adapter_record, generation_document, contract_state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'contract_valid') RETURNING source_case_version_id
                """,
                (case_id, revision_id, run_id, prompt_file_id, Jsonb({}), Jsonb({}), Jsonb({})),
            ).fetchone()[0]
        )
        prompt_record_id = int(
            conn.execute(
                """
                INSERT INTO inventory.prompt_records
                  (source_case_version_id, prompt_id, raw_text, language, source_file_id, source_location, raw_text_sha256)
                VALUES (%s,'prompt-1',%s,'en',%s,%s,%s) RETURNING prompt_record_id
                """,
                (
                    case_version_id,
                    prompt_text,
                    prompt_file_id,
                    Jsonb({"source_path": "cases/case-1.json"}),
                    hashlib.sha256(prompt_text.encode()).hexdigest(),
                ),
            ).fetchone()[0]
        )
        conn.execute(
            """
            INSERT INTO inventory.rights_records
              (source_case_version_id, prompt_rights_status, asset_rights_status, evidence_urls, note)
            VALUES (%s,'review_required','review_required',%s,'synthetic validator evidence')
            """,
            (case_version_id, Jsonb(["https://example.invalid/evidence"])),
        )
        output_ids: list[int] = []
        for index, (content_hash, source_file_id, path, source_role) in enumerate(
            (
                (primary_hash, primary_file_id, "assets/primary.png", "output_primary"),
                (gallery_hash, gallery_file_id, "assets/gallery.png", "output_secondary"),
            )
        ):
            conn.execute(
                """
                INSERT INTO inventory.assets(content_sha256, object_key, object_bucket, byte_size, media_type, integrity_state)
                VALUES (%s,%s,'synthetic-private',1024,'image/png','verified')
                """,
                (content_hash, f"sha256/{content_hash}"),
            )
            asset_source_id = int(
                conn.execute(
                    """
                    INSERT INTO inventory.asset_sources
                      (source_case_version_id, asset_ref_id, source_file_id, content_sha256, role, source_location)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING asset_source_id
                    """,
                    (
                        case_version_id,
                        f"asset-{index}",
                        source_file_id,
                        content_hash,
                        source_role,
                        Jsonb({"source_path": path}),
                    ),
                ).fetchone()[0]
            )
            generation_id = int(
                conn.execute(
                    """
                    INSERT INTO inventory.generation_examples
                      (generation_example_id, source_case_version_id, prompt_record_id, source_claim, contract_state)
                    VALUES (%s,%s,%s,%s,'contract_valid') RETURNING generation_example_row_id
                    """,
                    (
                        f"generation:{index}",
                        case_version_id,
                        prompt_record_id,
                        Jsonb({"evidence_status": "source_claimed", "model_raw": "gpt-image-2", "parameters_raw": None}),
                    ),
                ).fetchone()[0]
            )
            output_ids.append(
                int(
                    conn.execute(
                        "INSERT INTO inventory.generation_outputs(generation_example_row_id, ordinal, asset_source_id) VALUES (%s,0,%s) RETURNING generation_output_id",
                        (generation_id, asset_source_id),
                    ).fetchone()[0]
                )
            )
            conn.execute(
                "INSERT INTO inventory.pairing_evidence(generation_example_row_id, ordinal, method, status, evidence) VALUES (%s,0,'explicit','strong',%s)",
                (generation_id, Jsonb({"case": "case-1"})),
            )
        reviewed_at = datetime.now(timezone.utc) - timedelta(seconds=2)
        batch_id = int(
            conn.execute(
                """
                INSERT INTO content.rights_review_batches_v2
                  (source_case_version_id, idempotency_key, request_digest, expected_latest_batch_id,
                   repository_license, prompt_rights, author, original_url, evidence_url,
                   reviewer, reviewed_at, review_note)
                VALUES (%s,'synthetic-review-v2',%s,NULL,'MIT','approved','Synthetic Author',
                        'https://example.invalid/original','https://example.invalid/evidence',
                        'publication-v2-validator',%s,'synthetic validation review')
                RETURNING rights_review_batch_id
                """,
                (case_version_id, "3" * 64, reviewed_at),
            ).fetchone()[0]
        )
        for index, output_id in enumerate(output_ids):
            conn.execute(
                """
                INSERT INTO content.rights_review_output_decisions_v2
                  (rights_review_batch_id, generation_output_id, asset_rights, display_policy,
                   public_display_role, decision_note)
                VALUES (%s,%s,'approved','mirror_allowed',%s,'synthetic publication decision')
                """,
                (batch_id, output_id, "public_primary" if index == 0 else "public_gallery"),
            )
    return {
        "revision_sha": revision_sha,
        "case_key": "synthetic-source:case-1",
        "prompt_key": "synthetic-source:prompt-1",
        "primary_hash": primary_hash,
        "gallery_hash": gallery_hash,
    }


def _assert_quality_exclusion_domain(database_url: str) -> None:
    accepted = (
        "quality_non_result_capture",
        "quality_prompt_output_mismatch",
        "quality_near_identical_cross_source_render",
        "quality_exact_prompt_output_subset",
    )
    with psycopg.connect(database_url) as conn:
        version_id = int(
            conn.execute(
                "INSERT INTO content.publication_versions_v2(state, created_by) VALUES ('building','quality-domain-validator') RETURNING publication_version_v2_id"
            ).fetchone()[0]
        )
        selected = conn.execute(
            """
            SELECT project.source_project_id, revision.source_revision_id, version.source_case_version_id
            FROM inventory.source_projects project
            JOIN inventory.source_revisions revision ON revision.source_project_id=project.source_project_id
            JOIN inventory.source_case_versions version ON version.source_revision_id=revision.source_revision_id
            WHERE project.source_id='synthetic-source'
            """
        ).fetchone()
        conn.execute(
            "INSERT INTO content.publication_revision_selections_v2(publication_version_v2_id, source_project_id, source_revision_id) VALUES (%s,%s,%s)",
            (version_id, selected[0], selected[1]),
        )
        case_version_id = int(selected[2])
        for reason in accepted:
            with conn.transaction(force_rollback=True):
                conn.execute(
                    "INSERT INTO content.publication_exclusions_v2(publication_version_v2_id, source_case_version_id, reason_code) VALUES (%s,%s,%s)",
                    (version_id, case_version_id, reason),
                )
        try:
            with conn.transaction(force_rollback=True):
                conn.execute(
                    "INSERT INTO content.publication_exclusions_v2(publication_version_v2_id, source_case_version_id, reason_code) VALUES (%s,%s,'quality_unbounded_reason')",
                    (version_id, case_version_id),
                )
        except psycopg.errors.CheckViolation:
            pass
        else:
            raise ValidationFailure("quality exclusion reason domain accepted an unbounded value")


def validate() -> dict[str, Any]:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = uuid.uuid4().hex[:10]
    project = f"image2-task0025v2-{suffix}"
    database = f"image2_task0025_{suffix}"
    user = f"image2_task0025_{suffix}"
    password = "task0025-publication-v2-local-secret"
    port = 25435
    compose_environment = {
        **os.environ,
        "INVENTORY_POSTGRES_DB": database,
        "INVENTORY_POSTGRES_USER": user,
        "INVENTORY_POSTGRES_PASSWORD": password,
        "INVENTORY_POSTGRES_PORT": str(port),
        "INVENTORY_S3_ACCESS_KEY": "unused-task0025-access",
        "INVENTORY_S3_SECRET_KEY": "unused-task0025-secret",
        "INVENTORY_S3_PORT": "29003",
    }
    database_url = f"postgresql://{user}:{password}@127.0.0.1:{port}/{database}"
    runtime_environment = {
        **os.environ,
        "INVENTORY_DATABASE_URL": database_url,
        "CONTENT_DATABASE_URL": database_url,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        up = _run(["docker", "compose", "-p", project, "up", "-d", "postgres"], environment=compose_environment)
        if up.returncode != 0:
            raise ValidationFailure((up.stderr or up.stdout)[-1500:])
        container = f"{project}-postgres-1"
        for _ in range(60):
            health = _run(["docker", "inspect", container, "--format", "{{.State.Health.Status}}"])
            if health.returncode == 0 and health.stdout.strip() == "healthy":
                break
            time.sleep(0.25)
        else:
            raise ValidationFailure("isolated PostgreSQL did not become healthy")

        first = _json_command(
            ["-m", "inventory", "migrate", "--migrations-dir", str(REPO_ROOT / "migrations"), "--json"],
            runtime_environment,
        )
        replay = _json_command(
            ["-m", "inventory", "migrate", "--migrations-dir", str(REPO_ROOT / "migrations"), "--json"],
            runtime_environment,
        )
        versions = [item["version"] for item in first["migrations"]]
        required = "0006_publication_v2_and_takedown"
        if required not in versions:
            raise ValidationFailure("migration authority does not include Publication v2")
        if "0009_content_quality_exclusions" not in versions:
            raise ValidationFailure("migration authority does not include content-quality exclusions")
        if any(item["status"] != "verified_existing" for item in replay["migrations"]):
            raise ValidationFailure("migration replay is not idempotent")

        empty = _json_command(["-m", "content", "inspect-publication-v2", "--json"], runtime_environment)
        takedowns = _json_command(["-m", "content", "list-takedowns-v2", "--json"], runtime_environment)
        if empty.get("result") != {"state": "no_current", "publication_version": None, "entries": []}:
            raise ValidationFailure("fresh Publication v2 is not fail-closed")
        if takedowns.get("result", {}).get("total") != 0:
            raise ValidationFailure("fresh takedown timeline is not empty")
        seeded = _seed_publishable_case(database_url)
        _assert_quality_exclusion_domain(database_url)
        selection = json.dumps({"synthetic-source": seeded["revision_sha"]}, separators=(",", ":"))
        built = _json_command(
            [
                "-m", "content", "build-publication-v2", "--revision-selection-json", selection,
                "--created-by", "publication-v2-validator", "--idempotency-key", "synthetic-build-1", "--json",
            ],
            runtime_environment,
        )["result"]
        replay_build = _json_command(
            [
                "-m", "content", "build-publication-v2", "--revision-selection-json", selection,
                "--created-by", "publication-v2-validator", "--idempotency-key", "synthetic-build-1", "--json",
            ],
            runtime_environment,
        )["result"]
        if built.get("included_count") != 1 or replay_build.get("status") != "verified_existing":
            raise ValidationFailure("publishable build or idempotent replay failed")
        version_1 = int(built["publication_version_v2_id"])
        _json_command(["-m", "content", "activate-publication-v2", "--version-id", str(version_1), "--json"], runtime_environment)
        active_1 = _json_command(["-m", "content", "inspect-publication-v2", "--json"], runtime_environment)["result"]
        if active_1.get("publication_version", {}).get("included_count") != 1 or len(active_1.get("entries", [])) != 1:
            raise ValidationFailure("positive publication did not become current")
        public_case_key = active_1["entries"][0]["public_case_key"]

        requested_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        _json_command(
            [
                "-m", "content", "record-takedown-v2", "--idempotency-key", "remove-gallery-1",
                "--scope-type", "asset", "--scope-key", seeded["gallery_hash"], "--action", "remove",
                "--reason-code", "rights_request", "--evidence-url", "https://example.invalid/takedown",
                "--note", "remove gallery for validation", "--requested-by", "publication-v2-validator",
                "--requested-at", requested_at, "--json",
            ],
            runtime_environment,
        )
        built_2 = _json_command(
            [
                "-m", "content", "build-publication-v2", "--revision-selection-json", selection,
                "--created-by", "publication-v2-validator", "--idempotency-key", "synthetic-build-2", "--json",
            ],
            runtime_environment,
        )["result"]
        version_2 = int(built_2["publication_version_v2_id"])
        _json_command(["-m", "content", "activate-publication-v2", "--version-id", str(version_2), "--json"], runtime_environment)
        active_2 = _json_command(["-m", "content", "inspect-publication-v2", "--json"], runtime_environment)["result"]
        if active_2["entries"][0]["public_case_key"] != public_case_key:
            raise ValidationFailure("stable public case key drifted after asset takedown")
        public_output_count = sum(
            len(member["public_outputs"]) for member in active_2["entries"][0]["generation_members"]
        )
        if public_output_count != 1:
            raise ValidationFailure("gallery asset takedown did not redact exactly one public output")

        restore_at = datetime.now(timezone.utc).isoformat()
        _json_command(
            [
                "-m", "content", "record-takedown-v2", "--idempotency-key", "restore-gallery-1",
                "--scope-type", "asset", "--scope-key", seeded["gallery_hash"], "--action", "restore",
                "--reason-code", "resolved", "--evidence-url", "https://example.invalid/restore",
                "--note", "restore gallery for validation", "--requested-by", "publication-v2-validator",
                "--requested-at", restore_at, "--json",
            ],
            runtime_environment,
        )
        built_3 = _json_command(
            [
                "-m", "content", "build-publication-v2", "--revision-selection-json", selection,
                "--created-by", "publication-v2-validator", "--idempotency-key", "synthetic-build-3", "--json",
            ],
            runtime_environment,
        )["result"]
        version_3 = int(built_3["publication_version_v2_id"])
        _json_command(["-m", "content", "activate-publication-v2", "--version-id", str(version_3), "--json"], runtime_environment)
        active_3 = _json_command(["-m", "content", "inspect-publication-v2", "--json"], runtime_environment)["result"]
        if sum(len(member["public_outputs"]) for member in active_3["entries"][0]["generation_members"]) != 2:
            raise ValidationFailure("restore did not reinstate the gallery output in a new version")

        _json_command(
            [
                "-m", "content", "record-takedown-v2", "--idempotency-key", "remove-case-1",
                "--scope-type", "case", "--scope-key", seeded["case_key"], "--action", "remove",
                "--reason-code", "rights_request", "--evidence-url", "https://example.invalid/case-takedown",
                "--note", "remove case for validation", "--requested-by", "publication-v2-validator",
                "--requested-at", datetime.now(timezone.utc).isoformat(), "--json",
            ],
            runtime_environment,
        )
        built_4 = _json_command(
            [
                "-m", "content", "build-publication-v2", "--revision-selection-json", selection,
                "--created-by", "publication-v2-validator", "--idempotency-key", "synthetic-build-4", "--json",
            ],
            runtime_environment,
        )["result"]
        version_4 = int(built_4["publication_version_v2_id"])
        _json_command(["-m", "content", "activate-publication-v2", "--version-id", str(version_4), "--json"], runtime_environment)
        active_4 = _json_command(["-m", "content", "inspect-publication-v2", "--json"], runtime_environment)["result"]
        if active_4["publication_version"]["included_count"] != 0 or active_4["publication_version"]["reason_counts"] != {"takedown_case": 1}:
            raise ValidationFailure("case takedown did not produce an authorized empty version")
        rollback = _run(
            [sys.executable, "-B", "-m", "content", "rollback-publication-v2", "--version-id", str(version_3), "--json"],
            environment=runtime_environment,
        )
        if rollback.returncode == 0 or "publication_v2_active_takedown" not in rollback.stdout:
            raise ValidationFailure("rollback restored a case under active takedown")
        return {
            "status": "passed",
            "migration_versions": versions,
            "migration_replay": "verified_existing",
            "publication_v2": "no_current",
            "takedown_requests_v2": 0,
            "positive_publication": 1,
            "gallery_takedown": "redacted",
            "gallery_restore": "restored",
            "case_takedown": "authorized_empty",
            "rollback_under_active_takedown": "rejected",
            "quality_exclusion_domain": "closed",
        }
    finally:
        _run(["docker", "compose", "-p", project, "down", "-v"], environment=compose_environment)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate()
    except (ValidationFailure, OSError, subprocess.SubprocessError) as exc:
        payload = {"status": "failed", "message": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else payload)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
