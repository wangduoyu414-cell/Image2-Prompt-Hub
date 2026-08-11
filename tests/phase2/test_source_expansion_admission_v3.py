from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import validate_phase2_source_expansion_admission_v3 as validator


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _image(path: Path, magic: bytes = b"\x89PNG\r\n\x1a\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(magic + b"fixture" * 30)


def test_goku_parser_filters_wrong_model_and_missing_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"id": "ok", "category": "x", "model_info": {"name": "gpt-image-2"}, "raw_p": "A sufficiently detailed prompt that is long enough for the fixture to be admitted safely.", "media": {"images": ["gpt-image-2/images/0/a.jpg"]}, "sourceLink": "https://x.com/a/status/1"},
        {"id": "bad-model", "model_info": {"name": "dall-e-3"}, "media": {"images": ["gpt-image-2/images/3/b.jpg"]}},
        {"id": "missing", "model_info": {"name": "gpt-image-2"}, "raw_p": "prompt", "media": {"images": []}},
    ]
    (tmp_path / "metadata.jsonl").write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
    digest = validator._sha_file(tmp_path / "metadata.jsonl")
    monkeypatch.setattr(validator, "GOKU_METADATA_LFS_OID", digest)
    _json(tmp_path / "hf-tree.json", {"siblings": [{"rfilename": "metadata.jsonl", "size": (tmp_path / "metadata.jsonl").stat().st_size, "lfs": {"oid": digest, "size": (tmp_path / "metadata.jsonl").stat().st_size}}, {"rfilename": "gpt-image-2/images/0/a.jpg", "size": 12, "lfs": {"oid": "a" * 64, "size": 12}}, {"rfilename": "gpt-image-2/images/3/b.jpg", "size": 13, "lfs": {"oid": "b" * 64, "size": 13}}]})
    _json(tmp_path / "asset-manifest.json", {"assets": [{"path": "gpt-image-2/images/0/a.jpg", "lfs_oid": "a" * 64, "byte_size": 12, "classification": "global_orphan"}, {"path": "gpt-image-2/images/3/b.jpg", "lfs_oid": "b" * 64, "byte_size": 13, "classification": "out_of_scope_model_reference"}]})
    with pytest.raises(validator.ValidationFailure, match="recomputed HF tree/reference classification"):
        validator._parse_goku(tmp_path)
    _json(tmp_path / "asset-manifest.json", {"assets": [{"path": "gpt-image-2/images/0/a.jpg", "lfs_oid": "a" * 64, "byte_size": 12, "classification": "candidate_reference"}, {"path": "gpt-image-2/images/3/b.jpg", "lfs_oid": "b" * 64, "byte_size": 13, "classification": "out_of_scope_model_reference"}]})
    parsed = validator._parse_goku(tmp_path)
    assert [x["case_id"] for x in parsed["case_ledger"]] == ["ok"]
    assert {x["reason"] for x in parsed["exclusion_ledger"]} == {"missing_prompt_or_media"}
    assert parsed["metadata_lfs_oid"] == digest
    assert parsed["asset_classifications"]["out_of_scope"] == ["gpt-image-2/images/3/b.jpg"]


def test_chaos_parser_excludes_dependent_and_missing_assets_and_tracks_orphans(tmp_path: Path) -> None:
    index = {"images": [
        {"id": "ok", "topic_slug": "topic", "meta_path": "works/a/meta.json"},
        {"id": "dependency", "topic_slug": "topic", "meta_path": "works/b/meta.json"},
        {"id": "missing", "topic_slug": "topic", "meta_path": "works/c/meta.json"},
    ]}
    _json(tmp_path / "works/index.json", index)
    _json(tmp_path / "works/a/meta.json", {"prompt": "A complete direct prompt with enough detail to make the case independently useful and clearly document composition lighting materials subject framing and output constraints.", "generation": {"depends_on": []}, "refs": []})
    _json(tmp_path / "works/b/meta.json", {"prompt": "A complete dependent prompt with enough descriptive content to isolate the explicit reference dependency failure from unrelated short prompt lint behavior.", "generation": {"output": {"path": "works/b/image.png"}, "depends_on": [{"id": "a"}]}})
    _json(tmp_path / "works/c/meta.json", {"prompt": "A complete prompt with enough descriptive content to isolate the missing authoritative asset failure from unrelated short prompt lint behavior.", "generation": {"output": {"path": "works/c/image.png"}, "depends_on": []}})
    for width in (400, 1600, 2400): _image(tmp_path / f"works/a/image.w{width}.webp", b"RIFFxxxxWEBP")
    _image(tmp_path / "works/unreferenced.webp", b"RIFFxxxxWEBP")
    parsed = validator._parse_chaos(tmp_path)
    assert [x["case_id"] for x in parsed["case_ledger"]] == ["ok"]
    assert parsed["orphan_ledger"] == ["works/unreferenced.webp"]
    assert {x["reason"] for x in parsed["exclusion_ledger"]} == {"risk:reference_dependency", "missing_asset"}


