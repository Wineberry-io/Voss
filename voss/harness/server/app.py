"""FastAPI app: the harness REST+SSE server (HYBRID-REFACTOR-PLAN H1.5-H1.14).

Wraps the existing `agent.run_turn` behind the protocol in `.planning/PROTOCOL.md`.
Auth, providers, tools, sessions, and permissions are reused from the harness —
this module only adds transport: routes, an event bus, and a permission bridge.
"""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from concurrent.futures import Future
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sse_starlette import EventSourceResponse, ServerSentEvent
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from voss_runtime import EpisodicMemory, get_config  # noqa: F401  (get_config used lazily)

from .. import auth as auth_mod
from .. import session as session_store
from ..agent import run_turn
from ..permissions import PermissionGate, PermissionStore
from ..swarm_agents import is_native
from ..swarm_store import (
    OwnershipOverlapError,
    Role,
    SwarmStore,
    build_ownership_policy,
)
from ..tools import make_toolset
from . import events as E
from .renderer import EventBusRenderer
from .sessions import ServerSession, SessionManager

PERMISSION_TIMEOUT_S = 300.0


class _FakeResolution:
    """Stand-in Resolution for the VOSS_SERVE_FAKE_TURN test seam."""

    source = "fake"
    detail = "VOSS_SERVE_FAKE_TURN"


class _FakePlan:
    confidence = 0.9
    steps: list = []


