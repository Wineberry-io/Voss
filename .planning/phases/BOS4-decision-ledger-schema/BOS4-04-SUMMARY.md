---
phase: BOS4-decision-ledger-schema
plan: BOS4-04
status: complete
date: 2026-06-20
requirements: [BOS-DATA-02]
files_modified:
  - voss/harness/swarm_runtime.py
  - tests/harness/test_bos_decision_swarm_emit.py
---

# BOS4-04 Summary: task_to_agent Emission at Swarm Assignment Seam

## What shipped

Wired the **first live decision producer** (D-R02). In `run_cli_member`
(`swarm_runtime.py`), immediately after `store.mark_assigned(swarm_id, task.id)`
and before `resolve_agent_argv`, a `task_to_agent` decision record is built and
appended to `.voss/bos/decisions.jsonl` via the BOS4-03 builders.

- **Inline emission (D-R01):** freezes the assignment context at decision time —
  `feature_snapshot = {goal, roster, available_models, cwd}` (D-R06),
  `entity_ref = {task_id, swarm_id, agent_id}`, `as_of = build_as_of(<BOS3 events
  tail>)` (D-R05). `roster` pulled from `store.get(swarm_id).roster` (falls back
  to `[role]`).
- **Stable `decision_id`** = `dec-{swarm_id}-{task.id}` → re-run dedups to one
  record per assignment.
- **Best-effort guard:** the emit is wrapped in `try/except (OSError, ValueError)`
  so a ledger write error never aborts the swarm run (T-BOS4-04-02).
- **No-leakage:** assignment-time only; no outcome/result data captured (D-04).

## Verification

- `.venv/bin/pytest tests/harness/test_bos_decision_swarm_emit.py` — 2 passed.
  Drives `run_cli_member` against a real temp git repo + fake spawn_fn (mirrors
  `test_swarm_runtime.py`); asserts one schema-valid `task_to_agent` record,
  correct feature_snapshot/entity_ref keys, and dedup no-op on repeat.
- `.venv/bin/python -c "import voss.harness.swarm_runtime"` — clean import.
- Regression: `test_bos_decision_ledger.py` (6) + `test_swarm_runtime.py` (5) all
  still pass.

## Notes

- Test drives the full `run_cli_member` for fidelity (the plan's preferred path),
  not the lighter direct-builder fallback.
- `decisions_ledger_path` not imported — the seam uses `append_decision(repo_root,
  ...)` and an inline events-path expression, so the helper wasn't needed.

## Downstream

- BOS4-05: wire `build_verdict_record` at `permissions.py` `_prompt` human-answer
  return (auto-allows must NOT emit, D-R04) — the second and final live producer
  for this phase.