def test_youmind_parser_counts_unique_ids_hashes_and_reference_need(tmp_path: Path) -> None:
    _json(tmp_path / "references/manifest.json", {"categories": [{"file": "a.json"}, {"file": "b.json"}]})
    _json(tmp_path / "references/a.json", [{"id": 1, "content": "Prompt one sufficiently detailed", "needReferenceImages": True, "sourceMedia": ["https://cms-assets.youmind.com/media/one.jpg"]}, {"id": 2, "content": "Prompt two", "needReferenceImages": False, "sourceMedia": ["https://cms-assets.youmind.com/media/two.jpg"]}])
    _json(tmp_path / "references/b.json", [{"id": 2, "content": "Prompt two", "needReferenceImages": False, "sourceMedia": ["https://cms-assets.youmind.com/media/two.jpg"]}])
    parsed = validator._parse_youmind(tmp_path)
    assert (parsed["total"], parsed["unique_ids"], parsed["unique_prompt_hashes"], parsed["need_reference_images"]) == (3, 2, 2, 1)
    assert (parsed["source_media_reference_count"], parsed["unique_source_media_urls"], parsed["author_attribution_rows"], parsed["original_post_rows"]) == (3, 2, 0, 0)


def test_tigerowo_parser_preserves_chinese_evolink_backup_claim(tmp_path: Path) -> None:
    _json(tmp_path / "data/ingested_tweets.json", {"records": [{"tweet_url": "https://x.com/a/status/1", "image_dir": "images/1", "case_anchor": "case-1", "category": "fixture"}]})
    (tmp_path / "README.md").write_text("# Fixture\n\n备份于 EvoLinkAI 仓库\n", encoding="utf-8")
    assert validator._parse_tigerowo(tmp_path)["readme_backup_claim"] is True
    (tmp_path / "README.md").write_text("# Fixture\n\nEvoLinkAI collection\n", encoding="utf-8")
    assert validator._parse_tigerowo(tmp_path)["readme_backup_claim"] is False


