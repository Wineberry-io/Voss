"""R3 server-side swarm orchestrator — run a CLI swarm member end-to-end.

This is the glue tying together the already-built Wave 1/2 pieces (see
`SWARM-RECONCILIATION.md`, "R3 Concrete Plan"): the SwarmStore (state), the agent
argv resolver, the git-worktree-per-member lifecycle, the file-bus, and the
ownership detect/revert plane. It is the **headless execution backend** of R3's
two-backend split — the server spawns each CLI as a plain subprocess in its own
worktree; the GUI/Tauri PTY backend is the other (out of scope here).

The design centers on two things the tests pin down:

1. **An injectable spawn seam.** No real `claude`/`codex` binary exists in CI, so
   spawning is a `SpawnFn` the caller supplies. The default `subprocess_spawn`
   wraps `subprocess.Popen` (no shell) for production; tests pass a fake.

2. **Deterministic post-exit ownership reconciliation.** R3's ownership guarantee
   for black-box CLIs is post-hoc (the watcher can't gate a write before it
   lands). So *after* the member process exits we do the authoritative check —
   `changed_files` → `detect_violations` → revert + escalate — rather than racing
   live fs events. A live `OwnershipWatcher` may run alongside as
   belt-and-suspenders, but correctness never depends on it firing.

This module is the "control + enforcement plane" half: it owns the worktree
lifecycle and ownership reconciliation. It is intentionally free of any FastAPI /
SSE import — the caller (the swarm route) passes an `on_event` callback that
forwards the plain event dicts to the SSE emitter.
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .bos_decisions import (
    append_decision,
    build_as_of,
    build_task_to_agent_record,
)
from .swarm_agents import is_native, resolve_agent_argv
from .swarm_filebus import read_result_file, write_shared_context, write_task_file
from .swarm_store import Role, SwarmStore, Task
from .swarm_watch import OwnershipWatcher, detect_violations, revert_paths
from .swarm_worktree import (
    changed_files,
    create_member_worktree,
    merge_member,
    remove_member_worktree,
)

EventHook = Callable[[dict], None] | None


# ---------------------------------------------------------------------------
# Spawn seam — the one injectable point so tests never spawn a real CLI.
# ---------------------------------------------------------------------------
class SpawnHandle(Protocol):
    """A started member process. Minimal surface the orchestrator needs."""

    def wait(self, timeout: float | None = None) -> int:
        """Block until the process exits; return its exit code."""
        ...

    def terminate(self) -> None:
        """Request the process stop (best-effort teardown)."""
        ...


# (argv, cwd) -> a started process handle. cwd is the member's git worktree.
SpawnFn = Callable[[list[str], Path], SpawnHandle]


class _PopenHandle:
    """SpawnHandle backed by subprocess.Popen (the headless production backend)."""

    def __init__(self, proc: subprocess.Popen) -> None:
        self._proc = proc

    def wait(self, timeout: float | None = None) -> int:
        return self._proc.wait(timeout=timeout)

    def terminate(self) -> None:
        try:
            self._proc.terminate()
        except (OSError, ProcessLookupError):
            pass


def subprocess_spawn(argv: list[str], cwd: Path) -> SpawnHandle:
    """Default real spawn: start `argv` in `cwd` via Popen, no shell.

    This is the headless execution backend — the server runs the CLI member as a
    plain subprocess in its worktree. (The GUI/Tauri PTY backend is separate.)
    `shell=False` is implicit since argv is a list, so no shell-injection surface.
    """
    proc = subprocess.Popen(argv, cwd=str(cwd))
    return _PopenHandle(proc)


# ---------------------------------------------------------------------------
# Result of running one member.
# ---------------------------------------------------------------------------
@dataclass
class MemberResult:
    role: str
    task_id: str
    exit_code: int
    violations: list[str] = field(default_factory=list)
    merged: bool = False
    summary: str | None = None


def _emit(on_event: EventHook, event: dict) -> None:
    if on_event is not None:
        on_event(event)


# ---------------------------------------------------------------------------
# One CLI member, end to end.
# ---------------------------------------------------------------------------
async def run_cli_member(
    store: SwarmStore,
    repo_root: Path,
    swarm_id: str,
    role: Role,
    task: Task,
    *,
    spawn_fn: SpawnFn,
    on_event: EventHook = None,
    context: str = "",
) -> MemberResult:
    """Orchestrate ONE CLI swarm member through its full lifecycle.

    Steps (see SWARM-RECONCILIATION "R3 Concrete Plan"):
      1. `git worktree add` an isolated checkout for the role.
      2. Write the file-bus task (+ shared context) into the MAIN repo's
         `.voss/swarm/<id>/` — NOT the worktree. The member is hermetic in its
         worktree and gets its task inline via the resolved argv's trailing
         task_text; the file-bus is the shared host-side record.
      3. Mark the task assigned, resolve argv, spawn into the worktree, wait.
      4. **Deterministic** ownership reconciliation post-exit: diff the worktree,
         detect out-of-`owned_files` writes, revert them, and emit a
         `swarm.needs_operator` event. (A live OwnershipWatcher runs alongside as
         belt-and-suspenders, but the verdict here is the authority.)
      5. Merge the (now in-scope) worktree, read the member's result summary, mark
         the task done, and tear the worktree down.

    The member's result file is written into the MAIN repo's shared file-bus
    (`.voss/swarm/<id>/results/<role>.result.md`) — the host hands the CLI that
    absolute path so the worktree stays hermetic — so it is read from `repo_root`.
    """
    repo_root = Path(repo_root)

    mw = create_member_worktree(repo_root, swarm_id, role.name)

    # File-bus task lives in the MAIN checkout (shared), per R3.
    if context:
        write_shared_context(repo_root, swarm_id, context)
    write_task_file(
        repo_root,
        swarm_id,
        role.name,
        task,
        agent=role.agent,
        model=role.model,
        context=context,
    )

    store.mark_assigned(swarm_id, task.id)

    # Inline emission at the assignment seam (D-R01/D-R02): freeze the
    # task_to_agent decision against the exact assignment context + BOS3 event
    # ledger tail. Best-effort — a ledger write error must never abort the swarm
    # run. No outcome/result data is captured here (no-leakage, schema D-04).
    try:
        swarm = store.get(swarm_id)
        roster = swarm.roster if swarm is not None else [role]
        append_decision(
            repo_root,
            build_task_to_agent_record(
                decision_id=f"dec-{swarm_id}-{task.id}",
                task_id=task.id,
                chosen_agent_id=role.agent,
                candidate_agents=[role.agent],
                feature_snapshot={
                    "goal": task.goal,
                    "roster": [r.name for r in roster],
                    "available_models": [r.model for r in roster],
                    "cwd": str(repo_root),
                },
                entity_ref={
                    "task_id": task.id,
                    "swarm_id": swarm_id,
                    "agent_id": role.agent,
                },
                as_of=build_as_of(repo_root / ".voss" / "bos" / "events.jsonl"),
                rationale=(
                    f"swarm assignment: task {task.id} -> role {role.name} "
                    f"(agent {role.agent})"
                ),
            ),
        )
    except (OSError, ValueError):
        pass

    argv = resolve_agent_argv(role, cwd=mw.path, task_text=task.goal)

    # Belt-and-suspenders live watcher; the post-exit check below is the authority,
    # so a missed fs event cannot make us wrong. on_violation here is best-effort
    # flagging — the deterministic pass re-detects and re-emits.
    watcher = OwnershipWatcher(mw, task.owned_files, on_violation=lambda _paths: None)
    watcher.start()
    try:
        handle = spawn_fn(argv, mw.path)
        exit_code = handle.wait()
    finally:
        watcher.stop()

    # Deterministic post-exit ownership reconciliation — do NOT rely on the watcher.
    changed = changed_files(mw)
    violations = detect_violations(changed, task.owned_files)
    if violations:
        revert_paths(mw, violations)
        _emit(
            on_event,
            {
                "type": "swarm.needs_operator",
                "swarm_id": swarm_id,
                "task_id": task.id,
                "role": role.name,
                "paths": violations,
            },
        )

    # Read the member's result from the MAIN repo's file-bus (where the host
    # hands the CLI its result path; the bus is shared, not per-worktree).
    result = read_result_file(repo_root, swarm_id, role.name)
    summary = result.summary if result is not None else None

    # Commit the member's (now in-scope) work onto its branch so fan-in has
    # something to merge — a black-box CLI leaves uncommitted working-tree edits,
    # and merge_member merges the BRANCH. Skip the merge if nothing remains after
    # reverts (a no-op merge would error on "nothing to commit").
    merged = _commit_member_work(mw.path, role.name)
    if merged:
        merge_member(repo_root, mw)
    store.mark_done(swarm_id, task.id, summary=summary)
    remove_member_worktree(repo_root, mw)

    return MemberResult(
        role=role.name,
        task_id=task.id,
        exit_code=exit_code,
        violations=violations,
        merged=merged,
        summary=summary,
    )


def _commit_member_work(worktree: Path, role: str) -> bool:
    """Stage + commit the member's working-tree changes onto its branch.

    Returns True if a commit was made, False if the worktree was clean (nothing
    to fan in — e.g. all writes were out-of-scope and reverted). Uses local
    `-c user.*` so the commit never depends on global git identity in CI.
    """
    subprocess.run(
        ["git", "-C", str(worktree), "add", "-A"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    status = subprocess.run(
        ["git", "-C", str(worktree), "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if not status.stdout.strip():
        return False
    subprocess.run(
        [
            "git",
            "-C",
            str(worktree),
            "-c",
            "user.email=swarm@voss",
            "-c",
            "user.name=voss-swarm",
            "commit",
            "-q",
            "-m",
            f"swarm: {role} work",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return True


# ---------------------------------------------------------------------------
# The whole swarm.
# ---------------------------------------------------------------------------
async def run_cli_swarm(
    store: SwarmStore,
    repo_root: Path,
    swarm_id: str,
    *,
    spawn_fn: SpawnFn,
    on_event: EventHook = None,
    max_concurrency: int = 6,
) -> list[MemberResult]:
    """Run every NON-native CLI member of a swarm concurrently, then signal done.

    Pairing roster ↔ tasks: native roles are dropped first (they run via the V25
    in-process path, not here), then the remaining CLI roles are zipped with the
    swarm's tasks in order. This is the simplest defensible pairing — the
    coordinator decompose seeds one task per CLI member in roster order — and it
    naturally truncates to `min(len(cli_roles), len(tasks))`, so a roster with no
    matching task simply runs no member. `asyncio.Semaphore` caps in-flight
    members at `max_concurrency`. A `swarm.complete` event is emitted once all
    members finish (also for an all-native roster, which runs zero members).
    """
    import asyncio

    swarm = store.get(swarm_id)
    if swarm is None:
        raise KeyError(f"no swarm {swarm_id!r}")

    cli_roles = [r for r in swarm.roster if not is_native(r)]
    pairs = list(zip(cli_roles, swarm.tasks))  # zip truncates to the shorter

    sem = asyncio.Semaphore(max_concurrency)

    async def _guarded(role: Role, task: Task) -> MemberResult:
        async with sem:
            return await run_cli_member(
                store,
                repo_root,
                swarm_id,
                role,
                task,
                spawn_fn=spawn_fn,
                on_event=on_event,
            )

    results: list[MemberResult] = []
    if pairs:
        results = list(
            await asyncio.gather(*(_guarded(role, task) for role, task in pairs))
        )

    _emit(
        on_event,
        {
            "type": "swarm.complete",
            "swarm_id": swarm_id,
            "task_count": len(results),
        },
    )
    return results


__all__ = [
    "MemberResult",
    "SpawnFn",
    "SpawnHandle",
    "run_cli_member",
    "run_cli_swarm",
    "subprocess_spawn",
]
