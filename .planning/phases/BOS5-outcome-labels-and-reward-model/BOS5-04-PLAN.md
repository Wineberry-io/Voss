---
phase: BOS5
plan: 04
type: execute
wave: 2
depends_on: ["BOS5-03"]
files_modified:
  - .planning/schemas/examples/offline-eval-dataset-spec.json
  - .planning/schemas/examples/offline-eval-policy-report.json
  - .planning/schemas/examples/offline-eval-promotion-gate-criteria.json
  - tests/planning/test_bos_offline_eval_schema.py
autonomous: true
requirements: [BOS-DATA-05]

must_haves:
  truths:
    - "The offline-eval JSON Schema is proven valid against the Draft 2020-12 meta-schema by an automated test"
    - "A minimal valid EvalDatasetSpec, a minimal valid PolicyEvalReport (incl. guardrail_deltas + gate_result), and a PromotionGateCriteria example each round-trip against contracts/offline-eval.schema.json"
    - "The no-leakage invariant is proven on the example dataset: no_leakage_check present with outcome_as_of_after_as_of_cutoff:true, and outcome_as_of strictly greater than as_of_cutoff"
    - "estimator_eligibility and PolicyEvalReport.estimator are proven constrained to exactly {ips,snips,dr,dm,fqe} (no other value validates; not a single const)"
    - "PolicyEvalReport is proven to carry every D-14 mandatory property and the three D-16 gate-result checks (lift_threshold_met, ci_bound_met, all_hard_gates_non_regressed)"
    - "contracts/offline-eval.schema.json is lint-gated on every run of the new suite (ACC-16), the same hand-authored stability gate BOS5-02 used for outcomes.schema.json"
  artifacts:
    - path: "tests/planning/test_bos_offline_eval_schema.py"
      provides: "DATA-05 contract suite (ACC-08..ACC-13, ACC-15, ACC-16): schema-valid/lint-gate, record-types-present, EvalDatasetSpec + PolicyEvalReport example round-trips, no_leakage_check, estimator-family enum (eligibility + report.estimator), report required fields, gate_result shape, guardrail_delta shape, spec-doc presence"
      contains: "Draft202012Validator"
      min_lines: 110
    - path: ".planning/schemas/examples/offline-eval-dataset-spec.json"
      provides: "Minimal valid EvalDatasetSpec with no_leakage_check.outcome_as_of_after_as_of_cutoff=true and outcome_as_of > as_of_cutoff"
      contains: "no_leakage_check"
      min_lines: 0
    - path: ".planning/schemas/examples/offline-eval-policy-report.json"
      provides: "Minimal valid PolicyEvalReport with all D-14 mandatory props + guardrail_deltas + the 3-part gate_result"
      contains: "gate_result"
      min_lines: 0
  key_links:
    - from: "tests/planning/test_bos_offline_eval_schema.py"
      to: "contracts/offline-eval.schema.json"
      via: "loads + lints the schema and validates the example records against it"
      pattern: "offline-eval.schema.json"
    - from: "tests/planning/test_bos_offline_eval_schema.py"
      to: ".planning/schemas/examples/offline-eval-*.json"
      via: "globs + round-trips every offline-eval example record"
      pattern: "offline-eval"
---

<objective>
Build the contract-validation harness for the BOS5 offline-eval requirements schema:
bundled example records (a minimal valid EvalDatasetSpec, a minimal valid
PolicyEvalReport, and a PromotionGateCriteria) and the DATA-05 pytest suite
(`tests/planning/test_bos_offline_eval_schema.py`) that proves the schema is valid,
the examples round-trip, the no-leakage invariant holds, the admissible-estimator
enum is closed (no single binding), every D-14 mandatory property + the three D-16
gate-result checks are present, and the guardrail_delta sub-shape mirrors
GuardrailMetricSpec. Lint-gate `contracts/offline-eval.schema.json` on every run
(ACC-16).

Purpose: BOS-DATA-05 — make the BOS5-03 offline-eval contract machine-verifiable so
BOS13 (export/replay) and BOS15 (gate wiring) inherit a proven, regression-guarded
requirements substrate. This validates the REAL artifacts authored in BOS5-03 — no
xfail/skip scaffolding, no fictional API. Mirrors the BOS5-02 validation discipline.