def _payload() -> dict[str, Any]:
    empty_sha = validator._hash_lines([])
    metrics = {"stages": {key: 0 for key in ("raw", "parseable", "authority_valid", "safety_eligible", "within_source_unique", "within_family_unique", "current_exact_new", "quality_valid")}, "pair_rate": 0, "broken_authoritative_asset_count": 0, "broken_authoritative_asset_rate": 0, "within_source_duplicate_rate": 0, "exclusion_reason_counts": {}, "raw_case_count": 0, "filtered_case_count": 0, "asset_count": 0, "orphan_asset_count": 0, "excluded_case_count": 0, "exclusion_count": 0, "case_ledger_sha256": validator._digest([]), "asset_ledger_sha256": validator._digest([]), "orphan_ledger_sha256": validator._digest([]), "exclusion_ledger_sha256": validator._digest([]), "lint_version": validator.V3_LINT_VERSION}
    quality = {"result": "fail", "sample_manifest_sha256": None, "sample_size": 0, "sample_ids": [], "sample_ids_sha256": empty_sha, "reviews": [], "missing_review_ids": [], "exclusion_sample_ids": {}, "exclusion_reviews": [], "missing_exclusion_reviews": [], "exclusion_reviews_sha256": validator._digest([]), "selection_method": "fixture", "coverage": {"source_categories": [], "sampled_categories": [], "source_risk_flags": [], "sampled_risk_flags": []}}
    goku_spec = validator.SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]
    goku_authority = {"kind": "hf", "repository": "Goku-OpenLab/gpt-image-2-prompts-datasets", "revision": goku_spec["revision"], "file_count": goku_spec["entry_count"], "image_count": 28293, "lfs_count": 28294, "metadata_oid": validator.GOKU_METADATA_LFS_OID, "metadata_size": validator.GOKU_METADATA_BYTE_SIZE, "tree_manifest_sha256": goku_spec["tree_manifest_sha256"]}
    snapshots = [{"revision": "1" * 40, "date": "2026-07-10", "file_count": 1, "image_count": 1, "lfs_count": 1, "metadata_oid": "1" * 64, "metadata_size": 1, "tree_manifest_sha256": "1" * 64}, {"revision": goku_authority["revision"], "date": "2026-08-03", "file_count": 28296, "image_count": 28293, "lfs_count": 28294, "metadata_oid": validator.GOKU_METADATA_LFS_OID, "metadata_size": validator.GOKU_METADATA_BYTE_SIZE, "tree_manifest_sha256": goku_spec["tree_manifest_sha256"]}]
    base = {"raw_case_ledger": [], "case_ledger": [], "asset_ledger": [], "orphan_ledger": [], "exclusion_ledger": [], "metrics": metrics, "quality": quality, "contribution": {}}
    goku = copy.deepcopy(base); goku.update({"asset_classifications": {}, "metadata_lfs_oid": validator.GOKU_METADATA_LFS_OID, "metadata_sha256": validator.GOKU_METADATA_LFS_OID, "authority": goku_authority, "maintenance": {"kind": "continuous", "substantive_dates": ["2026-07-10", "2026-08-03"], "snapshots": snapshots, "history_sha256": validator._digest(snapshots), "continuous_eligible": False, "sync_eligible": False, "timestamp_only_refreshes_excluded": True}})
    chaos_spec = validator.SOURCE_SPECS["chaosrealmsai-gpt-image-2-gallery"]
    chaos_authority = {"kind": "git", "revision": chaos_spec["revision"], "remote_url": chaos_spec["url"], "entry_count": chaos_spec["entry_count"], "blob_count": chaos_spec["entry_count"], "tree_manifest_sha256": chaos_spec["tree_manifest_sha256"], "commit_date": "2026-04-24T03:28:27Z"}
    chaos = copy.deepcopy(base); chaos.update({"authority": chaos_authority, "maintenance": {"kind": "fixed_history", "fixed_snapshot_complete": False, "sync_eligible": False, "one_shot_import_only": True, "raw_case_count": 3798, "asset_count": 11559, "orphan_count": 168, "missing_asset_case_count": 1, "authority_tree_manifest_sha256": chaos_spec["tree_manifest_sha256"]}})
    youmind_spec = validator.SOURCE_SPECS["youmind-openlab-gpt-image-2-prompts-search"]
    youmind_authority = {"kind": "git", "revision": youmind_spec["revision"], "remote_url": youmind_spec["url"], "entry_count": youmind_spec["entry_count"], "blob_count": youmind_spec["entry_count"], "tree_manifest_sha256": youmind_spec["tree_manifest_sha256"], "commit_date": "2026-08-11T01:57:33Z"}
    youmind_record = {"category": "fixture", "category_file": "fixture.json", "row_index": 0, "id": 1, "prompt_sha256": "e" * 64, "need_reference_images": False, "source_media": ["https://cms-assets.youmind.com/media/fixture.jpg"], "author_attribution_exposed": False, "original_post_exposed": False}
    youmind = {"total": 1, "unique_ids": 1, "unique_prompt_hashes": 1, "need_reference_images": 0, "rows_with_source_media": 1, "source_media_reference_count": 1, "unique_source_media_urls": 1, "cms_https_reference_count": 1, "author_attribution_rows": 0, "original_post_rows": 0, "remote_asset_authority": "observation_only", "source_media_urls_sha256": validator._hash_lines(["https://cms-assets.youmind.com/media/fixture.jpg"]), "records": [youmind_record], "goku_prompt_overlap_hashes": [], "authority": youmind_authority}; youmind["digest"] = validator._digest(youmind)
    tiger_spec = validator.SOURCE_SPECS["tigerowo-awesome-gpt-image-2-prompts"]
    tiger_authority = {"kind": "git", "revision": tiger_spec["revision"], "remote_url": tiger_spec["url"], "entry_count": tiger_spec["entry_count"], "blob_count": tiger_spec["entry_count"], "tree_manifest_sha256": tiger_spec["tree_manifest_sha256"], "commit_date": "2026-07-25T12:37:10Z"}
    tiger = {"record_count": 1, "image_count": 1, "missing_fields": {}, "readme_backup_claim": True, "family_mapping": "blocked", "authority": tiger_authority}
    rows = [validator._source_row("goku-openlab-gpt-image-2-prompts-datasets", goku, status="blocked"), validator._source_row("chaosrealmsai-gpt-image-2-gallery", chaos, status="blocked"), validator._source_row("youmind-openlab-gpt-image-2-prompts-search", youmind), validator._source_row("tigerowo-awesome-gpt-image-2-prompts", tiger)]
    authority = validator._current_baseline()[0]
    payload = {"schema_version": validator.SCHEMA_VERSION, "generated_at": "2026-08-10T00:00:00Z", "authority": authority, "sources": rows, "adapter_ready_batch": [], "summary": {"source_count": 4, "protected_scope_modified": False, "auto_publish": False}}
    payload["canonical_digest"] = validator._digest(validator._fixed_core(payload))
    return payload


