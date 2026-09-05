"""Unit tests for SwarmStore, the append-only event log, overlap validation,
the ownership-policy builder, scoped recall, and the session index (V25-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from voss.harness.memory_store import Hit
from voss.harness.permissions import match_permission_rules
from voss.harness.swarm_store import (
    ASSIGNED,
    CANDIDATE_READY,
    DONE,
    OPEN,
    OwnershipOverlapError,
    SwarmStore,
    build_ownership_policy,
    default_roster,
    scoped_recall,
)


def _events_file(store: SwarmStore, swarm_id: str) -> Path:
    return store.cwd / ".voss" / "swarm" / swarm_id / "events" / "events.jsonl"


# ---------------------------------------------------------------------------
# Task 1 — replay + append-only event log
# ---------------------------------------------------------------------------
def test_replay_reconstructs_state(tmp_path: Path) -> None:
    store = SwarmStore(cwd=tmp_path)
    swarm = store.create(goal="ship V25", cwd=str(tmp_path))
    store.add_task(swarm.id, goal="task A", owned_files=["src/a.py"])
    store.add_task(swarm.id, goal="task B", owned_files=["src/b.py"])

    live = store.get(swarm.id)
    replayed = store.replay(swarm.id)

    # Replay from events.jsonl ALONE reconstructs an identical Swarm.
    assert replayed == live
    assert replayed.goal == "ship V25"
    assert [t.goal for t in replayed.tasks] == ["task A", "task B"]
    assert [r.name for r in replayed.roster] == [r.name for r in live.roster]


def test_event_log_append_only(tmp_path: Path) -> None:
    store = SwarmStore(cwd=tmp_path)
    swarm = store.create(goal="g", cwd=str(tmp_path))
    t1 = store.add_task(swarm.id, goal="A", owned_files=["src/a.py"])
    store.add_task(swarm.id, goal="B", owned_files=["src/b.py"])

    prefix = _events_file(store, swarm.id).read_bytes()
    assert len(prefix) > 0

    # Later mutations append only — the earlier byte-prefix is never rewritten.
    store.mark_assigned(swarm.id, t1.id, session_id="sess-1")
    store.mark_done(swarm.id, t1.id, summary="done")

    after = _events_file(store, swarm.id).read_bytes()
    assert after.startswith(prefix)
    assert len(after) > len(prefix)


def test_audit_replay_full_timeline(tmp_path: Path) -> None:
    store = SwarmStore(cwd=tmp_path)
    swarm = store.create(goal="g", cwd=str(tmp_path))
    t = store.add_task(swarm.id, goal="A", owned_files=["src/a.py"])
    store.mark_assigned(swarm.id, t.id, session_id="s")
    store.mark_done(swarm.id, t.id)

    timeline = store.replay_timeline(swarm.id)
    assert timeline[t.id] == [OPEN, ASSIGNED, DONE]

    # And the rebuilt task lands in its terminal state with no gaps.
    assert store.replay(swarm.id).task(t.id).state == DONE


def test_candidate_ready_replays_with_immutable_candidate_identity(
    tmp_path: Path,
) -> None:
    store = SwarmStore(cwd=tmp_path)
    swarm = store.create(goal="g", cwd=str(tmp_path))
    task = store.add_task(swarm.id, goal="A", owned_files=["src/a.py"])
    store.mark_assigned(swarm.id, task.id, session_id="s")
    store.mark_candidate_ready(
        swarm.id,
        task.id,
        branch="swarm/sw1/builder-1",
        worktree="/tmp/worktree",
        head="deadbeef",
        summary="ready",
    )

    live = store.get(swarm.id).task(task.id)
    replayed = store.replay(swarm.id).task(task.id)
    assert live.state == replayed.state == CANDIDATE_READY
    assert replayed.candidate_branch == "swarm/sw1/builder-1"
    assert replayed.candidate_worktree == "/tmp/worktree"
    assert replayed.candidate_head == "deadbeef"
    assert store.replay_timeline(swarm.id)[task.id] == [
        OPEN,
        ASSIGNED,
        CANDIDATE_READY,
    ]


# ---------------------------------------------------------------------------
# Task 2 — overlap, ownership policy, scoped recall, roster, session index
# ---------------------------------------------------------------------------
def test_overlap_rejected_unless_dependson(tmp_path: Path) -> None:
    store = SwarmStore(cwd=tmp_path)
    swarm = store.create(goal="g", cwd=str(tmp_path))
    first = store.add_task(swarm.id, goal="A", owned_files=["src/shared.py"])

    # Same file, no ordering → rejected.
    with pytest.raises(OwnershipOverlapError):
        store.add_task(swarm.id, goal="B", owned_files=["src/shared.py"])

    # Same file, ordered via depends_on → accepted.
    second = store.add_task(
        swarm.id, goal="B", owned_files=["src/shared.py"], depends_on=[first.id]
    )
    assert second.id in {t.id for t in store.get(swarm.id).tasks}


def test_ownership_policy_denies_non_owned(tmp_path: Path) -> None:
    policy = build_ownership_policy(["src/a.py"])
    for tool in ("fs_write", "fs_edit", "fs_edit_many"):
        assert (
            match_permission_rules(policy.rules, tool, {"path": "src/a.py"}) == "allow"
        )
        assert (
            match_permission_rules(policy.rules, tool, {"path": "src/other.py"})
            == "deny"
        )
    # `./`-prefixed owned path normalizes to the same allow (Pitfall 1).
    policy2 = build_ownership_policy(["./src/a.py"])
    assert (
        match_permission_rules(policy2.rules, "fs_edit", {"path": "src/a.py"})
        == "allow"
    )


def test_recall_scoped_to_owned_files(tmp_path: Path) -> None:
    class FakeMem:
        def __init__(self) -> None:
            self.called_top_k: int | None = None

        def recall(self, query: str, *, top_k: int = 5, source=None):
            self.called_top_k = top_k
            return [
                Hit(source="code", locator="code:src/a.py:0", score=1.0, excerpt="a"),
                Hit(source="code", locator="code:src/b.py:0", score=0.9, excerpt="b"),
                Hit(source="code", locator="code:src/a.py:1", score=0.8, excerpt="a2"),
            ]

    mem = FakeMem()
    hits = scoped_recall(mem, "q", owned_files=["src/a.py"], top_k=5)

    assert {h.locator for h in hits} == {"code:src/a.py:0", "code:src/a.py:1"}
    # Over-fetches (top_k*3) before the scope filter.
    assert mem.called_top_k == 15


def test_default_roster_no_scout(tmp_path: Path) -> None:
    roster = default_roster(builders=2)
    names = [r.name for r in roster]
    assert names == ["coordinator", "builder-1", "builder-2", "reviewer"]
    assert not any("scout" in n.lower() for n in names)


def test_session_index_lists_by_swarm(tmp_path: Path) -> None:
    store = SwarmStore(cwd=tmp_path)
    store.register_agent("sw-1", "sess-a", role="builder", owned_files=["src/a.py"])
    store.register_agent("sw-1", "sess-b", role="reviewer", owned_files=[])
    store.register_agent("sw-2", "sess-c", role="builder", owned_files=["src/c.py"])

    agents = store.list_agents_by_swarm("sw-1")
    assert {a["session_id"] for a in agents} == {"sess-a", "sess-b"}
    assert {a["role"] for a in agents} == {"builder", "reviewer"}