Output:
- `.planning/schemas/examples/offline-eval-*.json` (EvalDatasetSpec + PolicyEvalReport + PromotionGateCriteria)
- `tests/planning/test_bos_offline_eval_schema.py` (DATA-05 contract suite)
- `contracts/offline-eval.schema.json` joined to the contract gate via the suite's load+lint check (ACC-16)
</objective>

<execution_context>
@/Users/benjaminmarks/Projects/Voss/.claude/get-shit-done/workflows/execute-plan.md
@/Users/benjaminmarks/Projects/Voss/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

@.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-VALIDATION.md
@.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md
@.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md

<interfaces>
<!-- The artifacts under test were authored in BOS5-03. Load contracts/offline-eval.schema.json
     directly for the exact field names + enums; do NOT re-derive them. The test function names
     and ACC ids below are NORMATIVE (from BOS5-RESEARCH §RQ-6 Extended Validation Architecture);
     the example records validate against the REAL schema. The sibling suite to MATCH in shape is
     tests/planning/test_bos_outcome_schema.py (BOS5-02): load schema via pathlib+json+jsonschema,
     parametrize examples, assert structural properties. -->

Schema under test: contracts/offline-eval.schema.json (Draft 2020-12; authored BOS5-03).
Admissible estimator family (closed enum, BOS5-03): ips | snips | dr | dm | fqe.

DATA-05 contract checks owned by THIS suite (RESEARCH §RQ-6 — names are NORMATIVE):
  test_offline_eval_schema_is_valid   (ACC-08; doubles as the lint/stability gate, ACC-16)
  test_record_types_present           (ACC-09 — EvalDatasetSpec + PolicyEvalReport + PromotionGateCriteria $defs)
  test_eval_dataset_spec_example_validates   (ACC-09)
  test_policy_eval_report_example_validates  (ACC-09)
  test_no_leakage_check_field_present (ACC-11 — outcome_as_of_after_as_of_cutoff present + true on the example)
  test_estimator_family_enum_coverage (ACC-10 — estimator_eligibility items enum = exactly the 5; not a const)
  test_report_estimator_enum          (ACC-10 — PolicyEvalReport.estimator enum = exactly the 5)
  test_policy_eval_report_required_fields (ACC-12 — ci_lower/ci_upper/ci_level/effective_sample_size/bias_flags/guardrail_deltas/gate_result required)
  test_gate_result_shape              (ACC-13 — passed/lift_threshold_met/ci_bound_met/all_hard_gates_non_regressed/blocking_reasons)
  test_guardrail_delta_shape          (guardrail_id/role enum hard_gate|dashboard/candidate_value/baseline_value/delta/regression)
  test_offline_eval_spec_doc_exists   (ACC-15 — docs/BOS5-OFFLINE-EVAL-SPEC.md presence + section grep, comment-filtered)

NOTE on ACC-14: the propensity-field presence test on contracts/decision-ledger.schema.json
(test_propensity_field_on_decision_record) belongs to BOS5-05, which OWNS the decision-ledger
amendment + that test file. This plan does NOT author that test (clean file ownership).

Contract gate (ACC-16): offline-eval.schema.json is hand-authored (docs-first, no pydantic source),
so it canNOT join the pydantic regeneration gate (tests/harness/server/test_contract_drift.py). Its
gate is test_offline_eval_schema_is_valid here, which loads + Draft-2020-12-lints it on every run.
Do NOT add a pydantic model or wire offline-eval.schema.json into export_contract.py (that requires
runtime code, out of scope — same constraint BOS5-02 honored for outcomes.schema.json).

