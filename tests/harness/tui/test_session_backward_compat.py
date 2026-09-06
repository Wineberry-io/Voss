"""M9-06: pre-M9 session JSON files must round-trip via the new reader.

`_hydrate` (voss/harness/session.py) already filters to schema fields, so
adding `parent_id` / `parent_turn_index` is safe in BOTH directions.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path


from voss.harness import session as session_store
from voss.harness.session import SessionRecord


PRE_M9_FIXTURE = {
    "id": "abcd1234efgh",
    "name": "session-abcd1234",
    "cwd": "",
    "model": "claude-sonnet-4",
    "started_at": "2026-04-01T00:00:00",
    "updated_at": "2026-04-01T00:00:00",
    "total_cost_usd": 0.12,
    "turns": [
        {"role": "user", "content": "first task"},
        {"role": "assistant", "content": "first reply"},
    ],
    "runs": [],
}


def _write_session(dir_path: Path, data: dict) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    p = dir_path / f"{data['id']}.json"
    p.write_text(json.dumps(data))
    return p


def test_pre_m9_session_loads_without_crash(tmp_path: Path) -> None:
    data = dict(PRE_M9_FIXTURE)
    data["cwd"] = str(tmp_path)
    _write_session(tmp_path / ".voss" / "sessions", data)
    record, history = session_store.load(data["id"], cwd=tmp_path)
    assert record.id == data["id"]
    assert record.parent_id is None
    assert record.parent_turn_index is None
    assert len(record.turns) == 2


def test_new_session_with_parent_fields_roundtrips(tmp_path: Path) -> None:
    from voss_runtime import EpisodicMemory

    record = SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
    record.parent_id = "0123456789ab"
    record.parent_turn_index = 5
    history = EpisodicMemory(capacity=10)
    history.add("hi", role="user")
    session_store.save(record, history)
    reloaded, _ = session_store.load(record.id, cwd=tmp_path)
    assert reloaded.parent_id == "0123456789ab"
    assert reloaded.parent_turn_index == 5


def test_parent_fields_in_session_fields_set() -> None:
    names = {f.name for f in dataclasses.fields(SessionRecord)}
    assert "parent_id" in names
    assert "parent_turn_index" in names
    assert "parent_id" in session_store._SESSION_FIELDS
    assert "parent_turn_index" in session_store._SESSION_FIELDS


def test_pre_m9_extra_unknown_keys_dropped(tmp_path: Path) -> None:
    data = dict(PRE_M9_FIXTURE)
    data["cwd"] = str(tmp_path)
    data["legacy_telemetry"] = "should_be_dropped"
    data["api_key"] = "sk-evil-not-allowed"
    _write_session(tmp_path / ".voss" / "sessions", data)
    record, _ = session_store.load(data["id"], cwd=tmp_path)
    # Unknown keys never make it onto the dataclass.
    assert not hasattr(record, "legacy_telemetry") or getattr(
        record, "legacy_telemetry", None
    ) is None
    # And the redaction guarantee still holds.
    assert "api_key" not in {f.name for f in dataclasses.fields(SessionRecord)}
