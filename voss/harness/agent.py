"""Agent loop for `voss do` and the REPL.

This is a Python skeleton. Phase H3 ports it to .voss; the structure here
mirrors the constructs that will be lowered: ContextScope (token budget),
ProbableValue<Plan> (confidence-gated planning), gather (later, parallel
sub-agents), within/fallback (later, model tier-down).
"""
from __future__ import annotations

import asyncio
import functools
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

from voss.template_render import render_package_template
from voss_runtime import (
    ContextScope,
    EpisodicMemory,
    ProbableValue,
    get_config,
)
from voss_runtime.providers import get as get_provider
from voss_runtime.providers.base import ModelProvider

from . import cognition as cognition_mod
from . import instructions as instructions_mod
from .config import get_instructions_config
from . import telemetry
from .permissions import PermissionGate
from .providers import (
    Done,
    ParsedPlan,
    ProviderStreamEvent,
    TextDelta,
    ToolUseDelta,
    ToolUseEnd,
    ToolUseStart,
    Usage,
)
from .principles import resolve_principles
from .recorder import (
    RunRecorder,
    _append_savings_record,
    _emit_budget_osc,
    _emit_context_osc,
    estimate_savings_usd,
    write_decisions_md,
)
from .render import Renderer
from .session import IterationRecord, RunRecord
from .tools import ToolEntry


COGNITION_BUDGET_TOKENS = 6000
# V2-02 D-05: principles inject as their own ~1k-token block, mirroring cognition.
PRINCIPLES_BUDGET_TOKENS = 1000


class BatchInvariantError(Exception):
    """Raised when a multi-step batch contains a mutating or unknown step.

    T2-03 / PAR-02. Indicates a planner bug or partitioner regression —
    the partition scheduler must never dispatch a mutating tool inside a
    parallel read batch. Surfaces in RunRecord.exit_reason='batch-invariant'
    (5th additive enum value joining T1's done|max-iter|budget|interrupt).

    Standalone Exception subclass per CONTEXT.md D-18 + RESEARCH.md A1
    (no domain hierarchy; mirrors voss/harness/sandbox.py SandboxError).
    """


def _default_token_count(text: str, *, model: str) -> int:
    litellm = sys.modules.get("litellm")
    if litellm is not None:
        try:
            return int(litellm.token_counter(model=model, text=text))
        except Exception:  # noqa: BLE001 — never crash a turn over a token count
            pass
    # Fallback to a 4-chars-per-token approximation.
    return max(len(text) // 4, 1)


def _compose_cognition_prompt(
    bundle,
    *,
    model: str,
    token_count_fn=None,
    renderer: Renderer | None = None,
) -> str:
    """Render the cognition prepend block, enforcing the 6k token budget.

    Truncates constraints first on overflow; architecture stays intact.
    Emits `cognition_overflow` via the renderer if provided.
    """
    if bundle is None or not getattr(bundle, "initialized", False):
        return ""

    arch = bundle.architecture_md or ""
    constraints_bullets = cognition_mod.render_constraints_bullets(bundle.constraints)

    def _render(with_constraints: bool) -> str:
        return render_package_template(
            "voss",
            "templates/agent/cognition_block.md.jinja",
            {
                "architecture": arch,
                "with_constraints": with_constraints,
                "constraints_bullets": constraints_bullets,
            },
        )

    body = _render(with_constraints=True)

    if token_count_fn is None:
        return body

    try:
        measured = int(token_count_fn(body, model=model))
    except Exception:  # noqa: BLE001 — T-M2-20: never block over a count
        if renderer is not None:
            try:
                renderer.show_warning(
                    "cognition token-count unavailable; budget unchecked"
                )
            except Exception:  # noqa: BLE001
                pass
        return body

    if measured <= COGNITION_BUDGET_TOKENS:
        return body

    if renderer is not None:
        try:
            renderer.show_cognition_overflow(
                architecture_tokens=measured, budget=COGNITION_BUDGET_TOKENS
            )
        except Exception:  # noqa: BLE001
            pass

    truncated = _render(with_constraints=False)
    return truncated + "\n\n(constraints truncated due to budget)"


def _compose_instructions_block(
    bundle,
    *,
    budget: int = 4000,
    renderer: Renderer | None = None,
) -> str:
    """Render the `## Instructions` block (AGENTS.md / CLAUDE.md bundle).

    Budget enforcement happens in `instructions.load`; this only renders and
    surfaces truncation as `instructions_overflow` on the renderer.
    """
    if bundle is None:
        return ""
    if bundle.truncated and renderer is not None:
        try:
            renderer.show_instructions_overflow(
                instructions_tokens=bundle.tokens,
                budget=budget,
                truncated=list(bundle.truncated),
            )
        except Exception:  # noqa: BLE001
            pass
    if not bundle.merged_text:
        return ""
    return render_package_template(
        "voss",
        "templates/agent/instructions_block.md.jinja",
        {"merged_text": bundle.merged_text},
    )


def _compose_principles_block(
    config,
    *,
    model: str,
    token_count_fn=None,
    renderer: Renderer | None = None,
) -> str:
    """Render the distinct `## Principles` block, enforcing the ~1k budget.

    Opaque text only — iterates the config's ordered `principles` tuple and
    never branches on a key. On overflow, drops whole principles from the END
    of the ordered list until under budget (so earlier/default principles
    survive deterministically), appends a truncation marker, and emits
    `principles_overflow` via the renderer. Mirrors `_compose_cognition_prompt`.
    """
    items = list(config.principles) if config is not None else []
    if not items:
        return ""

    def _render(pairs) -> str:
        return render_package_template(
            "voss",
            "templates/agent/principles_block.md.jinja",
            {"principles": [text for _, text in pairs]},
        )

    body = _render(items)
    if token_count_fn is None:
        return body

    try:
        measured = int(token_count_fn(body, model=model))
    except Exception:  # noqa: BLE001 — never block a turn over a count
        if renderer is not None:
            try:
                renderer.show_warning(
                    "principles token-count unavailable; budget unchecked"
                )
            except Exception:  # noqa: BLE001
                pass
        return body

    if measured <= PRINCIPLES_BUDGET_TOKENS:
        return body

    if renderer is not None:
        try:
            renderer.show_principles_overflow(
                principles_tokens=measured, budget=PRINCIPLES_BUDGET_TOKENS
            )
        except Exception:  # noqa: BLE001
            pass

    marker = "\n\n(principles truncated due to budget)"
    kept = list(items)
    while kept:
        kept.pop()
        candidate = _render(kept) + marker
        try:
            if int(token_count_fn(candidate, model=model)) <= PRINCIPLES_BUDGET_TOKENS:
                return candidate
        except Exception:  # noqa: BLE001
            return candidate
    return "## Principles" + marker


# M2: how much conversation history to inject into the per-turn prompt, and how
# many prior RunRecords to summarise on resume. last(6) lost deep context on
# `voss resume`; widen the window (bounded; EpisodicMemory summarises overflow).
HISTORY_WINDOW = 30
PRIOR_RUNS_WINDOW = 5


def _normalize_run_for_template(run_dict: dict, label: str | None) -> dict:
    plan_obj = run_dict.get("plan") or {}
    plan_rationale = plan_obj.get("rationale", "") if isinstance(plan_obj, dict) else ""

    def _bullet_items(items, key: str | None = None) -> list[str]:
        result: list[str] = []
        for it in items:
            if key and isinstance(it, dict):
                result.append(it.get(key) or it.get("title") or "")
            else:
                result.append(str(it))
        return result

    return {
        "label": label,
        "goal": run_dict.get("goal", "") or "",
        "plan_rationale": plan_rationale,
        "decisions": _bullet_items(run_dict.get("decisions") or [], key="title"),
        "follow_ups": _bullet_items(run_dict.get("follow_ups") or []),
        "risks": _bullet_items(run_dict.get("risks") or []),
    }


def _compose_prior_context_block(run: dict | list | None) -> str:
    """Render prior-session context for resume.

    Accepts a single RunRecord dict (legacy single-turn, byte-compatible) or a
    LIST of RunRecord dicts (M2: the server forwards all prior runs so resume
    surfaces more than just the last turn). The most recent ``PRIOR_RUNS_WINDOW``
    runs are rendered, newest first.
    """
    if not run:
        return ""
    if isinstance(run, list):
        runs = [r for r in run if r]
        if not runs:
            return ""
        recent = list(reversed(runs))[:PRIOR_RUNS_WINDOW]
        normalized = [
            _normalize_run_for_template(
                r,
                "most-recent turn" if i == 0 else f"turn -{i + 1}",
            )
            for i, r in enumerate(recent)
        ]
        return render_package_template(
            "voss",
            "templates/agent/prior_context.md.jinja",
            {"multi_run": True, "runs": normalized},
        )
    return render_package_template(
        "voss",
        "templates/agent/prior_context.md.jinja",
        {
            "multi_run": False,
            "runs": [_normalize_run_for_template(run, None)],
        },
    )

# ---------------------------------------------------------------------------
# Plan schema — what the model must return
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    name: str = Field(description="Tool name from the available tool list.")
    args: dict[str, Any] = Field(default_factory=dict, description="Keyword arguments.")
    why: str = Field(default="", description="One-line rationale for this call.")


class Plan(BaseModel):
    rationale: str = Field(description="One-paragraph reasoning for the chosen approach.")
    steps: list[ToolCall] = Field(default_factory=list, description="Sequential tool calls.")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Self-rated confidence the plan resolves the user's task. 0.0-1.0.",
    )
    open_question: str | None = Field(
        default=None,
        description="If confidence is low, the clarifying question to ask the user.",
    )
    final_when_done: str = Field(
        default="",
        description="The answer to surface to the user once tools have run. May reference results.",
    )


