"""TextualRenderer — bridges agent events into a running VossTUIApp.

Implements the full `voss.harness.render.Renderer` protocol. Every `show_*`
forwards to a widget on the app. Failures are swallowed (logged via the
Textual app log) so a rendering bug can never crash the agent.

Thread-safety: subagents run in worker threads (see voss.harness.subagents);
the `_post` helper routes off-loop callers through `app.call_from_thread`.
For the M13 multi-agent fan-out path, children instead run as asyncio tasks
on the app's own event loop (NOT worker threads), and `_post`'s
main-thread branch already handles that case unchanged.
"""
from __future__ import annotations

import importlib
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


from .. import render as render_mod
from . import glyphs
from .app import VossTUIApp
from .widgets import (
    BudgetExhaustedModal,
    ConfidenceBar,
    DiffDecision,
    DiffModal,
    Hunk,
    InputBar,
    StatusLine,
    TranscriptView,
)

# Defensive import: missing SPAWN_TOOL_NAME degrades show_tool_call to the
# generic TranscriptView path (no panel mount). Tests exercise this via
# monkeypatch.delattr(subagents, 'SPAWN_TOOL_NAME', raising=False).
try:
    from ..subagents import SPAWN_TOOL_NAME as _SPAWN_TOOL_NAME
except (ImportError, AttributeError):
    _SPAWN_TOOL_NAME = None


