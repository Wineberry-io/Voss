"""BOS4: local append-only BOS decision ledger (inline emission, D-R01)."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from voss.harness.bos_decisions import (
    BosDecisionLedger,
    append_decision,
    build_as_of,
    build_task_to_agent_record,
    build_verdict_record,
    read_decisions,
    _read_last_event_id,
)

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "contracts" / "decision-ledger.schema.json"


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _task_record() -> dict:
    return build_task_to_agent_record(
        decision_id="dec-1",
        task_id="task-1",
        chosen_agent_id="claude",
        candidate_agents=["claude", "codex"],
        feature_snapshot={"goal": "wire ledger", "roster": ["impl"], "cwd": "/tmp"},
        entity_ref={"task_id": "task-1", "swarm_id": "swarm-1"},
        as_of={"event_seq": 2, "snapshot_id": "e2"},
        rationale="swarm assignment seam",
    )


def _verdict_record() -> dict:
    return build_verdict_record(
        decision_id="dec-2",
        verdict="approve",
        actor_id="ben",
        feature_snapshot={"tool_name": "Write", "is_mutating": True, "mode": "default"},
        entity_ref={"session_id": "sess-1"},
        as_of={"event_seq": 2, "snapshot_id": "e2"},
        rationale="human approved Write at permission gate",
        reason="operator allowed once",
    )


def test_records_append_replay_and_validate(
    validator: jsonschema.Draft202012Validator,
    tmp_path: Path,
) -> None:
    ledger = BosDecisionLedger(tmp_path)
    records = [_task_record(), _verdict_record()]

    assert ledger.append_decisions(records) == 2
    assert ledger.path == tmp_path / ".voss" / "bos" / "decisions.jsonl"

    replayed = ledger.read_decisions()
    assert [r["decision_id"] for r in replayed] == ["dec-1", "dec-2"]
    for record in replayed:
        validator.validate(record)


def test_duplicate_decision_id_is_noop_and_preserves_bytes(tmp_path: Path) -> None:
    record = _task_record()

    assert append_decision(tmp_path, record) is True
    before = (tmp_path / ".voss" / "bos" / "decisions.jsonl").read_bytes()

    assert append_decision(tmp_path, dict(record)) is False
    after = (tmp_path / ".voss" / "bos" / "decisions.jsonl").read_bytes()

    assert after == before


def test_read_decisions_tolerates_torn_trailing_line(tmp_path: Path) -> None:
    record = _task_record()
    path = tmp_path / ".voss" / "bos" / "decisions.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(record, sort_keys=True) + '\n{"decision_id":')

    assert read_decisions(tmp_path) == [record]


def test_as_of_reads_last_event_id(tmp_path: Path) -> None:
    events_path = tmp_path / ".voss" / "bos" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    events_path.write_text(
        json.dumps({"event_id": "e1"}, sort_keys=True)
        + "\n"
        + json.dumps({"event_id": "e2"}, sort_keys=True)
        + "\n"
    )

    assert _read_last_event_id(events_path) == "e2"
    assert _read_last_event_id(tmp_path / ".voss" / "bos" / "absent.jsonl") is None


def test_build_as_of_assembles_from_events(tmp_path: Path) -> None:
    events_path = tmp_path / ".voss" / "bos" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    events_path.write_text(
        json.dumps({"event_id": "e1"}, sort_keys=True)
        + "\n"
        + json.dumps({"event_id": "e2"}, sort_keys=True)
        + "\n"
    )

    assert build_as_of(events_path) == {"event_seq": 2, "snapshot_id": "e2"}
    assert build_as_of(tmp_path / ".voss" / "bos" / "absent.jsonl") == {}


def test_verdict_record_uses_no_action_type(
    validator: jsonschema.Draft202012Validator,
) -> None:
    record = _verdict_record()

    assert record["decision_type"] == "no_action"
    assert record["payload"]["decision_type"] == "no_action"
    assert record["human_verdict"]["verdict"] in {"approve", "dismiss"}
    validator.validate(record)

    denied = build_verdict_record(
        decision_id="dec-3",
        verdict="dismiss",
        actor_id="ben",
        feature_snapshot={"tool_name": "Bash"},
        entity_ref={"session_id": "sess-1"},
        as_of={},
        rationale="human denied Bash",
    )
    assert denied["human_verdict"]["verdict"] == "dismiss"
    validator.validate(denied)
