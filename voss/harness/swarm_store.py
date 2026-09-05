"""SwarmStore — server-side single source of truth for swarm runtime state (V25).

Every mutation appends an event to the per-swarm append-only JSONL log
(`swarm/events.py`); `replay()` rebuilds a Swarm purely from that log (VSWARM-01
/ VSWARM-11). This module also hosts the pure-Python pieces every other V25 plan
imports:

- overlap validation (VSWARM-06) — two active tasks may not own the same file
  unless ordered by `depends_on`;
- the per-session swarm index (VSWARM-09 headless boundary) — the Rust SQLite
  column-add is V25-03, a separate cargo concern;
- the ownership-deny policy builder (consumed by V25-05 / VSWARM-05);
- the scoped-recall helper (VSWARM-07) — a post-filter wrapper over
  `MemoryStore.recall`, not a recall signature change.

`SwarmStore` is app-scoped (stored on `app.state`, NOT a module global): module
globals leak across TestClient instances in pytest (research Anti-Pattern).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .cognition_schemas import PermissionsConfig
from .swarm.events import SwarmEventLog

# Task lifecycle states (VSWARM-11 replay timeline).
OPEN = "open"
ASSIGNED = "assigned"
CANDIDATE_READY = "candidate_ready"
DONE = "done"
_ACTIVE_STATES = {OPEN, ASSIGNED, CANDIDATE_READY}

# Write tools the ownership policy must cover. fs_edit_many is NOT in
# permissions.WRITE, so its rule is matched by tool-name key directly — list all
# three so a builder cannot route around the deny via the bulk-edit tool.
_WRITE_TOOLS = ("fs_write", "fs_edit", "fs_edit_many")


def _norm(p: str) -> str:
    """Normalize a stored/owned path. `str(Path(p))` strips `./` (Pitfall 1).

    Path normalization happens at WRITE time (task creation / policy build), not
    at check time — the deny check fnmatches the raw path the agent passes.
    """
    return str(Path(p))


class OwnershipOverlapError(ValueError):
    """Two active tasks declare the same owned file without a depends_on order."""


# ---------------------------------------------------------------------------
# Models — extra="ignore" mirrors the `_Base` convention so a forward-compatible
# event payload (extra keys from a newer writer) replays without raising.
# ---------------------------------------------------------------------------
class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Role(_Base):
    name: str
    # R3 agent axis (SWARM-RECONCILIATION): which executor backs this role.
    # "voss" = the native in-process run_turn loop (V25 behavior, default →
    # backward compatible). Any other value names a real CLI spawned in the
    # member's own git worktree; resolved to an argv by `swarm_agents`.
    agent: str = "voss"
    # Raw command for agent="custom" (host tokenizes via shlex). Ignored for
    # catalog agents and the native loop.
    command: str = ""
    # Extra CLI flags appended after the model/cwd flags. Ignored for native.
    args: list[str] = Field(default_factory=list)
    # Native model id OR the chosen CLI's `--model` flag value.
    model: str = "default"
    auth_pref: str = "auto"


class Task(_Base):
    id: str
    goal: str
    owned_files: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    state: str = OPEN
    candidate_branch: str | None = None
    candidate_worktree: str | None = None
    candidate_head: str | None = None


class Swarm(_Base):
    id: str
    goal: str
    cwd: str
    roster: list[Role] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)

    def task(self, task_id: str) -> Task | None:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------
def default_roster(builders: int = 2) -> list[Role]:
    """Coordinator + N builders + reviewer. NO scout.

    The scout capability is folded into the chroma/recall layer (VSWARM-07); it
    is never a default roster member.
    """
    roster = [Role(name="coordinator")]
    for i in range(1, builders + 1):
        roster.append(Role(name=f"builder-{i}"))
    roster.append(Role(name="reviewer"))
    return roster


# ---------------------------------------------------------------------------
# Overlap validation (VSWARM-06)
# ---------------------------------------------------------------------------
def _ordered_by_dependency(a: Task, b: Task) -> bool:
    return a.id in b.depends_on or b.id in a.depends_on


def validate_no_overlap(new_task: Task, active_tasks: list[Task]) -> None:
    """Raise OwnershipOverlapError if new_task shares an owned file with an
    active task and the two are not ordered via depends_on."""
    new_files = {_norm(f) for f in new_task.owned_files}
    for other in active_tasks:
        if other.id == new_task.id or other.state not in _ACTIVE_STATES:
            continue
        clash = new_files & {_norm(f) for f in other.owned_files}
        if clash and not _ordered_by_dependency(new_task, other):
            files = ", ".join(sorted(clash))
            raise OwnershipOverlapError(
                f"task {new_task.id!r} overlaps active task {other.id!r} on "
                f"[{files}] with no depends_on ordering"
            )


# ---------------------------------------------------------------------------
# Ownership policy builder (VSWARM-05 — consumed by V25-05)
# ---------------------------------------------------------------------------
def build_ownership_policy(owned_files: list[str]) -> PermissionsConfig:
    """Synthetic PermissionsConfig denying writes to any non-owned path.

    Uses ONLY the declared `rules` field — PermissionsConfig is STRICT
    (extra=forbid), so passing undeclared kwargs would raise. Within each
    per-tool sub-map "*" is listed first and owned paths after, so last-match-
    wins lets an owned path override the blanket deny (research Pattern 4).
    """
    rules: dict[str, Any] = {}
    for tool in _WRITE_TOOLS:
        tool_rules: dict[str, str] = {"*": "deny"}
        for f in owned_files:
            n = _norm(f)
            # The deny check fnmatches the RAW path the agent passes, which may
            # carry a `./` prefix. Allow both the normalized and `./`-prefixed
            # forms so an owned file is never falsely denied (Pitfall 1). The
            # blanket "*":"deny" still catches every non-owned path/form.
            tool_rules[n] = "allow"
            tool_rules[f"./{n}"] = "allow"
        rules[tool] = tool_rules
    return PermissionsConfig(rules=rules)


# ---------------------------------------------------------------------------
# Scoped recall (VSWARM-07) — post-filter wrapper, not a recall signature change
# ---------------------------------------------------------------------------
class _Recallable(Protocol):
    def recall(
        self, query: str, *, top_k: int = ..., source: str | None = ...
    ) -> list[Any]: ...


def _locator_path(locator: str) -> str:
    """Extract the file-path component of a Hit locator.

    Code-chunk hits use `code:<filepath>:<seq>` (V19). Plain locators are
    treated as a bare path. Returns the normalized path.
    """
    parts = locator.split(":")
    if len(parts) >= 3 and parts[0] == "code":
        return _norm(":".join(parts[1:-1]))
    return _norm(locator)


def scoped_recall(
    mem: _Recallable,
    query: str,
    owned_files: list[str],
    *,
    top_k: int = 5,
) -> list[Any]:
    """Recall then keep only hits whose locator path is in owned_files.

    Over-fetches (top_k*3) before filtering so the scope cut still returns up to
    top_k owned-file hits.
    """
    owned = {_norm(f) for f in owned_files}
    hits = mem.recall(query, top_k=top_k * 3)
    scoped = [h for h in hits if _locator_path(h.locator) in owned]
    return scoped[:top_k]


# ---------------------------------------------------------------------------
# SwarmStore
# ---------------------------------------------------------------------------
class SwarmStore:
    """In-process swarm registry. App-scoped, event-log backed."""

    def __init__(self, cwd: Path | str = ".") -> None:
        self.cwd = Path(cwd).resolve()
        self._log = SwarmEventLog(self.cwd)
        self._swarms: dict[str, Swarm] = {}
        # Session index (VSWARM-09 headless boundary).
        self._agents: dict[str, dict[str, Any]] = {}

    # -- event envelope ----------------------------------------------------
    @staticmethod
    def _event(etype: str, swarm_id: str, actor: str, payload: dict) -> dict:
        return {
            "v": 1,
            "id": uuid.uuid4().hex[:8],
            "type": etype,
            "swarm_id": swarm_id,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": actor,
            "payload": payload,
        }

    def _emit(self, etype: str, swarm_id: str, actor: str, payload: dict) -> None:
        self._log.append(swarm_id, self._event(etype, swarm_id, actor, payload))

    # -- mutations ---------------------------------------------------------
    def create(
        self,
        goal: str,
        cwd: str | None = None,
        *,
        builders: int = 2,
        roster: list[Role] | None = None,
    ) -> Swarm:
        sid = uuid.uuid4().hex[:12]
        # An explicit roster (R3: per-role agent axis) is persisted as-is so the
        # stored/replayed swarm matches what was spawned; otherwise the default
        # coordinator + N builders + reviewer.
        roster = roster if roster is not None else default_roster(builders=builders)
        swarm = Swarm(
            id=sid, goal=goal, cwd=cwd or str(self.cwd), roster=roster, tasks=[]
        )
        self._emit(
            "swarm.create",
            sid,
            actor="operator",
            payload={
                "goal": swarm.goal,
                "cwd": swarm.cwd,
                "roster": [r.model_dump() for r in roster],
            },
        )
        self._swarms[sid] = swarm
        return swarm

    def get(self, swarm_id: str) -> Swarm | None:
        return self._swarms.get(swarm_id)

    def add_task(
        self,
        swarm_id: str,
        goal: str,
        owned_files: list[str],
        depends_on: list[str] | None = None,
    ) -> Task:
        swarm = self._swarms[swarm_id]
        task = Task(
            id=uuid.uuid4().hex[:8],
            goal=goal,
            owned_files=[_norm(f) for f in owned_files],
            depends_on=list(depends_on or []),
            state=OPEN,
        )
        validate_no_overlap(task, swarm.tasks)
        self._emit(
            "swarm.task",
            swarm_id,
            actor="coordinator",
            payload={
                "task_id": task.id,
                "goal": task.goal,
                "owned_files": task.owned_files,
                "depends_on": task.depends_on,
            },
        )
        swarm.tasks.append(task)
        return task

    def mark_assigned(self, swarm_id: str, task_id: str, session_id: str = "") -> None:
        task = self._require_task(swarm_id, task_id)
        task.state = ASSIGNED
        self._emit(
            "swarm.assign",
            swarm_id,
            actor="coordinator",
            payload={"task_id": task_id, "session_id": session_id},
        )

    def mark_done(
        self, swarm_id: str, task_id: str, summary: str | None = None
    ) -> None:
        task = self._require_task(swarm_id, task_id)
        task.state = DONE
        self._emit(
            "swarm.worker_done",
            swarm_id,
            actor="builder",
            payload={"task_id": task_id, "summary": summary},
        )

    def mark_candidate_ready(
        self,
        swarm_id: str,
        task_id: str,
        *,
        branch: str,
        worktree: str,
        head: str,
        summary: str | None = None,
    ) -> None:
        task = self._require_task(swarm_id, task_id)
        task.state = CANDIDATE_READY
        task.candidate_branch = branch
        task.candidate_worktree = worktree
        task.candidate_head = head
        self._emit(
            "swarm.candidate_ready",
            swarm_id,
            actor="builder",
            payload={
                "task_id": task_id,
                "branch": branch,
                "worktree": worktree,
                "head": head,
                "summary": summary,
            },
        )

    def _require_task(self, swarm_id: str, task_id: str) -> Task:
        task = self._swarms[swarm_id].task(task_id)
        if task is None:
            raise KeyError(f"task {task_id!r} not in swarm {swarm_id!r}")
        return task

    # -- session index (VSWARM-09 headless) --------------------------------
    def register_agent(
        self,
        swarm_id: str,
        session_id: str,
        role: str,
        owned_files: list[str],
    ) -> None:
        self._agents[session_id] = {
            "swarm_id": swarm_id,
            "role": role,
            "owned_files": [_norm(f) for f in owned_files],
        }

    def list_agents_by_swarm(self, swarm_id: str) -> list[dict[str, Any]]:
        return [
            {"session_id": sid, **rec}
            for sid, rec in self._agents.items()
            if rec["swarm_id"] == swarm_id
        ]

    # -- decision recording (VSWARM-10) ------------------------------------
    def record_gate_decision(
        self,
        swarm_id: str,
        task_id: str,
        session_id: str,
        gate_type: str,
        confidence: float,
        detail: str = "",
    ) -> Path:
        """Write a `.voss/decisions/<date>-<slug>.md` audit file for a gate
        outcome (reviewer reject / resolved ownership gate). Create-exclusive —
        a unique slug means an existing decision file is never overwritten
        (T-V25-05-05). Mirrors the existing decision frontmatter format."""
        decisions = self.cwd / ".voss" / "decisions"
        decisions.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        slug = f"swarm-{gate_type}-{task_id}-{uuid.uuid4().hex[:6]}"
        did = f"{now.date().isoformat()}-{slug}"
        path = decisions / f"{did}.md"
        content = (
            "---\n"
            f"id: {did}\n"
            "status: active\n"
            f"related_session: {session_id}\n"
            f"confidence: {confidence}\n"
            f"created_at: {now.isoformat(timespec='seconds')}\n"
            f"swarm_id: {swarm_id}\n"
            f"task_id: {task_id}\n"
            f"gate_type: {gate_type}\n"
            "---\n\n"
            "# Swarm Gate Decision\n\n"
            f"{detail}\n"
        )
        with open(path, "x") as f:  # create-exclusive — never overwrite
            f.write(content)
        path.chmod(0o600)
        return path

    # -- replay (VSWARM-01 / VSWARM-11) ------------------------------------
    def replay(self, swarm_id: str) -> Swarm:
        """Rebuild a Swarm purely from its event log. State after replay is
        equal to the live in-memory Swarm (same goal, roster, tasks, states)."""
        swarm: Swarm | None = None
        for evt in self._log.read_events(swarm_id):
            etype = evt.get("type")
            payload = evt.get("payload", {})
            if etype == "swarm.create":
                swarm = Swarm(
                    id=swarm_id,
                    goal=payload["goal"],
                    cwd=payload["cwd"],
                    roster=[Role(**r) for r in payload.get("roster", [])],
                    tasks=[],
                )
            elif swarm is None:
                # No create seen yet — log is malformed/forged; skip.
                continue
            elif etype == "swarm.task":
                swarm.tasks.append(
                    Task(
                        id=payload["task_id"],
                        goal=payload["goal"],
                        owned_files=payload.get("owned_files", []),
                        depends_on=payload.get("depends_on", []),
                        state=OPEN,
                    )
                )
            elif etype == "swarm.assign":
                t = swarm.task(payload["task_id"])
                if t is not None:
                    t.state = ASSIGNED
            elif etype == "swarm.candidate_ready":
                t = swarm.task(payload["task_id"])
                if t is not None:
                    t.state = CANDIDATE_READY
                    t.candidate_branch = payload.get("branch")
                    t.candidate_worktree = payload.get("worktree")
                    t.candidate_head = payload.get("head")
            elif etype == "swarm.worker_done":
                t = swarm.task(payload["task_id"])
                if t is not None:
                    t.state = DONE
        if swarm is None:
            raise KeyError(f"no swarm.create event for {swarm_id!r}")
        return swarm

    def replay_timeline(self, swarm_id: str) -> dict[str, list[str]]:
        """Per-task ordered state-transition list, for audit (VSWARM-11)."""
        timeline: dict[str, list[str]] = {}
        for evt in self._log.read_events(swarm_id):
            etype = evt.get("type")
            tid = evt.get("payload", {}).get("task_id")
            if tid is None:
                continue
            if etype == "swarm.task":
                timeline.setdefault(tid, []).append(OPEN)
            elif etype == "swarm.assign":
                timeline.setdefault(tid, []).append(ASSIGNED)
            elif etype == "swarm.candidate_ready":
                timeline.setdefault(tid, []).append(CANDIDATE_READY)
            elif etype == "swarm.worker_done":
                timeline.setdefault(tid, []).append(DONE)
        return timeline
