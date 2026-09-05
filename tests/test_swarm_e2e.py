"""V25 acceptance bar — the 2-builder enforced swarm run as ONE integration test.

Drives the whole server-native swarm runtime headlessly via TestClient under the
VOSS_SERVE_FAKE_TURN seam (no live provider, no nudge files, no stdin). Exercises
VSWARM-01/02/03/04/05/06/07/10/11 in a single scripted path:

  create swarm → 2 disjoint tasks (3rd overlap rejected) → builders gated (zero
  turns until assign) → assign → owned-only edit allowed, 3rd-file write denied at
  the gate + swarm.needs_operator escalation → reviewer gate writes a decision →
  swarm.complete emitted → events.jsonl replays the full open→assigned→done timeline.
"""
from __future__ import annotations

import asyncio
import threading
import time

from fastapi.testclient import TestClient

from voss.harness.permissions import PermissionGate
from voss.harness.server import app as appmod
from voss.harness.swarm_store import ASSIGNED, DONE, OPEN

TOKEN = "e2e-token"


class _FakeRes:
    source = "test"
    detail = "fake creds"


def _auth() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _build(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("VOSS_SERVE_FAKE_TURN", "1")
    monkeypatch.setattr(appmod, "_resolve_provider", lambda pref: (_FakeRes(), object()))
    monkeypatch.setattr(appmod.session_store, "save", lambda record, history: None)
    app = appmod.create_app(TOKEN)
    app.state.swarm_store = appmod.SwarmStore(cwd=tmp_path)
    c = TestClient(app)
    c._cwd = str(tmp_path)  # type: ignore[attr-defined]
    return c

# Ensure number of turns are specified in the swarm setup window

async def _prove_zero_turns_until_assign(app, tmp_path) -> None:
    """A gated builder produces NO turn output until its gate fires, then runs
    exactly one turn (VSWARM-04). Event is created in THIS loop so wait() binds
    here; the FAKE_TURN path emits user/final/idle once unblocked."""
    mgr = app.state.sessions
    b = mgr.create(cwd=tmp_path, model="m", provider=object())
    b.gate_event = asyncio.Event()  # gated, unsignaled

    task = asyncio.create_task(appmod._run_turn(b, "go", "auto"))
    await asyncio.sleep(0)  # let it reach the gate wait — no timing tolerance
    assert b.queue.empty()  # ZERO turn output before assign

    b.gate_event.set()  # the swarm.assign equivalent
    await task
    types = []
    while not b.queue.empty():
        types.append(b.queue.get_nowait().type)
    assert "user" in types and types[-1] == "session.idle"  # exactly one turn ran


def test_swarm_two_builder_enforced_e2e(monkeypatch, tmp_path):
    client = _build(monkeypatch, tmp_path)
    mgr = client.app.state.sessions
    store = client.app.state.swarm_store

    # (1) Create the swarm — default roster: coordinator + 2 builders + reviewer.
    r = client.post("/swarm", json={"goal": "ship", "cwd": client._cwd}, headers=_auth())
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    spawned = r.json()["sessions"]
    coord = next(s["session_id"] for s in spawned if s["role"] == "coordinator")
    builders = [s["session_id"] for s in spawned if s["role"].startswith("builder")]
    assert len(builders) == 2

    # (2) Two disjoint-file tasks succeed; a 3rd overlapping task is rejected 4xx.
    ta = client.post(
        f"/swarm/{sid}/task", json={"goal": "A", "owned_files": ["a.py"]}, headers=_auth()
    ).json()["task"]["id"]
    tb = client.post(
        f"/swarm/{sid}/task", json={"goal": "B", "owned_files": ["b.py"]}, headers=_auth()
    ).json()["task"]["id"]
    dup = client.post(
        f"/swarm/{sid}/task", json={"goal": "C", "owned_files": ["a.py"]}, headers=_auth()
    )
    assert dup.status_code == 409  # VSWARM-06

    # (3) Builders are gated (waiting) — zero turns until assign (VSWARM-04).
    b0 = mgr.get(builders[0])
    b1 = mgr.get(builders[1])
    assert b0.gate_event is not None and not b0.gate_event.is_set()
    assert b1.gate_event is not None and not b1.gate_event.is_set()
    asyncio.run(_prove_zero_turns_until_assign(client.app, tmp_path))

    # (4) Assign each task to a builder — unblocks the gate + attaches the
    # ownership policy (VSWARM-04 unblock).
    for tid, bid in ((ta, builders[0]), (tb, builders[1])):
        assert client.post(
            f"/swarm/{sid}/message",
            json={"kind": "assign", "task_id": tid, "session_id": bid},
            headers=_auth(),
        ).status_code == 202
    assert b0.gate_event.is_set() and b1.gate_event.is_set()
    assert b0.swarm_policy is not None  # ownership policy attached at assign

    # (5) Ownership enforcement (VSWARM-05): builder0 may edit its owned a.py,
    # but a write to a 3rd file is DENIED at the gate and escalates to the
    # operator (VSWARM-10), answerable via the existing /permission endpoint.
    renderer = appmod.EventBusRenderer(b0.queue, session_id=b0.id)
    gate = PermissionGate(mode="auto", project_policy=b0.swarm_policy)
    appmod._install_server_permissions(gate, b0, renderer)
    appmod._apply_swarm_escalation(gate, b0, renderer)

    assert gate.check("fs_edit", {"path": "a.py"}, is_mutating=True)[0] is True

    result: dict = {}

    def _denied_write():
        result["r"] = gate.check("fs_edit", {"path": "secret.py"}, is_mutating=True)

    th = threading.Thread(target=_denied_write)
    th.start()
    deadline = time.time() + 2.0
    while not b0.pending and time.time() < deadline:
        time.sleep(0.01)
    req_id = next(iter(b0.pending))
    emitted = []
    while not b0.queue.empty():
        emitted.append(b0.queue.get_nowait().type)
    assert "swarm.needs_operator" in emitted  # escalation emitted
    # Operator denies via the existing per-session permission bridge.
    assert client.post(
        f"/session/{b0.id}/permission", json={"id": req_id, "choice": "d"}, headers=_auth()
    ).json()["status"] == "ok"
    th.join(timeout=2.0)
    assert result["r"][0] is False  # the 3rd-file write does NOT occur

    # (6) Reviewer gate writes a .voss/decisions/*.md (VSWARM-10).
    assert client.post(
        f"/swarm/{sid}/message",
        json={"kind": "gate", "task_id": ta, "session_id": b0.id,
              "gate_type": "reviewer_reject", "confidence": 0.8, "detail": "redo"},
        headers=_auth(),
    ).status_code == 202
    decisions = list((tmp_path / ".voss" / "decisions").glob("*.md"))
    assert decisions, "reviewer reject must write a decision audit"

    # (7) Builders complete; swarm.complete is emitted (VSWARM-02).
    for tid, bid in ((ta, builders[0]), (tb, builders[1])):
        client.post(
            f"/swarm/{sid}/message",
            json={"kind": "worker_done", "task_id": tid, "session_id": bid, "summary": "ok"},
            headers=_auth(),
        )
    client.post(
        f"/swarm/{sid}/message", json={"kind": "complete", "summary": "done"}, headers=_auth()
    )
    coord_q = mgr.get(coord).queue
    coord_types = []
    while not coord_q.empty():
        coord_types.append(coord_q.get_nowait().type)
    assert "swarm.complete" in coord_types

    # (8) Audit replay from events.jsonl ALONE — full ordered timeline, no gaps
    # (VSWARM-01/11).
    timeline = store.replay_timeline(sid)
    assert timeline[ta] == [OPEN, ASSIGNED, DONE]
    assert timeline[tb] == [OPEN, ASSIGNED, DONE]
    replayed = store.replay(sid)
    assert replayed.goal == "ship"
    assert {t.state for t in replayed.tasks} == {DONE}

    # No nudge file / stdin injection — coordination flowed through routes + SSE.
    assert not (tmp_path / ".voss" / "swarm" / sid / "nudge").exists()
