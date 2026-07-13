---
phase: BOS5
slug: outcome-labels-and-reward-model
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-18
---

# Phase BOS5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Docs-first schema-contract phase: "tests" validate the CONTRACT artifacts
> (JSON Schema lints, example label/measure/reward round-trip, tension-pair
> coverage, no-leakage guard, versioning), not runtime behavior. See
> BOS5-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing repo suite; `.venv/bin/python`) |
| **Config file** | existing repo pytest config |
| **Quick run command** | `.venv/bin/python -m pytest tests/planning/test_bos_outcome_schema.py -x` |
| **Full suite command** | `.venv/bin/python -m pytest tests/planning/ -x` |
| **Estimated runtime** | ~10 seconds |

> `jsonschema` 4.26.0 confirmed in `.venv` (per BOS3, 2026-06-18) — no install task
> expected. Planner should add a Wave-0 install task only if a fresh check shows it missing.

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** All ACC-01..ACC-07 green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

> Validates contract artifacts: (1) `contracts/outcomes.schema.json` is itself valid
> (Draft 2020-12 meta-schema), (2) all 7 categorical labels + cycle_time measure present
> as discriminated variants, (3) example label/measure/reward records round-trip, (4)
> bitemporal + no-leakage invariants hold over examples, (5) tension-pair coverage (every
> reward objective has >=1 counter-metric), (6) guardrail-role enum + named scalarization,
> (7) versioning + rationale doc completeness.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| author outcome JSON Schema | BOS5-01 | 1 | BOS-DATA-03/04 | schema-lint + variant coverage | `.venv/bin/python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/outcomes.schema.json')))"` | ⬜ pending |
| author rationale spec doc | BOS5-01 | 1 | BOS-DATA-03/04 | content + table assertions | `.venv/bin/python -c "t=open('docs/BOS5-OUTCOME-REWARD-SPEC.md').read(); assert all(s in t for s in ['derivation','observation window','objective','tension','migration'])"` | ⬜ pending |
| bundle example records | BOS5-02 | 2 | BOS-DATA-03/04 | example round-trip + bitemporal + no-leakage | `.venv/bin/python -c "import json,glob,jsonschema; s=json.load(open('contracts/outcomes.schema.json')); v=jsonschema.Draft202012Validator(s); [v.validate(json.load(open(f))) for f in glob.glob('.planning/schemas/examples/outcome*.json')]"` | ⬜ pending |
| contract pytest suite | BOS5-02 | 2 | BOS-DATA-03/04 | full 13-check contract suite (ACC-01..07) | `.venv/bin/python -m pytest tests/planning/test_bos_outcome_schema.py -x` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

The contract suite (`tests/planning/test_bos_outcome_schema.py`) asserts:
`test_schema_is_valid`, `test_categorical_label_coverage`, `test_measure_coverage`,
`test_label_examples_validate`, `test_bitemporal_invariant`,
`test_no_decision_leakage_in_label`, `test_reward_record_shape`,
`test_decision_schema_no_outcome_field`, `test_tension_pair_coverage`,
`test_guardrail_role_enum`, `test_scalarization_named`, `test_round_trip_scenario`,
`test_versioning_present`.

### Acceptance Criteria (ACC) — for use in task acceptance_criteria

| ACC ID | Description |
|--------|-------------|
| ACC-01 | `contracts/outcomes.schema.json` exists, passes Draft 2020-12 meta-schema lint |
| ACC-02 | All 7 categorical label types + cycle_time measure present as discriminated variants |
| ACC-03 | Every label variant carries `entity_id`, `event_time`, `ingest_time`, `obs_window_id`, `source_rule` |
| ACC-04 | Round-trip example: BOS3 event → CycleTimeMeasure + CleanMergeLabel validates; supersede scenario (CleanMerge → EscapedDefect) validates with `supersedes_outcome_id` present |
| ACC-05 | Tension-pair coverage: every named reward objective in the contract has ≥1 `GuardrailMetricSpec` with `linked_reward_objective` pointing to it |
| ACC-06 | CI drift gate includes `contracts/outcomes.schema.json` (same gate as `events.schema.json`) |
| ACC-07 | `docs/BOS5-OUTCOME-REWARD-SPEC.md` exists and contains: derivation rules table, observation window table, reward objective table, tension-pair table, migration notes |

---

## Wave 0 Requirements

> The normative artifacts under test are authored in Wave 1 (BOS5-01), so the
> Wave-2 tests (BOS5-02) validate REAL artifacts, not scaffolds. No xfail/skip
> scaffolding needed — schema + spec exist before the tests run. (Guards the
> [[gsd-scaffold-fictional-api]] false-green trap.)

- [ ] `contracts/outcomes.schema.json` — normative outcome/measure/reward/guardrail JSON Schema (BOS5-01)
- [ ] `docs/BOS5-OUTCOME-REWARD-SPEC.md` — rationale prose: derivation rules, observation windows, reward objectives, tension-pair table, migration notes (BOS5-01)
- [ ] `.planning/schemas/examples/outcome*.json` — example label/measure/reward records, ≥1 per label type + supersede scenario + round-trip (BOS5-02)
- [ ] `tests/planning/__init__.py` + `tests/planning/test_bos_outcome_schema.py` — 13-check contract suite (BOS5-02)
- [x] `jsonschema` available in `.venv` — confirmed 4.26.0 (re-verify; no install expected)

