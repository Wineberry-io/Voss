---
phase: BOS4-decision-ledger-schema
plan: BOS4-05
status: complete
date: 2026-07-26
requirements: [BOS-DATA-02]
files_modified:
  - voss/harness/permissions.py
  - tests/harness/test_bos_decision_permission_emit.py
  - tests/harness/tui/test_permissions_bridge.py
---

# BOS4-05 Summary: Human Permission Verdict Emission

## What shipped

Wired the second live BOS decision producer at `PermissionGate._prompt`.
Human-answered permission prompts now append one schema-valid `no_action`
decision record to `.voss/bos/decisions.jsonl`.

- **Human-only emission (D-R01/D-R04):** `a` / `A` map to `approve`; deny maps
  to `dismiss`. Auto, remembered, rule-allow, non-interactive, and rootless
  paths emit nothing.
- **Point-in-time row:** each answer gets a fresh UUID-backed `decision_id`,
  BOS3 `as_of`, actor `operator`, and a curated feature snapshot containing
  only tool name, mutability, mode, signature, and a non-sensitive diff
  summary. Raw tool arguments are never serialized.
- **Live root resolution:** an explicit keyword-only `cwd` wins; existing
  CLI/server gates fall back to their `PermissionStore.cwd`, so shipped prompt
  surfaces emit without broad constructor churn.
- **Best-effort boundary:** `OSError`, `ValueError`, and portalocker contention
  cannot change the permission result.

## Verification

- `.venv/bin/pytest tests/harness/test_bos_decision_permission_emit.py -x -q`
  — 13 passed.
- BOS decision suite (`test_bos_decision_ledger.py`,
  `test_bos_decision_swarm_emit.py`, permission emit) — 21 passed.
- Focused permission regression set — 61 passed.
- Broader permission-selected harness suite excluding
  `tests/harness/tui/test_cli_integration.py` — 66 passed.
- `.venv/bin/python -c "import voss.harness.permissions"` — clean import.
- `git diff --check` — passed.

## Deviations from Plan

- Updated the existing TUI dataclass-field guard to include the required BOS4
  `cwd` field.
- Used `PermissionStore.cwd` when explicit `cwd` is absent. The plan's
  two-production-file scope otherwise left all live CLI/server constructors
  rootless and unable to emit.
- Added `portalocker.exceptions.LockException` to the best-effort guard because
  lock contention is not an `OSError`.

## Issues Encountered

The literal `.venv/bin/pytest tests/harness/ -k permission -q` gate still fails
in two pre-existing TUI CLI integration tests. Their fake provider returns a
`Plan` without the now-required `confidence` field. Both failures occur during
provider response parsing before permission behavior; the same permission
selection passes when that unrelated file is excluded.

## Downstream

BOS4 decision-ledger runtime is complete: swarm assignment and human permission
producers both emit through the BOS4-03 writer. BOS5 can join outcomes later by
`decision_id` without writing outcome data into decision rows.