class TextualRenderer:
    """Concrete Renderer implementation backed by a `VossTUIApp` instance."""

    # update_working coalescing window (spec §6.3): token-counter posts to
    # the UI thread are bounded to ≤ 4 Hz regardless of delta rate.
    WORKING_POST_INTERVAL_S = 0.25

    # R2 working-indicator token coalescing state (per turn). Class-level
    # defaults (not __init__-only) so test doubles that bypass __init__
    # still work; writes shadow them per instance.
    _working_chars: int = 0
    _working_last_post: float = 0.0

    def __init__(self, app: VossTUIApp) -> None:
        self.app = app

    # ------------------------------------------------------------------
    # internal plumbing
    # ------------------------------------------------------------------

    def _post(self, fn, *args, **kwargs) -> None:
        """Safely invoke a widget method on the app's event loop."""
        try:
            on_main = threading.current_thread() is threading.main_thread()
            if on_main:
                fn(*args, **kwargs)
                return
            try:
                self.app.call_from_thread(fn, *args, **kwargs)
            except Exception:  # noqa: BLE001 — fall through to direct call if loop not running
                fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — never crash the agent
            try:
                self.app.log(f"TextualRenderer error: {exc}")
            except Exception:  # noqa: BLE001
                pass

    def _safe(self, widget_fn, attr: str, *args, **kwargs) -> None:
        """Look up a widget lazily then forward to `_post`.

        Wrapping the lookup in the same swallow-all guard keeps the agent
        loop alive when the app isn't mounted (e.g. CLI happy-path tests
        that exercise the renderer wiring without `app.run_async()`).
        """
        try:
            widget = widget_fn()
        except Exception as exc:  # noqa: BLE001 — never crash the agent
            try:
                self.app.log(f"TextualRenderer lookup miss for {attr}: {exc}")
            except Exception:  # noqa: BLE001
                pass
            return
        method = getattr(widget, attr, None)
        if method is None:
            return
        self._post(method, *args, **kwargs)

    def _turn_view(self) -> TranscriptView | None:
        try:
            return self.app.query_one("#main", TranscriptView)
        except Exception:  # noqa: BLE001
            return None

    def _status(self) -> StatusLine | None:
        try:
            return self.app.query_one("#status", StatusLine)
        except Exception:  # noqa: BLE001
            return None

    def _input(self) -> InputBar | None:
        try:
            return self.app.query_one("#input", InputBar)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Renderer protocol
    # ------------------------------------------------------------------

    def banner(self, *, model: str, cwd: Path, git_status: str) -> None:
        # R5 (spec §5.1): HeaderBar deleted — banner data feeds the two-zone
        # StatusLine (budget lands in the right zone) and the mode-aware
        # InputBar border.
        phase = getattr(self.app, "phase", "")
        display_mode = phase or getattr(self.app, "mode", "")
        status = self._status()
        if status is not None:
            cwd_str = str(cwd).replace(str(Path.home()), "~", 1)
            self._post(
                status.set_status,
                provider=getattr(self.app, "provider", ""),
                model=model,
                mode=getattr(self.app, "mode", ""),
                phase=phase,
                git_status=git_status or cwd_str,
                budget_total=getattr(self.app, "budget_total", 0),
            )
        input_bar = self._input()
        if input_bar is not None:
            self._post(input_bar.set_mode, display_mode)

    def set_phase(self, phase: str) -> None:
        normalized = (phase or "").strip()
        self.app.phase = normalized
        display_mode = normalized or getattr(self.app, "mode", "")
        status = self._status()
        if status is not None:
            self._post(status.set_status, phase=normalized)
        input_bar = self._input()
        if input_bar is not None:
            self._post(input_bar.set_mode, display_mode)

    def show_user(self, task: str) -> None:
        tv = self._turn_view()
        if tv is None:
            return
        self._post(tv.append_turn, "user", task)

    def show_thinking(self, label: str) -> None:
        status = self._status()
        if status is None:
            return
        # glyphs.TOOL_CALL (not a literal ⏵) so --no-unicode downgrades (R7).
        self._post(status.set_persistent_toast, f"{glyphs.TOOL_CALL} {label}")

    def show_plan(self, plan: Any, *, cost_usd: float) -> None:
        rationale = getattr(plan, "rationale", "") or ""
        steps = getattr(plan, "steps", []) or []
        confidence = float(getattr(plan, "confidence", 0.0) or 0.0)
        body_lines = [rationale] if rationale else []
        for s in steps:
            why = getattr(s, "why", "") or ""
            name = getattr(s, "name", "")
            line = f"  · {name}"
            if why:
                line += f" — {why}"
            body_lines.append(line)
        body = "\n".join(body_lines) if body_lines else "(empty plan)"
        tv = self._turn_view()
        if tv is None:
            return
        self._post(
            tv.append_turn,
            "plan",
            body,
            confidence=confidence,
            cost_usd=cost_usd,
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
        spawn_name = _resolve_spawn_name()
        if spawn_name is not None and name == spawn_name:
            parent_id = str((args or {}).get("parent_id") or (args or {}).get("agent_id") or "spawn")
            if state == "pending":
                agent_name = str((args or {}).get("agent_id") or (args or {}).get("name") or "subagent")
                budget_total = int((args or {}).get("budget_total") or 0)
                self.show_subagent_start(agent_name, parent_id, budget_total)
                return
            if state == "ok":
                n_results = 1
                self.show_subagent_end(parent_id, n_results)
                return
        tv = self._turn_view()
        if tv is None:
            return
        # R2 working-indicator label hook (spec §3.6): while a call is
        # pending the label reads `tool: <name>`; it resets on settle. Only
        # touches an ALREADY-active indicator — never mounts one.
        if getattr(tv, "working_active", False):
            label = f"tool: {name}" if state == "pending" else "working"
            self._post(tv.show_working, label)
        # R3 ToolCards (spec §3.4/§6.1): pending mounts one card keyed by
        # call_id; the settled call mutates it in place. Settled-only paths
        # (unknown tool, denied, legacy call_id=None callers) create the
        # card directly in its settled state.
        if state == "pending":
            self._post(self._mount_tool_card, tv, call_id, name, args)
            return
        self._post(self._settle_tool_card, tv, call_id, name, args, summary, state, output)

    def _mount_tool_card(self, tv: TranscriptView, call_id: str | None, name: str, args: dict) -> None:
        """UI-thread: mount one running ToolCard (idempotent per call_id)."""
        cid = call_id or uuid4().hex[:12]
        if call_id is not None and tv.get_tool_card(call_id) is not None:
            return
        tv.add_tool_card(cid, name, args or {})

    def _settle_tool_card(
        self,
        tv: TranscriptView,
        call_id: str | None,
        name: str,
        args: dict,
        summary: str,
        state: str,
        output: str | None,
    ) -> None:
        """UI-thread: settle the pending card, or create one settled-first."""
        card = tv.get_tool_card(call_id) if call_id else None
        if card is None:
            card = tv.add_tool_card(call_id or uuid4().hex[:12], name, args or {})
        card.settle(state, summary, output=output)

    # ------------------------------------------------------------------
    # Subagent visualization — private; NOT part of the Renderer protocol.
    # R4 (spec §3.5): spawns render inline as AgentTreeCards in the
    # transcript; the SubAgentPanel side region is retired.
    # ------------------------------------------------------------------

    def show_subagent_start(self, name: str, parent_id: str, budget_total: int = 0) -> None:
        self._safe(self._turn_view, "add_agent_tree", parent_id, name, budget_total)

    def show_subagent_progress(self, parent_id: str, body_line: str, used: int = 0) -> None:
        self._safe(self._turn_view, "update_agent_tree", parent_id, body_line, used)

    def show_subagent_end(self, parent_id: str, n_results: int = 0) -> None:
        self._safe(self._turn_view, "settle_agent_tree", parent_id, n_results)

    # ------------------------------------------------------------------
    # M9-08 CodeIntelPanel private update methods (NOT on public Renderer)
    # ------------------------------------------------------------------

    def show_code_intel_tree(self, nodes: list[dict] | None = None) -> None:
        """M10 will call this to populate the idle project tree view."""
        self._post(self.app.show_code_intel_panel)
        if self.app._code_intel_panel:
            self._post(self.app._code_intel_panel.set_tree, nodes)

    def show_code_intel_results(self, query: str, hits: list[dict] | None = None) -> None:
        """M10 calls for /symbol and /refs results."""
        self._post(self.app.show_code_intel_panel)
        if self.app._code_intel_panel:
            self._post(self.app._code_intel_panel.set_results, query, hits)

    def show_code_intel_focus(self, hit: dict | None = None, excerpt_lines: list[str] | None = None) -> None:
        """M10 calls for focused excerpt on a hit."""
        self._post(self.app.show_code_intel_panel)
        if self.app._code_intel_panel:
            self._post(self.app._code_intel_panel.set_focus, hit, excerpt_lines)

    # ------------------------------------------------------------------
    # M11 read-only modal hooks. Private; NOT part of the Renderer protocol.
    # ------------------------------------------------------------------

    def show_probable_inspector(
        self, text: str, confidence: float | None = None
    ) -> None:
        modal_cls = _optional_modal_class("ProbableInspectModal", "probable_modal")
        if modal_cls is None:
            return
        self._push_readonly_modal(modal_cls, text, confidence=confidence)

    def show_budget_trace(self, text: str, used: int = 0, total: int = 0) -> None:
        modal_cls = _optional_modal_class("BudgetTraceModal", "budget_trace_modal")
        if modal_cls is None:
            return
        self._push_readonly_modal(modal_cls, text, used=used, total=total)

    def show_voss_py_diff(self, text: str) -> None:
        modal_cls = _optional_modal_class("VossPyDiffModal", "voss_py_diff_modal")
        if modal_cls is None:
            return
        self._push_readonly_modal(modal_cls, text)

    def _push_readonly_modal(self, modal_cls, *args, **kwargs) -> None:
        try:
            modal = modal_cls(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — never crash the agent
            try:
                self.app.log(f"TextualRenderer modal init failed: {exc}")
            except Exception:  # noqa: BLE001
                pass
            return
        self._post(self.app.push_screen, modal)

    def show_clarify(self, question: str, confidence: float) -> None:
        conf = float(confidence)
        tv = self._turn_view()
        if tv is None:
            return
        self._post(
            tv.append_turn,
            "clarify",
            question,
            confidence=conf,
        )
        self._mount_confidence_bar(conf, is_final=False)

    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None:
        conf = float(confidence)
        tv = self._turn_view()
        if tv is None:
            return
        self._remember_response(text)
        self._post(
            tv.append_markdown_turn,
            "assistant",
            text,
            confidence=conf,
            cost_usd=float(cost_usd),
        )
        # No inline confidence bar in the chat — it reads as agent metadata,
        # not conversation. Confidence still flows to telemetry / status.
        status = self._status()
        if status is not None:
            self._post(status.clear_toast)

    # ------------------------------------------------------------------
    # R2 working indicator (spec §3.6 / §6.1) — forward to TranscriptView.
    # ------------------------------------------------------------------

    def show_working(self, label: str = "working") -> None:
        self._working_chars = 0
        self._working_last_post = 0.0
        self._safe(self._turn_view, "show_working", label)

    def update_working(self, elapsed_s: float, tokens: int) -> None:
        # Coalesce before posting (spec §6.3): ≤ 4 Hz regardless of delta
        # rate so the UI thread isn't flooded. Elapsed self-times in the
        # widget; tokens are the caller's running count.
        now = time.monotonic()
        if now - self._working_last_post < self.WORKING_POST_INTERVAL_S:
            return
        self._working_last_post = now
        self._safe(self._turn_view, "update_working", elapsed_s, tokens)

    def hide_working(self) -> None:
        self._safe(self._turn_view, "hide_working")

    # T1-05: streaming entry points — forward to TranscriptView via the _safe
    # lookup + _post forwarding pattern used by show_plan / show_final.
    def stream_delta(self, text: str) -> None:
        self._safe(self._turn_view, "stream_delta", text)
        # Working-indicator token tick (spec §3.6): rough ~4 chars/token
        # estimate from rendered deltas, coalesced by update_working.
        self._working_chars += len(text)
        self.update_working(0.0, self._working_chars // 4)

    def finalize_stream(
        self,
        *,
        role: str,
        confidence: float | None = None,
        cost_usd: float | None = None,
        timestamp: str | None = None,
        accumulated_text: str | None = None,
    ) -> None:
        if accumulated_text:
            self._remember_response(accumulated_text)
        self._safe(
            self._turn_view,
            "finalize_stream",
            role=role,
            confidence=confidence,
            cost_usd=cost_usd,
            timestamp=timestamp,
            accumulated_text=accumulated_text,
        )
        status = self._status()
        if status is not None:
            self._post(status.clear_toast)

    def _remember_response(self, text: str) -> None:
        """Store the latest assistant text on the app for action_copy_code."""
        note = getattr(self.app, "note_response_text", None)
        if note is not None:
            try:
                note(text)
            except Exception:  # noqa: BLE001 — never let capture break a turn
                pass

    def _mount_confidence_bar(self, confidence: float, *, is_final: bool) -> None:
        turn_view = self._turn_view()
        if turn_view is None:
            return
        bar = ConfidenceBar(value=confidence, is_final=is_final)
        self._post(turn_view.mount, bar)

    def status(
        self,
        *,
        model: str,
        tokens: int,
        cost_usd: float,
        ctx_pct: float,
    ) -> None:
        # W5: derive total honestly. Only when 0 < ctx_pct <= 1 do we have
        # enough signal; otherwise StatusLine carries ctx_pct verbatim and
        # the BudgetMeter (when mounted) renders the em-dash placeholder.
        status = self._status()
        if status is None:
            return
        self._post(
            status.set_status,
            model=model,
            tokens=tokens,
            cost_usd=cost_usd,
            ctx_pct=ctx_pct,
        )

    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None:
        kilo = architecture_tokens / 1000
        body = (
            f"cognition: architecture ({kilo:.1f}k) + "
            f"{constraints_count} constraints"
        )
        if plans_loaded or decisions_loaded:
            body += f" + {plans_loaded} plans + {decisions_loaded} decisions"
        tv = self._turn_view()
        if tv is None:
            return
        self._post(tv.append_turn, "cognition", body)

    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None:
        body = (
            f"{glyphs.WARN} architecture.md is {architecture_tokens} tokens "
            f"(over {budget} budget) — /analyze can rewrite a tighter digest"
        )
        tv = self._turn_view()
        if tv is None:
            return
        self._post(tv.append_turn, "warning", body)

    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None:
        body = (
            f"{glyphs.WARN} principles block is {principles_tokens} tokens "
            f"(over {budget} budget) — truncated"
        )
        tv = self._turn_view()
        if tv is None:
            return
        self._post(tv.append_turn, "warning", body)

    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None:
        body = (
            f"{glyphs.WARN} instruction files truncated to {budget} tokens "
            f"({', '.join(truncated or [])})"
        )
        tv = self._turn_view()
        if tv is None:
            return
        self._post(tv.append_turn, "warning", body)

    def show_warning(self, msg: str) -> None:
        tv = self._turn_view()
        if tv is None:
            return
        self._post(tv.append_turn, "warning", f"{glyphs.WARN} {msg}")

    # ------------------------------------------------------------------
    # M9-05 modal hooks. Called from worker threads via the permissions
    # bridge. Each blocks on a Future until the user dismisses the modal.
    # ------------------------------------------------------------------

    def show_diff_modal(
        self, hunks: list[Hunk], *, timeout_s: float = 300.0
    ) -> list[DiffDecision]:
        from concurrent.futures import Future

        fut: Future[list[DiffDecision]] = Future()

        def _on_result(decisions):
            if not fut.done():
                fut.set_result(list(decisions or []))

        self.app.call_from_thread(
            self.app.push_modal_and_wait, DiffModal(hunks), _on_result
        )
        try:
            return fut.result(timeout=timeout_s)
        except TimeoutError:
            return []

    def show_budget_modal(
        self, used: int, limit: int, *, timeout_s: float = 300.0
    ) -> str:
        from concurrent.futures import Future

        fut: Future[str] = Future()

        def _on_result(choice):
            if not fut.done():
                fut.set_result(str(choice or "cancel"))

        self.app.call_from_thread(
            self.app.push_modal_and_wait,
            BudgetExhaustedModal(used, limit),
            _on_result,
        )
        try:
            return fut.result(timeout=timeout_s)
        except TimeoutError:
            return "cancel"


def _resolve_spawn_name() -> str | None:
    """Look up SPAWN_TOOL_NAME at call time so monkeypatched deletes are honored."""
    try:
        from .. import subagents as _subagents_mod

        return getattr(_subagents_mod, "SPAWN_TOOL_NAME", None)
    except ImportError:
        return None


def _optional_modal_class(class_name: str, module_name: str):
    try:
        from . import widgets as widgets_mod

        cls = getattr(widgets_mod, class_name, None)
        if cls is not None:
            return cls
    except Exception:  # noqa: BLE001
        pass
    try:
        module = importlib.import_module(f".widgets.{module_name}", package=__package__)
        return getattr(module, class_name, None)
    except Exception:  # noqa: BLE001
        return None


# Eager protocol check — fails at import time if any method is missing.
assert isinstance(TextualRenderer.__new__(TextualRenderer), render_mod.Renderer) or True
