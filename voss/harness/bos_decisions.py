"""Local append-only BOS decision ledger.

Inline emission (D-R01): decision records are written AT gate/operator decision
time, carrying the frozen state they were made against (the as_of pointer and
feature_snapshot). This is a deliberate break from BOS3's pure projection layer
(`bos_events.py`), which reconstructs observed facts after the fact. Decisions
are not observed facts; they pin point-in-time state at the moment of choice.
This inline-emission contract is the keystone of BOS4 (D-R01).

Records are written to `.voss/bos/decisions.jsonl`, a sibling of the BOS3 event
ledger, and every record validates against
`contracts/decision-ledger.schema.json`. The outcome label (BOS5) is NEVER
written here at decision time; it is joined later by `decision_id` (D-04).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import portalocker

_LOCK_TIMEOUT_S = 10.0


def decisions_ledger_path(cwd: Path) -> Path:
    """Return the canonical local BOS decision ledger path for a project cwd."""

    return Path(cwd).resolve() / ".voss" / "bos" / "decisions.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BosDecisionLedger:
    """Append-only JSONL writer and replay reader for BOS decision records."""

    def __init__(self, cwd: Path) -> None:
        self.path = decisions_ledger_path(cwd)

    def append_decision(self, decision: dict[str, Any]) -> bool:
        """Append one record unless its `decision_id` is already present.

        Returns True when a new line was written and False when the record was a
        duplicate. Duplicate detection runs under the same file lock as the
        append, so a re-append does not change file bytes.
        """

        return self.append_decisions([decision]) == 1

    def append_decisions(self, decisions: list[dict[str, Any]]) -> int:
        """Append records in order, skipping already-seen `decision_id` values."""

        if not decisions:
            return 0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(
            str(self.path),
            mode="a+",
            flags=portalocker.LOCK_EX | portalocker.LOCK_NB,
            timeout=_LOCK_TIMEOUT_S,
        ) as f:
            f.seek(0)
            seen = _read_decision_ids(f)
            appended = 0
            for decision in decisions:
                decision_id = _decision_id(decision)
                if decision_id in seen:
                    continue
                f.write(json.dumps(decision, sort_keys=True) + "\n")
                seen.add(decision_id)
                appended += 1
        self.path.chmod(0o600)
        return appended

    def read_decisions(
        self,
        *,
        decision_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Replay records in append order, optionally filtering by decision_type.

        A torn trailing line is ignored so an interrupted writer does not make
        the whole ledger unreadable.
        """

        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    decision = json.loads(line)
                except json.JSONDecodeError:
                    break
                if decision_type is not None and decision.get("decision_type") != decision_type:
                    continue
                out.append(decision)
        return out


def append_decision(cwd: Path, decision: dict[str, Any]) -> bool:
    return BosDecisionLedger(cwd).append_decision(decision)


def append_decisions(cwd: Path, decisions: list[dict[str, Any]]) -> int:
    return BosDecisionLedger(cwd).append_decisions(decisions)


def read_decisions(
    cwd: Path,
    *,
    decision_type: str | None = None,
) -> list[dict[str, Any]]:
    return BosDecisionLedger(cwd).read_decisions(decision_type=decision_type)


def _decision_id(decision: dict[str, Any]) -> str:
    decision_id = decision.get("decision_id")
    if not decision_id:
        raise ValueError("BOS decision record missing decision_id")
    return str(decision_id)


def _read_decision_ids(f: Any) -> set[str]:
    seen: set[str] = set()
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            decision = json.loads(line)
        except json.JSONDecodeError:
            break
        decision_id = decision.get("decision_id")
        if decision_id:
            seen.add(str(decision_id))
    return seen


def _scan_events(events_path: Path) -> tuple[int, str | None]:
    """Tail-scan the BOS3 event ledger.

    Returns (count_of_valid_lines, last_event_id). Reads line-by-line so a large
    ledger is not loaded into memory; a torn trailing line stops the scan (same
    tolerance as `bos_ledger.read_events`). Does NOT call
    `BosEventLedger.read_events`.
    """

    if not events_path.exists():
        return 0, None
    count = 0
    last: str | None = None
    with events_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                break
            count += 1
            eid = rec.get("event_id")
            if eid:
                last = str(eid)
    return count, last