def test_schema_and_semantic_contract_reject_role_escalation_and_mode_change(tmp_path: Path) -> None:
    payload = _payload()
    schema = validator.REPO_ROOT / "schemas/phase2-source-expansion-admission-v3.schema.json"
    audit = tmp_path / "audit.json"; _json(audit, payload)
    assert validator.validate(audit, schema, determinism_check=True)["status"] == "passed"
    bad = copy.deepcopy(payload); bad["sources"][2]["role"] = "full"
    _json(audit, bad)
    with pytest.raises(validator.ValidationFailure): validator.validate(audit, schema)
    bad = copy.deepcopy(payload); bad["adapter_ready_batch"] = [{"source_id": "goku-openlab-gpt-image-2-prompts-datasets", "revision": validator.SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]["revision"], "mode": "fixed_history", "case_scope": {"case_count": 1, "case_ledger_sha256": "0" * 64}, "structure_strategy": "fixture", "family_role": "aggregator", "exclusions": []}]
    _json(audit, bad)
    with pytest.raises(validator.ValidationFailure, match="wrong adapter mode"): validator.validate(audit, schema)
    bad = copy.deepcopy(payload); bad["sources"][3]["evidence"]["control_record"]["readme_backup_claim"] = False
    _refresh_payload_digests(bad, 3); _json(audit, bad)
    with pytest.raises(validator.ValidationFailure, match="Schema validation failed"): validator.validate(audit, schema)


def _refresh_payload_digests(payload: dict[str, Any], source_index: int) -> None:
    row = payload["sources"][source_index]
    row["fixed_core_digest"] = validator._digest({key: value for key, value in row.items() if key != "fixed_core_digest"})
    payload["canonical_digest"] = validator._digest(validator._fixed_core(payload))


def test_schema_and_semantics_reject_forged_authority_and_history(tmp_path: Path) -> None:
    schema = validator.REPO_ROOT / "schemas/phase2-source-expansion-admission-v3.schema.json"
    audit = tmp_path / "audit.json"

    payload = _payload()
    payload["sources"][0]["evidence"]["authority"]["tree_manifest_sha256"] = "f" * 64
    payload["sources"][0]["evidence"]["maintenance"]["snapshots"][-1]["tree_manifest_sha256"] = "f" * 64
    _refresh_payload_digests(payload, 0); _json(audit, payload)
    with pytest.raises(validator.ValidationFailure, match="authority invariant drift"): validator.validate(audit, schema)

    payload = _payload()
    payload["sources"][1]["evidence"]["authority"]["unexpected"] = True
    _refresh_payload_digests(payload, 1); _json(audit, payload)
    with pytest.raises(validator.ValidationFailure, match="Schema validation failed"): validator.validate(audit, schema)

    payload = _payload()
    payload["sources"][2]["evidence"]["comparator_ledger"]["authority"]["tree_manifest_sha256"] = "e" * 64
    _refresh_payload_digests(payload, 2); _json(audit, payload)
    with pytest.raises(validator.ValidationFailure, match="control authority drift"): validator.validate(audit, schema)

    payload = _payload()
    payload["sources"][2]["evidence"]["comparator_ledger"]["source_media_reference_count"] = 2
    comparator = payload["sources"][2]["evidence"]["comparator_ledger"]
    comparator["digest"] = validator._digest({key: value for key, value in comparator.items() if key != "digest"})
    _refresh_payload_digests(payload, 2); _json(audit, payload)
    with pytest.raises(validator.ValidationFailure, match="media/attribution summary drift"): validator.validate(audit, schema)


