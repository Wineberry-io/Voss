"""O6-owned frozen audit dataclasses.

These types normalize O1-O5 persisted data into an audit-specific snapshot.
They use only primitives, tuples, and dicts — no imports from board, reviewer,
EM, CLI, or TUI modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


SeverityLabel = Literal["ok", "warning", "blocked", "accepted_gap"]


@dataclass(frozen=True, slots=True)
class RoutingRationale:
    """Normalized snapshot of an EM routing decision."""
    id: str
    card_id: str
    chosen_role: str
    candidates_considered: tuple[str, ...]
    rationale_text: str
    ts: str
    confidence_hint: Optional[float] = None


@dataclass(frozen=True, slots=True)
class KillRecord:
    """Normalized snapshot of an EM kill event."""
    killed_node_id: str
    rationale_text: str
    evidence_refs: tuple[str, ...]
    killed_at: str
    lineage_parent_id: Optional[str] = None
    successor_card_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class RescopeRecord:
    """Normalized snapshot of an EM rescope event."""
    predecessor_card_id: str
    successor_card_id: str
    diff_summary: str
    rationale_text: str
    rescoped_at: str
    new_acceptance: tuple[str, ...] = ()
    new_dod: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReviewerAssessment:
    """Normalized snapshot of a reviewer verdict."""
    conf: float
    source: str  # "A" or "B"
    tier: str  # "fast" or "strong"
    verdict: str  # "pass", "fail", or "block"
    notes: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LivenessEvent:
    """Normalized snapshot of a liveness-relevant event on a node."""
    node_id: str
    event_type: str  # "timeout", "reserve_exhausted", "open_node", "terminal"
    severity: SeverityLabel
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Leak6Assessment:
    """Leak-6 (semantic memory poisoning) assessment record."""
    status: SeverityLabel  # typically "ok" or "accepted_gap"
    evidence: str
    mitigation_present: bool = False


@dataclass(frozen=True, slots=True)
class AuditCard:
    """Normalized per-card audit record."""
    node_id: str
    column: str
    risk_tier: str
    retry_count: int = 0
    is_killed: bool = False
    kill_record: Optional[KillRecord] = None
    is_rescoped: bool = False
    rescope_record: Optional[RescopeRecord] = None
    routing: Optional[RoutingRationale] = None
    verdicts: tuple[ReviewerAssessment, ...] = ()
    retry_notes: tuple[dict, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditNode:
    """Normalized per-node audit record."""
    id: str
    root_id: str
    parent_run_id: Optional[str]
    envelope: dict
    terminal_state: Optional[dict]
    created_at: str
    ended_at: Optional[str]
    transitions: tuple[dict, ...] = ()
    cards: tuple[AuditCard, ...] = ()
    liveness_events: tuple[LivenessEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditSnapshot:
    """Complete read-only audit snapshot for one session tree."""
    root_id: str
    nodes: tuple[AuditNode, ...]
    cards: tuple[AuditCard, ...]
    kills: tuple[KillRecord, ...]
    rescopes: tuple[RescopeRecord, ...]
    routings: tuple[RoutingRationale, ...]
    verdicts: tuple[ReviewerAssessment, ...]
    liveness: tuple[LivenessEvent, ...]
    leak6: Leak6Assessment
    run_final: Optional[dict] = None


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    """Reviewer calibration metrics aggregated across runs (VAUD-CAL)."""
    total_pairs: int
    false_pass_count: int
    slop_rejection_count: int
    false_pass_rate: float
    slop_rejection_rate: float
    spot_audit_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Complete V9 audit report: wraps AuditSnapshot + all PRD §9 sections."""
    run_id: str
    idea: str
    principles: tuple[tuple[str, str], ...]
    team_config: dict
    snapshot: AuditSnapshot
    review_sidecars: dict
    run_final: Optional[dict]
    signoff_ack: Optional[dict]
    calibration: CalibrationReport
    sections_missing: tuple[str, ...]
    unsupported_claims: tuple[str, ...] = ()
    # V12 VSAFE-05: strict-runbook/factory-fallback marker. Default empty so old
    # audit snapshots hydrate; populated from run records' factory_fallbacks.
    factory_fallbacks: tuple[dict, ...] = ()