class RunSemantics(BaseModel):
    """Closing-turn semantics produced by the privileged record_run call.

    `extra="ignore"` is LENIENT (unlike cognition_schemas STRICT) because the
    LLM may hallucinate fields; we silently drop them rather than crashing
    the turn close.
    """
    model_config = {"extra": "ignore"}

    goal: str = ""
    avoided: list[dict] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    decisions: list[dict] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


PLAN_SYSTEM = render_package_template(
    "voss",
    "templates/prompts/plan_system.txt.jinja",
    {},
)


RECORD_RUN_SYSTEM = render_package_template(
    "voss",
    "templates/prompts/record_run_system.txt.jinja",
    {},
)


# T1-05: PLAN_LOOP_SYSTEM is the iteration-loop system prompt. The
# `{max_iterations}` token is filled by _compose_loop_system via str.replace
# (NOT f-string) so the prefix stays cacheable across calls for future T4.
PLAN_LOOP_SYSTEM = render_package_template(
    "voss",
    "templates/prompts/plan_loop_system.txt.jinja",
    {},
)


# T1-05: exact final-string sentinels for hit-cap and budget-exhaustion
# exits. SPEC ITER-01 acceptance + CONTEXT.md "halted: max-iter" lock the
# exact lowercase-hyphenated substring; tests grep for it.
HALTED_MAX_ITER_FINAL = "halted: max-iter"
HALTED_BUDGET_FINAL = "halted: budget"


def _compose_loop_system(max_iterations: int) -> str:
    """Fill the PLAN_LOOP_SYSTEM placeholder via str.replace (cache-stable)."""
    return PLAN_LOOP_SYSTEM.replace("{max_iterations}", str(max_iterations))


def _compose_system_blocks(
    *,
    voss_md_block: str,
    cognition_text: str,
    instructions_text: str = "",
    principles_text: str = "",
    project_index_text: str = "",
    pinned_memory_text: str = "",
    code_recall_text: str = "",
    prior_context_text: str,
    loop_system: str,
) -> list[dict]:
    """Render the CACHE-01 static prefix as cacheable text blocks.

    M10-05 inserts the bounded `## Project Index` as its own slice after cognition.
    V2-02 inserts the `## Principles` block as its OWN slice immediately after
    cognition (static per run, so it belongs in the cacheable prefix).
    """
    blocks = [
        {"type": "text", "text": text}
        for text in (
            voss_md_block,
            instructions_text,
            cognition_text,
            principles_text,
            project_index_text,
            pinned_memory_text,  # VRNK-06 — non-evictable fixed-cost block in the cacheable prefix (D-07), ahead of the evictable code_recall slot
            code_recall_text,  # V19-05 VSEM-06 — rides the same evictable tuple, no second budget
            prior_context_text,
            loop_system,
        )
        if text
    ]
    if blocks:
        blocks[-1] = {
            **blocks[-1],
            "cache_control": {"type": "ephemeral"},
        }
    return blocks


def _build_iter_rider(
    *,
    index: int,
    max_iterations: int,
    tokens_used: int,
    token_budget: int,
    prior_iters: list,
) -> str:
    """Build the per-iter rider system message.

    Stays SEPARATE from the cacheable PLAN_LOOP_SYSTEM block so future T4
    caching can mark the static prefix `cache_control: ephemeral` without
    bouncing the cache on each iteration.
    """
    lines = [
        f"Iteration {index + 1} of {max_iterations}.",
        f"Token budget: {tokens_used}/{token_budget} used.",
    ]
    if prior_iters:
        lines.append("Prior iterations:")
        for ir in prior_iters:
            plan = ir.plan or {}
            step_count = len(plan.get("steps", []) or [])
            tool_count = len(ir.tool_results or [])
            snippet_src = plan.get("final_when_done") or plan.get("rationale") or ""
            snippet = snippet_src.replace("\n", " ")[:60]
            lines.append(
                f"- Iter {ir.index}: {step_count} steps, {tool_count} tools, "
                f"{snippet}"
            )
    return "\n".join(lines)


def _serialize_iter_for_replay(iter_rec) -> tuple[dict, dict]:
    """Render one prior iter as (assistant, user) messages for replay.

    The assistant message carries the model's plan JSON; the user message
    carries the tool-result summary. Args are redacted via
    telemetry.redact_tool_args to keep secrets out of the message chain.
    """
    plan_dict = iter_rec.plan or {}
    assistant_content = json.dumps(
        {
            "rationale": plan_dict.get("rationale", ""),
            "steps": plan_dict.get("steps", []) or [],
            "final_when_done": plan_dict.get("final_when_done", ""),
        }
    )
    assistant_msg = {"role": "assistant", "content": assistant_content}

    lines = [f"Tool results for iteration {iter_rec.index}:"]
    for tr in iter_rec.tool_results or []:
        name = tr.get("name", "")
        args = tr.get("args", {}) or {}
        if isinstance(args, dict):
            args = telemetry.redact_tool_args(dict(args))
        args_str = str(args)[:400]
        result_str = str(tr.get("result", ""))[:400]
        lines.append(f"- {name}({args_str}) -> {result_str}")
    user_msg = {"role": "user", "content": "\n".join(lines)}
    return assistant_msg, user_msg


