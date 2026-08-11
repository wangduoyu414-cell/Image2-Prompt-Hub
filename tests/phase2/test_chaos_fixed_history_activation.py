from __future__ import annotations

import copy

import pytest

from scripts import validate_chaos_fixed_history as validator


def test_checked_in_fixed_history_activation_closes_static_authority() -> None:
    assert validator.validate_static() == {
        "status": "passed",
        "source_count": 7,
        "case_count": 2460,
        "output_count": 7380,
        "sync_eligible": False,
        "auto_publish": False,
    }


def test_fixed_history_mode_cannot_be_silently_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = validator._load

    def mutated(path):
        payload = original(path)
        if path.name == "sources-v2.yaml":
            payload = copy.deepcopy(payload)
            chaos = next(item for item in payload["sources"] if item["source_id"] == validator.SOURCE_ID)
            chaos["sync"]["enabled"] = True
        return payload

    monkeypatch.setattr(validator, "_load", mutated)
    with pytest.raises(validator.ValidationFailure):
        validator.validate_static()