def test_digest_excludes_generated_at_but_not_contract_mutation() -> None:
    payload = _payload(); original = payload["canonical_digest"]
    payload["generated_at"] = "2026-08-11T00:00:00Z"
    assert validator._digest(validator._fixed_core(payload)) == original
    payload["sources"][0]["status"] = "fixed_history_ready"
    assert validator._digest(validator._fixed_core(payload)) != original


def test_checked_in_report_if_present() -> None:
    audit = validator.REPO_ROOT / "reports/phase2/source-expansion-admission-v3.json"
    if not audit.exists(): pytest.skip("coordinator has not generated checked-in v3 report yet")
    result = validator.validate(audit, validator.REPO_ROOT / "schemas/phase2-source-expansion-admission-v3.schema.json", determinism_check=True)
    assert result["status"] == "passed"


@pytest.mark.parametrize("source_id,role,mode,status", [
    ("goku-openlab-gpt-image-2-prompts-datasets", "full", "continuous", "continuous_ready"),
    ("chaosrealmsai-gpt-image-2-gallery", "full", "fixed_history", "fixed_history_ready"),
    ("youmind-openlab-gpt-image-2-prompts-search", "comparator", "reserve", "comparator_only"),
    ("tigerowo-awesome-gpt-image-2-prompts", "excluded_control", "excluded", "excluded"),
])
def test_source_role_contract_is_fixed(source_id: str, role: str, mode: str, status: str) -> None:
    spec = validator.SOURCE_SPECS[source_id]
    assert (spec["role"], spec["mode"], spec["status"]) == (role, mode, status)


@pytest.mark.parametrize("count,expected", [(0, 0), (1, 1), (30, 30), (50, 30), (95, 30), (198, 30), (284, 43), (400, 60)])
def test_quality_sample_formula_remains_v2_compatible(count: int, expected: int) -> None:
    assert validator.v2._expected_sample_size(count) == expected


@pytest.mark.parametrize("value,expected", [
    (" https://twitter.com/User/status/8?x=1 ", "https://x.com/user/status/8"),
    ("https://github.com/owner/repo", None),
    ("not a URL", None),
    ("HTTPS://x.com/A/status/9", "https://x.com/a/status/9"),
])
def test_source_url_normalization_is_reused(value: str, expected: str | None) -> None:
    assert validator._normalize_source_url(value) == expected


@pytest.mark.parametrize("text,flag", [
    ("German Reisepass Ausweis portrait", "identity_or_official_document"),
    ("FIFA Cristiano Ronaldo CR7 stadium poster", "public_figure_or_celebrity"),
    ("Sam Altman speaking at an event", "public_figure_or_celebrity"),
    ("OpenAI SpaceX ClaudeCode product visual", "brand_or_logo"),
    ("Ferrari Minions GTA transparent background no watermark", "third_party_ip_or_character"),
    ("minor child holding a rifle with blood", "minor_or_young_person"),
    ("remove watermark transparent cutout", "watermark_removal_or_transparency"),
    ("文字化け ??? AI watermark", "suspicious_garbled_or_watermark"),
])
def test_v3_multilingual_lint_catches_empirical_risk_terms(text: str, flag: str) -> None:
    assert flag in validator._v3_risk_flags(text)


def test_ascii_risk_terms_use_token_boundaries() -> None:
    assert "weapon_or_gore" not in validator._v3_risk_flags("A burgundy editorial poster with layered paper texture and soft studio lighting")
    assert "weapon_or_gore" in validator._v3_risk_flags("A documentary photograph showing a gun on a table")


def test_risk_exclusions_are_specific_and_recomputable() -> None:
    case = validator._case("risk", "risk", "x", "A long complete prompt describing an otherwise useful graphic image with enough words to avoid short prompt handling.", "https://x.com/a/status/1", "fixture", [{"lfs_oid": "a" * 64}], risk_text="Sam Altman OpenAI Ferrari Minions")
    retained, exclusions = validator._reasoned_filter([case], family_hashes=set(), current={"prompt": set(), "source_url": set(), "image": set()})
    assert not retained
    assert {item["reason"] for item in exclusions} >= {"risk:public_figure_or_celebrity", "risk:brand_or_logo", "risk:third_party_ip_or_character"}


