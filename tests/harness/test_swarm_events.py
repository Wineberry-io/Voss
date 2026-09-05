"""V25-02: swarm SSE event models + ServerSession swarm fields."""

from __future__ import annotations

import asyncio
from pathlib import Path

from voss.harness.server.events import (
    AgentEventAdapter,
    EventEnvelope,
    SwarmAssign,
    SwarmCandidateReady,
    SwarmCandidatesReady,
    SwarmComplete,
    SwarmGate,
    SwarmNeedsOperator,
    SwarmWorkerDone,
)
from voss.harness.server.sessions import ServerSession, SessionManager


# ---------------------------------------------------------------------------
# Task 1 — event models + union
# ---------------------------------------------------------------------------
def test_swarm_event_union_roundtrip() -> None:
    samples = [
        SwarmAssign(
            swarm_id="sw1",
            task_id="t1",
            session_id="s1",
            owned_files=["src/a.py"],
            role="builder",
        ),
        SwarmCandidateReady(
            swarm_id="sw1",
            task_id="t1",
            role="builder-1",
            branch="swarm/sw1/builder-1",
            worktree="/tmp/wt",
            head="deadbeef",
        ),
        SwarmCandidatesReady(swarm_id="sw1", candidate_count=1),
        SwarmWorkerDone(swarm_id="sw1", task_id="t1", session_id="s1", summary="ok"),
        SwarmGate(
            swarm_id="sw1", task_id="t1", gate_type="reviewer_reject", detail="no"
        ),
        SwarmNeedsOperator(
            swarm_id="sw1",
            task_id="t1",
            session_id="s1",
            tool_name="fs_write",
            path="src/x.py",
        ),
        SwarmComplete(swarm_id="sw1", task_count=2, summary="done"),
    ]
    for ev in samples:
        parsed = AgentEventAdapter.validate_json(ev.model_dump_json())
        assert type(parsed) is type(ev)
        assert parsed.swarm_id == "sw1"


def test_swarm_events_in_envelope_schema() -> None:
    schema = EventEnvelope.model_json_schema()
    literals = set()
    for name, defn in schema.get("$defs", {}).items():
        const = defn.get("properties", {}).get("type", {})
        if "const" in const:
            literals.add(const["const"])
    for t in (
        "swarm.assign",
        "swarm.candidate_ready",
        "swarm.candidates_ready",
        "swarm.worker_done",
        "swarm.gate",
        "swarm.needs_operator",
        "swarm.complete",
    ):
        assert t in literals, f"{t} missing from EventEnvelope schema"


# ---------------------------------------------------------------------------
# Task 2 — ServerSession swarm fields
# ---------------------------------------------------------------------------
def _make_session() -> ServerSession:
    mgr = SessionManager()
    return mgr.create(cwd=Path("."), model="test-model", provider=object())


def test_session_swarm_fields_default_none() -> None:
    s = _make_session()
    assert s.gate_event is None
    assert s.swarm_id is None
    assert s.swarm_task_id is None
    assert s.swarm_role is None
    assert s.swarm_policy is None
    assert s.swarm_owned_files == []
    # Ungated parity: a fresh session is not busy.
    assert s.busy is False


def test_session_swarm_fields_settable() -> None:
    s = _make_session()
    s.gate_event = asyncio.Event()
    s.swarm_owned_files = ["a.py"]
    s.swarm_id = "sw1"
    s.swarm_role = "builder"
    assert isinstance(s.gate_event, asyncio.Event)
    assert s.swarm_owned_files == ["a.py"]
    # busy still reflects task state (no task set → not busy).
    assert s.busy is False