Example record values (RESEARCH §RQ-3 deterministic-phase + §RQ-4):
  EvalDatasetSpec: policy_version="heuristic-v1", as_of_cutoff < outcome_as_of (e.g. cutoff 2026-07-01,
    outcome_as_of 2026-09-29 for a 90d/long horizon), outcome_horizon="long", no_leakage_check all true,
    propensity_coverage_pct=100, estimator_eligibility=["dm"] (deterministic phase; IPS degenerate at
    propensity=1.0), reward_objective_keys=["throughput","quality","rework_cost","flow"].
  PolicyEvalReport: estimator="dm", ope_lift = ope_point_estimate - baseline_point_estimate, ci on the lift,
    bias_flags=["deterministic_propensity"], one guardrail_deltas item (e.g. guardrail_id from outcomes,
    role hard_gate, regression false), gate_result all booleans consistent (passed reflects the 3 checks).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bundle offline-eval example records (.planning/schemas/examples/offline-eval-*.json)</name>
  <files>.planning/schemas/examples/offline-eval-dataset-spec.json, .planning/schemas/examples/offline-eval-policy-report.json, .planning/schemas/examples/offline-eval-promotion-gate-criteria.json</files>
  <read_first>
    - contracts/offline-eval.schema.json (authored in BOS5-03 — examples MUST validate against it; copy the exact required field names + enum values)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md (§RQ-3 deterministic-phase EvalDatasetSpec values; §RQ-4 PolicyEvalReport + guardrail_deltas + gate_result example values; §RQ-5 PromotionGateCriteria [ASSUMED] defaults; DATA-05 Pitfalls 9/10)
    - .planning/schemas/examples/outcome-reward.json (the sibling BOS5-02 example style — record formatting + realistic value conventions to match)
  </read_first>
  <action>
    Create three example records under `.planning/schemas/examples/`, each validating against
    `contracts/offline-eval.schema.json`. Use realistic, internally consistent deterministic-phase values:

    - `offline-eval-dataset-spec.json` (EvalDatasetSpec): v=1, spec_id, created_at, dataset_version
      (e.g. "eval-2026-Q3-v1"), policy_version="heuristic-v1", as_of_cutoff (e.g. "2026-07-01T00:00:00Z"),
      outcome_horizon="long", outcome_as_of STRICTLY LATER than as_of_cutoff (e.g. "2026-09-29T00:00:00Z",
      ~90 days later — proves Pitfall 9 / no-leakage), no_leakage_check with outcome_as_of_after_as_of_cutoff=true,
      all_outcomes_ingest_after_decision=true, verified_by="BOS13-exporter", decision_count, 
      propensity_coverage_pct=100, estimator_eligibility=["dm"], reward_objective_keys=["throughput","quality",
      "rework_cost","flow"], weight_set_version="ws-v1-task-to-agent", decision_types_included=["task_to_agent"].
    - `offline-eval-policy-report.json` (PolicyEvalReport): v=1, report_id, created_at, eval_dataset_spec_id
      (matching the dataset spec_id), candidate_policy_version, baseline_policy_version="heuristic-v1",
      estimator="dm", ope_point_estimate + baseline_point_estimate with ope_lift = the DIFFERENCE of the two
      (Pitfall 10), ci_level=0.95, ci_lower/ci_upper bracketing the lift, effective_sample_size, 
      bias_flags=["deterministic_propensity"], one guardrail_deltas item (guardrail_id, role="hard_gate",
      candidate_value, baseline_value, delta, regression=false), gate_result with passed/lift_threshold_met/
      ci_bound_met/all_hard_gates_non_regressed booleans consistent with the values + blocking_reasons (empty
      when passed=true), reward_objective_keys (matching the dataset), weight_set_version, horizon="long".
    - `offline-eval-promotion-gate-criteria.json` (PromotionGateCriteria): v=1, criteria_id, effective_from,
      min_ope_lift=0.0, min_ci_lower=0.0, ci_level=0.95, min_effective_sample_size=30,
      hard_gate_non_regression_required=true, required_estimators=["dm"].

    Do NOT modify the schema or the spec doc — these examples are CONSUMERS of the contract.
    NO git add/commit/push — the operator commits manually.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/offline-eval.schema.json')); ds=s['\$defs']; vd=jsonschema.Draft202012Validator({**s,'\$ref':'#/\$defs/EvalDatasetSpec'}); vr=jsonschema.Draft202012Validator({**s,'\$ref':'#/\$defs/PolicyEvalReport'}); vg=jsonschema.Draft202012Validator({**s,'\$ref':'#/\$defs/PromotionGateCriteria'}); d=json.load(open('.planning/schemas/examples/offline-eval-dataset-spec.json')); r=json.load(open('.planning/schemas/examples/offline-eval-policy-report.json')); g=json.load(open('.planning/schemas/examples/offline-eval-promotion-gate-criteria.json')); vd.validate(d); vr.validate(r); vg.validate(g); assert d['no_leakage_check']['outcome_as_of_after_as_of_cutoff'] is True, 'no_leakage_check true'; assert d['outcome_as_of']>d['as_of_cutoff'], 'outcome_as_of strictly after cutoff'; assert abs(r['ope_lift']-(r['ope_point_estimate']-r['baseline_point_estimate']))<1e-9, 'ope_lift = point - baseline'; assert r['eval_dataset_spec_id']==d['spec_id'], 'report references dataset spec'; print('3 offline-eval examples validate; no-leakage + lift-definition + FK ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/schemas/examples/` contains the three records `offline-eval-dataset-spec.json`, `offline-eval-policy-report.json`, `offline-eval-promotion-gate-criteria.json`, each validating against its `$defs` shape in `contracts/offline-eval.schema.json`.
    - (ACC-11) The EvalDatasetSpec example carries `no_leakage_check.outcome_as_of_after_as_of_cutoff = true` and `outcome_as_of` strictly later than `as_of_cutoff`.
    - The PolicyEvalReport example sets `ope_lift = ope_point_estimate - baseline_point_estimate`, carries `bias_flags`, one `guardrail_deltas` item (role=hard_gate, regression=false), and a `gate_result` with all three D-16 booleans; `eval_dataset_spec_id` matches the dataset's `spec_id`.
    - The PromotionGateCriteria example carries the [ASSUMED] defaults (min_ope_lift=0.0, min_ci_lower=0.0, ci_level=0.95, min_effective_sample_size=30, hard_gate_non_regression_required=true).
    - `git diff --quiet contracts/ docs/BOS5-OFFLINE-EVAL-SPEC.md` exits 0 (Task 1 adds only example files; schema + doc unchanged) and `git diff --quiet voss/` exits 0.
  </acceptance_criteria>
  <done>Three offline-eval example records exist, each validating against the BOS5-03 schema; the dataset spec proves the no-leakage invariant (outcome_as_of > as_of_cutoff, no_leakage_check true); the report pins ope_lift to point - baseline and references the dataset; the gate-criteria carries the shape defaults; schema + doc untouched.</done>