def test_failed_quality_sample_produces_blocked_waterfall() -> None:
    output = {"path": "fixture.png", "byte_size": 12, "sha256": "a" * 64}
    case = validator._case("ok", "ok", "x", "A sufficiently detailed fixture prompt with many terms and constraints for deterministic quality sample selection.", "https://x.com/a/status/1", "fixture", [output])
    reviews = {"_sample_manifest_sha256": "b" * 64, "ok": {"result": "fail", "prompt_complete": True, "image_readable": True, "semantic_match": False, "visual_quality": "acceptable", "asset_checks": [{**output, "decoded": True}]}}
    quality = validator._quality([case], reviews, [])
    evidence = {"case_ledger": [case], "quality": quality, "eligibility": {key: True for key in ("asset_authority_complete", "strong_pairing", "within_source_unique", "family_unique", "current_exact_new", "maintenance_eligible", "rights_review_required", "quality_pass", "sync_eligible")}}
    assert quality["result"] == "fail"
    assert not validator._eligible(evidence, "goku-openlab-gpt-image-2-prompts-datasets")


def test_exclusion_quality_review_is_required_and_reason_bound() -> None:
    output = {"path": "fixture.png", "byte_size": 12, "sha256": "a" * 64}
    case = validator._case("ok", "ok", "x", "A sufficiently detailed fixture prompt with many terms and constraints for deterministic quality sample selection.", "https://x.com/a/status/1", "fixture", [output])
    excluded_case = validator._case("x", "x", "x", "Another sufficiently detailed fixture prompt used to prove exclusion evidence remains reason-bound and asset-bound.", "https://x.com/a/status/2", "fixture-x", [output])
    checks = [{**output, "decoded": True}]
    review = {"_sample_manifest_sha256": "b" * 64, "ok": {"result": "pass", "prompt_complete": True, "image_readable": True, "semantic_match": True, "visual_quality": "high", "asset_checks": checks}}
    excluded = [{"case_id": "x", "reason": "missing_asset"}]
    failed = validator._quality([case], review, excluded, [excluded_case])
    assert failed["result"] == "fail" and failed["missing_exclusion_reviews"]
    review["_exclusions"] = {"missing_asset": {"case_id": "x", "result": "confirmed", "reason_confirmed": True, "asset_checks": checks}}
    assert validator._quality([case], review, excluded, [excluded_case])["result"] == "pass"


def test_live_cli_uses_canonical_external_quality_review_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_validate(audit: Path, schema: Path, *, determinism_check: bool, live: bool, quality_review: Path | None) -> dict[str, Any]:
        captured.update({"audit": audit, "schema": schema, "determinism_check": determinism_check, "live": live, "quality_review": quality_review})
        return {"status": "passed", "canonical_digest": "a" * 64, "summary": {}}

    monkeypatch.setattr(validator, "validate", fake_validate)
    assert validator.main(["--audit", str(tmp_path / "audit.json"), "--schema", str(tmp_path / "schema.json"), "--live", "--determinism-check", "--json"]) == 0
    assert captured["live"] is True and captured["determinism_check"] is True
    assert captured["quality_review"] == validator.RUNTIME_ROOT / "quality-review.json"


def test_sample_manifest_binds_digest_decoded_asset_and_runtime_root(tmp_path: Path) -> None:
    image_module = pytest.importorskip("PIL.Image")
    asset = tmp_path / "samples-final-v3" / "assets" / "sample.png"
    asset.parent.mkdir(parents=True)
    image_module.new("RGB", (2, 2), "white").save(asset)
    data = asset.read_bytes()
    item = {
        "source_id": "goku-openlab-gpt-image-2-prompts-datasets",
        "kind": "admission",
        "case_id": "case-1",
        "reason": "admission_sample",
        "asset_checks": [{"path": "images/sample.png", "local_path": str(asset), "byte_size": len(data), "sha256": validator.hashlib.sha256(data).hexdigest(), "decoded": True}],
    }
    digest = validator.hashlib.sha256(json.dumps([item], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    _json(tmp_path / "samples-final-v3" / "sample-manifest.json", {"schema_version": 1, "revision": validator.SOURCE_SPECS["goku-openlab-gpt-image-2-prompts-datasets"]["revision"], "items": [item], "item_count": 1, "decoded_asset_count": 1, "manifest_sha256": digest})
    reviews = {"goku-openlab-gpt-image-2-prompts-datasets": {"_sample_manifest_sha256": digest}}
    assert validator._verified_sample_manifest(tmp_path, reviews) == [item]
    asset.write_bytes(data + b"drift")
    with pytest.raises(validator.ValidationFailure, match="asset authority mismatch"):
        validator._verified_sample_manifest(tmp_path, reviews)
