"""Per-turn mechanical observation collaborator (COG-08 D-15).

Wraps run_turn's tool dispatch loop to capture inspected/changed/validation/
failures without changing the agent surface. Semantic fields (goal/decisions/
risks/follow_ups/assumptions/avoided) are populated by a separate privileged
`record_run` closing call dispatched in M2-03.
"""
from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import json
import sys

from voss.template_render import render_package_template

from .session import EXIT_REASONS, BatchRecord, IterationRecord, RunRecord


@dataclass
class FileContextState:
    """Per-file context window state for F4 heatmap visualization."""
    path: str
    tokens: int
    state: str = "full"  # "full" | "dropped"
    pinned: bool = False


class ContextTracker:
    """Accumulates per-file context state for OSC emission (F4 D-25)."""

    def __init__(self) -> None:
        self.files: dict[str, FileContextState] = {}
        self.pinned: set[str] = set()
        self.prev_prompt_tokens: int = 0

    def track_file(self, path: str, content: str) -> None:
        """Record a file read into context with token estimate (len//4)."""
        tokens = max(len(content) // 4, 1)
        self.files[path] = FileContextState(
            path=path, tokens=tokens, state="full",
            pinned=path in self.pinned,
        )

    def detect_drops(self, prompt_tokens: int) -> None:
        """Mark oldest non-pinned files as dropped when prompt_tokens decreases."""
        if self.prev_prompt_tokens > 0 and prompt_tokens < self.prev_prompt_tokens:
            deficit = self.prev_prompt_tokens - prompt_tokens
            accounted = 0
            # Sort by insertion order (dict preserves it), oldest first
            for fcs in self.files.values():
                if accounted >= deficit:
                    break
                if fcs.pinned or fcs.state == "dropped":
                    continue
                fcs.state = "dropped"
                accounted += fcs.tokens
        self.prev_prompt_tokens = prompt_tokens

    def load_pins(self, pin_file: Path) -> None:
        """Read pin commands from .voss/context-pins.json (F4 D-20, D-22)."""
        if not pin_file.is_file():
            return
        try:
            data = json.loads(pin_file.read_text())
        except (json.JSONDecodeError, OSError):
            return
        raw_pins = data.get("pinned", [])
        if not isinstance(raw_pins, list):
            return
        # D-22: only accept paths already in tracked files
        self.pinned = {p for p in raw_pins if isinstance(p, str) and p in self.files}
        for path, fcs in self.files.items():
            fcs.pinned = path in self.pinned

    def snapshot(self) -> dict:
        """Return D-25 payload dict. Files sorted by tokens desc, capped at 200."""
        sorted_files = sorted(self.files.values(), key=lambda f: f.tokens, reverse=True)
        capped = sorted_files[:200]
        total = sum(f.tokens for f in self.files.values())
        return {
            "system_tokens": 0,
            "conversation_tokens": 0,
            "total_tokens": total,
            "token_limit": None,
            "files": [
                {"path": f.path, "tokens": f.tokens, "state": f.state, "pinned": f.pinned}
                for f in capped
            ],
        }


def _emit_budget_osc(
    *,
    tokens_used: int,
    token_limit: int | None,
    cost_usd: float,
    iteration: int,
    model: str,
) -> None:
    """Write an OSC 1337 voss-budget= sequence to stdout (D-02, D-04).

    The Rust PTY reader (reader.rs extract_voss_osc) strips this sequence
    before bytes reach xterm, so the terminal never renders it.

    Only meaningful to a PTY/terminal consumer; suppressed when stdout is not
    a TTY (--plain, piped, CI) so it never pollutes scriptable output.
    """
    if not sys.stdout.isatty():
        return
    payload = json.dumps(
        {
            "tokens_used": tokens_used,
            "token_limit": token_limit,
            "cost_usd": cost_usd,
            "iteration": iteration,
            "model": model,
        },
        separators=(",", ":"),
    )
    sys.stdout.write(f"\x1b]1337;voss-budget={payload}\x07")
    sys.stdout.flush()


def _emit_context_osc(payload: dict) -> None:
    """Write an OSC 1337 voss-context= sequence to stdout (F4 D-23, D-24).

    Stripped by reader.rs extract_voss_osc before bytes reach xterm.
    Suppressed on a non-TTY stdout (--plain, piped, CI).
    """
    if not sys.stdout.isatty():
        return
    json_str = json.dumps(payload, separators=(",", ":"))
    sys.stdout.write(f"\x1b]1337;voss-context={json_str}\x07")
    sys.stdout.flush()


def _append_savings_record(cwd, session_id: str, record: dict) -> None:
    """V18 VOPT-05: append one token-savings row to the session ledger.

    Ledger path: `.voss/sessions/<id>/token-savings.jsonl` — a SUBDIRECTORY
    of the sessions dir, not the flat `<id>.json` session-file convention
    (RESEARCH A7). Clamps packed <= original and saved >= 0 BEFORE the
    write so phantom savings are impossible by construction (Pitfall 4).
    """
    from .session import _sessions_dir

    row = dict(record)
    original = int(row.get("original_tokens_est", 0))
    packed = min(int(row.get("packed_tokens_est", 0)), original)
    row["packed_tokens_est"] = packed
    row["saved_tokens_est"] = max(original - packed, 0)
    path = _sessions_dir(Path(cwd)) / str(session_id) / "token-savings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def estimate_savings_usd(
    saved_tokens: int, cache_read_tokens: int, model: str
) -> float | None:
    """V18 D-04: cache-netted dollar estimate of packing savings.

    Cache reads already bill at the reduced cache_read rate, so the naive
    saved_tokens * input_rate figure is reduced by the cache delta
    (Pitfall 3 — never inflated). Unknown model -> None (ledger records
    null; no fabricated figure). Never negative, never raises.
    """
    try:
        import litellm
    except Exception:  # pragma: no cover - litellm always in venv
        return None
    try:
        entry = litellm.model_cost.get(model) or litellm.model_cost.get(
            f"anthropic.{model}"
        )
    except Exception:
        return None
    if not entry:
        return None
    input_rate = entry.get("input_cost_per_token", 0) or 0
    cache_read_rate = entry.get("cache_read_input_token_cost", 0) or 0
    gross = saved_tokens * input_rate
    cache_reduction = cache_read_tokens * (input_rate - cache_read_rate)
    return max(gross - cache_reduction, 0.0)