def _is_done_plan(plan) -> bool:
    """Predicate: plan signals loop termination via empty steps + non-empty final."""
    steps = getattr(plan, "steps", None)
    if steps is None or len(steps) != 0:
        return False
    final = getattr(plan, "final_when_done", "") or ""
    return bool(final.strip())


@dataclass
class TurnResult:
    plan: Plan
    confidence: float
    final: str
    tool_results: list[str]
    cost_usd: float
    run: RunRecord | None = None


def _format_tools(tools: dict[str, ToolEntry]) -> str:
    catalog = []
    for name, td in tools.items():
        params = td.parameters.get("properties", {})
        sig = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
        catalog.append({"name": name, "signature": sig, "description": td.description})
    return render_package_template(
        "voss",
        "templates/agent/tool_catalog.txt.jinja",
        {"tools": catalog},
    )


async def run_turn(
    task: str,
    *,
    tools: dict[str, ToolEntry],
    cwd: Path,
    renderer: Renderer,
    confidence_threshold: float = 0.60,
    token_budget: int = 60_000,
    model: str | None = None,
    provider: ModelProvider | None = None,
    history: EpisodicMemory | None = None,
    permissions: PermissionGate | None = None,
    session_id: str | None = None,
    cognition=None,
    prior_context: dict | list | None = None,
    voss_md_text: str | None = None,
    project_index_text: str = "",
    code_recall_text: str = "",
    pinned_memory_text: str = "",
    steer_inbox: asyncio.Queue | None = None,
    packing_enabled: bool = True,
) -> TurnResult:
    """Run one agent turn.

    Mirrors the planned .voss loop:

        ctx(budget: token_budget) {
            let plan: probable<Plan> = ask(...)
            if plan @ p >= threshold {
                for step in plan.steps: tool.invoke(step)
                yield review(results)
            } else {
                yield clarify(plan.open_question)
            }
        }
    """
    _tel_ok = True
    _tel_err: str | None = None
    preview = task.replace("\n", " ").strip()
    if len(preview) > 200:
        preview = preview[:199] + "…"
    telemetry.begin_turn()
    telemetry.emit(
        "turn.start",
        "info",
        data={"task_preview": preview, "cwd": str(cwd.resolve())},
    )
    try:
        # R2 working indicator (tui-redesign-spec §3.6/§6.1): turn start.
        # getattr-guarded — bridge/fake renderers may predate the protocol
        # addition, and indicator failures must never crash the turn.
        _show_working = getattr(renderer, "show_working", None)
        if _show_working is not None:
            try:
                _show_working("working")
            except Exception:  # noqa: BLE001
                pass
        return await _run_turn_exec(
            task,
            tools=tools,
            cwd=cwd,
            renderer=renderer,
            confidence_threshold=confidence_threshold,
            token_budget=token_budget,
            model=model,
            provider=provider,
            history=history,
            permissions=permissions,
            session_id=session_id,
            cognition=cognition,
            prior_context=prior_context,
            voss_md_text=voss_md_text,
            project_index_text=project_index_text,
            code_recall_text=code_recall_text,
            pinned_memory_text=pinned_memory_text,
            steer_inbox=steer_inbox,
            packing_enabled=packing_enabled,
        )
    except BaseException as e:
        _tel_ok = False
        _tel_err = str(e)[:500]
        raise
    finally:
        # Indicator comes down however the turn ends (finalize, error,
        # interrupt) — same guard rationale as show_working above.
        _hide_working = getattr(renderer, "hide_working", None)
        if _hide_working is not None:
            try:
                _hide_working()
            except Exception:  # noqa: BLE001
                pass
        telemetry.finalize_turn(_tel_ok, _tel_err)


