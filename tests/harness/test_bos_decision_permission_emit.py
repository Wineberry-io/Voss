"""BOS4: permission prompts emit human-verdict decision records."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from portalocker.exceptions import LockException

from voss.harness.bos_decisions import decisions_ledger_path, read_decisions
from voss.harness.cognition_schemas import PermissionsConfig
from voss.harness.permissions import PermissionGate, PermissionStore

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "contracts" / "decision-ledger.schema.json"
MUTATING_ARGS = {
    "path": "target.txt",
    "content": "new content\n",
    "api_token": "super-secret-token",
}


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _assert_no_decisions(cwd: Path) -> None:
    ledger_path = decisions_ledger_path(cwd)
    assert read_decisions(cwd) == []
    assert not ledger_path.exists() or not ledger_path.read_text().strip()


@pytest.mark.parametrize(
    ("choice", "reason"),
    [
        ("a", "allowed once"),
        ("A", "allowed always"),
    ],
)
def test_human_approval_emits_one_schema_valid_record(
    choice: str,
    reason: str,
    validator: jsonschema.Draft202012Validator,
    tmp_path: Path,
) -> None:
    gate = PermissionGate(
        mode="edit",
        cwd=tmp_path,
        prompt_fn=lambda _tool, _args: choice,
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (True, reason)

    records = read_decisions(tmp_path)
    assert len(records) == 1
    record = records[0]
    assert record["decision_type"] == "no_action"
    assert record["human_verdict"]["verdict"] == "approve"
    assert record["actual_action"] == {"allowed": True}
    snapshot = record["feature_snapshot"]
    assert set(snapshot) == {
        "tool_name",
        "is_mutating",
        "mode",
        "signature",
        "diff_summary",
    }
    assert snapshot["tool_name"] == "fs_write"
    assert snapshot["is_mutating"] is True
    assert snapshot["mode"] == "edit"
    assert snapshot["signature"] == "fs_write"
    assert isinstance(snapshot["diff_summary"], str)
    assert "super-secret-token" not in json.dumps(snapshot)
    validator.validate(record)


def test_human_denial_emits_one_schema_valid_dismiss_record(
    validator: jsonschema.Draft202012Validator,
    tmp_path: Path,
) -> None:
    gate = PermissionGate(
        mode="edit",
        cwd=tmp_path,
        prompt_fn=lambda _tool, _args: "n",
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (False, "denied")

    records = read_decisions(tmp_path)
    assert len(records) == 1
    assert records[0]["human_verdict"]["verdict"] == "dismiss"
    assert records[0]["actual_action"] == {"allowed": False}
    validator.validate(records[0])


def test_repeated_human_answers_emit_distinct_decisions(tmp_path: Path) -> None:
    gate = PermissionGate(
        mode="edit",
        cwd=tmp_path,
        prompt_fn=lambda _tool, _args: "a",
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True)[0] is True
    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True)[0] is True

    records = read_decisions(tmp_path)
    assert len(records) == 2
    assert len({record["decision_id"] for record in records}) == 2


@pytest.mark.parametrize("error_type", [OSError, ValueError, LockException])
def test_ledger_error_does_not_change_permission_verdict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error_type: type[Exception],
) -> None:
    def fail_append(*_args: object, **_kwargs: object) -> bool:
        raise error_type("simulated ledger failure")

    monkeypatch.setattr("voss.harness.permissions.append_decision", fail_append)
    gate = PermissionGate(
        mode="edit",
        cwd=tmp_path,
        prompt_fn=lambda _tool, _args: "a",
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (
        True,
        "allowed once",
    )
    _assert_no_decisions(tmp_path)


def test_permission_store_cwd_is_used_when_explicit_cwd_is_absent(
    tmp_path: Path,
) -> None:
    gate = PermissionGate(
        mode="edit",
        store=PermissionStore(cwd=tmp_path),
        prompt_fn=lambda _tool, _args: "a",
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (
        True,
        "allowed once",
    )
    assert len(read_decisions(tmp_path)) == 1


def test_auto_allow_does_not_emit(tmp_path: Path) -> None:
    gate = PermissionGate(mode="auto", cwd=tmp_path)

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (True, "auto")

    _assert_no_decisions(tmp_path)


def test_rule_allow_does_not_emit(tmp_path: Path) -> None:
    gate = PermissionGate(
        mode="edit",
        cwd=tmp_path,
        prompt_fn=lambda _tool, _args: pytest.fail("allow rule must not prompt"),
        project_policy=PermissionsConfig(rules={"fs_write": "allow"}),
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (
        True,
        "allowed by permission rule (.voss/permissions.yml)",
    )
    _assert_no_decisions(tmp_path)


def test_remembered_allow_does_not_emit(tmp_path: Path) -> None:
    store = PermissionStore(cwd=tmp_path, always={"fs_write"})
    gate = PermissionGate(mode="edit", cwd=tmp_path, store=store)

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (
        True,
        "remembered",
    )

    _assert_no_decisions(tmp_path)


def test_noninteractive_denial_does_not_emit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    gate = PermissionGate(mode="edit", cwd=tmp_path)

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (
        False,
        "non-interactive denial",
    )

    _assert_no_decisions(tmp_path)


def test_human_answer_with_no_cwd_does_not_emit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    gate = PermissionGate(
        mode="edit",
        cwd=None,
        prompt_fn=lambda _tool, _args: "a",
    )

    assert gate.check("fs_write", MUTATING_ARGS, is_mutating=True) == (
        True,
        "allowed once",
    )

    _assert_no_decisions(tmp_path)
