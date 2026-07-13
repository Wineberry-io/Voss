"""BOS4-04: task_to_agent decision emission at the swarm assignment seam (D-R02).

Drives `run_cli_member` against a REAL temp git repo with a FAKE spawn_fn
(mirrors tests/harness/test_swarm_runtime.py), then asserts the inline-emitted
decision record landed in `.voss/bos/decisions.jsonl` and validates against the
authoritative contract.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from voss.harness.swarm_runtime import run_cli_member
from voss.harness.swarm_store import Role, SwarmStore

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "contracts" / "decision-ledger.schema.json"


@pytest.fixture(scope="module")
def validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@test"], root)
    _git(["config", "user.name", "test"], root)
    (root / "base.txt").write_text("base\n")
    (root / "owned.py").write_text("# original\n")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", "init"], root)
    return root


class _FakeHandle:
    def __init__(self, code: int = 0) -> None:
        self._code = code

    def wait(self, timeout: float | None = None) -> int:
        return self._code

    def terminate(self) -> None:
        pass


def _write_result(repo: Path, swarm_id: str, role: str) -> None:
    results = repo / ".voss" / "swarm" / swarm_id / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{role}.result.md").write_text(
        "---\nagent: codex\nstatus: complete\n---\n\ndone\n"
    )


def _spawn(repo: Path, swarm_id: str, role: str):
    def spawn_fn(argv: list[str], cwd: Path) -> _FakeHandle:
        (cwd / "owned.py").write_text("# changed\n")
        _write_result(repo, swarm_id, role)
        return _FakeHandle(0)

    return spawn_fn


def _read_decisions(repo: Path) -> list[dict]:
    path = repo / ".voss" / "bos" / "decisions.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_assignment_seam_emits_schema_valid_task_to_agent(
    validator: jsonschema.Draft202012Validator,
    repo: Path,
) -> None:
    store = SwarmStore(cwd=repo)
    swarm = store.create("ship it", cwd=str(repo), roster=[Role(name="builder-1", agent="codex")])
    role = swarm.roster[0]
    task = store.add_task(swarm.id, "edit owned", owned_files=["owned.py"])

    asyncio.run(
        run_cli_member(store, repo, swarm.id, role, task, spawn_fn=_spawn(repo, swarm.id, "builder-1"))
    )

    records = _read_decisions(repo)
    assert len(records) == 1
    record = records[0]
    assert record["decision_type"] == "task_to_agent"
    validator.validate(record)

    assert set(record["feature_snapshot"]) == {"goal", "roster", "available_models", "cwd"}
    assert record["feature_snapshot"]["goal"] == "edit owned"
    assert record["entity_ref"]["task_id"] == task.id
    assert record["entity_ref"]["swarm_id"] == swarm.id
    assert record["payload"]["chosen_agent_id"] == "codex"


def test_repeat_assignment_is_dedup_noop(repo: Path) -> None:
    store = SwarmStore(cwd=repo)
    swarm = store.create("ship it", cwd=str(repo), roster=[Role(name="builder-1", agent="codex")])
    role = swarm.roster[0]
    task = store.add_task(swarm.id, "edit owned", owned_files=["owned.py"])

    for _ in range(2):
        asyncio.run(
            run_cli_member(store, repo, swarm.id, role, task, spawn_fn=_spawn(repo, swarm.id, "builder-1"))
        )

    assert len(_read_decisions(repo)) == 1