async def _run_turn_exec(
    task: str,
    *,
    tools: dict[str, ToolEntry],
    cwd: Path,
    renderer: Renderer,
    confidence_threshold: float = 0.60,
    token_budget: int = 60_000,
    model: str | None = None,
    provider: ModelProvider | None = None,
    history: EpisodicMemory | None = None,
    permissions: PermissionGate | None = None,
    session_id: str | None = None,
    cognition=None,
    prior_context: dict | list | None = None,
    voss_md_text: str | None = None,
    project_index_text: str = "",
    code_recall_text: str = "",
    pinned_memory_text: str = "",
    steer_inbox: asyncio.Queue | None = None,
    packing_enabled: bool = True,
) -> TurnResult:
    """T1-05: iteration-loop turn driver.

    Replaces the pre-T1 single-shot plan→exec→done flow with a while-loop
    that streams plan tokens, re-plans on tool results, and exits on
    done / max-iter / budget. Confidence gate fires only on the
    terminating iteration. Per-iteration telemetry and IterationRecord
    capture land in the RunRecorder. Pre-T1 placeholder substitution is gone.
    """
    cfg = get_config()
    model = model or cfg.default_model
    if provider is None:
        provider = get_provider(model)
    max_iterations: int = cfg.max_iterations

    history_block = ""
    if history is not None:
        # M2: include the rolling summary (if any) + a wider window so resumed
        # sessions see real conversation depth, not just the last 6 turns.
        parts: list[str] = []
        summary = getattr(history, "summary", "")
        if summary:
            parts.append(f"summary: {summary}")
        parts.extend(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in history.last(HISTORY_WINDOW)
        )
        if parts:
            history_block = "\n\nRecent conversation:\n" + "\n".join(parts)

    user_prompt = (
        f"Task:\n{task}\n\n"
        f"Working directory: {cwd}\n\n"
        f"Available tools:\n{_format_tools(tools)}{history_block}\n"
    )

    if history is not None:
        history.add(task, role="user")

    rec = RunRecorder.start()
    try:

        cognition_text = _compose_cognition_prompt(
            cognition,
            model=model,
            token_count_fn=_default_token_count,
            renderer=renderer,
        )
        prior_context_text = _compose_prior_context_block(prior_context)
        voss_md_block = f"# VOSS.md\n{voss_md_text}" if voss_md_text else ""
        instructions_cfg = get_instructions_config()
        instructions_bundle = instructions_mod.load(
            cwd,
            config=instructions_cfg,
            token_count=lambda t: _default_token_count(t, model=model),
        )
        rec.instructions_hash = instructions_bundle.bundle_hash
        rec.instructions_files = list(instructions_bundle.paths)
        instructions_text = _compose_instructions_block(
            instructions_bundle,
            budget=int(instructions_cfg["budget_tokens"]),
            renderer=renderer,
        )
        # V2-02 VPRIN-04: resolve + inject the team's principles as a distinct
        # cacheable block (capped, overflow-warned) alongside cognition.
        principles_text = _compose_principles_block(
            resolve_principles(cwd),
            model=model,
            token_count_fn=_default_token_count,
            renderer=renderer,
        )
        # T4 CACHE-01: cached static prefix as block list; rider (below, per-iter) stays a string and remains uncached.
        sys_blocks = _compose_system_blocks(
            voss_md_block=voss_md_block,
            cognition_text=cognition_text,
            instructions_text=instructions_text,
            principles_text=principles_text,
            project_index_text=project_index_text,
            pinned_memory_text=pinned_memory_text,
            code_recall_text=code_recall_text,
            prior_context_text=prior_context_text,
            loop_system=_compose_loop_system(max_iterations),
        )

        if cognition is not None and getattr(cognition, "initialized", False):
            c_count = (
                len(cognition.constraints.rules)
                if cognition.constraints and cognition.constraints.rules
                else 0
            )
            renderer.show_cognition(
                architecture_tokens=cognition.architecture_tokens,
                constraints_count=c_count,
            )
            telemetry.emit(
                "cognition.snapshot",
                "info",
                data={
                    "architecture_tokens": cognition.architecture_tokens,
                    "constraints_count": c_count,
                },
            )

        # Loop-scoped state.
        iteration_index: int = 0
        exit_reason: str | None = None
        final_plan: Plan | None = None
        total_cost_usd: float = 0.0
        total_prompt_tokens: int = 0
        total_completion_tokens: int = 0
        all_iter_records: list[IterationRecord] = []
        # M13-03 D-04: per-turn buffer for parent->child steer guidance drained
        # from steer_inbox at the loop boundary (agent.py:830) and injected
        # once as a synthetic next-iteration user message (see injection site).
        pending_steer: list[str] = []
        this_iter_plan: Plan | None = None
        this_iter_usage: Usage | None = None
        # R2 working indicator token tick (tui-redesign-spec §3.6): running
        # ~4-chars/token estimate across the whole turn; the renderer
        # coalesces posts to <= 4 Hz. getattr-guarded like show_working.
        _working_chars: int = 0
        _update_working = getattr(renderer, "update_working", None)

        # V18 VOPT-03/06: profile + allocator resolved ONCE per run (not per
        # iteration) so the stable-region hysteresis state persists and the
        # T4 prompt cache stays warm (RESEARCH Pitfall 1).
        from voss.harness.config import get_packing_profile
        from voss.harness.context_allocator import ContextAllocator

        _packing_profile = get_packing_profile()
        # VOSS_NO_PACK env disables packing on paths that bypass the CLI
        # flag (eval runner calls run_turn directly — VOPT-07 driver).
        _packing_env_off = os.environ.get("VOSS_NO_PACK", "") not in ("", "0")
        _allocator = ContextAllocator(
            token_count=functools.partial(_default_token_count, model=model)
        )

        async with ContextScope(
            token_budget=token_budget, model=model, provider=provider
        ) as ctx:
            while iteration_index < max_iterations:
                # F4: load pin commands from file-based channel
                _pin_file = cwd / ".voss" / "context-pins.json"
                rec._context_tracker.load_pins(_pin_file)
                iter_rec = rec.begin_iteration()
                telemetry.emit(
                    "iteration.start",
                    "info",
                    data={
                        "iteration_index": iteration_index,
                        "max_iterations": max_iterations,
                    },
                )

                rider = _build_iter_rider(
                    index=iteration_index,
                    max_iterations=max_iterations,
                    tokens_used=total_prompt_tokens + total_completion_tokens,
                    token_budget=token_budget,
                    prior_iters=all_iter_records,
                )
                messages: list[dict] = [
                    {"role": "system", "content": sys_blocks},  # cached static prefix (CACHE-01)
                    {"role": "system", "content": rider},
                    {"role": "user", "content": user_prompt},
                ]
                _packing_disabled = (
                    not packing_enabled
                    or not _packing_profile.enabled
                    or _packing_env_off
                )
                if all_iter_records and not _packing_disabled:
                    # V18 VOPT-01: pack the replay tail under what remains of
                    # token_budget after the cached prefix + rider + prompt +
                    # completion headroom. sys_blocks NEVER enters the
                    # allocator (T4 prefix stays byte-identical, VOPT-06).
                    _reserve = (
                        sum(
                            _default_token_count(b["text"], model=model)
                            for b in sys_blocks
                            if isinstance(b, dict) and isinstance(b.get("text"), str)
                        )
                        + _default_token_count(rider, model=model)
                        + _default_token_count(user_prompt, model=model)
                        + cfg.max_output_tokens
                    )
                    _packing_budget = max(token_budget - _reserve, 0)
                    _replay_pairs = _allocator.pack(
                        all_iter_records, _packing_budget, _packing_profile
                    )
                    for a_msg, u_msg in _replay_pairs:
                        messages.append(a_msg)
                        messages.append(u_msg)
                    # V18 VOPT-05: honest baseline — render the full replay
                    # for MEASUREMENT only (never sent when packing is on).
                    _full_pairs = [
                        _serialize_iter_for_replay(p) for p in all_iter_records
                    ]
                    _orig_est = sum(
                        _default_token_count(str(m["content"]), model=model)
                        for pair in _full_pairs
                        for m in pair
                    )
                    _packed_est = sum(
                        _default_token_count(str(m["content"]), model=model)
                        for pair in _replay_pairs
                        for m in pair
                    )
                    _pack_method = (
                        "full"
                        if _replay_pairs == _full_pairs
                        else f"tiered-K{_packing_profile.recent_full_k}"
                        f"-M{_packing_profile.digest_cutoff_m}"
                    )
                else:
                    # V18 VOPT-06 disabled branch: the ORIGINAL replay loop,
                    # verbatim — byte-identity by code path, not by golden.
                    for prior in all_iter_records:
                        a_msg, u_msg = _serialize_iter_for_replay(prior)
                        messages.append(a_msg)
                        messages.append(u_msg)
                    # V18 VOPT-05: no packing — original == packed by definition.
                    _orig_est = _packed_est = sum(
                        _default_token_count(str(m["content"]), model=model)
                        for m in messages[3:]
                    )
                    _pack_method = "no-pack" if _packing_disabled else "full"
                _savings_osc = {
                    "original": _orig_est,
                    "packed": _packed_est,
                    "pct": round((1 - _packed_est / _orig_est) * 100)
                    if _orig_est
                    else 0,
                }

                # M13-03 OQ-A2 (RESEARCH Pattern 3): land a parent steer as ONE
                # synthetic next-iteration user message — a sibling of the
                # replay messages above. This is the ONLY route that surfaces
                # mid-loop: `history_block` is built ONCE before the while-loop
                # from history.last(HISTORY_WINDOW) and is NEVER rebuilt
                # per iteration, so mutating history/EpisodicMemory after turn
                # start cannot reach the model. The `messages` list IS rebuilt
                # every loop entry, so this append (then clear, inject-once) is
                # the correct landing site (no shared mutable history).
                if pending_steer:
                    messages.append(
                        {
                            "role": "user",
                            "content": "[steering from parent agent]\n"
                            + "\n".join(pending_steer),
                        }
                    )
                    pending_steer.clear()

                renderer.show_thinking(
                    f"planning iter {iteration_index + 1}/{max_iterations}"
                )
                telemetry.emit(
                    "provider.request",
                    "info",
                    data={
                        "phase": "plan",
                        "model": model,
                        "iteration_index": iteration_index,
                    },
                )
                iter_t0 = time.monotonic()
                this_iter_plan = None
                this_iter_usage = None
                this_iter_stop = "end_turn"
                accumulated_text_buffer: list[str] = []

                async for event in provider.stream(
                    messages=messages,
                    model=model,
                    response_format=Plan,
                    temperature=0.2,
                    max_tokens=cfg.max_output_tokens,
                ):
                    if isinstance(event, TextDelta):
                        # Plan-phase deltas are the structured-output JSON, not
                        # prose. Buffer for the unparsed-fallback below, but do
                        # NOT render — streaming raw {"rationale":...} leaks the
                        # schema into the chat (provider-agnostic fix; some
                        # providers emit the JSON as TextDelta by contract).
                        accumulated_text_buffer.append(event.text)
                        _working_chars += len(event.text)
                        if _update_working is not None:
                            try:
                                _update_working(0.0, _working_chars // 4)
                            except Exception:  # noqa: BLE001
                                pass
                    elif isinstance(event, ParsedPlan):
                        this_iter_plan = event.plan
                    elif isinstance(event, Usage):
                        this_iter_usage = event
                    elif isinstance(event, Done):
                        this_iter_stop = event.stop_reason
                    # ToolUseStart / ToolUseDelta / ToolUseEnd are consumed
                    # internally by the provider into ParsedPlan.

                iter_cost = this_iter_usage.cost_usd if this_iter_usage else 0.0
                iter_prompt_tokens = (
                    this_iter_usage.prompt_tokens if this_iter_usage else 0
                )
                iter_completion_tokens = (
                    this_iter_usage.completion_tokens if this_iter_usage else 0
                )
                iter_cache_creation = (
                    getattr(this_iter_usage, "cache_creation_input_tokens", 0)
                    if this_iter_usage
                    else 0
                )
                iter_cache_read = (
                    getattr(this_iter_usage, "cache_read_input_tokens", 0)
                    if this_iter_usage
                    else 0
                )

                # V18 VOPT-05: one ledger row per assembled turn. Best-effort
                # only — a ledger failure must never crash the turn.
                if session_id is not None:
                    try:
                        _saved_tokens = max(_orig_est - _packed_est, 0)
                        _append_savings_record(
                            cwd,
                            session_id,
                            {
                                "iter": iteration_index,
                                "original_tokens_est": _orig_est,
                                "packed_tokens_est": _packed_est,
                                "method": _pack_method,
                                "cache_read_tokens": iter_cache_read,
                                "saved_tokens_est": _saved_tokens,
                                "saved_usd_est": estimate_savings_usd(
                                    _saved_tokens, iter_cache_read, model
                                ),
                                "model": model,
                                "ts": datetime.now(timezone.utc).isoformat(
                                    timespec="seconds"
                                ),
                            },
                        )
                    except Exception:
                        pass

                renderer.finalize_stream(
                    role="assistant",
                    confidence=(
                        this_iter_plan.confidence if this_iter_plan else None
                    ),
                    cost_usd=iter_cost,
                    timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    # accumulated_text is the structured-output JSON, not a
                    # displayable assistant message — never surface it.
                    accumulated_text=None,
                )

                if this_iter_plan is None:
                    final_text = (
                        "".join(accumulated_text_buffer)[:1000]
                        or "(provider returned no parsed plan)"
                    )
                    this_iter_plan = Plan(
                        rationale="(unparsed)",
                        steps=[],
                        confidence=1.0,
                        final_when_done=final_text,
                    )

                telemetry.emit(
                    "provider.response",
                    "info",
                    data={
                        "phase": "plan",
                        "model": model,
                        "iteration_index": iteration_index,
                        "latency_ms": int((time.monotonic() - iter_t0) * 1000),
                        "prompt_tokens": iter_prompt_tokens,
                        "completion_tokens": iter_completion_tokens,
                        "cost_usd": iter_cost,
                        "stop_reason": this_iter_stop,
                        # T4 CACHE-07: flat additive keys, NO nested
                        # cache: {...} sub-object.
                        "cache_creation_input_tokens": iter_cache_creation,
                        "cache_read_input_tokens": iter_cache_read,
                    },
                )
                # Only surface the plan when it proposes work. A terminating
                # (stepless) plan's rationale is internal "thinking" — showing
                # it makes a plain Q&A read like a log instead of a chat; the
                # answer itself lands via show_final below.
                if this_iter_plan.steps:
                    renderer.show_plan(this_iter_plan, cost_usd=iter_cost)
                telemetry.emit(
                    "plan.parsed",
                    "info",
                    data={
                        "iteration_index": iteration_index,
                        "confidence": this_iter_plan.confidence,
                        "steps": len(this_iter_plan.steps),
                    },
                )

                if _is_done_plan(this_iter_plan):
                    # Terminating iter — confidence gate fires HERE only.
                    if this_iter_plan.confidence < confidence_threshold:
                        question = (
                            this_iter_plan.open_question
                            or "I'm not confident enough — can you clarify the task?"
                        )
                        renderer.show_clarify(question, this_iter_plan.confidence)
                        rec.end_iteration(
                            plan=this_iter_plan,
                            tool_results=[],
                            cost_usd=iter_cost,
                            prompt_tokens=iter_prompt_tokens,
                            completion_tokens=iter_completion_tokens,
                            cache_creation_input_tokens=iter_cache_creation,
                            cache_read_input_tokens=iter_cache_read,
                            exit_reason="done",
                        )
                        _emit_budget_osc(
                            tokens_used=total_prompt_tokens + total_completion_tokens + iter_prompt_tokens + iter_completion_tokens,
                            token_limit=token_budget,
                            cost_usd=total_cost_usd + iter_cost,
                            iteration=iteration_index + 1,
                            model=model,
                        )
                        _emit_context_osc({**rec._context_tracker.snapshot(), "savings": _savings_osc})
                        telemetry.emit(
                            "iteration.end",
                            "info",
                            data={
                                "iteration_index": iteration_index,
                                "cost_usd": iter_cost,
                                "prompt_tokens": iter_prompt_tokens,
                                "completion_tokens": iter_completion_tokens,
                                "exit_reason": "done",
                            },
                        )
                        telemetry.note_turn(
                            cost_usd=total_cost_usd + iter_cost,
                            outcome="clarify",
                            confidence=this_iter_plan.confidence,
                            iteration_count=iteration_index + 1,
                            exit_reason="done",
                        )
                        return TurnResult(
                            plan=this_iter_plan,
                            confidence=this_iter_plan.confidence,
                            final=question,
                            tool_results=[],
                            cost_usd=total_cost_usd + iter_cost,
                            run=None,
                        )

                    exit_reason = "done"
                    final_plan = this_iter_plan
                    rec.end_iteration(
                        plan=this_iter_plan,
                        tool_results=[],
                        cost_usd=iter_cost,
                        prompt_tokens=iter_prompt_tokens,
                        completion_tokens=iter_completion_tokens,
                        cache_creation_input_tokens=iter_cache_creation,
                        cache_read_input_tokens=iter_cache_read,
                        exit_reason="done",
                    )
                    _emit_budget_osc(
                        tokens_used=total_prompt_tokens + total_completion_tokens + iter_prompt_tokens + iter_completion_tokens,
                        token_limit=token_budget,
                        cost_usd=total_cost_usd + iter_cost,
                        iteration=iteration_index + 1,
                        model=model,
                    )
                    _emit_context_osc({**rec._context_tracker.snapshot(), "savings": _savings_osc})
                    telemetry.emit(
                        "iteration.end",
                        "info",
                        data={
                            "iteration_index": iteration_index,
                            "cost_usd": iter_cost,
                            "prompt_tokens": iter_prompt_tokens,
                            "completion_tokens": iter_completion_tokens,
                            "exit_reason": "done",
                        },
                    )
                    total_cost_usd += iter_cost
                    total_prompt_tokens += iter_prompt_tokens
                    total_completion_tokens += iter_completion_tokens
                    all_iter_records.append(rec._iterations[-1])
                    break

                # Non-terminating iter: execute the proposed steps and continue.
                results = await _run_step_loop(
                    this_iter_plan.steps,
                    tools,
                    permissions,
                    renderer,
                    recorder=rec,
                )
                tool_results_for_iter = [
                    {
                        "name": s.name,
                        "args": telemetry.redact_tool_args(dict(s.args)),
                        "result": str(r)[:4096],
                    }
                    for s, r in zip(this_iter_plan.steps, results)
                ]
                rec.end_iteration(
                    plan=this_iter_plan,
                    tool_results=tool_results_for_iter,
                    cost_usd=iter_cost,
                    prompt_tokens=iter_prompt_tokens,
                    completion_tokens=iter_completion_tokens,
                    cache_creation_input_tokens=iter_cache_creation,
                    cache_read_input_tokens=iter_cache_read,
                    exit_reason=None,
                )
                _emit_budget_osc(
                    tokens_used=total_prompt_tokens + total_completion_tokens + iter_prompt_tokens + iter_completion_tokens,
                    token_limit=token_budget,
                    cost_usd=total_cost_usd + iter_cost,
                    iteration=iteration_index + 1,
                    model=model,
                )
                _emit_context_osc({**rec._context_tracker.snapshot(), "savings": _savings_osc})
                telemetry.emit(
                    "iteration.end",
                    "info",
                    data={
                        "iteration_index": iteration_index,
                        "cost_usd": iter_cost,
                        "prompt_tokens": iter_prompt_tokens,
                        "completion_tokens": iter_completion_tokens,
                        "exit_reason": None,
                    },
                )
                total_cost_usd += iter_cost
                total_prompt_tokens += iter_prompt_tokens
                total_completion_tokens += iter_completion_tokens
                all_iter_records.append(rec._iterations[-1])

                # M13-03 D-04 steer-inbox drain (RESEARCH Pattern 3). This sits
                # in the NON-terminating branch only: the _is_done_plan branch
                # (line ~787) breaks BEFORE here, so a "done" child never
                # consumes a pending steer (D-04 / Pitfall 2). Non-blocking
                # drain of every queued guidance into pending_steer; injected
                # once on the next iteration's messages build (see above).
                if steer_inbox is not None:
                    while not steer_inbox.empty():
                        try:
                            pending_steer.append(steer_inbox.get_nowait())
                        except asyncio.QueueEmpty:
                            break

                if (
                    ctx.token_budget
                    and ctx.tokens_used >= ctx.token_budget
                ):
                    exit_reason = "budget"
                    break

                iteration_index += 1
            # End while

            if exit_reason is None:
                exit_reason = "max-iter"
        # End ContextScope async-with

        # Resolve user-facing final string per exit_reason.
        if exit_reason == "done":
            final = (final_plan.final_when_done if final_plan else "") or "(no final answer)"
        elif exit_reason == "max-iter":
            final = HALTED_MAX_ITER_FINAL
            if final_plan is None and all_iter_records:
                last_plan_dict = all_iter_records[-1].plan or {}
                # Build a synthetic Plan to keep TurnResult shape stable.
                final_plan = Plan(
                    rationale=last_plan_dict.get("rationale", "") or "(max-iter)",
                    steps=[],
                    confidence=float(last_plan_dict.get("confidence", 0.0) or 0.0),
                    final_when_done=final,
                )
        elif exit_reason == "budget":
            final = HALTED_BUDGET_FINAL
            if final_plan is None and all_iter_records:
                last_plan_dict = all_iter_records[-1].plan or {}
                final_plan = Plan(
                    rationale=last_plan_dict.get("rationale", "") or "(budget)",
                    steps=[],
                    confidence=float(last_plan_dict.get("confidence", 0.0) or 0.0),
                    final_when_done=final,
                )
        else:
            final = "(no final answer)"

        # Closing record_run + finalize.
        transcript_plan = final_plan if isinstance(final_plan, Plan) else this_iter_plan
        transcript_results = (
            [r["result"] for r in all_iter_records[-1].tool_results]
            if all_iter_records
            else []
        )
        transcript = _compose_run_transcript(
            task, transcript_plan, transcript_results, rec
        )
        semantics = await _record_run_call(provider, model, transcript)
        if semantics is not None:
            rec.absorb(semantics, transcript_plan)
        else:
            rec.goal = "(record_run failed)"
            rec.plan = (
                transcript_plan.model_dump() if transcript_plan is not None else {}
            )

        run = rec.finalize(cwd, cost_usd=total_cost_usd, exit_reason=exit_reason)
        if run.decisions:
            try:
                write_decisions_md(cwd, run, session_id or "(no-session)")
            except OSError as exc:
                import click as _click

                _click.echo(f"warning: failed to mirror decisions: {exc}", err=True)

        if history is not None:
            history.add(final, role="assistant")

        total_tokens = total_prompt_tokens + total_completion_tokens
        ctx_pct = total_tokens / token_budget if token_budget else 0.0
        renderer.status(
            model=model,
            tokens=total_tokens,
            cost_usd=total_cost_usd,
            ctx_pct=ctx_pct,
        )

        telemetry.note_turn(
            cost_usd=total_cost_usd,
            outcome="complete",
            step_count=sum(
                len((ir.plan or {}).get("steps", []) or []) for ir in all_iter_records
            ),
            tool_calls=sum(len(ir.tool_results or []) for ir in all_iter_records),
            total_tokens=total_tokens,
            iteration_count=len(all_iter_records),
            exit_reason=exit_reason,
        )

        return TurnResult(
            plan=transcript_plan if transcript_plan is not None else Plan(
                rationale="(empty)", steps=[], confidence=0.0, final_when_done=final
            ),
            confidence=(
                transcript_plan.confidence if transcript_plan is not None else 0.0
            ),
            final=final,
            tool_results=[
                r["result"] for ir in all_iter_records for r in (ir.tool_results or [])
            ],
            cost_usd=total_cost_usd,
            run=run,
        )
    except BatchInvariantError as e:
        # T2-03 / PAR-02: partition-time invariant violation. Close any
        # open iteration with exit_reason="batch-invariant", finalize the
        # recorder, surface in the TurnView, emit telemetry, then re-raise.
        open_iter = next(
            (ir for ir in reversed(rec._iterations) if not ir.ended_at), None
        )
        if open_iter is not None:
            rec.end_iteration(
                plan=this_iter_plan
                or Plan(
                    rationale="(batch-invariant)",
                    steps=[],
                    confidence=0.0,
                    final_when_done="",
                ),
                tool_results=[],
                cost_usd=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                exit_reason="batch-invariant",
            )
        try:
            renderer.stream_delta(f"\n[error: batch-invariant: {e}]\n")
            renderer.finalize_stream(
                role="system",
                confidence=None,
                cost_usd=None,
                timestamp=None,
            )
        except Exception:  # noqa: BLE001 — renderer may not be mounted
            pass
        try:
            rec.finalize(
                cwd, cost_usd=total_cost_usd, exit_reason="batch-invariant"
            )
        except Exception:  # noqa: BLE001 — never block re-raise on finalize error
            pass
        telemetry.note_turn(
            cost_usd=total_cost_usd,
            outcome="batch-invariant",
            iteration_count=len(all_iter_records),
            exit_reason="batch-invariant",
            total_tokens=total_prompt_tokens + total_completion_tokens,
        )
        raise
    except asyncio.CancelledError:
        # T1-06: interrupt handler. Close any open iteration with
        # exit_reason="interrupt", finalize the recorder, surface the
        # cancel in the TurnView, emit telemetry, then re-raise.
        # Interrupt precedence (CONTEXT.md): this except runs BEFORE the
        # post-while-loop fallthrough that would otherwise pick "max-iter",
        # so cancel at the cap iteration still records as "interrupt".
        open_iter = next(
            (ir for ir in reversed(rec._iterations) if not ir.ended_at), None
        )
        if open_iter is not None:
            rec.end_iteration(
                plan=Plan(
                    rationale="(interrupted)",
                    steps=[],
                    confidence=0.0,
                    final_when_done="",
                ),
                tool_results=[],
                cost_usd=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                exit_reason="interrupt",
            )
        try:
            renderer.stream_delta("\n[interrupted]\n")
            renderer.finalize_stream(
                role="system",
                confidence=None,
                cost_usd=None,
                timestamp=None,
            )
        except Exception:  # noqa: BLE001 — renderer may not be mounted
            pass
        try:
            rec.finalize(cwd, cost_usd=total_cost_usd, exit_reason="interrupt")
        except Exception:  # noqa: BLE001 — never block re-raise on finalize error
            pass
        telemetry.note_turn(
            cost_usd=total_cost_usd,
            outcome="interrupt",
            iteration_count=len(all_iter_records),
            exit_reason="interrupt",
            total_tokens=total_prompt_tokens + total_completion_tokens,
        )
        raise


def _summarize(text: str, limit: int = 80) -> str:
    first = text.splitlines()[0] if text else ""
    if len(first) > limit:
        return first[: limit - 1] + "…"
    return first or f"({len(text)}B)"


async def _invoke_step_with_gate(
    step,
    tools: dict[str, ToolEntry],
    gate: PermissionGate,
    renderer: Renderer,
    recorder: RunRecorder | None,
) -> str:
    """Resolve, gate-check, and invoke a single step. Returns result string.

    Lifted from the previous serial `_run_step_loop` body verbatim. Catches
    `Exception` (not `BaseException`) so `asyncio.CancelledError` propagates
    to the gather/scheduler for outer-cancel discipline (D-06/D-07).

    R3 ToolCards: `call_id` is minted HERE (Voss tool calls are not
    provider-native — the harness executes plan.steps itself, and the
    ToolCall schema is part of the LLM structured-output contract, so it
    cannot carry an id). The same id is threaded through the pending and
    settled `show_tool_call` calls so the TUI mutates one card in place;
    read batches run concurrently, so this id is the only safe pairing.
    Settled-only paths (unknown tool, denied) also carry a minted id.
    """
    call_id = uuid.uuid4().hex[:12]
    entry = tools.get(step.name)
    if entry is None:
        text = f"<error: unknown tool {step.name!r}>"
        renderer.show_tool_call(
            call_id, step.name, step.args, "<unknown tool>", "error", output=text
        )
        telemetry.emit(
            "tool.result",
            "warn",
            data={
                "tool": step.name,
                "ok": False,
                "error": "unknown_tool",
                "args": telemetry.redact_tool_args(dict(step.args)),
            },
        )
        if recorder is not None:
            recorder.observe(step.name, step.args, "<unknown tool>", ok=False)
        return text
    # A bridge-injected prompt_fn (server/TUI permission bridge) blocks on a
    # Future resolved by the event loop — checking on-loop deadlocks until
    # the 300s timeout (E3-04). Offload those gates to a thread; plain gates
    # (auto_yes, interactive TTY) keep the existing sync path.
    if gate.prompt_fn is not None:
        allowed, why = await asyncio.to_thread(
            gate.check,
            step.name,
            step.args,
            is_mutating=entry.is_mutating,
            is_network=entry.is_network,
        )
    else:
        allowed, why = gate.check(
            step.name,
            step.args,
            is_mutating=entry.is_mutating,
            is_network=entry.is_network,
        )
    # V12 VSAFE-05: persist factory-fallback evidence for every strict-procedure
    # route (confirmed irreversible that proceeds, or routed/denied dangerous op).
    if recorder is not None and getattr(gate, "safety_policy", None) is not None:
        from .safety import classify as _safety_classify

        _cls = _safety_classify(
            gate.safety_policy,
            step.name,
            step.args,
            actor=getattr(gate, "safety_actor", None),
        )
        if _cls.matched:
            recorder.observe_factory_fallback(
                step.name,
                label=_cls.label,
                classes=list(_cls.classes),
                trigger_rule=_cls.trigger_rule_id,
                runbook=_cls.runbook,
                pipeline=_cls.pipeline,
                actor_role=_cls.actor_role,
                actor_model_tier=_cls.actor_model_tier,
                confirmation_required=_cls.requires_confirmation,
                confirmed=bool(allowed and _cls.requires_confirmation),
                outcome=("allowed" if allowed else "denied"),
                args=step.args,
            )
    if not allowed:
        text = f"<denied: {why}>"
        renderer.show_tool_call(call_id, step.name, step.args, text, "error", output=text)
        telemetry.emit(
            "tool.result",
            "info",
            data={
                "tool": step.name,
                "ok": False,
                "error": "denied",
                "why": why,
                "args": telemetry.redact_tool_args(dict(step.args)),
            },
        )
        if recorder is not None:
            recorder.observe(step.name, step.args, text, ok=False)
            recorder.observe_capability(
                step.name,
                getattr(entry, "group", "shell"),
                step.args,
                is_mutating=entry.is_mutating,
                is_network=entry.is_network,
                audit_behavior=getattr(entry, "audit_behavior", "full"),
                ok=False,
            )
        return text
    telemetry.emit(
        "tool.call",
        "info",
        data={
            "tool": step.name,
            "args": telemetry.redact_tool_args(dict(step.args)),
        },
    )
    renderer.show_tool_call(call_id, step.name, step.args, "running…", "pending")
    _tool_t0 = time.monotonic()
    try:
        res = await entry.invoke(**step.args)
        text = str(res)
    except Exception as e:  # noqa: BLE001 — catch all to surface, not crash
        text = f"<error: {e}>"
        renderer.show_tool_call(call_id, step.name, step.args, text, "error", output=text)
        telemetry.emit(
            "tool.result",
            "warn",
            data={
                "tool": step.name,
                "ok": False,
                "latency_ms": int((time.monotonic() - _tool_t0) * 1000),
                "error": str(e)[:300],
            },
        )
        if recorder is not None:
            recorder.observe(step.name, step.args, text, ok=False)
            recorder.observe_capability(
                step.name,
                getattr(entry, "group", "shell"),
                step.args,
                is_mutating=entry.is_mutating,
                is_network=entry.is_network,
                audit_behavior=getattr(entry, "audit_behavior", "full"),
                ok=False,
            )
        return text
    renderer.show_tool_call(
        call_id, step.name, step.args, _summarize(text), "ok", output=text
    )
    telemetry.emit(
        "tool.result",
        "info",
        data={
            "tool": step.name,
            "ok": True,
            "latency_ms": int((time.monotonic() - _tool_t0) * 1000),
            "summary": _summarize(text, 120),
        },
    )
    if recorder is not None:
        recorder.observe(step.name, step.args, text, ok=True)
        recorder.observe_capability(
            step.name,
            getattr(entry, "group", "shell"),
            step.args,
            is_mutating=entry.is_mutating,
            is_network=entry.is_network,
            audit_behavior=getattr(entry, "audit_behavior", "full"),
            ok=True,
        )
    return text


def _result_is_failure(text: str) -> bool:
    return text.startswith("<error:") or text.startswith("<denied:")


async def _dispatch_singleton(
    *,
    step,
    step_index: int,
    tools: dict[str, ToolEntry],
    gate: PermissionGate,
    renderer: Renderer,
    recorder: RunRecorder | None,
    results: list,
) -> None:
    """Run one step serially. NO batch.start/end. NO recorder.begin_batch."""
    results[step_index] = await _invoke_step_with_gate(
        step, tools, gate, renderer, recorder
    )


async def _dispatch_read_batch(
    *,
    steps: list,
    step_indices: list[int],
    tools: dict[str, ToolEntry],
    gate: PermissionGate,
    renderer: Renderer,
    recorder: RunRecorder | None,
    results: list,
    cap: int,
    batch_index: int | None,
) -> None:
    """Run a batch of (presumed read-only) steps under a per-batch semaphore.

    `batch_index is None` means this dispatch is a singleton wrapper:
    no batch.start/end events, no recorder.begin_batch call, and the
    multi-step invariant is NOT enforced (single mutating step is allowed
    to reach the tool through this path).

    `batch_index is not None` AND len(steps) > 1 means a true parallel
    batch: enforce the partition-time invariant (every step must be a
    known, non-mutating tool) and emit batch.start/end + recorder
    begin_batch/end_batch wrappers around the gather.
    """
    if batch_index is not None and len(steps) > 1:
        for step in steps:
            entry = tools.get(step.name)
            if entry is None or entry.is_mutating:
                raise BatchInvariantError(
                    f"step {step.name!r} in multi-step batch is mutating or "
                    f"unregistered (batch_index={batch_index})"
                )

    sem = asyncio.Semaphore(cap)
    t0 = time.monotonic()

    if batch_index is not None:
        telemetry.emit(
            "batch.start",
            "info",
            data={
                "batch_index": batch_index,
                "step_indices": list(step_indices),
                "parallel_count": len(steps),
            },
        )
        if recorder is not None:
            recorder.begin_batch(
                batch_index=batch_index, step_indices=list(step_indices)
            )

    async def _run_one(slot: int, step) -> None:
        async with sem:
            results[slot] = await _invoke_step_with_gate(
                step, tools, gate, renderer, recorder
            )

    await asyncio.gather(
        *(_run_one(slot, step) for slot, step in zip(step_indices, steps)),
        return_exceptions=True,
    )

    if batch_index is not None:
        wall_clock_ms = int((time.monotonic() - t0) * 1000)
        ok_count = sum(
            1
            for slot in step_indices
            if isinstance(results[slot], str) and not _result_is_failure(results[slot])
        )
        err_count = len(steps) - ok_count
        telemetry.emit(
            "batch.end",
            "info",
            data={
                "batch_index": batch_index,
                "wall_clock_ms": wall_clock_ms,
                "ok_count": ok_count,
                "err_count": err_count,
            },
        )
        if recorder is not None:
            recorder.end_batch(
                wall_clock_ms=wall_clock_ms,
                ok_count=ok_count,
                err_count=err_count,
            )


async def _run_step_loop(
    plan_steps,
    tools: dict[str, ToolEntry],
    permissions: PermissionGate | None,
    renderer: Renderer,
    *,
    recorder: RunRecorder | None = None,
) -> list[str]:
    """T2-03 PAR-01: one-pass author-order partition scheduler.

    Walks plan_steps left-to-right grouping consecutive non-mutating
    (and registered) steps into a parallel batch; mutating or unknown
    steps flush as singletons. Read batches dispatch through
    asyncio.gather under asyncio.Semaphore(get_config().max_parallel_reads).
    Author order is preserved in the returned results list. The semaphore
    is per-batch (created at batch entry, GC'd after gather returns) per
    CONTEXT.md D-17.
    """
    gate = permissions or PermissionGate(auto_yes=True)
    n = len(plan_steps)
    results: list[str | None] = [None] * n
    if n == 0:
        return []
    cap = get_config().max_parallel_reads
    batch_index = 0
    i = 0
    while i < n:
        j = i
        while j < n:
            entry = tools.get(plan_steps[j].name)
            if entry is None or entry.is_mutating:
                break
            j += 1
        if j > i:
            multi_step = (j - i) > 1
            await _dispatch_read_batch(
                steps=list(plan_steps[i:j]),
                step_indices=list(range(i, j)),
                tools=tools,
                gate=gate,
                renderer=renderer,
                recorder=recorder,
                results=results,
                cap=cap,
                batch_index=batch_index if multi_step else None,
            )
            if multi_step:
                batch_index += 1
            i = j
        else:
            await _dispatch_singleton(
                step=plan_steps[i],
                step_index=i,
                tools=tools,
                gate=gate,
                renderer=renderer,
                recorder=recorder,
                results=results,
            )
            i += 1
    return [r if r is not None else "<error: missing result>" for r in results]


def _make_turn_result(
    plan: Plan,
    confidence: float,
    final: str,
    tool_results: list[str],
    cost_usd: float = 0.0,
) -> TurnResult:
    return TurnResult(
        plan=plan,
        confidence=confidence,
        final=final,
        tool_results=tool_results,
        cost_usd=cost_usd,
    )


def _compose_run_transcript(task: str, plan, results: list[str], rec) -> str:
    parts = [f"Task: {task}", f"Plan rationale: {plan.rationale}"]
    for i, step in enumerate(plan.steps):
        result_snippet = (results[i] if i < len(results) else "")[:200]
        parts.append(f"Step {i}: {step.name}({step.args}) -> {result_snippet}")
    if rec.inspected:
        parts.append(f"Inspected: {', '.join(rec.inspected[:20])}")
    if rec.changed:
        parts.append(f"Changed: {', '.join(rec.changed[:20])}")
    text = "\n".join(parts)
    return text[:3000]


async def _record_run_call(provider, model: str, transcript: str):
    """Privileged closing call. Returns RunSemantics or None on any failure.

    Never raises — Pitfall 1 mitigation. Turn must continue if this fails.
    """
    telemetry.emit(
        "provider.request",
        "info",
        data={"phase": "record_run", "model": model},
    )
    _rr_t0 = time.monotonic()
    try:
        resp = await provider.complete(
            messages=[
                {"role": "system", "content": RECORD_RUN_SYSTEM},
                {"role": "user", "content": transcript},
            ],
            model=model,
            response_format=RunSemantics,
            temperature=0.0,
            max_tokens=800,
        )
    except Exception:  # noqa: BLE001 — sentinel-return is the contract
        telemetry.emit(
            "provider.response",
            "warn",
            data={
                "phase": "record_run",
                "model": model,
                "latency_ms": int((time.monotonic() - _rr_t0) * 1000),
                "ok": False,
            },
        )
        return None
    telemetry.emit(
        "provider.response",
        "info",
        data={
            "phase": "record_run",
            "model": resp.model,
            "latency_ms": int((time.monotonic() - _rr_t0) * 1000),
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
            "cost_usd": resp.cost_usd,
            "parsed_ok": resp.parsed is not None,
        },
    )
    if resp.parsed is None:
        return None
    return resp.parsed
