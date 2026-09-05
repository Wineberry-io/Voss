"""EventBusRenderer (HYBRID-REFACTOR-PLAN H1.3).

A `render.Renderer` implementation that publishes events onto an
`asyncio.Queue` instead of writing to a terminal. The SSE endpoint (H1.8)
drains the queue. Because it satisfies the existing 13-method `Renderer`
protocol, the agent loop (`agent.run_turn`) drives it unchanged — this is the
seam that makes the server cheap.

Renderer methods are SYNCHRONOUS and may be called from TWO thread contexts:
the event loop (streaming) and harness worker threads (tool/permission
callbacks run via `asyncio.to_thread` — see `tui/permissions_bridge.py`).
`asyncio.Queue.put_nowait` is NOT thread-safe across threads, so when a `loop`
is supplied the renderer routes every enqueue through `loop.call_soon_threadsafe`
from off-loop threads. On a full bounded queue the oldest event is dropped to
keep the latest (lossy-latest); a single localhost SSE consumer normally keeps
up, and dropping a stale token beats blocking the agent loop.

`loop=None` (the default) keeps a direct synchronous `put_nowait` for tests
that drive the renderer without a running loop.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from . import events as E


class EventBusRenderer:
    """Publishes `render.Renderer` calls as protocol events to a queue."""

    def __init__(
        self,
        queue: "asyncio.Queue[E._Base]",
        *,
        session_id: str = "",
        loop: "asyncio.AbstractEventLoop | None" = None,
    ) -> None:
        self._q = queue
        self._sid = session_id
        self._loop = loop

    # -- internal -----------------------------------------------------------

    def _put(self, ev: E._Base) -> None:
        """Enqueue on the loop thread; drop oldest if the queue is full."""
        try:
            self._q.put_nowait(ev)
        except asyncio.QueueFull:
            try:
                self._q.get_nowait()  # drop oldest
            except asyncio.QueueEmpty:
                pass
            try:
                self._q.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    def _emit(self, ev: E._Base) -> None:
        loop = self._loop
        if loop is None:
            self._put(ev)
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            self._put(ev)
        else:
            loop.call_soon_threadsafe(self._put, ev)

    # -- Renderer protocol (13 methods) -------------------------------------

    def banner(self, *, model: str, cwd: Path, git_status: str) -> None:
        self._emit(E.BannerEvent(model=model, cwd=str(cwd), git=git_status))

    def show_user(self, task: str) -> None:
        self._emit(E.UserEvent(task=task))

    def show_thinking(self, label: str) -> None:
        self._emit(E.ThinkingEvent(label=label))

    def show_plan(self, plan: Any, *, cost_usd: float) -> None:
        steps = [
            E.PlanStep(name=s.name, args=s.args) for s in getattr(plan, "steps", [])
        ]
        self._emit(
            E.PlanEvent(
                confidence=getattr(plan, "confidence", 0.0),
                steps=steps,
                cost_usd=cost_usd,
            )
        )

    def show_tool_call(
        self,
        call_id: str | None,
        name: str,
        args: dict,
        summary: str,
        state: str,
        *,
        output: str | None = None,
    ) -> None:
        # R3: call_id/output accepted and dropped — the server event contract
        # (ToolEvent) is V15-gated and must not change here.
        self._emit(E.ToolEvent(name=name, args=args, summary=summary, state=state))

    def show_clarify(self, question: str, confidence: float) -> None:
        self._emit(E.ClarifyEvent(question=question, confidence=confidence))
        # H5.2: surface the confidence gate firing as an observable gate event.
        self._emit(
            E.GateUpdated(session_id=self._sid, gate="confidence", decision="ask")
        )

    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None:
        self._emit(E.FinalEvent(text=text, confidence=confidence, cost_usd=cost_usd))

    def stream_delta(self, text: str) -> None:
        self._emit(E.StreamDelta(text=text))

    def finalize_stream(
        self,
        *,
        role: str,
        confidence: float | None = None,
        cost_usd: float | None = None,
        timestamp: str | None = None,
        accumulated_text: str | None = None,
    ) -> None:
        self._emit(
            E.StreamFinalize(
                role=role,
                confidence=confidence,
                cost_usd=cost_usd,
                timestamp=timestamp,
            )
        )

    # R2 working indicator (tui-redesign-spec §6.1): protocol no-ops — the
    # event-bus vocabulary is a locked contract; turn activity is already
    # observable via stream/tool events.
    def show_working(self, label: str = "working") -> None:
        pass

    def update_working(self, elapsed_s: float, tokens: int) -> None:
        pass

    def hide_working(self) -> None:
        pass

    def status(self, *, model: str, tokens: int, cost_usd: float, ctx_pct: float) -> None:
        self._emit(
            E.StatusEvent(
                model=model, tokens=tokens, cost_usd=cost_usd, ctx_pct=ctx_pct
            )
        )

    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None:
        self._emit(
            E.CognitionLoaded(
                architecture_tokens=architecture_tokens,
                constraints_count=constraints_count,
                plans_loaded=plans_loaded,
                decisions_loaded=decisions_loaded,
            )
        )

    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None:
        self._emit(
            E.CognitionOverflow(
                architecture_tokens=architecture_tokens, budget=budget
            )
        )

    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None:
        self._emit(
            E.PrinciplesOverflow(
                principles_tokens=principles_tokens, budget=budget
            )
        )

    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None:
        self._emit(
            E.InstructionsOverflow(
                instructions_tokens=instructions_tokens,
                budget=budget,
                truncated=list(truncated or []),
            )
        )

    def show_warning(self, msg: str) -> None:
        self._emit(E.WarningEvent(message=msg))

    # -- server-only helpers (not part of the Renderer protocol) ------------

    def emit(self, ev: E._Base) -> None:
        """Publish a server-originated event (handshake, permission, idle, Voss)."""
        self._emit(ev)

    def server_connected(self) -> None:
        self._emit(E.ServerConnected())

    def session_idle(self) -> None:
        self._emit(E.SessionIdle(session_id=self._sid))
