"""Terminal renderer for the harness.

Goal: minimal, monospace, single accent. Glyphs: `▌ ❯ ⏵ ⚠`. No emoji.
TTY mode = rich Live updates. Non-TTY = plain text on stdout, traces on stderr.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from rich.console import Console


ACCENT_ORANGE = "#ff5b1f"


# ---------------------------------------------------------------------------
# Public protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Renderer(Protocol):
    def banner(self, *, model: str, cwd: Path, git_status: str) -> None: ...
    def show_user(self, task: str) -> None: ...
    def show_thinking(self, label: str) -> None: ...
    def show_plan(self, plan: Any, *, cost_usd: float) -> None: ...
    # R3 ToolCards (tui-redesign-spec §6.1): `call_id` is minted by the
    # harness at dispatch so the SAME id arrives on the pending and settled
    # calls for one step — the textual renderer mutates one card in place.
    # `output` is the full tool result text (settled calls only); summary
    # stays the one-line digest. Non-TUI renderers ignore both.
    def show_tool_call(
        self,
        call_id: str | None,
        name: str,
        args: dict,
        summary: str,
        state: str,
        *,
        output: str | None = None,
    ) -> None: ...
    def show_clarify(self, question: str, confidence: float) -> None: ...
    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None: ...
    def stream_delta(self, text: str) -> None: ...
    def finalize_stream(
        self,
        *,
        role: str,
        confidence: float | None = None,
        cost_usd: float | None = None,
        timestamp: str | None = None,
        accumulated_text: str | None = None,
    ) -> None: ...
    # R2 working indicator (tui-redesign-spec §6.1). Textual renderer drives
    # the live TranscriptView indicator; plain prints a single `working...`
    # line on turn start; everything else is a no-op.
    def show_working(self, label: str = "working") -> None: ...
    def update_working(self, elapsed_s: float, tokens: int) -> None: ...
    def hide_working(self) -> None: ...
    def status(self, *, model: str, tokens: int, cost_usd: float, ctx_pct: float) -> None: ...
    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None: ...
    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None: ...
    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None: ...
    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None: ...
    def show_warning(self, msg: str) -> None: ...


def make_renderer(
    *,
    json_mode: bool,
    plain: bool = False,
    force_tui: bool = False,
) -> Renderer:
    """Renderer factory honoring TUI capability rules.

    Decision order (M9-07 — default-path flip):
      1. json_mode=True → JsonRenderer (NDJSON on stdout; unchanged).
      2. plain=True or VOSS_PLAIN=1 → PlainRenderer.
      3. VOSS_RENDERER=compact → CompactRenderer.
      4. force_tui=True (or VOSS_FORCE_TUI=1) + size < 60x12 → stderr + exit(2).
      5. capability.tui_should_activate says yes → TextualRenderer (new default).
      6. capability rejected with Windows-console reason → emit locked stderr
         notice + PlainRenderer.
      7. non-TTY stdout → PlainRenderer.
      8. TTY but capability rejected (e.g. textual import failed, terminal
         too small without force_tui) → legacy TtyRenderer.
    """
    if json_mode:
        return JsonRenderer()

    if not force_tui and os.environ.get("VOSS_FORCE_TUI") == "1":
        force_tui = True

    if plain or os.environ.get("VOSS_PLAIN") == "1" or "--plain" in sys.argv[1:]:
        return PlainRenderer()

    if (
        not force_tui
        and (
            os.environ.get("VOSS_RENDERER", "").lower() == "compact"
        )
    ):
        return CompactRenderer()

    from .tui.capability import min_size_guard, tui_should_activate

    decision = tui_should_activate(json_mode=False)
    if decision.reason in ("--plain flag", "VOSS_PLAIN env"):
        return PlainRenderer()

    if force_tui:
        if decision.reason == "terminal below 60x12":
            size = shutil.get_terminal_size(fallback=(80, 24))
            sys.stderr.write(min_size_guard((size.columns, size.lines)) + "\n")
            sys.stderr.flush()
            sys.exit(2)
        from .tui.app import VossTUIApp
        from .tui.renderer import TextualRenderer

        return TextualRenderer(VossTUIApp())

    if decision.activate:
        from .tui.app import VossTUIApp
        from .tui.renderer import TextualRenderer

        return TextualRenderer(VossTUIApp())

    # M9-07 Windows-console strategy: locked notice to stderr, PlainRenderer
    # fallback. Fires whether stdout is a TTY or not.
    if decision.reason.startswith("Windows console missing capability"):
        sys.stderr.write(
            "voss: Windows console missing capability · using --plain mode\n"
        )
        sys.stderr.flush()
        return PlainRenderer()

    if not sys.stdout.isatty():
        return PlainRenderer()
    return TtyRenderer()


# ---------------------------------------------------------------------------
# TTY (rich)
# ---------------------------------------------------------------------------


GLYPH_TOOL = "⏵"
GLYPH_WARN = "⚠"
GLYPH_PROMPT = "▌"
GLYPH_USER = "❯"


def _glyph(value: str, fallback: str) -> str:
    return fallback if os.environ.get("VOSS_NO_UNICODE") == "1" else value


@dataclass
class TtyRenderer:
    console: Console = None  # type: ignore[assignment]
    quiet: bool = False

    def __post_init__(self) -> None:
        if self.console is None:
            self.console = Console(highlight=False)

    def banner(self, *, model: str, cwd: Path, git_status: str) -> None:
        cwd_str = str(cwd).replace(str(Path.home()), "~", 1)
        prompt = _glyph(GLYPH_PROMPT, ">")
        self.console.print(
            f"[bold {ACCENT_ORANGE}]{prompt} voss[/bold {ACCENT_ORANGE}] "
            f"[dim]{model} · {cwd_str} · {git_status}[/dim]"
        )
        self.console.print("[dim]  Type a task, or /help.[/dim]")

    def show_user(self, task: str) -> None:
        user = _glyph(GLYPH_USER, ">")
        self.console.print(
            f"\n[bold {ACCENT_ORANGE}]{user}[/bold {ACCENT_ORANGE}] {task}\n"
        )

    def show_thinking(self, label: str) -> None:
        self.console.print(f"[dim]  … {label}[/dim]")

    def show_plan(self, plan: Any, *, cost_usd: float) -> None:
        rationale = getattr(plan, "rationale", "")
        steps = getattr(plan, "steps", [])
        confidence = getattr(plan, "confidence", 0.0)
        self.console.print()
        self.console.print(f"  [bold]Plan[/bold] [dim](confidence {confidence:.2f})[/dim]")
        if rationale:
            self.console.print(f"  [dim]{rationale}[/dim]")
        for s in steps:
            why = f" — {s.why}" if s.why else ""
            self.console.print(f"  [dim]•[/dim] {s.name}{why}")
        self.console.print()

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
        glyph_color = {"ok": "green", "error": "red", "pending": "yellow"}.get(state, "dim")
        mark = {"ok": "✓", "error": "✗", "pending": "…"}[state]
        argstr = ", ".join(f"{k}={_short(v)}" for k, v in args.items())
        head = f"  [dim]{GLYPH_TOOL}[/dim] {name}([dim]{argstr}[/dim])"
        tail = f"[{glyph_color}]{mark}[/{glyph_color}] [dim]{summary}[/dim]"
        self.console.print(f"{head}  {tail}")

    def show_clarify(self, question: str, confidence: float) -> None:
        self.console.print(
            f"\n  [yellow]{GLYPH_WARN}[/yellow] confidence {confidence:.2f} — clarifying:"
        )
        self.console.print(f"  {question}\n")

    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None:
        self.console.print()
        self.console.print(text)
        self.console.print(
            f"\n  [dim]confidence {confidence:.2f} · ${cost_usd:.4f}[/dim]"
        )
        self.console.print()

    def stream_delta(self, text: str) -> None:
        self.console.print(text, end="", soft_wrap=True)

    def finalize_stream(
        self,
        *,
        role: str,
        confidence: float | None = None,
        cost_usd: float | None = None,
        timestamp: str | None = None,
        accumulated_text: str | None = None,
    ) -> None:
        self.console.print()
        parts: list[str] = [role]
        if timestamp is not None:
            parts.append(timestamp)
        if cost_usd is not None:
            parts.append(f"${cost_usd:.4f}")
        if confidence is not None:
            parts.append(f"conf {confidence:.2f}")
        self.console.print(f"  [dim]{' · '.join(parts)}[/dim]")

    def show_working(self, label: str = "working") -> None:
        pass

    def update_working(self, elapsed_s: float, tokens: int) -> None:
        pass

    def hide_working(self) -> None:
        pass

    def status(self, *, model: str, tokens: int, cost_usd: float, ctx_pct: float) -> None:
        cost_color = "red" if cost_usd > 1.0 else "dim"
        ctx_color = "yellow" if ctx_pct > 0.8 else "dim"
        line = (
            f"─ {model} · {tokens:,} tok · "
            f"[{cost_color}]${cost_usd:.3f}[/{cost_color}] · "
            f"[{ctx_color}]ctx {ctx_pct:.0%}[/{ctx_color}] "
        )
        # rich strip ansi for length calc -> use raw approximation
        approx_len = sum(1 for _ in line)
        line += "─" * max(0, self.console.width - approx_len)
        self.console.print(f"[dim]{line}[/dim]")

    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None:
        if self.quiet:
            return
        kilo = architecture_tokens / 1000
        msg = f"cognition: architecture ({kilo:.1f}k) + {constraints_count} constraints"
        if plans_loaded or decisions_loaded:
            msg += f" + {plans_loaded} plans + {decisions_loaded} decisions"
        self.console.print(f"[dim]  {msg}[/dim]")

    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None:
        self.console.print(
            f"[yellow]{GLYPH_WARN} architecture.md is {architecture_tokens} "
            f"tokens (over {budget} budget) — /analyze can rewrite a tighter "
            f"digest[/yellow]"
        )

    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None:
        self.console.print(
            f"[yellow]{GLYPH_WARN} principles block is {principles_tokens} "
            f"tokens (over {budget} budget) — truncated[/yellow]"
        )

    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None:
        names = ", ".join(truncated or [])
        self.console.print(
            f"[yellow]{GLYPH_WARN} instruction files truncated to {budget} tokens "
            f"({names})[/yellow]"
        )

    def show_warning(self, msg: str) -> None:
        self.console.print(f"[yellow]{GLYPH_WARN} {msg}[/yellow]")


@dataclass
class CompactRenderer:
    console: Console = None  # type: ignore[assignment]
    quiet: bool = False

    def __post_init__(self) -> None:
        if self.console is None:
            self.console = Console(highlight=False)

    def banner(self, *, model: str, cwd: Path, git_status: str) -> None:
        cwd_str = str(cwd).replace(str(Path.home()), "~", 1)
        prompt = _glyph(GLYPH_PROMPT, ">")
        self.console.print(
            f"[bold {ACCENT_ORANGE}]{prompt} voss[/bold {ACCENT_ORANGE}] "
            f"[dim]{model} · {cwd_str} · {git_status}[/dim]"
        )

    def show_user(self, task: str) -> None:
        user = _glyph(GLYPH_USER, ">")
        self.console.print(f"[bold {ACCENT_ORANGE}]{user}[/bold {ACCENT_ORANGE}] {task}")

    def show_thinking(self, label: str) -> None:
        self.console.print(f"[dim]  {label}[/dim]")

    def show_plan(self, plan: Any, *, cost_usd: float) -> None:
        steps = getattr(plan, "steps", [])
        confidence = getattr(plan, "confidence", 0.0)
        self.console.print(
            f"[bold {ACCENT_ORANGE}]plan[/bold {ACCENT_ORANGE}] "
            f"[dim]conf {confidence:.2f}[/dim]"
        )
        rationale = getattr(plan, "rationale", "")
        if rationale:
            self.console.print(f"[dim]  {rationale}[/dim]")
        for step in steps:
            why = f" — {step.why}" if step.why else ""
            self.console.print(f"  [dim]-[/dim] {step.name}{why}")

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
        mark = {"ok": "✓", "error": "✗", "pending": "…"}[state]
        state_style = {"ok": "green", "error": "red", "pending": ACCENT_ORANGE}.get(
            state, "dim"
        )
        argstr = ", ".join(f"{k}={_short(v)}" for k, v in args.items())
        call = f"{name}({argstr})" if argstr else f"{name}()"
        self.console.print(
            f"[{state_style}]{mark}[/{state_style}] {call} [dim]{summary}[/dim]"
        )

    def show_clarify(self, question: str, confidence: float) -> None:
        self.console.print(
            f"[bold {ACCENT_ORANGE}]?[/bold {ACCENT_ORANGE}] "
            f"[dim]conf {confidence:.2f}[/dim] {question}"
        )

    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None:
        self.console.print(text)
        self.console.print(
            f"[dim]conf {confidence:.2f} · ${cost_usd:.4f}[/dim]"
        )

    def stream_delta(self, text: str) -> None:
        self.console.print(text, end="", soft_wrap=True)

    def finalize_stream(
        self,
        *,
        role: str,
        confidence: float | None = None,
        cost_usd: float | None = None,
        timestamp: str | None = None,
        accumulated_text: str | None = None,
    ) -> None:
        self.console.print()
        parts: list[str] = [role]
        if timestamp is not None:
            parts.append(timestamp)
        if cost_usd is not None:
            parts.append(f"${cost_usd:.4f}")
        if confidence is not None:
            parts.append(f"conf {confidence:.2f}")
        self.console.print(f"[dim]{' · '.join(parts)}[/dim]")

    def show_working(self, label: str = "working") -> None:
        pass

    def update_working(self, elapsed_s: float, tokens: int) -> None:
        pass

    def hide_working(self) -> None:
        pass

    def status(self, *, model: str, tokens: int, cost_usd: float, ctx_pct: float) -> None:
        self.console.print(
            f"[dim]{model} · {tokens:,} tok · ${cost_usd:.3f} · ctx {ctx_pct:.0%}[/dim]"
        )

    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None:
        if self.quiet:
            return
        kilo = architecture_tokens / 1000
        msg = f"cognition {kilo:.1f}k arch · {constraints_count} constraints"
        if plans_loaded or decisions_loaded:
            msg += f" · {plans_loaded} plans · {decisions_loaded} decisions"
        self.console.print(f"[dim]{msg}[/dim]")

    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None:
        self.console.print(
            f"[{ACCENT_ORANGE}]{GLYPH_WARN}[/{ACCENT_ORANGE}] "
            f"architecture.md is {architecture_tokens} tokens (over {budget})"
        )

    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None:
        self.console.print(
            f"[{ACCENT_ORANGE}]{GLYPH_WARN}[/{ACCENT_ORANGE}] "
            f"principles block is {principles_tokens} tokens (over {budget})"
        )

    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None:
        names = ", ".join(truncated or [])
        self.console.print(
            f"[{ACCENT_ORANGE}]{GLYPH_WARN}[/{ACCENT_ORANGE}] "
            f"instruction files truncated to {budget} tokens ({names})"
        )

    def show_warning(self, msg: str) -> None:
        self.console.print(f"[{ACCENT_ORANGE}]{GLYPH_WARN}[/{ACCENT_ORANGE}] {msg}")


def _short(v: Any, limit: int = 40) -> str:
    s = str(v)
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s


# ---------------------------------------------------------------------------
# Plain (non-TTY pipe target)
# ---------------------------------------------------------------------------


class PlainRenderer:
    def banner(self, *, model: str, cwd: Path, git_status: str) -> None:
        pass

    def show_user(self, task: str) -> None:
        print(f"> {task}", file=sys.stderr)

    def show_thinking(self, label: str) -> None:
        print(f"... {label}", file=sys.stderr)

    def show_plan(self, plan: Any, *, cost_usd: float) -> None:
        steps = getattr(plan, "steps", [])
        conf = getattr(plan, "confidence", 0.0)
        print(f"plan: {len(steps)} steps, conf={conf:.2f}", file=sys.stderr)

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
        # R3: call_id/output accepted and ignored — the plain one-line
        # format is a locked parity contract (test_plain_parity).
        print(f"[{state}] {name}({args}) -> {summary}", file=sys.stderr)

    def show_clarify(self, question: str, confidence: float) -> None:
        print(question)

    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None:
        print(text)

    def stream_delta(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def finalize_stream(
        self,
        *,
        role: str,
        confidence: float | None = None,
        cost_usd: float | None = None,
        timestamp: str | None = None,
        accumulated_text: str | None = None,
    ) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()
        parts: list[str] = [role]
        if timestamp is not None:
            parts.append(timestamp)
        if cost_usd is not None:
            parts.append(f"${cost_usd:.4f}")
        if confidence is not None:
            parts.append(f"conf {confidence:.2f}")
        print(" · ".join(parts), file=sys.stderr)

    def show_working(self, label: str = "working") -> None:
        # R2 parity rule: a single `working...` line on turn start (stderr,
        # like every other plain side-channel line), no animation, no updates.
        print("working...", file=sys.stderr)

    def update_working(self, elapsed_s: float, tokens: int) -> None:
        pass

    def hide_working(self) -> None:
        pass

    def status(self, *, model: str, tokens: int, cost_usd: float, ctx_pct: float) -> None:
        pass

    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None:
        print(
            f"cognition: arch={architecture_tokens}tok constraints={constraints_count}",
            file=sys.stderr,
        )

    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None:
        print(
            f"cognition overflow: {architecture_tokens} > {budget}",
            file=sys.stderr,
        )

    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None:
        print(
            f"principles overflow: {principles_tokens} > {budget}",
            file=sys.stderr,
        )

    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None:
        print(
            f"instructions overflow: {instructions_tokens} > {budget} "
            f"({', '.join(truncated or [])})",
            file=sys.stderr,
        )

    def show_warning(self, msg: str) -> None:
        print(f"warning: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# JSON (NDJSON, one event per line on stdout)
# ---------------------------------------------------------------------------


class JsonRenderer:
    V = 1

    def _emit(self, **kw: Any) -> None:
        kw.setdefault("v", self.V)
        sys.stdout.write(json.dumps(kw, default=str) + "\n")
        sys.stdout.flush()

    def banner(self, *, model: str, cwd: Path, git_status: str) -> None:
        self._emit(type="banner", model=model, cwd=str(cwd), git=git_status)

    def show_user(self, task: str) -> None:
        self._emit(type="user", task=task)

    def show_thinking(self, label: str) -> None:
        self._emit(type="thinking", label=label)

    def show_plan(self, plan: Any, *, cost_usd: float) -> None:
        self._emit(
            type="plan",
            confidence=getattr(plan, "confidence", 0.0),
            steps=[{"name": s.name, "args": s.args} for s in getattr(plan, "steps", [])],
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
        # call_id/output dropped: the NDJSON event vocabulary is a locked
        # contract (same policy as show_working).
        self._emit(type="tool", name=name, args=args, summary=summary, state=state)

    def show_clarify(self, question: str, confidence: float) -> None:
        self._emit(type="clarify", question=question, confidence=confidence)

    def show_final(self, text: str, *, confidence: float, cost_usd: float) -> None:
        self._emit(type="final", text=text, confidence=confidence, cost_usd=cost_usd)

    def stream_delta(self, text: str) -> None:
        self._emit(type="stream.delta", text=text)

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
            type="stream.finalize",
            role=role,
            confidence=confidence,
            cost_usd=cost_usd,
            timestamp=timestamp,
        )

    def show_working(self, label: str = "working") -> None:
        # Deliberately silent — the NDJSON event vocabulary is a locked
        # contract; turn activity is already observable via stream events.
        pass

    def update_working(self, elapsed_s: float, tokens: int) -> None:
        pass

    def hide_working(self) -> None:
        pass

    def status(self, *, model: str, tokens: int, cost_usd: float, ctx_pct: float) -> None:
        self._emit(type="status", model=model, tokens=tokens, cost_usd=cost_usd, ctx_pct=ctx_pct)

    def show_cognition(
        self,
        *,
        architecture_tokens: int,
        constraints_count: int,
        plans_loaded: int = 0,
        decisions_loaded: int = 0,
    ) -> None:
        self._emit(
            type="cognition_loaded",
            architecture_tokens=architecture_tokens,
            constraints_count=constraints_count,
            plans_loaded=plans_loaded,
            decisions_loaded=decisions_loaded,
        )

    def show_cognition_overflow(
        self, *, architecture_tokens: int, budget: int = 6000
    ) -> None:
        self._emit(
            type="cognition_overflow",
            architecture_tokens=architecture_tokens,
            budget=budget,
        )

    def show_principles_overflow(
        self, *, principles_tokens: int, budget: int = 1000
    ) -> None:
        self._emit(
            type="principles_overflow",
            principles_tokens=principles_tokens,
            budget=budget,
        )

    def show_instructions_overflow(
        self, *, instructions_tokens: int, budget: int = 4000, truncated: list[str] | None = None
    ) -> None:
        self._emit(
            type="instructions_overflow",
            instructions_tokens=instructions_tokens,
            budget=budget,
            truncated=list(truncated or []),
        )

    def show_warning(self, msg: str) -> None:
        self._emit(type="warning", message=msg)