class _BearerASGI:
    """Raw ASGI bearer-auth middleware.

    Implemented at the ASGI layer (not BaseHTTPMiddleware) because
    BaseHTTPMiddleware buffers response bodies, which breaks SSE streaming.
    Rejects unauthenticated requests before they reach any route.
    """

    def __init__(self, app, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode("latin-1")
        ok = auth.startswith("Bearer ") and secrets.compare_digest(
            auth[7:], self._token
        )
        if not ok:
            resp = JSONResponse({"v": 1, "detail": "unauthorized"}, status_code=401)
            await resp(scope, receive, send)
            return
        await self._app(scope, receive, send)


# ---------------------------------------------------------------------------
# auth -> provider (mirrors cli._resolve_auth_or_die, minus TTY wizard/sys.exit)
# ---------------------------------------------------------------------------


def _resolve_provider(preference: str) -> tuple[auth_mod.Resolution, Any]:
    """Resolve credentials to a (Resolution, provider). Never exits the process.

    Server analogue of `cli._resolve_auth_or_die`: same provider-selection
    switch, but a missing credential is a caller error (raised by the route),
    not a login wizard / `sys.exit`.
    """
    # Test seam: a hermetic fake turn needs a session without real creds.
    if os.environ.get("VOSS_SERVE_FAKE_TURN"):
        return _FakeResolution(), object()

    from voss_runtime.providers import LiteLLMProvider

    from ..claude_agent_provider import ClaudeAgentProvider
    from ..providers import OpenAIOAuthProvider

    res = auth_mod.resolve(preference)
    if res.source == "none":
        return res, None
    if res.source == "claude-agent":
        provider: Any = ClaudeAgentProvider(cli_path=res.cli_path)
    elif res.source == "codex-oauth":
        provider = OpenAIOAuthProvider(res.codex_oauth)
    else:
        # env/voss anthropic|openai|codex all go through LiteLLM (key already
        # injected into os.environ by auth.resolve).
        provider = LiteLLMProvider()
    return res, provider


def _codex_session_model() -> str:
    """Default model id for codex-oauth sessions (gpt-5.x only).

    The ChatGPT-account Codex backend rejects non-gpt-5.x model ids; the harness
    default (`claude-sonnet-4-5`) 400s there and the turn dies before any output.
    Mirrors `cli._codex_default_model` WITHOUT importing `cli` (whose top-level
    `@click` command registration has heavy import side effects): read Codex CLI's
    own default, else fall back to the first subscription codex model.
    """
    m = auth_mod.load_codex_default_model()
    if m and m.startswith("gpt-5."):
        return m
    from ..subscription_models import SUBSCRIPTION_MODELS

    return SUBSCRIPTION_MODELS["codex"][0].id


def _effective_model(requested: str | None, res: Any) -> str:
    """Resolve a requested model id to a concrete one for a spawned session.

    The swarm roster uses the literal `"default"` sentinel (swarm_store.Role)
    to mean 'no explicit choice' — treat it (and None) as unspecified and fall
    through to the serve-env default then the config default. An explicit,
    non-sentinel model is honored as-is. In all cases the codex-oauth gpt-5.x
    constraint is applied last (mirrors create_session, app.py:556-565), so a
    non-gpt-5.x id never reaches the Codex backend and 400s the turn.
    """
    model = requested if (requested and requested != "default") else None
    model = (
        model
        or os.environ.get("VOSS_SERVE_DEFAULT_MODEL")
        or get_config().default_model
    )
    if res.source == "codex-oauth" and not model.startswith("gpt-5."):
        model = _codex_session_model()
    return model


# ---------------------------------------------------------------------------
# permission bridge (H1.9) — mirrors tui/permissions_bridge over the protocol
# ---------------------------------------------------------------------------


def _install_server_permissions(
    gate: PermissionGate, session: ServerSession, renderer: EventBusRenderer
) -> None:
    """Route gate prompts through `permission.updated` events + /permission replies.

    `prompt_fn`/`scope_prompt_fn` run on harness worker threads; they emit an
    event (thread-safe via the renderer's loop hop) and block on a
    `concurrent.futures.Future` that the /permission route resolves.
    """

    def _ask(tool_name: str, args: dict, dimension: str) -> str:
        req_id = uuid.uuid4().hex[:8]
        fut: Future[str] = Future()
        session.pending[req_id] = fut
        renderer.emit(
            E.PermissionUpdated(
                id=req_id, tool_name=tool_name, args=args, dimension=dimension
            )
        )
        try:
            return fut.result(timeout=PERMISSION_TIMEOUT_S)
        except TimeoutError:
            return "d"
        finally:
            session.pending.pop(req_id, None)

    def prompt(tool_name: str, args: dict) -> str:
        return _ask(tool_name, args, "tool")

    def scope_prompt(target: str) -> str:
        # Scope-expand uses the same channel; map y/n at the client.
        return _ask("scope_expand", {"target": target}, "tool")

    gate.prompt_fn = prompt
    gate.scope_prompt_fn = scope_prompt


# ---------------------------------------------------------------------------
# swarm ownership escalation + scoped recall (V25 VSWARM-05/07/10)
# ---------------------------------------------------------------------------

# fs_edit_many is NOT in permissions.WRITE but the ownership policy keys it, so
# escalate on it too.
_SWARM_WRITE_TOOLS = {"fs_write", "fs_edit", "fs_edit_many"}


def _apply_swarm_escalation(
    gate: PermissionGate, session: ServerSession, renderer: EventBusRenderer
) -> None:
    """Wrap `gate.check` so an ownership denial on a WRITE tool escalates to the
    operator instead of silently failing (VSWARM-10). The deny itself already
    fired at the project_policy deny-wins layer (permissions.py:288-295) which
    runs before mode/auto_yes — auto_yes cannot bypass it. On denial we emit
    `swarm.needs_operator` (+ a paired PermissionUpdated carrying the request id
    so the EXISTING /session/{id}/permission Future bridge answers it) and block
    on that Future. An approve overrides to allow + records a decision; anything
    else keeps the deny + records it."""
    orig_check = gate.check

    def _checked(tool_name, args, *, is_mutating=False, is_network=False):
        allowed, why = orig_check(
            tool_name, args, is_mutating=is_mutating, is_network=is_network
        )
        if allowed or tool_name not in _SWARM_WRITE_TOOLS:
            return allowed, why
        # Ownership denial → escalate through the existing permission bridge.
        path = str(args.get("path", ""))
        req_id = uuid.uuid4().hex[:8]
        fut: Future[str] = Future()
        session.pending[req_id] = fut
        renderer.emit(
            E.SwarmNeedsOperator(
                swarm_id=session.swarm_id or "",
                task_id=session.swarm_task_id or "",
                session_id=session.id,
                tool_name=tool_name,
                path=path,
            )
        )
        # Paired event on the existing permission channel carries the id so a
        # client answers via POST /session/{id}/permission (reuse, not new wire).
        renderer.emit(
            E.PermissionUpdated(
                id=req_id, tool_name=tool_name, args=dict(args), dimension="tool"
            )
        )
        try:
            answer = fut.result(timeout=PERMISSION_TIMEOUT_S)
        except TimeoutError:
            answer = "d"
        finally:
            session.pending.pop(req_id, None)
        approved = answer in ("a", "A", "y")
        if session.swarm_id:
            # Decision audit is cwd-scoped (.voss/decisions); a fresh store
            # writes the file without needing the in-memory swarm state.
            SwarmStore(session.cwd).record_gate_decision(
                session.swarm_id,
                session.swarm_task_id or "",
                session.id,
                gate_type="ownership_override" if approved else "ownership_denied",
                confidence=1.0 if approved else 0.0,
                detail=f"{tool_name} {path}: operator {'approved' if approved else 'denied'}",
            )
        if approved:
            return True, "operator approved"
        return False, why

    gate.check = _checked  # type: ignore[method-assign]


def _swarm_recall_text(session: ServerSession, text: str) -> str:
    """Task-scoped recall for a swarm builder: recall filtered to ownedFiles
    (VSWARM-07). Returns "" when there are no owned files or no scoped hits."""
    if not session.swarm_owned_files:
        return ""
    from ..memory_store import MemoryStore
    from ..swarm_store import scoped_recall

    store = MemoryStore(session.cwd)
    hits = scoped_recall(store, text, session.swarm_owned_files)
    if not hits:
        return ""
    lines = ["## Task-scoped recall (your owned files)"]
    for h in hits:
        lines.append(f"- {h.locator}: {h.excerpt}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# turn runner
# ---------------------------------------------------------------------------


async def _run_turn(session: ServerSession, text: str, mode: str) -> None:
    """Drive one turn; publish events; persist. Runs as session.task."""
    loop = asyncio.get_running_loop()
    renderer = EventBusRenderer(session.queue, session_id=session.id, loop=loop)

    # VSWARM-04 spawn-gate: a builder session created before its assignment
    # holds a set (unsignaled) gate_event and runs ZERO turns until the
    # coordinator's swarm.assign sets it. await directly in the coroutine
    # (NOT asyncio.to_thread — RESEARCH Pitfall) so it suspends, yields the
    # loop, and integrates with cancellation. Ungated sessions (gate_event is
    # None) skip this entirely — byte-identical to pre-V25 behaviour.
    if session.gate_event is not None:
        await session.gate_event.wait()

    # Test seam: emit a canned turn over the real event/SSE path (no provider).
    if os.environ.get("VOSS_SERVE_FAKE_TURN"):
        try:
            renderer.show_user(text)
            renderer.show_thinking("planning 1/1")
            renderer.show_plan(_FakePlan(), cost_usd=0.0)
            renderer.stream_delta("hello ")
            renderer.stream_delta("from fake turn")
            renderer.finalize_stream(role="assistant", confidence=0.9, cost_usd=0.0)
            renderer.show_final(f"echo: {text}", confidence=0.9, cost_usd=0.0)
        finally:
            renderer.session_idle()
            session.task = None
        return

    try:
        renderer.show_user(text)
        tools = make_toolset(session.cwd, renderer=renderer)
        gate = PermissionGate(
            mode=mode,  # type: ignore[arg-type]
            store=PermissionStore.load(session.cwd),
            auto_yes=False,
            # VSWARM-05: a swarm builder's ownership-deny policy rides the
            # deny-wins project_policy layer. None for non-swarm sessions →
            # byte-identical to pre-V25 behaviour.
            project_policy=session.swarm_policy,
        )
        _install_server_permissions(gate, session, renderer)
        if session.swarm_policy is not None:
            _apply_swarm_escalation(gate, session, renderer)

        try:
            from .. import voss_md

            voss_md_text = voss_md.read_and_inject(session.cwd)
        except Exception:
            voss_md_text = None

        # Seed the turn with the project index + task-relevant code recall (V19)
        # so the agent has a map of the repo instead of blind-globbing to
        # discover it. Mirrors the CLI's `voss do` injection path; both renders
        # are additive and self-guard (return "" on any failure / not-ready /
        # inject-off), so a turn never breaks because injection is unavailable.
        try:
            from ..cli import _render_project_index_text, _render_code_recall_text

            project_index_text = _render_project_index_text(
                session.cwd, session_id=session.id
            )
            # VSWARM-07: a swarm builder gets recall filtered to its ownedFiles;
            # non-swarm sessions keep the unscoped code-recall path unchanged.
            if session.swarm_owned_files:
                code_recall_text = _swarm_recall_text(session, text)
            else:
                code_recall_text = _render_code_recall_text(
                    session.cwd, text, session_id=session.id
                )
        except Exception:
            project_index_text = ""
            code_recall_text = ""

        result = await run_turn(
            text,
            tools=tools,
            cwd=session.cwd,
            renderer=renderer,
            model=session.model,
            provider=session.provider,
            permissions=gate,
            history=session.history,
            session_id=session.id,
            voss_md_text=voss_md_text,
            project_index_text=project_index_text,
            code_recall_text=code_recall_text,
            prior_context=session.prior_context,
        )
        # Consume resume context once: deep history now flows via session.history.
        session.prior_context = None
        renderer.show_final(
            result.final, confidence=result.confidence, cost_usd=result.cost_usd
        )
        if result.run is not None:
            session.record.runs.append(asdict(result.run))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 — surface, don't vanish into a bare idle
        # A provider/backend failure (e.g. a codex 4xx from run_turn ->
        # provider.stream) would otherwise propagate past this finally as an
        # un-awaited task exception, leaving the user a bare session.idle with
        # no signal. Surface it visibly on the transcript BEFORE the finally
        # idles — mirrors agent.py's interrupt/batch-invariant error paths.
        renderer.stream_delta(f"\n[error: {e}]\n")
        renderer.finalize_stream(role="system", confidence=None, cost_usd=None)
    finally:
        try:
            session_store.save(session.record, session.history)
        except Exception:
            pass
        renderer.session_idle()
        session.task = None


# ---------------------------------------------------------------------------
# request models
# ---------------------------------------------------------------------------


class CreateSessionBody(BaseModel):
    parentID: str | None = None
    title: str | None = None
    cwd: str | None = None
    model: str | None = None
    auth: str = "auto"
    resume: str | None = None  # id/name of a saved session to resume (H4.1)


class MessagePart(BaseModel):
    type: str = "text"
    text: str = ""


class MessageBody(BaseModel):
    parts: list[MessagePart] = []
    mode: str = "plan"


class PermissionReply(BaseModel):
    id: str
    choice: str  # a | A | d  (or y | n for scope)


# -- swarm (V25) ------------------------------------------------------------


class RoleSpec(BaseModel):
    name: str
    # R3 agent axis — mirrors swarm_store.Role (see SWARM-RECONCILIATION).
    agent: str = "voss"
    command: str = ""
    args: list[str] = []
    model: str = "default"
    auth_pref: str = "auto"


class CreateSwarmBody(BaseModel):
    goal: str
    cwd: str | None = None
    builders: int = 2
    # Optional explicit roster; when omitted the SwarmStore default_roster
    # (coordinator + N builders + reviewer) is spawned (VSWARM-08).
    roster: list[RoleSpec] | None = None


class CreateTaskBody(BaseModel):
    goal: str
    owned_files: list[str] = []
    depends_on: list[str] = []


class SwarmMessageBody(BaseModel):
    # Inter-agent / operator message. `kind` selects the lifecycle event the
    # route emits over the swarm SSE plane (assign also unblocks a builder's
    # spawn-gate). gate/needs_operator are scriptable here; their automatic
    # emit points are wired in V25-05.
    from_session: str | None = None
    text: str = ""
    kind: str = "message"  # message|assign|worker_done|gate|needs_operator|complete
    task_id: str | None = None
    session_id: str | None = None  # target builder (assign) / subject session
    gate_type: str = ""
    detail: str = ""
    tool_name: str = ""
    path: str | None = None
    summary: str | None = None
    task_count: int = 0
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# app factory
# ---------------------------------------------------------------------------


def create_app(token: str | None = None) -> FastAPI:
    token = token or secrets.token_urlsafe(32)
    mgr = SessionManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        # shutdown: cancel any in-flight turns
        for s in mgr.list():
            if s.busy and s.task is not None:
                s.task.cancel()

    app = FastAPI(title="voss-harness", version="1", lifespan=lifespan)
    app.state.token = token
    app.state.sessions = mgr
    # App-scoped SwarmStore (NOT a module global — module globals leak across
    # TestClient instances; RESEARCH Anti-Pattern). Event-log cwd defaults to
    # the serve cwd; tests override app.state.swarm_store to point at a tmp dir.
    app.state.swarm_store = SwarmStore(cwd=Path(".").resolve())

    app.add_middleware(_BearerASGI, token=token)

    # CORS: the voss-app webview document (dev `http://localhost:5173`, prod
    # `tauri://localhost`) fetches this loopback server cross-origin and sends
    # `Authorization: Bearer …`, which makes every call a CORS request with an
    # OPTIONS preflight. Added AFTER _BearerASGI so it is the OUTERMOST
    # middleware: Starlette's CORSMiddleware answers the (unauthenticated)
    # preflight directly, before bearer auth would 401 it. Auth itself is still
    # enforced on the real request. Loopback-bound + token-gated, so the origin
    # set is restricted to localhost / 127.0.0.1 / [::1] (any port) and the
    # Tauri custom-protocol origins; credentials are off (token rides the
    # Authorization header, not cookies).
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"^(https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?"
            r"|tauri://localhost|https?://tauri\.localhost)$"
        ),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    def _require(session_id: str) -> ServerSession:
        s = mgr.get(session_id)
        if s is None:
            raise HTTPException(404, "session not found")
        return s

    # -- session CRUD (H1.6) ------------------------------------------------

    @app.post("/session", status_code=201)
    def create_session(body: CreateSessionBody) -> dict:
        cwd = Path(body.cwd or ".").resolve()
        # Serve-owner session defaults (E4): SDK clients post only {cwd} — the
        # public createSession surfaces carry no auth/model. The process that
        # spawns `voss serve` may pin defaults via env; an explicit body value
        # always wins.
        auth_pref = body.auth
        if auth_pref == "auto":
            auth_pref = os.environ.get("VOSS_SERVE_DEFAULT_AUTH", "auto")
        res, provider = _resolve_provider(auth_pref)
        if provider is None:
            raise HTTPException(400, f"no usable credentials ({res.detail})")
        if body.resume:
            try:
                record, history = session_store.load(body.resume, cwd)
            except FileNotFoundError:
                raise HTTPException(404, f"no saved session {body.resume!r}")
            except ValueError as exc:  # ambiguous id
                raise HTTPException(409, str(exc))
            # M2: forward ALL prior runs as prior context (consumed on turn 1).
            s = mgr.adopt(
                record=record,
                history=history,
                provider=provider,
                prior_context=record.runs or None,
            )
            # Twin of the create snap: a saved record may carry a non-gpt-5.x
            # model (e.g. the old default) that the Codex backend 400s on. Snap
            # the EFFECTIVE session model only — `record.model` stays intact so
            # the turn-end save (app.py: session_store.save) never corrupts the
            # user's saved model.
            if res.source == "codex-oauth" and not s.model.startswith("gpt-5."):
                s.model = _codex_session_model()
            return {"v": 1, "id": s.id, "auth": res.source, "resumed": True}
        model = (
            body.model
            or os.environ.get("VOSS_SERVE_DEFAULT_MODEL")
            or get_config().default_model
        )
        # codex-oauth: snap a non-gpt-5.x model to Codex's default so the
        # backend doesn't 400 the turn into a bare idle (session-scoped; mirrors
        # cli.py:686-687 without the global configure() mutation).
        if res.source == "codex-oauth" and not model.startswith("gpt-5."):
            model = _codex_session_model()
        s = mgr.create(cwd=cwd, model=model, provider=provider, title=body.title or "")
        return {"v": 1, "id": s.id, "auth": res.source, "resumed": False}

    @app.get("/session")
    def list_sessions() -> dict:
        return {
            "v": 1,
            "sessions": [
                {
                    "id": s.id,
                    "cwd": str(s.cwd),
                    "model": s.model,
                    "title": s.title,
                    "busy": s.busy,
                }
                for s in mgr.list()
            ],
        }

    @app.get("/sessions/saved")
    def list_saved_sessions(cwd: str = ".") -> dict:
        records = session_store.list_sessions(Path(cwd).resolve())
        return {
            "v": 1,
            "sessions": [
                {
                    "id": r.id,
                    "name": r.name,
                    "cwd": r.cwd,
                    "model": r.model,
                    "updated_at": r.updated_at,
                    "total_cost_usd": r.total_cost_usd,
                    "turns": len(r.turns),
                }
                for r in records
            ],
        }

    @app.get("/session/{session_id}")
    def get_session(session_id: str) -> dict:
        s = _require(session_id)
        return {
            "v": 1,
            "id": s.id,
            "cwd": str(s.cwd),
            "model": s.model,
            "title": s.title,
            "busy": s.busy,
        }

    @app.delete("/session/{session_id}", status_code=204)
    def delete_session(session_id: str) -> None:
        if not mgr.delete(session_id):
            raise HTTPException(404, "session not found")

    # -- message + abort + permission (H1.7, H1.10, H1.9) -------------------

    @app.post("/session/{session_id}/message", status_code=202)
    async def post_message(session_id: str, body: MessageBody) -> dict:
        s = _require(session_id)
        if s.busy:
            raise HTTPException(409, "a turn is already running")
        text = " ".join(p.text for p in body.parts if p.type == "text").strip()
        if not text:
            raise HTTPException(422, "empty message")
        s.task = asyncio.create_task(_run_turn(s, text, body.mode))
        return {"v": 1, "status": "accepted"}

    @app.post("/session/{session_id}/abort", status_code=202)
    async def abort(session_id: str) -> dict:
        s = _require(session_id)
        if s.busy and s.task is not None:
            s.task.cancel()
        return {"v": 1, "status": "aborting"}

    @app.get("/session/{session_id}/cost")
    def cost(session_id: str) -> dict:
        s = _require(session_id)
        runs = s.record.runs
        total = sum(float(r.get("cost_usd", 0.0) or 0.0) for r in runs)
        return {"v": 1, "total_usd": total, "turns": len(runs)}

    @app.post("/session/{session_id}/permission")
    def reply_permission(session_id: str, body: PermissionReply) -> dict:
        s = _require(session_id)
        fut = s.pending.get(body.id)
        if fut is not None and not fut.done():
            fut.set_result(body.choice)
            return {"v": 1, "status": "ok"}
        return {"v": 1, "status": "stale"}

    # -- SSE (H1.8) ---------------------------------------------------------

    @app.get(
        "/session/{session_id}/events",
        responses={
            200: {
                "content": {
                    "text/event-stream": {
                        "schema": {"$ref": "#/components/schemas/EventEnvelope"}
                    }
                }
            }
        },
    )
    async def events(session_id: str, request: Request) -> EventSourceResponse:
        s = _require(session_id)

        async def gen():
            yield ServerSentEvent(
                event="server.connected", data=E.ServerConnected().model_dump_json()
            )
            try:
                while True:
                    ev = await s.queue.get()
                    yield ServerSentEvent(event=ev.type, data=ev.model_dump_json())
            except asyncio.CancelledError:
                # client disconnected -> abort the in-flight turn
                if s.busy and s.task is not None:
                    s.task.cancel()
                raise

        return EventSourceResponse(gen(), ping=15, send_timeout=30)

    # -- doctor (H1.7; expanded H3.1 — full registry via diagnostics.to_dict;
    #    read-only by design: repairs are CLI-local `voss doctor --fix` only) --

    @app.get("/doctor")
    def doctor(auth: str = "auto", cwd: str = ".") -> dict:
        from .. import diagnostics as diag

        res, provider = _resolve_provider(auth)
        checks = diag.run_all_checks(Path(cwd).resolve())
        return {
            "v": 1,
            "auth_source": res.source,
            "auth_detail": res.detail,
            "has_provider": provider is not None,
            "default_model": get_config().default_model,
            "exit_code": diag.aggregate_exit_code(checks),
            "checks": [diag.to_dict(c) for c in checks],
        }

    # -- memory (read-only) -------------------------------------------------

    @app.get("/memory")
    def get_memory(cwd: str = ".", q: str | None = None, top_k: int = 5) -> dict:
        # Read-only view of the harness memory store for the workspace. summary()
        # is a cheap fs walk (handles missing dirs); recall() runs only when a
        # query is given (it lazily builds the semantic index). VADE2-11.
        from ..memory_store import MemoryStore

        store = MemoryStore(Path(cwd).resolve())
        out: dict = {"v": 1, "summary": store.summary(), "query": q, "hits": []}
        if q:
            hits = store.recall(q, top_k=max(1, min(top_k, 50)))
            out["hits"] = [
                {
                    "source": h.source,
                    "locator": h.locator,
                    "score": h.score,
                    "excerpt": h.excerpt,
                    "session_id": h.session_id,
                    "ts": h.ts,
                    "line_start": h.line_start,
                    "line_end": h.line_end,
                }
                for h in hits
            ]
        return out

    # -- swarm (V25 VSWARM-02/03/04/06/08) ----------------------------------

    def _emit_swarm_event(swarm_id: str, ev: E._Base) -> None:
        """Fan a swarm event out to EVERY registered session's queue (Pitfall
        3 — not just the coordinator). Validates the swarm exists first so a
        forged swarm_id cannot inject into unrelated queues (T-V25-04-04)."""
        store = app.state.swarm_store
        if store.get(swarm_id) is None:
            return
        for rec in store.list_agents_by_swarm(swarm_id):
            sess = mgr.get(rec["session_id"])
            if sess is not None:
                EventBusRenderer(sess.queue, session_id=sess.id).emit(ev)

    @app.post("/swarm", status_code=201)
    async def create_swarm(body: CreateSwarmBody) -> dict:
        store = app.state.swarm_store
        cwd = Path(body.cwd or ".").resolve()
        # Persist the explicit roster (R3 per-role agent axis) so the stored /
        # replayed swarm matches what is spawned; swarm.roster is then the single
        # source the spawn loop iterates.
        explicit = (
            [Role(**r.model_dump()) for r in body.roster] if body.roster else None
        )
        swarm = store.create(
            goal=body.goal, cwd=str(cwd), builders=body.builders, roster=explicit
        )
        # Per-role spawn: native (agent="voss") roles run the in-process run_turn
        # loop (V25 behavior). R3 CLI roles (agent!="voss") are spawned in their
        # own git worktree by the host — that integration lands in a later wave;
        # here they are recorded as pending so the axis is visible end-to-end.
        # Builders are spawn-gated (asyncio.Event created HERE — async handler).
        spawned: list[dict] = []
        for role in swarm.roster:
            if not is_native(role):
                spawned.append(
                    {
                        "role": role.name,
                        "agent": role.agent,
                        "model": role.model,
                        "pending": True,
                    }
                )
                continue
            res, provider = _resolve_provider(role.auth_pref)
            if provider is None:
                raise HTTPException(400, f"no usable credentials ({res.detail})")
            model = _effective_model(role.model, res)
            sess = mgr.create(cwd=cwd, model=model, provider=provider, title=role.name)
            sess.swarm_id = swarm.id
            sess.swarm_role = role.name
            if role.name.startswith("builder"):
                sess.gate_event = asyncio.Event()
            store.register_agent(swarm.id, sess.id, role.name, [])
            spawned.append(
                {
                    "session_id": sess.id,
                    "role": role.name,
                    "model": sess.model,
                    "agent": role.agent,
                }
            )
        return {"v": 1, "id": swarm.id, "sessions": spawned}

    @app.get("/swarm/{swarm_id}")
    def get_swarm(swarm_id: str) -> dict:
        swarm = app.state.swarm_store.get(swarm_id)
        if swarm is None:
            raise HTTPException(404, "swarm not found")
        return {"v": 1, "swarm": swarm.model_dump()}

    @app.post("/swarm/{swarm_id}/task", status_code=201)
    def create_swarm_task(swarm_id: str, body: CreateTaskBody) -> dict:
        store = app.state.swarm_store
        if store.get(swarm_id) is None:
            raise HTTPException(404, "swarm not found")
        try:
            # add_task runs validate_no_overlap; overlap → 4xx (VSWARM-06).
            task = store.add_task(
                swarm_id, body.goal, body.owned_files, body.depends_on
            )
        except OwnershipOverlapError as exc:
            raise HTTPException(409, str(exc))
        return {"v": 1, "task": task.model_dump()}

    @app.post("/swarm/{swarm_id}/message", status_code=202)
    async def swarm_message(swarm_id: str, body: SwarmMessageBody) -> dict:
        store = app.state.swarm_store
        swarm = store.get(swarm_id)
        if swarm is None:
            raise HTTPException(404, "swarm not found")

        if body.kind == "assign":
            if not body.task_id or not body.session_id:
                raise HTTPException(422, "assign requires task_id and session_id")
            task = swarm.task(body.task_id)
            if task is None:
                raise HTTPException(404, "task not found")
            store.mark_assigned(swarm_id, body.task_id, session_id=body.session_id)
            builder = mgr.get(body.session_id)
            if builder is not None:
                builder.swarm_task_id = body.task_id
                builder.swarm_owned_files = task.owned_files
                # VSWARM-05: attach the per-task ownership-deny policy now that
                # owned_files are known. _run_turn injects it into the gate.
                builder.swarm_policy = build_ownership_policy(task.owned_files)
                # In-process unblock (Pitfall 6 — independent of queue state).
                if builder.gate_event is not None:
                    builder.gate_event.set()
            _emit_swarm_event(
                swarm_id,
                E.SwarmAssign(
                    swarm_id=swarm_id,
                    task_id=body.task_id,
                    session_id=body.session_id,
                    owned_files=task.owned_files,
                    role=(builder.swarm_role if builder else None) or "builder",
                ),
            )
        elif body.kind == "worker_done":
            if body.task_id:
                store.mark_done(swarm_id, body.task_id, summary=body.summary)
            _emit_swarm_event(
                swarm_id,
                E.SwarmWorkerDone(
                    swarm_id=swarm_id,
                    task_id=body.task_id or "",
                    session_id=body.session_id or "",
                    summary=body.summary,
                ),
            )
        elif body.kind == "gate":
            # A reviewer reject (or any gate) records a decision audit (VSWARM-10).
            if "reject" in body.gate_type:
                store.record_gate_decision(
                    swarm_id,
                    body.task_id or "",
                    body.session_id or "",
                    gate_type=body.gate_type,
                    confidence=body.confidence,
                    detail=body.detail,
                )
            _emit_swarm_event(
                swarm_id,
                E.SwarmGate(
                    swarm_id=swarm_id,
                    task_id=body.task_id or "",
                    gate_type=body.gate_type,
                    detail=body.detail,
                ),
            )
        elif body.kind == "needs_operator":
            _emit_swarm_event(
                swarm_id,
                E.SwarmNeedsOperator(
                    swarm_id=swarm_id,
                    task_id=body.task_id or "",
                    session_id=body.session_id or "",
                    tool_name=body.tool_name,
                    path=body.path,
                ),
            )
        elif body.kind == "complete":
            _emit_swarm_event(
                swarm_id,
                E.SwarmComplete(
                    swarm_id=swarm_id,
                    task_count=body.task_count or len(swarm.tasks),
                    summary=body.summary,
                ),
            )
        return {"v": 1, "status": "accepted"}

    def _r3_event_adapter(swarm_id: str):
        """Map the orchestrator's plain-dict events onto typed SSE events.

        `swarm_runtime` stays transport-free (emits dicts); this closure is the
        seam that turns them into `E.Swarm*` models fanned out via
        `_emit_swarm_event` (R3 execution-plane → SSE)."""

        def emit(ev: dict) -> None:
            etype = ev.get("type")
            if etype == "swarm.needs_operator":
                paths = ev.get("paths") or []
                _emit_swarm_event(
                    swarm_id,
                    E.SwarmNeedsOperator(
                        swarm_id=swarm_id,
                        task_id=ev.get("task_id", ""),
                        session_id=ev.get("session_id", ""),
                        tool_name=ev.get("tool_name", "fs_write"),
                        path=", ".join(paths) if paths else ev.get("path"),
                    ),
                )
            elif etype == "swarm.candidate_ready":
                _emit_swarm_event(
                    swarm_id,
                    E.SwarmCandidateReady(
                        swarm_id=swarm_id,
                        task_id=ev.get("task_id", ""),
                        role=ev.get("role", ""),
                        branch=ev.get("branch", ""),
                        worktree=ev.get("worktree", ""),
                        head=ev.get("head", ""),
                        summary=ev.get("summary"),
                    ),
                )
            elif etype == "swarm.candidates_ready":
                _emit_swarm_event(
                    swarm_id,
                    E.SwarmCandidatesReady(
                        swarm_id=swarm_id,
                        candidate_count=ev.get("candidate_count", 0),
                    ),
                )
            elif etype == "swarm.complete":
                _emit_swarm_event(
                    swarm_id,
                    E.SwarmComplete(
                        swarm_id=swarm_id,
                        task_count=ev.get("task_count", 0),
                        summary=ev.get("summary"),
                    ),
                )

        return emit

    @app.post("/swarm/{swarm_id}/run", status_code=202)
    async def run_swarm(swarm_id: str) -> dict:
        """Drive the R3 CLI members of a swarm (worktree spawn + ownership +
        candidate preservation) headlessly. Native roles are untouched — they run via the
        in-process turn path. Fire-and-forget: the orchestrator streams progress
        over the swarm SSE plane; the route returns immediately."""
        store = app.state.swarm_store
        swarm = store.get(swarm_id)
        if swarm is None:
            raise HTTPException(404, "swarm not found")

        from ..swarm_runtime import run_cli_swarm, subprocess_spawn

        repo_root = Path(swarm.cwd)
        on_event = _r3_event_adapter(swarm_id)

        async def _drive() -> None:
            try:
                await run_cli_swarm(
                    store,
                    repo_root,
                    swarm_id,
                    spawn_fn=subprocess_spawn,
                    on_event=on_event,
                )
            except Exception:  # noqa: BLE001 — background driver must not crash the loop
                pass

        asyncio.create_task(_drive())
        return {"v": 1, "status": "running"}

    # -- OpenAPI: force the event union into components (H1.14) --------------

    _force_event_schema(app)
    return app


def _force_event_schema(app: FastAPI) -> None:
    """Ensure EventEnvelope (the AgentEvent union) lands in OpenAPI components."""
    base = app.openapi

    def openapi():
        schema = base()
        comps = schema.setdefault("components", {}).setdefault("schemas", {})
        env = E.EventEnvelope.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        for name, defn in env.pop("$defs", {}).items():
            comps.setdefault(name, defn)
        comps["EventEnvelope"] = env
        app.openapi_schema = schema
        return schema

    app.openapi = openapi  # type: ignore[assignment]