*Schema representation: JSON Schema Draft 2020-12 (mirrors `contracts/events.schema.json`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Default observation-window lengths are operationally sane | BOS-DATA-03 | RESEARCH confidence LOW — defaults need real incident-data calibration | Human review: the windows are reasonable starting points; flagged tunable, not load-bearing for the contract. |
| Tension-pair thresholds catch real gaming | BOS-DATA-04 | RESEARCH confidence LOW on thresholds | Human review: counter-metric *coverage* is auto-checked (ACC-05); threshold *values* are judgment, refined in BOS15. |

*Contract structure is automatically verified (schema lint + round-trip + coverage + invariants). Only numeric defaults/thresholds are manual.*

---

## DATA-05 Offline-Eval Slice (added 2026-06-20 — plans BOS5-03/04/05)

> Same docs-first discipline: "tests" validate the offline-eval CONTRACT artifacts
> (`contracts/offline-eval.schema.json` + `docs/BOS5-OFFLINE-EVAL-SPEC.md` + the additive
> `policy_context` amendment to `contracts/decision-ledger.schema.json`), not runtime behavior.
> See BOS5-RESEARCH.md §BOS-DATA-05 + extended §Validation Architecture (ACC-08..ACC-16).

| Quick run command | `.venv/bin/python -m pytest tests/planning/test_bos_offline_eval_schema.py tests/planning/test_bos_decision_policy_context.py -x` |
|----|----|

### Per-Task Verification Map (DATA-05)

| Task | Plan | Wave | Requirement | Test Type | Status |
|------|------|------|-------------|-----------|--------|
| author `contracts/offline-eval.schema.json` (EvalDatasetSpec + PolicyEvalReport + PromotionGateCriteria + estimator enum) | BOS5-03 | 1 | BOS-DATA-05 | schema-lint + variant/enum/gate-shape coverage | ⬜ pending |
| author `docs/BOS5-OFFLINE-EVAL-SPEC.md` | BOS5-03 | 1 | BOS-DATA-05 | content + table assertions | ⬜ pending |
| bundle offline-eval example records (+ no-leakage example) | BOS5-04 | 2 | BOS-DATA-05 | round-trip + no-leakage + FK check | ⬜ pending |
| DATA-05 contract pytest suite (`test_bos_offline_eval_schema.py`) | BOS5-04 | 2 | BOS-DATA-05 | ACC-08..13,15,16 | ⬜ pending |
| additive `policy_context` on `decision-ledger.schema.json` + presence test | BOS5-05 | 2 | BOS-DATA-05 (D-15, BOS4 follow-up) | additive-schema lint + ACC-14 presence | ⬜ pending |
| deterministic `policy_context` example (propensity=1.0) | BOS5-05 | 2 | BOS-DATA-05 | example round-trip | ⬜ pending |

### Acceptance Criteria (ACC-08..ACC-16)

| ACC ID | Description |
|--------|-------------|
| ACC-08 | `contracts/offline-eval.schema.json` exists, passes Draft 2020-12 meta-schema lint |
| ACC-09 | `EvalDatasetSpec` and `PolicyEvalReport` both present as named `$defs`; both validate example round-trips |
| ACC-10 | `estimator_eligibility` and `PolicyEvalReport.estimator` constrained to the D-14 admissible family enum (`ips`, `snips`, `dr`, `dm`, `fqe`) — no other values, no single binding |
| ACC-11 | `EvalDatasetSpec.no_leakage_check` present with `outcome_as_of_after_as_of_cutoff` boolean; example dataset spec sets it `true` |
| ACC-12 | `PolicyEvalReport` carries all D-14 mandatory properties: `ope_point_estimate`, `ci_lower`, `ci_upper`, `ci_level`, `effective_sample_size`, `bias_flags[]` |
| ACC-13 | `PolicyEvalReport.gate_result` carries all three D-16 gate checks: `lift_threshold_met`, `ci_bound_met`, `all_hard_gates_non_regressed` |
| ACC-14 | `contracts/decision-ledger.schema.json` `policy_context` present + REQUIRED with `propensity` (0..1), `action_space` (array), `exploration_flag` (boolean), `policy_version` (string) — BOS4 follow-up deliverable (BOS5-05) |
| ACC-15 | `docs/BOS5-OFFLINE-EVAL-SPEC.md` contains: admissible estimator family table, propensity-logging requirement, gate-criteria shape table, no-leakage join explanation, migration notes |
| ACC-16 | CI drift gate extended to include `contracts/offline-eval.schema.json` |

### Wave 0 Requirements (DATA-05)

- [ ] `contracts/offline-eval.schema.json` (BOS5-03)
- [ ] `docs/BOS5-OFFLINE-EVAL-SPEC.md` (BOS5-03)
- [ ] `.planning/schemas/examples/offline-eval-*.json` (BOS5-04)
- [ ] `tests/planning/test_bos_offline_eval_schema.py` (BOS5-04)
- [ ] `policy_context` amendment + `tests/planning/test_bos_decision_policy_context.py` + `decision-policy-context.json` (BOS5-05)
- [x] `jsonschema` 4.26.0 in `.venv` — confirmed

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter (flipped by BOS5-02 on green suite)

**Approval:** planned — `nyquist_compliant` flips true when `tests/planning/test_bos_outcome_schema.py` is green.