INSPECT_TOOLS = {"fs_read", "fs_glob", "fs_grep"}
CHANGE_TOOLS = {"fs_write", "fs_edit"}
VALIDATE_TOOLS = {"shell_run", "voss_check"}
SKILL_EVENTS = {"skill_install", "skill_remove", "skill_update"}
FAILURE_TRUNC = 200
SUMMARY_TRUNC = 160


@dataclass
class RunRecorder:
    id: str
    started_at: str
    inspected: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    validation: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    cost_usd: float = 0.0
    diff_summary: str = ""
    # semantic fields (populated by absorb() in M2-03)
    goal: str = ""
    plan: Optional[dict] = None
    avoided: list[dict] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    # M15-05: skill install/run/deny audit events
    skill_events: list[dict] = field(default_factory=list)
    scope_denials: list[dict] = field(default_factory=list)
    # V1-04 CAP-08: one audit row per capability invocation (all outcomes).
    capability_invocations: list[dict] = field(default_factory=list)
    # V12 VSAFE-05: one row per safety factory-fallback route (additive).
    factory_fallbacks: list[dict] = field(default_factory=list)
    instructions_hash: str = ""
    instructions_files: list[str] = field(default_factory=list)
    # T1-01: per-iteration sub-records appended via begin_iteration /
    # end_iteration; forwarded to RunRecord.iterations on finalize.
    _iterations: list[IterationRecord] = field(default_factory=list)
    # F4: per-file context tracking for heatmap visualization
    _context_tracker: ContextTracker = field(default_factory=ContextTracker)

    @classmethod
    def start(cls) -> "RunRecorder":
        return cls(
            id=uuid.uuid4().hex[:12],
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def observe(self, tool_name: str, args: dict, result: Any, *, ok: bool) -> None:
        if not ok:
            self.failures.append(
                {"tool": tool_name, "error": str(result)[:FAILURE_TRUNC]}
            )
            return
        if tool_name in INSPECT_TOOLS:
            path = args.get("path") or args.get("pattern") or ""
            if path:
                self.inspected.append(path)
            # F4: track file content for context heatmap
            if tool_name == "fs_read" and path and isinstance(result, str) and result:
                self._context_tracker.track_file(path, result)
        elif tool_name in CHANGE_TOOLS:
            path = args.get("path", "")
            if path:
                self.changed.append(path)
        elif tool_name in VALIDATE_TOOLS:
            text = str(result) if result is not None else ""
            exit_code = _parse_exit(text)
            summary = text.splitlines()[0] if text else ""
            cmd = args.get("cmd") or f"{tool_name}({args})"
            self.validation.append(
                {
                    "cmd": cmd,
                    "exit": exit_code,
                    "summary": summary[:SUMMARY_TRUNC],
                }
            )

    def observe_skill_event(
        self,
        action: str,
        skill_id: str,
        source: str,
        *,
        ok: bool,
        error: str = "",
    ) -> None:
        """Record a skill install/remove/update/run event."""
        self.skill_events.append({
            "action": action,
            "skill_id": skill_id,
            "source": source,
            "ok": ok,
            "error": error[:FAILURE_TRUNC],
        })

    def observe_scope_denial(
        self, skill_id: str, tool: str, reason: str
    ) -> None:
        """Record a scope-limited gate denial for a third-party skill."""
        self.scope_denials.append({
            "skill_id": skill_id,
            "tool": tool,
            "reason": reason,
        })

    def observe_capability(
        self,
        name: str,
        group: str,
        args: dict,
        *,
        is_mutating: bool,
        is_network: bool,
        audit_behavior: str = "full",
        ok: bool = True,
    ) -> None:
        """V1-04 CAP-08: structured audit row for a capability invocation.

        Args are shaped by `audit_behavior`: `full` and `redact_args` both pass
        through `telemetry.redact_tool_args` (we never store raw args — `full`
        keeps the full *set* of args, redacted in value, not the raw secrets);
        `metadata_only` omits args entirely. Never raises on malformed args.
        """
        from . import telemetry

        event: dict = {
            "name": name,
            "group": group,
            "is_mutating": is_mutating,
            "is_network": is_network,
            "ok": ok,
        }
        if audit_behavior == "metadata_only":
            event["args"] = None
        else:
            try:
                event["args"] = telemetry.redact_tool_args(dict(args))
            except Exception:  # noqa: BLE001 — audit must never crash the run
                event["args"] = None
        self.capability_invocations.append(event)

    def observe_factory_fallback(
        self,
        name: str,
        *,
        label: str,
        classes: Any = (),
        trigger_rule: Optional[str] = None,
        runbook: Optional[str] = None,
        pipeline: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor_model_tier: Optional[str] = None,
        confirmation_required: bool = False,
        confirmed: bool = False,
        outcome: str = "denied",
        args: Optional[dict] = None,
    ) -> None:
        """V12 VSAFE-05: durable evidence for one safety factory-fallback route.

        Records classification, trigger rule, runbook/pipeline, actor role/tier,
        confirmation flags, and outcome. Args are redacted via the same
        telemetry path as capability rows — raw secrets are never stored. Never
        raises (audit must not crash the run).
        """
        from . import telemetry

        event: dict = {
            "name": name,
            "label": label,
            "classes": list(classes) if classes else [],
            "trigger_rule": trigger_rule,
            "runbook": runbook,
            "pipeline": pipeline,
            "actor_role": actor_role,
            "actor_model_tier": actor_model_tier,
            "confirmation_required": confirmation_required,
            "confirmed": confirmed,
            "outcome": outcome,
        }
        if args is None:
            event["args"] = None
        else:
            try:
                event["args"] = telemetry.redact_tool_args(dict(args))
            except Exception:  # noqa: BLE001 — audit must never crash the run
                event["args"] = None
        self.factory_fallbacks.append(event)

    def absorb(self, semantics: Any, plan: Any = None) -> None:
        """Copy semantic fields from a duck-typed semantics object.

        Tolerates SimpleNamespace stubs and pydantic BaseModel instances via
        getattr. `semantics is None` is a no-op (mechanical-only persistence).
        """
        if semantics is None:
            if plan is not None:
                self.plan = plan.model_dump() if hasattr(plan, "model_dump") else plan
            return
        self.goal = getattr(semantics, "goal", self.goal)
        self.avoided = getattr(semantics, "avoided", self.avoided)
        self.assumptions = getattr(semantics, "assumptions", self.assumptions)
        self.decisions = getattr(semantics, "decisions", self.decisions)
        self.risks = getattr(semantics, "risks", self.risks)
        self.follow_ups = getattr(semantics, "follow_ups", self.follow_ups)
        if plan is not None:
            self.plan = plan.model_dump() if hasattr(plan, "model_dump") else plan

    def begin_iteration(self) -> IterationRecord:
        """Open a new iteration sub-record (T1-01).

        Appends an IterationRecord with index = current count, started_at set
        to UTC ISO now, and other fields at defaults. Returns the record so
        callers can attach fields incrementally before end_iteration.
        """
        record = IterationRecord(
            index=len(self._iterations),
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._iterations.append(record)
        return record

    def end_iteration(
        self,
        *,
        plan: Any,
        tool_results: list[dict],
        cost_usd: float,
        prompt_tokens: int,
        completion_tokens: int,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        exit_reason: Optional[str] = None,
    ) -> None:
        """Close the most recently opened iteration (T1-01).

        Writes the supplied fields onto the most recent open iteration (the
        one with empty ended_at). Validates exit_reason against EXIT_REASONS
        when not None — raises ValueError on mismatch.
        """
        if exit_reason is not None and exit_reason not in EXIT_REASONS:
            raise ValueError(
                f"invalid exit_reason {exit_reason!r}; "
                f"must be one of {sorted(EXIT_REASONS)}"
            )
        target: Optional[IterationRecord] = None
        for rec in reversed(self._iterations):
            if not rec.ended_at:
                target = rec
                break
        if target is None:
            raise RuntimeError("end_iteration called without an open iteration")
        target.plan = plan.model_dump() if hasattr(plan, "model_dump") else plan
        target.tool_results = list(tool_results)
        target.cost_usd = cost_usd
        target.prompt_tokens = prompt_tokens
        target.completion_tokens = completion_tokens
        target.cache_creation_input_tokens = cache_creation_input_tokens
        target.cache_read_input_tokens = cache_read_input_tokens
        target.exit_reason = exit_reason
        target.ended_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        # F4: update drop detection state
        self._context_tracker.detect_drops(prompt_tokens)

    def begin_batch(
        self, *, batch_index: int, step_indices: list[int]
    ) -> BatchRecord:
        """Append a new BatchRecord onto the current iteration (T2-01).

        Must be called inside an iteration scope. The caller supplies
        batch_index; the recorder is a passive append site. Returns the
        appended BatchRecord so callers may hold a reference, though the
        normal flow patches via end_batch.
        """
        if not self._iterations:
            raise RuntimeError("begin_batch called outside an iteration scope")
        br = BatchRecord(
            batch_index=batch_index,
            step_indices=list(step_indices),  # defensive copy
            parallel_count=len(step_indices),
        )
        self._iterations[-1].batches.append(br)
        return br

    def end_batch(
        self, *, wall_clock_ms: int, ok_count: int, err_count: int
    ) -> None:
        """Patch the trailing BatchRecord on the current iteration (T2-01).

        Pure mutation of the trailing batch; does NOT append a new record.
        Caller (scheduler in T2-03) computes wall-clock + ok/err totals
        after asyncio.gather completes.
        """
        if not self._iterations or not self._iterations[-1].batches:
            raise RuntimeError("end_batch called without a matching begin_batch")
        br = self._iterations[-1].batches[-1]
        br.wall_clock_ms = wall_clock_ms
        br.ok_count = ok_count
        br.err_count = err_count

    def finalize(
        self,
        cwd: Path,
        cost_usd: float,
        *,
        exit_reason: Optional[str] = None,
    ) -> RunRecord:
        self.cost_usd = cost_usd
        self.diff_summary = _git_diff_stat(cwd)
        total_prompt = sum(it.prompt_tokens for it in self._iterations)
        total_completion = sum(it.completion_tokens for it in self._iterations)
        return RunRecord(
            id=self.id,
            started_at=self.started_at,
            ended_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            goal=self.goal,
            plan=self.plan,
            inspected=list(self.inspected),
            changed=list(self.changed),
            avoided=list(self.avoided),
            assumptions=list(self.assumptions),
            decisions=list(self.decisions),
            risks=list(self.risks),
            validation=list(self.validation),
            failures=list(self.failures),
            diff_summary=self.diff_summary,
            follow_ups=list(self.follow_ups),
            cost_usd=self.cost_usd,
            iterations=list(self._iterations),
            iteration_count=len(self._iterations),
            exit_reason=exit_reason,
            iteration_total_prompt_tokens=total_prompt,
            iteration_total_completion_tokens=total_completion,
            skill_events=list(self.skill_events),
            scope_denials=list(self.scope_denials),
            capability_invocations=list(self.capability_invocations),
            factory_fallbacks=list(self.factory_fallbacks),
            instructions_hash=self.instructions_hash,
            instructions_files=list(self.instructions_files),
        )


def _parse_exit(result: str) -> int:
    """Parse `[exit N]` prefix from shell_run result. Returns 0 on failure."""
    if not result.startswith("[exit "):
        return 0
    close = result.find("]")
    if close < 0:
        return 0
    try:
        return int(result[6:close])
    except ValueError:
        return 0


def write_decisions_md(cwd: Path, run, session_id: str) -> list[Path]:
    """Mirror each decision to .voss/decisions/YYYY-MM-DD-<slug>.md (D-08, COG-06)."""
    from .cognition import reserve_filename, slug

    if not run.decisions:
        return []
    decisions_dir = cwd / ".voss" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for d in run.decisions:
        title = d.get("title") or "untitled"
        body = d.get("body", "")
        try:
            conf = float(d.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        path = reserve_filename(decisions_dir, slug(title))
        id_str = path.stem
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        content = render_package_template(
            "voss",
            "templates/recorder/decision.md.jinja",
            {
                "id": id_str,
                "session_id": session_id,
                "confidence": f"{conf:.2f}",
                "created_at": created_at,
                "title": title,
                "body": body,
            },
        )
        path.write_text(content)
        paths.append(path)
    return paths


def _git_diff_stat(cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if out.returncode != 0:
        return ""
    return out.stdout[:4096]