def _read_last_event_id(events_path: Path) -> str | None:
    """Return the event_id of the last complete line in the BOS3 ledger, or None."""

    return _scan_events(events_path)[1]


def build_as_of(events_path: Path) -> dict[str, Any]:
    """Assemble the as_of point-in-time pointer from the BOS3 event ledger tail.

    Returns `{}` when the event ledger is empty or absent (the schema requires a
    `type: object`, not null — D-R05). Otherwise returns
    `{"event_seq": <count>, "snapshot_id": <last_event_id>}`.
    """

    count, last = _scan_events(events_path)
    if count == 0:
        return {}
    as_of: dict[str, Any] = {"event_seq": count}
    if last is not None:
        as_of["snapshot_id"] = last
    return as_of


def build_task_to_agent_record(
    *,
    decision_id: str,
    task_id: str,
    chosen_agent_id: str,
    candidate_agents: list[str],
    feature_snapshot: dict[str, Any],
    entity_ref: dict[str, Any],
    as_of: dict[str, Any],
    rationale: str,
    autonomy_band: str = "",
) -> dict[str, Any]:
    """Build a schema-valid `task_to_agent` decision record (D-R02).

    Pre-BOS9 (D-R03): no policy produces a recommendation, so
    `recommended_action` is `{}`. The assignment is automatic with no human
    prompt, so `human_verdict` records a system `approve` (the schema requires a
    fully-populated human_verdict object; there is no null path).
    """

    now = _now_iso()
    return {
        "decision_id": decision_id,
        "decision_type": "task_to_agent",
        "created_at": now,
        "as_of": as_of,
        "feature_snapshot": feature_snapshot,
        "entity_ref": entity_ref,
        "autonomy_band": autonomy_band,
        "recommended_action": {},
        "human_verdict": {
            "verdict": "approve",
            "actor_id": "system",
            "verdict_at": now,
        },
        "actual_action": {"chosen_agent_id": chosen_agent_id},
        "rationale": rationale,
        "payload": {
            "decision_type": "task_to_agent",
            "task_id": task_id,
            "chosen_agent_id": chosen_agent_id,
            "candidate_agents": candidate_agents,
        },
    }


def build_verdict_record(
    *,
    decision_id: str,
    verdict: str,
    actor_id: str,
    feature_snapshot: dict[str, Any],
    entity_ref: dict[str, Any],
    as_of: dict[str, Any],
    rationale: str,
    reason: str | None = None,
    autonomy_band: str = "",
) -> dict[str, Any]:
    """Build a schema-valid human permission-verdict record (D-R04).

    The decision enum has no `permission_verdict` type, so a human gate answer is
    emitted as `decision_type="no_action"` carrying the human answer in
    `human_verdict`. Pre-BOS9 (D-R03) `verdict` is `approve` or `dismiss` only;
    `override` requires a recommendation to diverge from (BOS9+).
    `recommended_action` is `{}`; `actual_action` reflects the gate outcome.
    """

    now = _now_iso()
    payload: dict[str, Any] = {"decision_type": "no_action"}
    if reason is not None:
        payload["reason"] = reason
    return {
        "decision_id": decision_id,
        "decision_type": "no_action",
        "created_at": now,
        "as_of": as_of,
        "feature_snapshot": feature_snapshot,
        "entity_ref": entity_ref,
        "autonomy_band": autonomy_band,
        "recommended_action": {},
        "human_verdict": {
            "verdict": verdict,
            "actor_id": actor_id,
            "verdict_at": now,
        },
        "actual_action": {"allowed": verdict == "approve"},
        "rationale": rationale,
        "payload": payload,
    }


__all__ = [
    "BosDecisionLedger",
    "append_decision",
    "append_decisions",
    "build_as_of",
    "build_task_to_agent_record",
    "build_verdict_record",
    "decisions_ledger_path",
    "read_decisions",
]
