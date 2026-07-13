---
phase: BOS4-decision-ledger-schema
plan: BOS4-03
status: complete
date: 2026-06-20
requirements: [BOS-DATA-02]
files_modified:
  - voss/harness/bos_decisions.py
  - tests/harness/test_bos_decision_ledger.py
---

# BOS4-03 Summary: Decision Ledger Runtime Writer + Builders

## What shipped

`voss/harness/bos_decisions.py` — the inline-emission decision-ledger writer and
record builders (storage + record-construction half of BOS-DATA-02). Foundation
that BOS4-04 (swarm assignment seam) and BOS4-05 (permission gate) consume.

- **`BosDecisionLedger`** — append/dedup/replay mirroring `bos_ledger.py` exactly:
  portalocker `LOCK_EX|LOCK_NB` (10s timeout), dedup by `decision_id` under the
  lock, `sort_keys=True` writes, torn-trailing-line tolerance (break on first
  `JSONDecodeError`), `chmod(0o600)` after every append. Path =
  `.voss/bos/decisions.jsonl`. `read_decisions` filters on `decision_type` only.
- **`build_as_of` / `_read_last_event_id` / `_scan_events`** — cheap line-by-line
  tail scan of the BOS3 `.voss/bos/events.jsonl` (does NOT call
  `BosEventLedger.read_events`). `build_as_of` returns `{}` when the event ledger
  is empty/absent, else `{"event_seq": <count>, "snapshot_id": <last_event_id>}`
  (D-R05).
- **`build_task_to_agent_record`** (D-R02) — `decision_type="task_to_agent"`,
  `recommended_action={}` (pre-BOS9, D-R03), automatic system `approve` verdict
  (no human prompt path), `TaskToAgentPayload`.
- **`build_verdict_record`** (D-R04) — human permission answer. The enum has no
  `permission_verdict` type, so it emits `decision_type="no_action"` carrying the
  human answer in `human_verdict` (`approve`/`dismiss` only pre-BOS9; `override`
  reserved for BOS9+). `actual_action={"allowed": verdict=="approve"}`,
  `NoActionPayload`.
- Module-level wrappers `append_decision` / `append_decisions` / `read_decisions`.

## Verification

- `.venv/bin/pytest tests/harness/test_bos_decision_ledger.py` — 6 passed.
- `.venv/bin/python -c "import voss.harness.bos_decisions"` — clean import.
- Both builders' output validates against `contracts/decision-ledger.schema.json`
  (asserted in tests via `jsonschema.Draft202012Validator`).
- Only `task_to_agent` and `no_action` decision_types emitted — no stub rows for
  the four no-producer types (D-R02). No outcome/label field anywhere (D-04).

## Notes / deviations

- **TDD RED→GREEN** followed: test file written first (confirmed import-fail RED),
  then module turned all 6 green.
- **6th test** added beyond the 5 named in the plan behavior block
  (`test_build_as_of_assembles_from_events`) to cover the `build_as_of` assembly
  contract distinctly from `_read_last_event_id`; matches the plan's "collected 6"
  RED gate.
- No new dependencies (stdlib + already-vendored portalocker/jsonschema).

## Downstream

- BOS4-04: wire `build_task_to_agent_record` at `swarm_runtime.py` assignment seam
  (after `store.mark_assigned`, line ~165).
- BOS4-05: wire `build_verdict_record` at `permissions.py` `_prompt` human-answer
  return path (lines ~442-456); auto-allows must NOT emit (D-R04).