</task>

<task type="auto">
  <name>Task 2: Author the DATA-05 contract suite + lint-gate offline-eval.schema.json</name>
  <files>tests/planning/test_bos_offline_eval_schema.py</files>
  <read_first>
    - contracts/offline-eval.schema.json + .planning/schemas/examples/offline-eval-*.json (the artifacts under test, from BOS5-03 + Task 1)
    - docs/BOS5-OFFLINE-EVAL-SPEC.md (test_offline_eval_spec_doc_exists greps its section keywords, comment-filtered)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md (§RQ-6 Extended Validation Architecture — the NORMATIVE test names + ACC-08..ACC-16 + the extended test map)
    - tests/planning/test_bos_outcome_schema.py (REFERENCE — the sibling BOS5-02 suite shape to MATCH: pathlib+json+jsonschema loaders, parametrized example round-trips, structural assertions, the load+lint stability gate for a hand-authored schema)
    - tests/harness/server/test_contract_drift.py (REFERENCE ONLY — the pydantic-regeneration gate; understand why offline-eval.schema.json canNOT join it and instead gets a load+lint stability check in this suite)
  </read_first>
  <action>
    Create `tests/planning/test_bos_offline_eval_schema.py` implementing EXACTLY these test functions
    (names are normative, from RESEARCH §RQ-6), loading `contracts/offline-eval.schema.json` and the
    `.planning/schemas/examples/offline-eval-*.json` records via pathlib + json + jsonschema. Reuse the
    existing tests/planning/__init__.py package marker (authored in BOS5-02 — do NOT recreate it):
    - test_offline_eval_schema_is_valid: jsonschema.Draft202012Validator.check_schema on the schema (ACC-08);
      doubles as the lint/stability gate for offline-eval.schema.json (ACC-16 — it canNOT join the pydantic
      regeneration gate).
    - test_record_types_present: EvalDatasetSpec, PolicyEvalReport, PromotionGateCriteria all present as $defs (ACC-09).
    - test_eval_dataset_spec_example_validates: the EvalDatasetSpec example validates against its $defs shape (ACC-09).
    - test_policy_eval_report_example_validates: the PolicyEvalReport example validates against its $defs shape (ACC-09).
    - test_no_leakage_check_field_present: EvalDatasetSpec.no_leakage_check defines outcome_as_of_after_as_of_cutoff;
      the example record has it set true and outcome_as_of > as_of_cutoff (ACC-11).
    - test_estimator_family_enum_coverage: EvalDatasetSpec.estimator_eligibility.items is an enum of EXACTLY
      {ips,snips,dr,dm,fqe} and is NOT a const; a record with an out-of-family estimator_eligibility value fails
      validation (ACC-10).
    - test_report_estimator_enum: PolicyEvalReport.estimator is an enum of EXACTLY the same 5 values; an
      out-of-family estimator value fails validation (ACC-10).
    - test_policy_eval_report_required_fields: PolicyEvalReport $def requires ope_point_estimate, baseline_point_estimate,
      ope_lift, ci_lower, ci_upper, ci_level, effective_sample_size, bias_flags, guardrail_deltas, gate_result (ACC-12).
    - test_gate_result_shape: gate_result $def requires passed, lift_threshold_met, ci_bound_met,
      all_hard_gates_non_regressed, blocking_reasons (ACC-13).
    - test_guardrail_delta_shape: the guardrail_deltas item $def requires guardrail_id, role (enum exactly
      {hard_gate,dashboard}), candidate_value, baseline_value, delta, regression.
    - test_offline_eval_spec_doc_exists: docs/BOS5-OFFLINE-EVAL-SPEC.md exists and (comment-filtered body)
      contains the estimator-family table keywords (ips/snips/dr/dm/fqe), the propensity requirement, the gate
      shape, and a migration-notes section (ACC-15).
    Use `.venv/bin/python -m pytest`. Do NOT add a pydantic model, do NOT modify export_contract.py,
    contracts/* (schema/outcomes/events/decision-ledger), or the example records — this suite only READS them.
    Do NOT recreate tests/planning/__init__.py. NO git add/commit/push.
    After the suite is green, update BOS5-VALIDATION.md: add the ACC-08..ACC-16 rows + this suite to the
    Per-Task Verification Map (DATA-05 section), keeping nyquist_compliant: true.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/planning/test_bos_offline_eval_schema.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/planning/test_bos_offline_eval_schema.py` exists; the suite defines all 11 normative test functions named in RESEARCH §RQ-6 (test_offline_eval_schema_is_valid through test_offline_eval_spec_doc_exists).
    - `.venv/bin/python -m pytest tests/planning/test_bos_offline_eval_schema.py -q` passes with 0 failures/errors.
    - test_offline_eval_schema_is_valid lints contracts/offline-eval.schema.json against Draft 2020-12 (the ACC-16 stability gate for the hand-authored sibling schema).
    - (ACC-10) test_estimator_family_enum_coverage + test_report_estimator_enum prove both estimator fields are enums of exactly {ips,snips,dr,dm,fqe} and reject an out-of-family value (not a const, D-14).
    - (ACC-12) test_policy_eval_report_required_fields proves the report requires all D-14 mandatory properties; (ACC-13) test_gate_result_shape proves the gate_result carries the three D-16 checks; test_guardrail_delta_shape proves the guardrail_deltas item mirrors GuardrailMetricSpec (guardrail_id + role enum).
    - (ACC-11) test_no_leakage_check_field_present proves outcome_as_of_after_as_of_cutoff is present and true with outcome_as_of > as_of_cutoff on the example.
    - (ACC-15) test_offline_eval_spec_doc_exists proves the spec doc exists and contains the estimator table / propensity / gate-shape / migration sections.
    - `git diff --quiet contracts/ docs/ .planning/schemas/examples/offline-eval-dataset-spec.json .planning/schemas/examples/offline-eval-policy-report.json .planning/schemas/examples/offline-eval-promotion-gate-criteria.json` exits 0 (the suite reads, does not modify, those artifacts) and `git diff --quiet voss/` exits 0.
  </acceptance_criteria>
  <done>The DATA-05 contract suite exists and passes against the real BOS5-03 schema + BOS5-04 examples; offline-eval.schema.json is lint-gated on every run (ACC-16); the closed estimator enum (no const), every D-14 mandatory report property, the three D-16 gate-result checks, the guardrail_delta sub-shape, the no-leakage invariant, and the spec-doc presence are all proven; BOS5-VALIDATION.md records the ACC-08..ACC-16 rows.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (no runtime boundary in this phase) | Docs-only contract validation. The suite reads JSON Schema + example records and asserts structural properties; no service, network, or untrusted input at runtime. Threats are data-governance correctness. |
| example/test author -> existing source artifacts | The plan must NOT cross into contracts/offline-eval.schema.json, outcomes/events/decision-ledger schemas, openapi.json, export_contract.py, PROTOCOL.md, or voss/** — examples + tests are new consumers only. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-BOS5-04-01 | Information disclosure | no-leakage regression in eval datasets | mitigate | test_no_leakage_check_field_present asserts outcome_as_of_after_as_of_cutoff present + true and outcome_as_of > as_of_cutoff on the example; makes the no-leakage invariant machine-checked and regression-proof (ACC-11). |
| T-BOS5-04-02 | Tampering | premature single-estimator binding (violates D-14) | mitigate | test_estimator_family_enum_coverage + test_report_estimator_enum fail if either field becomes a const or drops a family member; an out-of-family value is asserted to fail validation. Coverage cannot silently erode (ACC-10). |
| T-BOS5-04-03 | Tampering | gate-result shape erosion (dropping a D-16 check) | mitigate | test_gate_result_shape pins lift_threshold_met/ci_bound_met/all_hard_gates_non_regressed; test_policy_eval_report_required_fields pins the D-14 mandatory props incl. baseline_point_estimate (CI-on-lift, Pitfall 10). A dropped field fails CI (ACC-12/ACC-13). |
| T-BOS5-04-04 | Tampering | silent drift of the hand-authored offline-eval.schema.json | mitigate | test_offline_eval_schema_is_valid loads + Draft-2020-12-lints the schema on every run (ACC-16 gate for a schema with no pydantic source); a malformed edit fails CI. |
| T-BOS5-04-SC | Tampering | package installs | accept | No package-manager installs; `jsonschema` 4.26.0 + pytest already in `.venv`. No legitimacy gate needed. No runtime code in this phase; threats are data-governance, mitigated by contract structure + tests. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/planning/test_bos_offline_eval_schema.py -x -q` — full DATA-05 suite green.
- `.venv/bin/python -m pytest tests/planning/ -x -q` — the full planning suite (BOS5-02 outcome suite + this DATA-05 suite) green.
- `git diff --quiet contracts/ docs/ && git diff --quiet voss/` — no existing source or BOS5-03 artifact modified by this plan (except the BOS5-VALIDATION.md verification-map row append).
</verification>

<success_criteria>
- Three offline-eval example records authored (EvalDatasetSpec + PolicyEvalReport + PromotionGateCriteria), each round-tripping against the schema; the no-leakage invariant present on the dataset spec (ACC-11).
- DATA-05 pytest suite authored under tests/planning/ and passing (ACC-08, ACC-09, ACC-10, ACC-11, ACC-12, ACC-13, ACC-15, ACC-16).
- contracts/offline-eval.schema.json lint-gated on every run (ACC-16).
- BOS5-VALIDATION.md verification map records the ACC-08..ACC-16 rows; nyquist_compliant stays true.
- contracts/* schemas, openapi.json, export_contract.py, PROTOCOL.md, voss/harness/**, and the BOS5-03 artifacts unchanged.
</success_criteria>

<output>
Create `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-04-SUMMARY.md` when done.
</output>
