"""V25-04: /swarm routes, overlap 4xx, per-role routing, spawn-gate, fan-out SSE.

Mirrors tests/harness/test_server_app.py — TestClient with _resolve_provider +
run_turn monkeypatched; app.state.swarm_store redirected to a tmp event-log dir.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from voss.harness.agent import Plan, TurnResult
from voss.harness.memory_store import Hit, MemoryStore
from voss.harness.permissions import PermissionGate
from voss.harness.server import app as appmod
from voss.harness.swarm_store import build_ownership_policy

TOKEN = "test-token-swarm"


class _FakeRes:
    source = "test"
    detail = "fake creds"


async def _fake_run_turn(text, *, renderer, **kw):
    renderer.stream_delta("ok")
    renderer.finalize_stream(role="assistant", confidence=0.9, cost_usd=0.0)
    return TurnResult(
        plan=Plan(rationale="r", steps=[], confidence=0.9),
        confidence=0.9,
        final="ok",
        tool_results=[],
        cost_usd=0.0,
        run=None,
    )


def _build_app(monkeypatch, tmp_path):
    monkeypatch.setattr(
        appmod, "_resolve_provider", lambda pref: (_FakeRes(), object())
    )
    monkeypatch.setattr(appmod, "run_turn", _fake_run_turn)
    monkeypatch.setattr(appmod.session_store, "save", lambda record, history: None)
    app = appmod.create_app(TOKEN)
    app.state.swarm_store = appmod.SwarmStore(cwd=tmp_path)
    return app


@pytest.fixture
def client(monkeypatch, tmp_path):
    app = _build_app(monkeypatch, tmp_path)
    c = TestClient(app)
    c._cwd = str(tmp_path)  # type: ignore[attr-defined]
    return c


def _auth() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


# ---------------------------------------------------------------------------
# Task 1
# ---------------------------------------------------------------------------
def test_swarm_auth(client):
    # 401 without a token on every route.
    assert client.post("/swarm", json={"goal": "g"}).status_code == 401
    assert client.get("/swarm/none").status_code == 401
    assert client.post("/swarm/none/task", json={"goal": "t"}).status_code == 401
    assert client.post("/swarm/none/message", json={}).status_code == 401

    # With a token the routes work.
    r = client.post(
        "/swarm", json={"goal": "ship", "cwd": client._cwd}, headers=_auth()
    )
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    assert client.get(f"/swarm/{sid}", headers=_auth()).status_code == 200
    assert client.get("/swarm/nope", headers=_auth()).status_code == 404

    rt = client.post(
        f"/swarm/{sid}/task",
        json={"goal": "do A", "owned_files": ["src/a.py"]},
        headers=_auth(),
    )
    assert rt.status_code == 201, rt.text

    rm = client.post(
        f"/swarm/{sid}/message",
        json={"kind": "message", "text": "hi"},
        headers=_auth(),
    )
    assert rm.status_code == 202, rm.text


def test_overlap_rejected(client):
    sid = client.post(
        "/swarm", json={"goal": "g", "cwd": client._cwd}, headers=_auth()
    ).json()["id"]

    r1 = client.post(
        f"/swarm/{sid}/task",
        json={"goal": "A", "owned_files": ["src/shared.py"]},
        headers=_auth(),
    )
    assert r1.status_code == 201
    first_id = r1.json()["task"]["id"]

    # Same file, no ordering → 4xx overlap.
    r2 = client.post(
        f"/swarm/{sid}/task",
        json={"goal": "B", "owned_files": ["src/shared.py"]},
        headers=_auth(),
    )
    assert r2.status_code == 409, r2.text

    # Same file, ordered via depends_on → accepted.
    r3 = client.post(
        f"/swarm/{sid}/task",
        json={"goal": "B", "owned_files": ["src/shared.py"], "depends_on": [first_id]},
        headers=_auth(),
    )
    assert r3.status_code == 201, r3.text


def test_per_role_model_routing(client):
    roster = [
        {"name": "coordinator", "model": "model-coord"},
        {"name": "builder-1", "model": "model-build"},
        {"name": "reviewer", "model": "model-review"},
    ]
    r = client.post(
        "/swarm",
        json={"goal": "g", "cwd": client._cwd, "roster": roster},
        headers=_auth(),
    )
    assert r.status_code == 201, r.text
    spawned = r.json()["sessions"]
    assert len(spawned) == 3
    assert {s["model"] for s in spawned} == {
        "model-coord",
        "model-build",
        "model-review",
    }
    # The sessions really exist with those models.
    listing = client.get("/session", headers=_auth()).json()["sessions"]
    models = {s["model"] for s in listing}
    assert {"model-coord", "model-build", "model-review"} <= models


@pytest.mark.parametrize(
    ("agent", "model", "args"),
    [
        ("codex", "gpt-5.5", ["--fast"]),
        ("claude", "opus", ["--dangerously-skip-permissions"]),
        ("opencode", "kimi-k2.7-code", ["--experimental"]),
    ],
)
def test_explicit_roster_agent_axis_persists_and_cli_roles_pending(
    client, agent, model, args
):
    # R3: a mixed roster — native coordinator + CLI builder + native reviewer.
    roster = [
        {"name": "coordinator", "agent": "voss", "model": "model-coord"},
        {"name": "builder-1", "agent": agent, "model": model, "args": args},
        {"name": "reviewer", "agent": "voss"},
    ]
    r = client.post(
        "/swarm",
        json={"goal": "g", "cwd": client._cwd, "roster": roster},
        headers=_auth(),
    )
    assert r.status_code == 201, r.text
    spawned = {s["role"]: s for s in r.json()["sessions"]}
    # Native roles get a live session; the CLI role is recorded pending (no
    # in-process session — its worktree spawn lands in a later wave).
    assert "session_id" in spawned["coordinator"]
    assert spawned["builder-1"].get("pending") is True
    assert spawned["builder-1"]["agent"] == agent
    assert spawned["builder-1"]["model"] == model
    assert "session_id" not in spawned["builder-1"]

    # GET /swarm snapshot carries the agent axis on the persisted roster.
    swarm_id = r.json()["id"]
    snap = client.get(f"/swarm/{swarm_id}", headers=_auth()).json()["swarm"]
    by_name = {role["name"]: role for role in snap["roster"]}
    assert by_name["builder-1"]["agent"] == agent
    assert by_name["builder-1"]["model"] == model
    assert by_name["builder-1"]["args"] == args
    assert by_name["coordinator"]["agent"] == "voss"


def test_default_roster_resolves_sentinel_model(client):
    # No explicit roster -> default_roster, every Role.model == "default".
    # The spawn must resolve that sentinel to a real model id, not ship the
    # literal "default" string to the provider.
    from voss_runtime import get_config

    r = client.post(
        "/swarm",
        json={"goal": "g", "cwd": client._cwd},
        headers=_auth(),
    )
    assert r.status_code == 201, r.text
    spawned = r.json()["sessions"]
    assert spawned, "default roster spawned no sessions"
    expected = get_config().default_model
    assert {s["model"] for s in spawned} == {expected}
    assert "default" not in {s["model"] for s in spawned}


# ---------------------------------------------------------------------------
# Task 2
# ---------------------------------------------------------------------------
async def test_spawn_gate_zero_turns_before_assign(monkeypatch, tmp_path):
    calls = {"n": 0}

    async def _counting_run_turn(text, *, renderer, **kw):
        calls["n"] += 1
        renderer.finalize_stream(role="assistant", confidence=0.9, cost_usd=0.0)
        return TurnResult(
            plan=Plan(rationale="r", steps=[], confidence=0.9),
            confidence=0.9,
            final="ok",
            tool_results=[],
            cost_usd=0.0,
            run=None,
        )

    app = _build_app(monkeypatch, tmp_path)
    # Override run_turn AFTER _build_app (which set the default fake) so the
    # counter is the one actually invoked.
    monkeypatch.setattr(appmod, "run_turn", _counting_run_turn)
    mgr = app.state.sessions
    s = mgr.create(cwd=tmp_path, model="m", provider=object())
    s.gate_event = asyncio.Event()  # gated builder, unsignaled

    task = asyncio.create_task(appmod._run_turn(s, "hi", "plan"))
    await asyncio.sleep(0)  # let it reach the gate wait
    assert calls["n"] == 0  # ZERO turns before assign — no timing tolerance

    s.gate_event.set()  # coordinator's swarm.assign equivalent
    await task
    assert calls["n"] == 1  # exactly one turn after assign


def test_run_route_drives_orchestrator_and_maps_events(client, monkeypatch):
    # R3 driver: POST /swarm/{id}/run kicks off run_cli_swarm and its plain-dict
    # events are mapped to typed SSE events fanned to registered sessions.
    import voss.harness.swarm_runtime as rt

    r = client.post(
        "/swarm", json={"goal": "g", "cwd": client._cwd}, headers=_auth()
    ).json()
    sid = r["id"]
    coord = next(s["session_id"] for s in r["sessions"] if s["role"] == "coordinator")

    async def _fake_run_cli_swarm(
        store, repo_root, swarm_id, *, spawn_fn, on_event=None, **kw
    ):
        # Emit the containment event kinds the adapter maps; no real CLIs/worktrees.
        on_event(
            {
                "type": "swarm.needs_operator",
                "swarm_id": swarm_id,
                "task_id": "t1",
                "session_id": "s1",
                "paths": ["src/x.py"],
            }
        )
        on_event(
            {
                "type": "swarm.candidate_ready",
                "swarm_id": swarm_id,
                "task_id": "t1",
                "role": "builder-1",
                "branch": "swarm/s1/builder-1",
                "worktree": "/tmp/wt",
                "head": "deadbeef",
            }
        )
        on_event(
            {
                "type": "swarm.candidates_ready",
                "swarm_id": swarm_id,
                "candidate_count": 1,
            }
        )

    monkeypatch.setattr(rt, "run_cli_swarm", _fake_run_cli_swarm)

    resp = client.post(f"/swarm/{sid}/run", headers=_auth())
    assert resp.status_code == 202, resp.text

    # The driver fires `asyncio.create_task`; a follow-up request gives the
    # portal loop a tick to run the (await-free) fake to completion.
    client.get(f"/swarm/{sid}", headers=_auth())

    # The background task ran; the coordinator queue received the mapped events.
    q = client.app.state.sessions.get(coord).queue
    seen = set()
    while not q.empty():
        seen.add(q.get_nowait().type)
    assert {
        "swarm.needs_operator",
        "swarm.candidate_ready",
        "swarm.candidates_ready",
    } <= seen
    assert "swarm.complete" not in seen

    # Unknown swarm -> 404.
    assert client.post("/swarm/nope/run", headers=_auth()).status_code == 404


def test_swarm_sse_event_types(client):
    # Spawn a default-roster swarm (coordinator + 2 builders + reviewer).
    r = client.post(
        "/swarm", json={"goal": "g", "cwd": client._cwd}, headers=_auth()
    ).json()
    sid = r["id"]
    spawned = r["sessions"]
    coord = next(s["session_id"] for s in spawned if s["role"] == "coordinator")
    builder = next(s["session_id"] for s in spawned if s["role"].startswith("builder"))

    task_id = client.post(
        f"/swarm/{sid}/task",
        json={"goal": "A", "owned_files": ["src/a.py"]},
        headers=_auth(),
    ).json()["task"]["id"]

    # Script all 5 swarm event kinds over the message route — no nudge file,
    # no stdin injection; delivery is via EventBusRenderer.emit only.
    msgs = [
        {"kind": "assign", "task_id": task_id, "session_id": builder},
        {
            "kind": "worker_done",
            "task_id": task_id,
            "session_id": builder,
            "summary": "x",
        },
        {
            "kind": "gate",
            "task_id": task_id,
            "gate_type": "reviewer_reject",
            "detail": "no",
        },
        {
            "kind": "needs_operator",
            "task_id": task_id,
            "session_id": builder,
            "tool_name": "fs_write",
            "path": "src/x.py",
        },
        {"kind": "complete", "summary": "done"},
    ]
    for m in msgs:
        assert (
            client.post(f"/swarm/{sid}/message", json=m, headers=_auth()).status_code
            == 202
        )

    # The coordinator (a registered swarm session) received all 5 via fan-out.
    q = client.app.state.sessions.get(coord).queue
    seen = set()
    while not q.empty():
        seen.add(q.get_nowait().type)
    assert {
        "swarm.assign",
        "swarm.worker_done",
        "swarm.gate",
        "swarm.needs_operator",
        "swarm.complete",
    } <= seen

    # No nudge file was written for delivery (events flow through queues only).
    assert not (Path(client._cwd) / ".voss" / "swarm" / sid / "nudge").exists()


# ---------------------------------------------------------------------------
# V25-05 Task 1 — ownership enforcement + operator escalation
# ---------------------------------------------------------------------------
def test_ownership_denies_non_owned_write():
    # Deny-wins project_policy fires before mode/auto_yes — auto cannot bypass.
    gate = PermissionGate(mode="auto", project_policy=build_ownership_policy(["a.py"]))

    assert gate.check("fs_edit", {"path": "a.py"}, is_mutating=True)[0] is True
    # `./`-prefixed owned path still allowed (Pitfall 1 normalization).
    assert gate.check("fs_edit", {"path": "./a.py"}, is_mutating=True)[0] is True
    # Non-owned writes denied in every form — the edit does not occur.
    assert gate.check("fs_edit", {"path": "b.py"}, is_mutating=True)[0] is False
    assert gate.check("fs_edit", {"path": "./b.py"}, is_mutating=True)[0] is False
    assert gate.check("fs_write", {"path": "b.py"}, is_mutating=True)[0] is False
    assert gate.check("fs_edit_many", {"path": "b.py"}, is_mutating=True)[0] is False


def test_operator_escalation(monkeypatch, tmp_path):
    app = _build_app(monkeypatch, tmp_path)
    mgr = app.state.sessions
    s = mgr.create(cwd=tmp_path, model="m", provider=object())
    s.swarm_id = "sw1"
    s.swarm_task_id = "t1"
    s.swarm_policy = build_ownership_policy(["a.py"])

    renderer = appmod.EventBusRenderer(s.queue, session_id=s.id)
    gate = PermissionGate(mode="auto", project_policy=s.swarm_policy)
    appmod._install_server_permissions(gate, s, renderer)
    appmod._apply_swarm_escalation(gate, s, renderer)

    result: dict = {}

    def _run():
        result["r"] = gate.check("fs_edit", {"path": "b.py"}, is_mutating=True)

    th = threading.Thread(target=_run)
    th.start()

    # The denial registered a pending Future and emitted the escalation.
    deadline = time.time() + 2.0
    while not s.pending and time.time() < deadline:
        time.sleep(0.01)
    req_id = next(iter(s.pending))

    types = []
    while not s.queue.empty():
        types.append(s.queue.get_nowait().type)
    assert "swarm.needs_operator" in types

    # Answer via the EXISTING permission endpoint — operator approves.
    client = TestClient(app)
    r = client.post(
        f"/session/{s.id}/permission",
        json={"id": req_id, "choice": "a"},
        headers=_auth(),
    )
    assert r.json()["status"] == "ok"

    th.join(timeout=2.0)
    assert result["r"][0] is True  # operator override → allowed
    # A decision audit was written for the resolved gate.
    assert list((tmp_path / ".voss" / "decisions").glob("*.md"))


# ---------------------------------------------------------------------------
# V25-05 Task 2 — scoped recall + decision recording
# ---------------------------------------------------------------------------
def test_recall_scoped_injected_into_turn(monkeypatch, tmp_path):
    app = _build_app(monkeypatch, tmp_path)
    mgr = app.state.sessions

    def _fake_recall(self, query, *, top_k=5, source=None):
        return [
            Hit(source="code", locator="code:a.py:0", score=1.0, excerpt="AAA"),
            Hit(source="code", locator="code:b.py:0", score=0.9, excerpt="BBB"),
            Hit(source="code", locator="code:a.py:1", score=0.8, excerpt="AAA2"),
        ]

    monkeypatch.setattr(MemoryStore, "recall", _fake_recall)

    s = mgr.create(cwd=tmp_path, model="m", provider=object())
    s.swarm_owned_files = ["a.py"]
    txt = appmod._swarm_recall_text(s, "query")

    assert "code:a.py:0" in txt and "AAA" in txt
    assert "code:b.py:0" not in txt and "BBB" not in txt


def test_reviewer_reject_writes_decision(tmp_path):
    store = appmod.SwarmStore(cwd=tmp_path)
    path = store.record_gate_decision(
        "sw1",
        "t1",
        "sess-abc",
        gate_type="reviewer_reject",
        confidence=0.8,
        detail="missing tests",
    )
    text = path.read_text()
    assert "confidence: 0.8" in text
    assert "related_session: sess-abc" in text
    assert "gate_type: reviewer_reject" in text
    assert "# Swarm Gate Decision" in text
