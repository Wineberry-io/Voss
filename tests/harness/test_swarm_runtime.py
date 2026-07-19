"""R3 swarm runtime orchestrator tests (SWARM-RECONCILIATION, Wave 3).

Drives `run_cli_member` / `run_cli_swarm` end-to-end against a REAL temp git repo
(mirrors tests/harness/test_layout.py + test_swarm_worktree.py `_git` style) with
a FAKE spawn_fn — no real `claude`/`codex` is ever launched, and nothing uses
`time.sleep` for synchronization.

Each fake spawn writes inside the worktree cwd it is handed (simulating the CLI
doing its work in its own checkout), then returns a handle whose `wait()` returns
an exit code. Correctness of the ownership reconciliation is asserted on the MAIN
branch state AFTER the run, which is what the deterministic post-exit check (not a
racing watcher) guarantees.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from voss.harness.swarm_runtime import (
    MemberResult,
    run_cli_member,
    run_cli_swarm,
    subprocess_spawn,
)
from voss.harness.swarm_store import CANDIDATE_READY, DONE, Role, SwarmStore


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """git init repo with a committed file (worktree add needs a HEAD)."""
    root = tmp_path / "proj"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@test"], root)
    _git(["config", "user.name", "test"], root)
    (root / "base.txt").write_text("base\n")
    (root / "owned.py").write_text("# original\n")
    (root / "other.py").write_text("# untouched\n")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "-m", "init"], root)
    return root


class _FakeHandle:
    """A SpawnHandle whose wait() returns a fixed code; terminate() is a no-op."""

    def __init__(self, code: int = 0) -> None:
        self._code = code

    def wait(self, timeout: float | None = None) -> int:
        return self._code

    def terminate(self) -> None:
        pass


def _result_md(agent: str, summary: str) -> str:
    return (
        "---\n"
        f"agent: {agent}\n"
        "status: complete\n"
        "---\n\n"
        f"{summary}\n"
    )


def _write_result(repo: Path, swarm_id: str, role: str, summary: str) -> None:
    """Write the member's result into the MAIN repo's shared file-bus — where the
    host hands the CLI its result path and where run_cli_member reads it back."""
    results = repo / ".voss" / "swarm" / swarm_id / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / f"{role}.result.md").write_text(_result_md("codex", summary))


def _spawn_with_result(
    repo: Path, edits: dict[str, str], swarm_id: str, role: str, summary: str
):
    """Fake spawn: edits files in the worktree cwd, writes the result into the
    main repo file-bus, then returns a clean handle."""

    def spawn_fn(argv: list[str], cwd: Path) -> _FakeHandle:
        for rel, content in edits.items():
            target = cwd / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        _write_result(repo, swarm_id, role, summary)
        return _FakeHandle(0)

    return spawn_fn


def test_happy_path_owned_edit_preserves_candidate_for_review(repo: Path) -> None:
    store = SwarmStore(cwd=repo)
    swarm = store.create("ship it", cwd=str(repo), roster=[Role(name="builder-1", agent="codex")])
    role = swarm.roster[0]
    task = store.add_task(swarm.id, "edit owned", owned_files=["owned.py"])

    spawn = _spawn_with_result(
        repo, {"owned.py": "# changed by builder\n"}, swarm.id, "builder-1", "edited owned.py"
    )

    result = asyncio.run(
        run_cli_member(store, repo, swarm.id, role, task, spawn_fn=spawn)
    )

    assert isinstance(result, MemberResult)
    assert result.violations == []
    assert result.merged is False
    assert result.candidate_ready is True
    assert result.candidate_branch == f"swarm/{swarm.id}/builder-1"
    assert result.candidate_head
    assert result.candidate_worktree
    assert Path(result.candidate_worktree).is_dir()
    assert result.summary == "edited owned.py"
    # The worker finished, but integration is still gated on candidate review.
    stored = store.get(swarm.id).task(task.id)
    assert stored.state == CANDIDATE_READY
    assert stored.candidate_branch == result.candidate_branch
    assert stored.candidate_head == result.candidate_head
    # The main checkout remains untouched until explicit integration.
    assert (repo / "owned.py").read_text() == "# original\n"
    candidate = subprocess.run(
        ["git", "show", f"{result.candidate_head}:owned.py"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )
    assert candidate.stdout == "# changed by builder\n"


def test_ownership_violation_reverted_and_escalated(repo: Path) -> None:
    store = SwarmStore(cwd=repo)
    swarm = store.create("ship it", cwd=str(repo), roster=[Role(name="builder-1", agent="codex")])
    role = swarm.roster[0]
    task = store.add_task(swarm.id, "edit owned", owned_files=["owned.py"])

    # Fake edits BOTH the owned file and a NON-owned file (out of scope).
    spawn = _spawn_with_result(
        repo,
        {"owned.py": "# legit\n", "other.py": "# OUT OF SCOPE\n"},
        swarm.id,
        "builder-1",
        "touched two files",
    )

    events: list[dict] = []
    result = asyncio.run(
        run_cli_member(
            store, repo, swarm.id, role, task, spawn_fn=spawn, on_event=events.append
        )
    )

    # detect_violations caught the out-of-scope write.
    assert "other.py" in result.violations
    # A needs_operator event was emitted with the offending path.
    needs_op = [e for e in events if e["type"] == "swarm.needs_operator"]
    assert needs_op and "other.py" in needs_op[0]["paths"]
    assert needs_op[0]["task_id"] == task.id

    # Main remains untouched; the preserved candidate contains only the owned edit.
    assert (repo / "other.py").read_text() == "# untouched\n"
    assert (repo / "owned.py").read_text() == "# original\n"
    assert result.candidate_head
    assert subprocess.run(
        ["git", "show", f"{result.candidate_head}:owned.py"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout == "# legit\n"
    assert subprocess.run(
        ["git", "show", f"{result.candidate_head}:other.py"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout == "# untouched\n"


def test_native_roles_skipped_still_completes(repo: Path) -> None:
    store = SwarmStore(cwd=repo)
    # All-native roster (agent defaults to "voss") → run_cli_swarm runs no member.
    swarm = store.create(
        "native only",
        cwd=str(repo),
        roster=[Role(name="coordinator"), Role(name="reviewer")],
    )

    spawn_calls: list[list[str]] = []

    def spy_spawn(argv: list[str], cwd: Path) -> _FakeHandle:
        spawn_calls.append(argv)
        return _FakeHandle(0)

    events: list[dict] = []
    results = asyncio.run(
        run_cli_swarm(store, repo, swarm.id, spawn_fn=spy_spawn, on_event=events.append)
    )

    assert results == []
    assert spawn_calls == []  # zero members spawned
    complete = [e for e in events if e["type"] == "swarm.complete"]
    assert complete and complete[0]["task_count"] == 0


def test_run_cli_swarm_runs_cli_members(repo: Path) -> None:
    """run_cli_swarm zips CLI roles to tasks and runs them; native roles dropped."""
    store = SwarmStore(cwd=repo)
    swarm = store.create(
        "mixed",
        cwd=str(repo),
        roster=[
            Role(name="coordinator"),  # native → skipped
            Role(name="builder-1", agent="codex"),
            Role(name="builder-2", agent="codex"),
        ],
    )
    ta = store.add_task(swarm.id, "A", owned_files=["owned.py"])
    tb = store.add_task(swarm.id, "B", owned_files=["other.py"])

    # Two fakes keyed by role; run_cli_swarm zips cli_roles[0]→tasks[0], etc.
    def spawn(argv: list[str], cwd: Path) -> _FakeHandle:
        # Figure out which member this is from its worktree dir name (last part).
        role = cwd.name
        rel = "owned.py" if role == "builder-1" else "other.py"
        (cwd / rel).write_text(f"# by {role}\n")
        _write_result(repo, swarm.id, role, f"{role} done")
        return _FakeHandle(0)

    events: list[dict] = []
    results = asyncio.run(
        run_cli_swarm(store, repo, swarm.id, spawn_fn=spawn, on_event=events.append)
    )

    assert len(results) == 2
    assert {r.role for r in results} == {"builder-1", "builder-2"}
    assert all(r.violations == [] and not r.merged and r.candidate_ready for r in results)
    assert {store.get(swarm.id).task(t).state for t in (ta.id, tb.id)} == {
        CANDIDATE_READY
    }
    # Neither candidate is merged into main automatically.
    assert (repo / "owned.py").read_text() == "# original\n"
    assert (repo / "other.py").read_text() == "# untouched\n"
    ready = [e for e in events if e["type"] == "swarm.candidates_ready"]
    assert ready and ready[0]["candidate_count"] == 2
    assert not [e for e in events if e["type"] == "swarm.complete"]


def test_no_change_member_completes_and_cleans_up(repo: Path) -> None:
    store = SwarmStore(cwd=repo)
    swarm = store.create("inspect", cwd=str(repo), roster=[Role(name="reviewer", agent="codex")])
    role = swarm.roster[0]
    task = store.add_task(swarm.id, "inspect only", owned_files=["owned.py"])

    def spawn(argv: list[str], cwd: Path) -> _FakeHandle:
        _write_result(repo, swarm.id, role.name, "no changes")
        return _FakeHandle(0)

    result = asyncio.run(
        run_cli_member(store, repo, swarm.id, role, task, spawn_fn=spawn)
    )

    assert result.candidate_ready is False
    assert result.candidate_head is None
    assert store.get(swarm.id).task(task.id).state == DONE
    assert not Path(result.candidate_worktree or "missing").exists()


def test_subprocess_spawn_real_process(tmp_path: Path) -> None:
    """The default headless backend actually starts a process and reports its
    exit code (no shell, argv list)."""
    handle = subprocess_spawn(["python3", "-c", "import sys; sys.exit(3)"], tmp_path)
    assert handle.wait() == 3
