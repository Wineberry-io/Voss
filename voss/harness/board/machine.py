"""Board state machine: Card, Board, WIP enforcement, transition-delta emission.

Implements OBRD-01 (card == session-tree node), OBRD-02 (one board per team),
OBRD-03 (6 columns + WIP), OBRD-06 (risk-tier thresholds from single source).

Gate-predicate evaluation is O3-03. This wave enforces:
  - Unknown-column rejection (BoardGateError)
  - Per-column WIP cap (BoardWIPError)
  - Transition-delta emission on every move attempt (passed or refused)
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Optional

from voss.harness.session_tree import (
    SessionTreeManager,
    _write_node_file,
    finalize_node,
)
from .tick import _tick_loop
from voss.harness.team import BoardSpec, TeamCeiling, TeamConfig, TeamRoleScope
from voss.ast_nodes import BoardGate, DictLit, IntLit, FloatLit, StringLit

from .errors import BoardGateError, BoardWIPError
from .gates import (
    Gates,
    GateContext,
    a_verification_passes,
    b_passes,
    eval_meets_threshold,
    human_approved,
    scope_clean,
)
from .verdict import Reviewer, ReviewerVerdict
from .review_persistence import _write_review_sidecar


# ---------------------------------------------------------------------------
# Type aliases + constants
# ---------------------------------------------------------------------------

Column = Literal[
    "Backlog", "Planned", "InProgress", "InReview", "Blocked", "Done"
]
RiskTier = Literal["low", "med", "high", "critical"]

_COLUMNS: tuple[str, ...] = (
    "Backlog", "Planned", "InProgress", "InReview", "Blocked", "Done",
)
_TERMINAL_COLUMNS: frozenset[str] = frozenset({"Done", "Blocked"})

# SPEC L116 SINGLE SOURCE OF TRUTH — do not duplicate elsewhere.
_DEFAULT_RISK_THRESHOLDS: dict[str, float] = {
    "low": 0.60,
    "med": 0.80,
    "high": 0.95,
    # V20 VRES-04: confidence threshold only — Done additionally requires an
    # explicit human approval record (human_approved gate predicate).
    "critical": 0.99,
}

_DEFAULT_WIP: dict[str, Optional[int]] = {
    "Backlog": None,
    "Planned": None,
    "InProgress": 3,
    "InReview": 2,
    "Blocked": None,
    "Done": None,
}
_DEFAULT_RETRY_CEILING = 3
_DEFAULT_CARD_DEADLINE_S = 1800.0  # 30 min
_DEFAULT_TICK_INTERVAL_S = 1.0


# ---------------------------------------------------------------------------
# Card (frozen value-object)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Card:
    """A board card mapped 1:1 to a SessionTreeNode (OBRD-01).

    Immutable — mutated via `dataclasses.replace` so EM cannot widen
    `scope` by direct attribute assignment (cage invariant).
    """
    node_id: str
    column: Column
    risk_tier: RiskTier
    retry_count: int
    deadline: float
    scope: Optional[TeamRoleScope] = None
    artifact: Optional[object] = None
    eval_threshold: float = 1.0
    # V5 additions — additive, back-compat defaults (VBOARD-03):
    idea: str = ""
    role: str = ""
    acceptance_criteria: str = ""
    verification_requirement: str = ""


def card_status(card: "Card") -> str:
    """Status derives from current column (VBOARD-03). Not a stored field."""
    return card.column


# ---------------------------------------------------------------------------
# V20 VRES-04: human approval records for critical-tier cards
# ---------------------------------------------------------------------------

def _human_approval_path(cwd: Path, root_id: str, card_id: str) -> Path:
    return cwd / ".voss" / "sessions" / root_id / "approvals" / f"{card_id}.json"


def write_human_approval(
    cwd: Path,
    root_id: str,
    card_id: str,
    *,
    decision: str,
    note: str = "",
) -> Path:
    """Record an operator approve/reject for a critical-tier card.

    Governance sidecar alongside the run (mirrors _write_signoff_ack's
    mkdir+write+chmod pattern in harness/cli.py) — never a mutation of node
    JSON. This record is the ONLY thing that can clear the 'human' Done
    clause; no agent verdict writes it.
    """
    if decision not in ("approved", "rejected"):
        raise ValueError(f"decision must be approved|rejected, got {decision!r}")
    path = _human_approval_path(cwd, root_id, card_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "card_id": card_id,
        "decision": decision,
        "note": note,
    }, indent=2))
    path.chmod(0o600)
    return path


def read_human_decision(cwd: Path, root_id: str, card_id: str) -> Optional[str]:
    """Best-effort read of the approval sidecar: 'approved' | 'rejected' | None."""
    try:
        data = json.loads(_human_approval_path(cwd, root_id, card_id).read_text())
    except (OSError, ValueError):
        return None
    decision = data.get("decision") if isinstance(data, dict) else None
    return decision if decision in ("approved", "rejected") else None


def card_budget(node_envelope: dict) -> tuple[int, int]:
    """Returns (spent, limit) from a persisted node envelope (VBOARD-03)."""
    return node_envelope.get("spent", 0), node_envelope.get("limit", 0)


# ---------------------------------------------------------------------------
# _BoardConfig + adapter
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _BoardConfig:
    """Parsed board configuration — private, produced by _read_board_spec."""
    wip: dict
    p_overrides: dict
    retry_ceiling: int
    card_deadline_s: float
    tick_interval_s: float
    gates: tuple


def _read_board_spec(spec: BoardSpec | None) -> _BoardConfig:
    """Adapt O2's opaque BoardSpec.raw_items into a typed _BoardConfig.

    Single localized consumer of raw_items — per O3-RESEARCH §9. Defensive:
    wrong types fall back to defaults rather than raising.
    """
    wip = dict(_DEFAULT_WIP)
    p_overrides: dict[str, float] = {}
    retry_ceiling = _DEFAULT_RETRY_CEILING
    card_deadline_s = _DEFAULT_CARD_DEADLINE_S
    tick_interval_s = _DEFAULT_TICK_INTERVAL_S
    gates: list[BoardGate] = []

    if spec is None:
        return _BoardConfig(
            wip=wip, p_overrides=p_overrides, retry_ceiling=retry_ceiling,
            card_deadline_s=card_deadline_s, tick_interval_s=tick_interval_s,
            gates=(),
        )

    for item in spec.raw_items:
        if isinstance(item, BoardGate):
            gates.append(item)
            continue
        if isinstance(item, tuple) and len(item) == 2:
            key, val = item
            if key == "wip":
                wip.update(_parse_wip(val))
            elif key == "p":
                p_overrides.update(_parse_p_overrides(val))
            elif key == "retry":
                parsed = _parse_retry(val)
                if parsed is not None:
                    retry_ceiling = parsed
            elif key == "liveness":
                parsed = _parse_liveness(val)
                if parsed is not None:
                    card_deadline_s = parsed
            # "columns" → IGNORE (SPEC locks the 6 columns)

    return _BoardConfig(
        wip=wip, p_overrides=p_overrides, retry_ceiling=retry_ceiling,
        card_deadline_s=card_deadline_s, tick_interval_s=tick_interval_s,
        gates=tuple(gates),
    )


def _parse_wip(val: object) -> dict[str, int | None]:
    """Extract WIP overrides from a DictLit or return empty dict."""
    if isinstance(val, DictLit):
        result: dict[str, int | None] = {}
        for k, v in val.items:
            col_name = _lit_str(k)
            if col_name and col_name in _COLUMNS:
                n = _lit_int(v)
                result[col_name] = n
        return result
    return {}


def _parse_p_overrides(val: object) -> dict[str, float]:
    """Extract risk-tier threshold overrides from a DictLit."""
    if isinstance(val, DictLit):
        result: dict[str, float] = {}
        for k, v in val.items:
            tier = _lit_str(k)
            if tier in ("low", "med", "high"):
                fv = _lit_float(v)
                if fv is not None:
                    result[tier] = fv
        return result
    return {}


def _parse_retry(val: object) -> int | None:
    """Extract retry ceiling — IntLit or DictLit with 'ceiling' key."""
    if isinstance(val, IntLit):
        return val.value
    if isinstance(val, DictLit):
        for k, v in val.items:
            if _lit_str(k) == "ceiling":
                return _lit_int(v)
    return None


def _parse_liveness(val: object) -> float | None:
    """Extract card_timeout seconds from liveness DictLit."""
    if isinstance(val, DictLit):
        for k, v in val.items:
            name = _lit_str(k)
            if name in ("card_timeout", "timeout"):
                n = _lit_int(v)
                if n is not None:
                    return float(n)
    return None


def _lit_str(val: object) -> str | None:
    if isinstance(val, StringLit):
        return val.value
    if hasattr(val, "name"):  # Identifier
        return val.name  # type: ignore[attr-defined]
    return None


def _lit_int(val: object) -> int | None:
    if isinstance(val, IntLit):
        return val.value
    return None


def _lit_float(val: object) -> float | None:
    if isinstance(val, FloatLit):
        return val.value
    if isinstance(val, IntLit):
        return float(val.value)
    return None


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

class Board:
    """6-column Kanban state machine bound to a SessionTreeManager (OBRD-02/03)."""

    def __init__(
        self,
        *,
        manager: SessionTreeManager,
        reviewer: Optional[Reviewer] = None,
        reviewer_a: Optional[Reviewer] = None,
        reviewer_b: Optional[Reviewer] = None,
        cwd: Path,
        cfg: _BoardConfig,
        team_ceiling: TeamCeiling,
        root_node_id: str,
        clock: Callable[[], float] = time.monotonic,
        per_card_budget: int = 100_000,
        reserve: int = 0,
    ) -> None:
        self._manager = manager
        # V6 (D-01): legacy single `reviewer` aliases both A and B slots. The
        # legacy slot drives conf_meets_p at InProgress→InReview; when only the
        # A/B slots are supplied, B owns that intermediate confidence check.
        self._reviewer = reviewer if reviewer is not None else reviewer_b
        self._reviewer_a = reviewer_a if reviewer_a is not None else reviewer
        self._reviewer_b = reviewer_b if reviewer_b is not None else reviewer
        # VBOARD-07: track whether ANY independent reviewer was injected. Note
        # self._reviewer defaults to reviewer_b above, so a bare `is None` check
        # on the legacy slot alone would misfire for A/B-only construction
        # (two-source gate). Equivalent to `self._reviewer is not None`.
        self._reviewer_injected = (
            reviewer is not None or reviewer_a is not None or reviewer_b is not None
        )
        self._cwd = cwd
        self._cfg = cfg
        self._team_ceiling = team_ceiling
        self._root_node_id = root_node_id
        self._clock = clock
        self._per_card_budget = per_card_budget
        self._reserve = reserve
        self._cards: list[Card] = []
        self._gates = Gates.build_default()
        self._team_p_overrides: dict = {}
        self._tick_task = None  # populated by O3-04

    @classmethod
    def from_team_config(
        cls,
        team_config: TeamConfig,
        *,
        recorder: SessionTreeManager,
        reviewer: Optional[Reviewer] = None,
        reviewer_a: Optional[Reviewer] = None,
        reviewer_b: Optional[Reviewer] = None,
        cwd: Path,
        clock: Callable[[], float] = time.monotonic,
        parent_node_id: str | None = None,
        per_card_budget: int = 100_000,
    ) -> Board:
        cfg = _read_board_spec(team_config.board)
        if team_config.ceiling.latency_seconds:
            cfg = dataclasses.replace(
                cfg, card_deadline_s=float(team_config.ceiling.latency_seconds),
            )
        root_id = parent_node_id if parent_node_id else recorder._root.id
        board = cls(
            manager=recorder,
            reviewer=reviewer,
            reviewer_a=reviewer_a,
            reviewer_b=reviewer_b,
            cwd=cwd,
            cfg=cfg,
            team_ceiling=team_config.ceiling,
            root_node_id=root_id,
            clock=clock,
            per_card_budget=per_card_budget,
        )
        # Derive p_overrides from team_config.policy.p if it's a dict.
        if isinstance(team_config.policy.p, dict):
            board._team_p_overrides = dict(team_config.policy.p)
        elif cfg.p_overrides:
            board._team_p_overrides = dict(cfg.p_overrides)
        return board

    @property
    def root_node_id(self) -> str:
        return self._root_node_id

    def cards(self) -> list[Card]:
        """Snapshot of current card list (copy — caller mutation is safe)."""
        return list(self._cards)

    async def spawn_card(
        self,
        *,
        risk_tier: RiskTier = "med",
        artifact: Optional[object] = None,
        deadline_override: Optional[float] = None,
        per_card_budget: Optional[int] = None,
    ) -> Card:
        """Create a new card in Backlog, backed by a child session-tree node."""
        limit = per_card_budget if per_card_budget is not None else self._per_card_budget
        node = await self._manager.allocate_child(limit=limit)
        deadline = (
            deadline_override
            if deadline_override is not None
            else self._clock() + self._cfg.card_deadline_s
        )
        card = Card(
            node_id=node.id,
            column="Backlog",
            risk_tier=risk_tier,
            retry_count=0,
            deadline=deadline,
            scope=self._team_ceiling.scope,
            artifact=artifact,
        )
        self._cards.append(card)
        return card

    def move(self, card: Card, to: str) -> Card:
        """Transition a card to `to` column.

        Enforces: unknown-column → WIP → gate predicates (O3-03).
        Every attempt (passed or refused) emits exactly one transition delta.
        """
        # 1. Unknown column rejection
        if to not in _COLUMNS:
            self._append_delta(
                card, from_col=card.column, to_col=to,
                outcome="refused", failing_clauses=["unknown-column"],
            )
            raise BoardGateError(f"unknown column: {to}")

        # 2. WIP enforcement
        cap = self._cfg.wip.get(to)
        if cap is not None:
            in_dest = sum(1 for c in self._cards if c.column == to)
            if in_dest >= cap:
                self._append_delta(
                    card, from_col=card.column, to_col=to,
                    outcome="refused", failing_clauses=["wip"],
                )
                raise BoardWIPError(to, cap)

        # 2.5 VBOARD-07: Done requires an independent reviewer (no self-Done).
        if to == "Done" and not self._reviewer_injected:
            self._append_delta(
                card, from_col=card.column, to_col=to,
                outcome="refused", failing_clauses=["no-reviewer"],
            )
            raise BoardGateError(
                "Done requires an independent reviewer",
                failing_clauses=["no-reviewer"],
            )

        # 3. Gate predicate evaluation (O3-03).
        transition = (card.column, to)
        predicates = self._gates.transitions.get(transition)
        verdict_snapshot = None
        if predicates is not None:
            # AI-vs-code Done variant: swap by artifact introspection.
            if transition == ("InReview", "Done") and card.artifact is not None:
                if hasattr(card.artifact, "eval_score") and not hasattr(
                    card.artifact, "tests_passed"
                ):
                    predicates = (
                        human_approved(),
                        scope_clean(),
                        a_verification_passes(),
                        b_passes(),
                        eval_meets_threshold(),
                    )
            node = self._manager.get_node(card.node_id)
            if node is None:
                raise BoardGateError("card node missing", failing_clauses=["scope"])
            # V20 (VRES-04): hydrate the operator decision for the Done gate;
            # an explicit rejection is terminal (NOT a resumable refusal).
            human_decision = None
            if transition == ("InReview", "Done") and card.risk_tier == "critical":
                human_decision = read_human_decision(
                    self._cwd, self._manager._root.id, card.node_id
                )
                if human_decision == "rejected":
                    return self._force_terminal(card, reason="pending_human_rejected")
            ctx = GateContext(
                card=card,
                node_envelope=dict(node.envelope),
                team_ceiling=self._team_ceiling,
                team_p_overrides=dict(self._team_p_overrides),
                retry_ceiling=self._cfg.retry_ceiling,
                reserve=self._reserve,
                now=self._clock(),
                reviewer=self._reviewer,
                reviewer_a=self._reviewer_a,
                reviewer_b=self._reviewer_b,
                human_decision=human_decision,
            )
            failing: list[str] = []
            for p in predicates:
                if not p.evaluate(ctx):
                    if p.name not in failing:
                        failing.append(p.name)
                    if p.name == "human":
                        # V20 (VRES-04) gate-before-spend: do not pay A/B
                        # reviews while the card waits on its operator.
                        break
            # Snapshot whichever verdict the evaluated predicates produced:
            # ctx.verdict at the intermediate (conf) gate; verdict_b/verdict_a
            # at the two-source Done gate.
            snap_verdict = ctx.verdict or ctx.verdict_b or ctx.verdict_a
            if snap_verdict is not None:
                verdict_snapshot = dataclasses.asdict(snap_verdict)
            if failing:
                # V6 (D-03): a B `block` at the Done gate is TERMINAL, not a
                # retry. Persist the review then force the card to Blocked.
                if ctx.verdict_b is not None and ctx.verdict_b.verdict == "block":
                    _write_review_sidecar(
                        card, ctx, outcome="Blocked",
                        cwd=self._cwd, manager=self._manager,
                    )
                    return self._force_terminal(card, reason="retry_ceiling")
                self._append_delta(
                    card,
                    from_col=card.column,
                    to_col=to,
                    outcome="refused",
                    failing_clauses=failing,
                    verdict_snapshot=verdict_snapshot,
                )
                raise BoardGateError("gate refused", failing_clauses=failing)

        # 4. Emit passed delta + rebuild card with new column.
        # V6 (VREV-09): on a successful two-source Done, persist the review
        # sidecar. Guard on BOTH verdicts present so a pure A-fail (verdict_b
        # never populated) cannot write a partial sidecar (Pitfall 5).
        if (
            transition == ("InReview", "Done")
            and ctx.verdict_a is not None
            and ctx.verdict_b is not None
        ):
            _write_review_sidecar(
                card, ctx, outcome="Done", cwd=self._cwd, manager=self._manager,
            )
        new_card = dataclasses.replace(card, column=to)
        self._cards = [
            new_card if c.node_id == card.node_id else c
            for c in self._cards
        ]
        self._append_delta(
            card, from_col=card.column, to_col=to,
            outcome="passed", failing_clauses=None,
            verdict_snapshot=verdict_snapshot,
        )

        # 5. Finalize on Done (O3-04).
        if to == "Done":
            node = self._manager.get_node(new_card.node_id)
            if node is not None and not node._finalized:
                finalize_node(node, exit_reason="done", cwd=self._cwd)

        return new_card

    def dry_run_gate(
        self, card: Card, transition: tuple[str, str],
    ) -> tuple[bool, list[str]]:
        """Non-destructive predicate evaluation. SPEC L114 acceptance.

        Returns (passed, failing_clauses). Never mutates board state, never
        appends to node.transitions, never invokes the reviewer unless a
        confidence predicate is in the registry for `transition`.
        """
        predicates = self._gates.transitions.get(transition)
        if predicates is None:
            return (True, [])
        # AI-vs-code Done variant — same logic as move.
        if transition == ("InReview", "Done") and card.artifact is not None:
            if hasattr(card.artifact, "eval_score") and not hasattr(
                card.artifact, "tests_passed"
            ):
                predicates = (
                    human_approved(),
                    scope_clean(),
                    a_verification_passes(),
                    b_passes(),
                    eval_meets_threshold(),
                )
        node = self._manager.get_node(card.node_id)
        human_decision = None
        if transition == ("InReview", "Done") and card.risk_tier == "critical":
            human_decision = read_human_decision(
                self._cwd, self._manager._root.id, card.node_id
            )
        ctx = GateContext(
            card=card,
            node_envelope=dict(node.envelope) if node else {"limit": 0, "spent": 0},
            team_ceiling=self._team_ceiling,
            team_p_overrides=dict(self._team_p_overrides),
            retry_ceiling=self._cfg.retry_ceiling,
            reserve=self._reserve,
            now=self._clock(),
            reviewer=self._reviewer,
            reviewer_a=self._reviewer_a,
            reviewer_b=self._reviewer_b,
            human_decision=human_decision,
        )
        failing: list[str] = []
        for p in predicates:
            if not p.evaluate(ctx):
                if p.name not in failing:
                    failing.append(p.name)
                if p.name == "human":
                    break  # V20 (VRES-04): same gate-before-spend as move
        return (not failing, failing)

    def _append_delta(
        self,
        card: Card,
        *,
        from_col: str,
        to_col: str,
        outcome: str,
        failing_clauses: list[str] | None = None,
        reason: str | None = None,
        verdict_snapshot: object | None = None,
    ) -> None:
        node = self._manager.get_node(card.node_id)
        if node is None:
            return  # defensive — card.node_id should always resolve
        delta = {
            "kind": "board.transition",
            "from": from_col,
            "to": to_col,
            "outcome": outcome,
            "failing_clauses": list(failing_clauses) if failing_clauses else None,
            "reason": reason,
            "verdict_snapshot": verdict_snapshot,
            "retry_count": card.retry_count,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        node.transitions.append(delta)
        _write_node_file(node, self._cwd)

    # --- O3-04: tick, forced terminal, critic loop, start/stop ----------------

    def _tick_once(self, now: float) -> None:
        """Synchronous test entry. Forces terminal states only — no forward
        progression. Idempotent: terminal cards are skipped."""
        for card in list(self._cards):
            if card.column in _TERMINAL_COLUMNS:
                continue
            # 1. Wall-clock deadline check.
            if now >= card.deadline:
                self._force_terminal(card, reason="timeout")
                continue
            # 2. Budget exhaustion check.
            node = self._manager.get_node(card.node_id)
            if node is None:
                continue
            env = node.envelope
            if env["spent"] >= env["limit"] - self._reserve:
                self._force_terminal(card, reason="budget")

    def _force_terminal(self, card: Card, *, reason: str) -> Card:
        """Force a card to Blocked with the given reason; finalize the node.

        Mapping for finalize_node exit_reason:
          - "timeout" → exit_reason="timeout"  (in EXIT_REASONS post-O3-01)
          - "budget"  → exit_reason="budget"   (in EXIT_REASONS)
          - "retry_ceiling" → exit_reason="max-iter" (avoids further
            EXIT_REASONS extension; transition delta retains "retry_ceiling")
        """
        new_card = dataclasses.replace(card, column="Blocked")
        self._cards = [
            new_card if c.node_id == card.node_id else c
            for c in self._cards
        ]
        self._append_delta(
            card, from_col=card.column, to_col="Blocked",
            outcome="forced", reason=reason,
        )
        node = self._manager.get_node(card.node_id)
        if node is not None and not node._finalized:
            exit_reason = reason if reason in {"timeout", "budget"} else "max-iter"
            finalize_node(node, exit_reason=exit_reason, cwd=self._cwd)
        return new_card

    def critic_step(self, card: Card, last_verdict: ReviewerVerdict) -> Card:
        """Process a reviewer verdict after InReview.

        - pass: no-op (caller drives forward progression).
        - fail: if retry_count < ceiling, card returns to InProgress with
          retry_count+1 and a RetryNote on node.retry_notes. If ceiling
          hit: forced to Blocked(reason="retry_ceiling").
        - block: forced to Blocked(reason="retry_ceiling") immediately.
        """
        if last_verdict.verdict == "pass":
            return card
        if last_verdict.verdict == "block":
            return self._force_terminal(card, reason="retry_ceiling")

        # verdict == "fail"
        new_retry = card.retry_count + 1
        if new_retry > self._cfg.retry_ceiling:
            return self._force_terminal(card, reason="retry_ceiling")

        new_card = dataclasses.replace(
            card, column="InProgress", retry_count=new_retry,
        )
        self._cards = [
            new_card if c.node_id == card.node_id else c
            for c in self._cards
        ]
        # Append RetryNote to node.
        node = self._manager.get_node(card.node_id)
        if node is not None:
            note = {
                "round": new_retry,
                "notes": last_verdict.notes,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            node.retry_notes.append(note)
        # Emit passed transition InReview→InProgress.
        self._append_delta(
            card, from_col="InReview", to_col="InProgress",
            outcome="passed",
            verdict_snapshot=dataclasses.asdict(last_verdict),
        )
        if node is not None:
            _write_node_file(node, self._cwd)
        return new_card

    def start(self) -> None:
        """Start the periodic tick loop (idempotent)."""
        if self._tick_task is not None and not self._tick_task.done():
            return
        self._tick_task = asyncio.create_task(
            _tick_loop(self, self._clock, self._cfg.tick_interval_s),
        )

    async def stop(self) -> None:
        """Cancel the tick loop and await drain."""
        if self._tick_task is None:
            return
        self._tick_task.cancel()
        try:
            await self._tick_task
        except asyncio.CancelledError:
            pass
        self._tick_task = None
