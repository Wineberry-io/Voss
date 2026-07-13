---
phase: BOS5
plan: 03
type: execute
wave: 1
depends_on: []
files_modified:
  - contracts/offline-eval.schema.json
  - docs/BOS5-OFFLINE-EVAL-SPEC.md
autonomous: true
requirements: [BOS-DATA-05]

must_haves:
  truths:
    - "A reader can determine the exact shape of EvalDatasetSpec (frozen point-in-time eval dataset manifest) and PolicyEvalReport (offline-eval result record) from the contract"
    - "The admissible OPE estimator family is named as a closed enum (ips, snips, dr, dm, fqe) and NO single estimator is bound — both estimator_eligibility and PolicyEvalReport.estimator are constrained to exactly these five values (D-14)"
    - "PolicyEvalReport carries every D-14 mandatory property: ope_point_estimate, baseline_point_estimate, ope_lift, ci_lower/ci_upper/ci_level, effective_sample_size, bias_flags[], guardrail_deltas[], gate_result"
    - "The three-part promotion-gate SHAPE (D-16) is expressed: min_ope_lift threshold, min_ci_lower at ci_level, and hard-gate guardrail non-regression boolean — as PromotionGateCriteria + PolicyEvalReport.gate_result; threshold VALUES are tunable team config, not bound numbers"
    - "EvalDatasetSpec carries a no_leakage_check object making outcome_as_of > as_of_cutoff explicit, so eval datasets cannot conflate the decision-time cutoff with the outcome-observation horizon"
    - "contracts/offline-eval.schema.json joins the contract drift gate via the same hand-authored lint/stability path BOS5-02 established for outcomes.schema.json (no pydantic source, docs-first)"
  artifacts:
    - path: "contracts/offline-eval.schema.json"
      provides: "Normative JSON Schema (Draft 2020-12): EvalDatasetSpec, PolicyEvalReport (incl. guardrail_deltas + gate_result sub-shapes), PromotionGateCriteria, and the closed admissible-estimator enum"
      contains: "https://json-schema.org/draft/2020-12/schema"
      min_lines: 180
    - path: "docs/BOS5-OFFLINE-EVAL-SPEC.md"
      provides: "Normative prose: admissible estimator family table, propensity-logging requirement, EvalDatasetSpec requirements, gate-criteria shape, no-leakage join for eval datasets, migration notes"
      contains: "propensity"
      min_lines: 150
  key_links:
    - from: "docs/BOS5-OFFLINE-EVAL-SPEC.md"
      to: "contracts/offline-eval.schema.json"
      via: "prose spec documents the same record shapes + estimator enum + gate-criteria shape the JSON Schema enforces"
      pattern: "offline-eval.schema.json"
    - from: "contracts/offline-eval.schema.json PolicyEvalReport.guardrail_deltas"
      to: "contracts/outcomes.schema.json GuardrailMetricSpec"
      via: "guardrail_deltas items mirror GuardrailMetricSpec.guardrail_id + role (hard_gate|dashboard)"
      pattern: "guardrail_id"
    - from: "contracts/offline-eval.schema.json EvalDatasetSpec.no_leakage_check"
      to: "outcome_as_of / as_of_cutoff"
      via: "outcome_as_of_after_as_of_cutoff boolean makes the no-leakage invariant explicit in the dataset manifest"
      pattern: "no_leakage_check"
---

<objective>
Author the two NORMATIVE artifacts for the BOS-DATA-05 offline-evaluation
REQUIREMENTS slice: a machine-readable JSON Schema
(`contracts/offline-eval.schema.json`, a sibling to `events.schema.json`,
`decision-ledger.schema.json`, and `outcomes.schema.json`) and a human-readable
spec (`docs/BOS5-OFFLINE-EVAL-SPEC.md`). Together they define what a valid offline
eval dataset must contain (`EvalDatasetSpec`), what an offline eval MUST report
(`PolicyEvalReport`), the admissible OPE estimator family (named, none bound), and
the promotion-gate criteria SHAPE (`PromotionGateCriteria`).

Purpose: BOS-DATA-05 (offline-evaluation requirements for heuristic, contextual
bandit, and later RL policies), defined BEFORE the export/replay machinery (BOS13)
or gate wiring (BOS15) exist. DOCS-FIRST contract slice: requirements, not an eval
harness, exporter, or replay engine. No runtime code, no migrations, no live
services. This plan mirrors the DATA-03/04 schema+doc pattern shipped in BOS5-01.

Output:
- `contracts/offline-eval.schema.json` (source-of-truth machine contract)
- `docs/BOS5-OFFLINE-EVAL-SPEC.md` (normative human spec mirroring the schema)
</objective>

<execution_context>
@/Users/benjaminmarks/Projects/Voss/.claude/get-shit-done/workflows/execute-plan.md
@/Users/benjaminmarks/Projects/Voss/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

@.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md
@.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md
@.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-VALIDATION.md

<interfaces>
<!-- Authoritative inputs from BOS5-RESEARCH.md §BOS-DATA-05 (RQ-1..RQ-6) + CONTEXT.md
     D-13..D-16. Use these directly; do NOT re-derive OPE semantics. The analog patterns
     to MIRROR are: contracts/outcomes.schema.json (the sibling discriminated/record-shape
     style, $defs + required[] + additionalProperties:false on closed sub-objects, $comment
     migration note); contracts/events.schema.json (per-variant const + v:1). The new schema
     is a NEW sibling file under contracts/. Field names below are RECOMMENDED (CONTEXT.md
     Claude's Discretion, A14/A15); the structure + enum membership + the 3-part gate shape
     are NORMATIVE. -->

Admissible OPE estimator family (D-14 — name these, bind NONE; closed enum):
  ips | snips | dr | dm | fqe
  Used as the item enum of EvalDatasetSpec.estimator_eligibility AND as the enum of
  PolicyEvalReport.estimator. Exactly these five values, no const, no single binding
  (RESEARCH RQ-1 + Pitfall 12). ACC-10 checks the enum covers all five and is not a const.

EvalDatasetSpec (RESEARCH RQ-3 — frozen point-in-time eval-dataset manifest record; NOT a runtime event):
  required: spec_id (str) | v (int const 1) | created_at (date-time) | dataset_version (str) |
  policy_version (str) | as_of_cutoff (date-time, T_eval decision cutoff) |
  outcome_horizon (str: short|long or named horizon) | outcome_as_of (date-time, T_outcome) |
  no_leakage_check (object, see below) | decision_count (int) | propensity_coverage_pct (number 0..100) |
  estimator_eligibility (array, items enum ips|snips|dr|dm|fqe) | reward_objective_keys (array of str) |
  weight_set_version (str) | decision_types_included (array of str)
  OPTIONAL: horizon_note (str).
  no_leakage_check (required object): outcome_as_of_after_as_of_cutoff (bool) |
    all_outcomes_ingest_after_decision (bool) | verified_by (str). Makes outcome_as_of > as_of_cutoff
    explicit (RESEARCH RQ-3 + Pitfall 9). ACC-11.

PolicyEvalReport (RESEARCH RQ-4 — offline-eval result record BOS15 reads; NOT a runtime event):
  required: report_id (str) | v (int const 1) | created_at (date-time) | eval_dataset_spec_id (str, FK -> EvalDatasetSpec.spec_id) |
  candidate_policy_version (str) | baseline_policy_version (str) | estimator (enum ips|snips|dr|dm|fqe) |
  ope_point_estimate (number) | baseline_point_estimate (number) | ope_lift (number, = point - baseline; RESEARCH Pitfall 10/A15) |
  ci_level (number) | ci_lower (number) | ci_upper (number) | effective_sample_size (number) |
  bias_flags (array of str) | guardrail_deltas (array, item shape below) | gate_result (object, shape below) |
  reward_objective_keys (array of str) | weight_set_version (str) | horizon (str)
  OPTIONAL: notes (str).
  guardrail_deltas item (RESEARCH RQ-4; mirrors outcomes.schema.json GuardrailMetricSpec):
    required guardrail_id (str) | role (enum hard_gate|dashboard) | candidate_value (number) |
    baseline_value (number) | delta (number) | regression (bool). ACC checks role enum + the 6 fields.
  gate_result (RESEARCH RQ-4/RQ-5; ties to D-16):
    required passed (bool) | lift_threshold_met (bool) | ci_bound_met (bool) |
    all_hard_gates_non_regressed (bool) | blocking_reasons (array of str). ACC-13 (the 3 D-16 checks).

PromotionGateCriteria (RESEARCH RQ-5 — D-16 gate-criteria SHAPE; versioned team-config record):
  required: criteria_id (str) | v (int const 1) | effective_from (date-time) |
  min_ope_lift (number) | min_ci_lower (number) | ci_level (number) |
  min_effective_sample_size (number) | hard_gate_non_regression_required (bool) |
  required_estimators (array, items enum ips|snips|dr|dm|fqe)
  OPTIONAL: notes (str).
  Threshold VALUES are tunable team config ([ASSUMED] defaults: min_ope_lift 0.0, min_ci_lower 0.0,
  ci_level 0.95, min_effective_sample_size 30). Lock the SHAPE, not the numbers (D-16; A11/A12/A13).
  The 3-part gate (RESEARCH RQ-5): (1) min_ope_lift threshold, (2) min_ci_lower at ci_level CI bound,
  (3) hard_gate_non_regression_required boolean (every hard_gate guardrail must have regression:false).

Versioning (mirror outcomes.schema.json / PROTOCOL.md `v` + $comment migration note):
  schema_version 1; additive changes (new estimator filling the family, new named horizon, new gate
  field) do NOT bump; breaking changes bump + migration note in the doc.

Contract gate (ACC-16): the existing drift gate (tests/harness/server/test_contract_drift.py) REGENERATES
events.schema.json/openapi.json from pydantic models. offline-eval.schema.json is hand-authored (docs-first,
no pydantic source), so it canNOT join that regeneration gate — exactly like outcomes.schema.json. Its
"gate" is the load+lint stability check in the BOS5-04 pytest suite. This plan does NOT add a pydantic model
or wire export_contract.py; it only authors the schema + doc. The actual lint test is authored in BOS5-04.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author contracts/offline-eval.schema.json (normative JSON Schema, Draft 2020-12)</name>
  <files>contracts/offline-eval.schema.json</files>
  <read_first>
    - contracts/outcomes.schema.json (the SIBLING pattern to mirror: $defs of record shapes, required[] arrays, additionalProperties:false on closed sub-objects, the $comment migration note, GuardrailMetricSpec.role enum {hard_gate,dashboard} + guardrail_id that guardrail_deltas mirrors)
    - contracts/events.schema.json (per-variant const + v:1 versioning convention)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md (§BOS-DATA-05 RQ-1 estimator family enum; RQ-3 EvalDatasetSpec + no_leakage_check fields; RQ-4 PolicyEvalReport + guardrail_deltas + gate_result shapes; RQ-5 PromotionGateCriteria; Pitfalls 9/10/11/12)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md (D-13..D-16 verbatim — cite the driving D-ID per construct)
  </read_first>
  <action>
    Create `contracts/offline-eval.schema.json` as a JSON Schema Draft 2020-12 document
    (`"$schema": "https://json-schema.org/draft/2020-12/schema"`, versioned `"$id"`
    `https://voss.dev/contracts/offline-eval.schema.json`, a `description` noting `v: 1` and the
    DATA-05 / D-13..D-16 scope). Build, per the <interfaces> block and the driving decisions:

    (a) A shared `$defs.AdmissibleEstimator` (or an inline `enum`) listing EXACTLY ips, snips, dr, dm, fqe
        (D-14). It MUST be an `enum` of all five values, NOT a `const` and NOT a single binding (Pitfall 12).
        Reference it from both EvalDatasetSpec.estimator_eligibility.items and PolicyEvalReport.estimator.
    (b) `$defs.EvalDatasetSpec` (D-13/RQ-3): required spec_id, v(const 1), created_at, dataset_version,
        policy_version, as_of_cutoff, outcome_horizon, outcome_as_of, no_leakage_check, decision_count,
        propensity_coverage_pct, estimator_eligibility (array, items = the admissible-estimator enum),
        reward_objective_keys (array of string), weight_set_version, decision_types_included (array of string);
        OPTIONAL horizon_note. Timestamps use `format: date-time`. `additionalProperties: false`.
    (c) `$defs.NoLeakageCheck` referenced by EvalDatasetSpec.no_leakage_check (RQ-3 + Pitfall 9): required
        outcome_as_of_after_as_of_cutoff (boolean), all_outcomes_ingest_after_decision (boolean),
        verified_by (string). This makes outcome_as_of > as_of_cutoff explicit in the manifest. `additionalProperties: false`.
    (d) `$defs.GuardrailDelta` referenced by PolicyEvalReport.guardrail_deltas.items (RQ-4): required
        guardrail_id (string), role (enum EXACTLY ["hard_gate","dashboard"] — mirror outcomes.schema.json
        GuardrailMetricSpec.role), candidate_value (number), baseline_value (number), delta (number),
        regression (boolean). `additionalProperties: false`.
    (e) `$defs.GateResult` referenced by PolicyEvalReport.gate_result (RQ-4/RQ-5, D-16): required
        passed (boolean), lift_threshold_met (boolean), ci_bound_met (boolean),
        all_hard_gates_non_regressed (boolean), blocking_reasons (array of string). These three booleans
        (lift_threshold_met, ci_bound_met, all_hard_gates_non_regressed) are the 3-part D-16 gate (ACC-13).
        `additionalProperties: false`.
    (f) `$defs.PolicyEvalReport` (D-13/D-14/RQ-4): required report_id, v(const 1), created_at,
        eval_dataset_spec_id, candidate_policy_version, baseline_policy_version, estimator (the admissible enum),
        ope_point_estimate, baseline_point_estimate, ope_lift, ci_level, ci_lower, ci_upper,
        effective_sample_size, bias_flags (array of string), guardrail_deltas (array of GuardrailDelta),
        gate_result (GateResult), reward_objective_keys (array of string), weight_set_version, horizon;
        OPTIONAL notes. Add a `description` on ope_lift pinning it to ope_point_estimate - baseline_point_estimate
        and noting the CI (ci_lower/ci_upper) is on the LIFT, not the absolute estimate (Pitfall 10/A15).
        `additionalProperties: false`.
    (g) `$defs.PromotionGateCriteria` (D-16/RQ-5): required criteria_id, v(const 1), effective_from,
        min_ope_lift (number), min_ci_lower (number), ci_level (number), min_effective_sample_size (number),
        hard_gate_non_regression_required (boolean), required_estimators (array, items = the admissible enum);
        OPTIONAL notes. Do NOT bake threshold VALUES into the schema as consts — only the SHAPE (D-16 scope
        fence; values are team config). `additionalProperties: false`.
    (h) A `$comment` migration note (mirror outcomes.schema.json / PROTOCOL.md `v`): "schema_version=1;
        additive changes (new admissible estimator, new named outcome horizon, new gate criterion field) do
        NOT bump; breaking changes increment + add a migration note in docs/BOS5-OFFLINE-EVAL-SPEC.md."

    Do NOT bind a single estimator anywhere (D-14). Do NOT author an exporter, replay harness, or runtime
    code (that is BOS13). Do NOT modify contracts/outcomes.schema.json, contracts/events.schema.json,
    contracts/decision-ledger.schema.json, contracts/openapi.json, PROTOCOL.md, export_contract.py, or any
    voss/harness/** source. NO git add/commit/push — the operator commits manually.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/offline-eval.schema.json')); jsonschema.Draft202012Validator.check_schema(s); d=s.get('\$defs',{}); assert {'EvalDatasetSpec','PolicyEvalReport','PromotionGateCriteria'} <= set(d), 'three record \$defs present'; blob=json.dumps(s); fam={'ips','snips','dr','dm','fqe'}; assert all(('\"%s\"'%e) in blob for e in fam), 'all 5 estimators named'; assert '\"const\": \"doubly_robust\"' not in blob and '\"const\": \"dr\"' not in blob, 'no single estimator bound'; assert all(k in blob for k in ['no_leakage_check','outcome_as_of_after_as_of_cutoff','ope_lift','baseline_point_estimate','ci_lower','ci_upper','ci_level','effective_sample_size','bias_flags','guardrail_deltas','gate_result']), 'D-14 mandatory props'; assert all(k in blob for k in ['lift_threshold_met','ci_bound_met','all_hard_gates_non_regressed']), 'D-16 3-part gate'; assert all(k in blob for k in ['min_ope_lift','min_ci_lower','min_effective_sample_size','hard_gate_non_regression_required']), 'PromotionGateCriteria shape'; print('offline-eval.schema.json valid Draft2020-12 + estimator family + no-leakage + gate shape')"</automated>
  </verify>
  <acceptance_criteria>
    - (ACC-08) `contracts/offline-eval.schema.json` parses as JSON and passes `jsonschema.Draft202012Validator.check_schema` (lints clean against the Draft 2020-12 meta-schema).
    - (ACC-09 / partial) `EvalDatasetSpec`, `PolicyEvalReport`, and `PromotionGateCriteria` are all present as named `$defs`.
    - (ACC-10) The admissible-estimator enum contains EXACTLY {ips, snips, dr, dm, fqe} and is referenced by both `EvalDatasetSpec.estimator_eligibility.items` and `PolicyEvalReport.estimator`; it is an `enum`, NOT a `const`, and no single estimator is bound (D-14).
    - (ACC-11) `EvalDatasetSpec.no_leakage_check` is a required object carrying `outcome_as_of_after_as_of_cutoff` (boolean), `all_outcomes_ingest_after_decision` (boolean), and `verified_by` (string).
    - (ACC-12) `PolicyEvalReport` requires all D-14 mandatory properties: `ope_point_estimate`, `baseline_point_estimate`, `ope_lift`, `ci_lower`, `ci_upper`, `ci_level`, `effective_sample_size`, `bias_flags`, `guardrail_deltas`, `gate_result`; `ope_lift` description pins it to `ope_point_estimate - baseline_point_estimate` (Pitfall 10).
    - (ACC-13) `PolicyEvalReport.gate_result` carries the three D-16 gate checks: `lift_threshold_met`, `ci_bound_met`, `all_hard_gates_non_regressed` (plus `passed`, `blocking_reasons`); `guardrail_deltas` items carry `guardrail_id`, `role` enum {hard_gate, dashboard}, `candidate_value`, `baseline_value`, `delta`, `regression`.
    - `PromotionGateCriteria` requires `min_ope_lift`, `min_ci_lower`, `ci_level`, `min_effective_sample_size`, `hard_gate_non_regression_required`, `required_estimators`; no threshold VALUE is hardcoded as a const (D-16 shape-only).
    - `git diff --quiet contracts/outcomes.schema.json contracts/events.schema.json contracts/decision-ledger.schema.json contracts/openapi.json PROTOCOL.md` exits 0 and `git diff --quiet voss/` exits 0 (no existing contract or harness source touched).
  </acceptance_criteria>
  <done>The offline-eval JSON Schema exists, lints clean against Draft 2020-12, defines EvalDatasetSpec (with the explicit no_leakage_check), PolicyEvalReport (all D-14 mandatory properties + guardrail_deltas + the 3-part D-16 gate_result), and PromotionGateCriteria (shape only); names the admissible estimator family as a closed 5-value enum binding none (D-14); carries a PROTOCOL.md-style migration note; no existing source files modified.</done>
</task>

<task type="auto">
  <name>Task 2: Author docs/BOS5-OFFLINE-EVAL-SPEC.md (normative prose + tables)</name>
  <files>docs/BOS5-OFFLINE-EVAL-SPEC.md</files>
  <read_first>
    - contracts/offline-eval.schema.json (the artifact authored in Task 1 — the spec MUST mirror its record shapes, the estimator enum, the gate-criteria shape, and the no_leakage_check fields)
    - docs/BOS5-OUTCOME-REWARD-SPEC.md (the SIBLING DATA-03/04 doc — match its structure, section style, D-ID citation convention, and migration-notes section)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md (§BOS-DATA-05 RQ-1 admissible-estimator table; RQ-2 propensity requirement prose; RQ-3 EvalDatasetSpec requirements; RQ-5 three-part gate anatomy; §Point-in-Time-Correct Outcome Joins for the no-leakage eval-dataset join; DATA-05 Pitfalls 8-12)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md (D-13..D-16 verbatim, to cite by ID in each section)
    - .planning/PROJECT.md (§Safety — "no autonomy increase without offline eval + guardrails + human approval", the governance framing for the gate-criteria section)
  </read_first>
  <action>
    Create `docs/BOS5-OFFLINE-EVAL-SPEC.md` as the normative human spec, referencing
    `contracts/offline-eval.schema.json` as the machine source of truth. Sections (each citing the
    driving D-ID; mirror the schema exactly):

    1. Scope + record overview (D-13) — state BOS5 owns the offline-eval REQUIREMENTS contract only;
       BOS13 builds the export/replay machinery, BOS15 wires the gate enforcement. Name the two record
       shapes EvalDatasetSpec + PolicyEvalReport + the PromotionGateCriteria config record. Reference the
       sibling outcomes.schema.json (GuardrailMetricSpec the guardrail_deltas mirror).
    2. Admissible OPE estimator family (D-14) — a table of ips / snips / dr / dm / fqe: abbreviation,
       policy class, what each requires from logged data, what each reports, key property (from RESEARCH
       RQ-1). State explicitly that BOS5 NAMES the family and BINDS NONE; BOS13 picks per policy class.
       Use the word "estimator". List the four mandatory reported properties (point estimate, CI/uncertainty
       bound, effective sample size, bias disclosure) and map each to its PolicyEvalReport field.
    3. Propensity-logging requirement (D-15, cross-phase) — prose stating OPE is impossible unless the
       behavior policy's action propensity + exploration metadata is logged at decision time on the BOS4
       decision record; currently deterministic (argmax -> propensity=1.0) but the field MUST exist now so
       historical decisions stay evaluable. Cross-reference the BOS5-05 BOS4-follow-up plan that amends
       contracts/decision-ledger.schema.json with policy_context. Use the word "propensity".
    4. EvalDatasetSpec requirements (D-13) — a table/list of the required fields and what a valid frozen
       point-in-time eval dataset must contain; explain as_of_cutoff (T_eval decision boundary) vs
       outcome_as_of (T_outcome observation boundary) and why they MUST differ (Pitfall 9); document the
       no_leakage_check object and the rule outcome_as_of > as_of_cutoff. Use the phrase "no leakage" and
       the word "as-of". Explain estimator_eligibility (which estimators the dataset supports) and
       propensity_coverage_pct (must be 100% for IPS-family).
    5. PolicyEvalReport + gate-criteria shape (D-14/D-16) — document the report fields, then the three-part
       promotion gate: (a) min_ope_lift threshold, (b) min_ci_lower at ci_level CI bound on the LIFT (not the
       absolute estimate, Pitfall 10), (c) hard-gate guardrail non-regression boolean (every hard_gate
       GuardrailMetricSpec must have regression:false). State the threshold VALUES are tunable team config
       ([ASSUMED] defaults min_ope_lift=0.0, min_ci_lower=0.0, ci_level=0.95, min_effective_sample_size=30);
       BOS5 locks the SHAPE, BOS15 wires enforcement. Note ESS as a gate precondition (Pitfall 11). Use the
       word "gate".
    6. Versioning & migration notes — schema_version=1; additive vs breaking rules (mirror outcomes.schema.json
       / PROTOCOL.md); note the BOS4 follow-up (policy_context) is itself a versioned additive amendment.
       Use the word "migration".

    Do NOT author runtime code or an eval harness/exporter. Do NOT modify contracts/*, PROTOCOL.md, or any
    voss/harness/** source. NO git add/commit/push — the operator commits manually.
  </action>
  <verify>
    <automated>.venv/bin/python -c "t=open('docs/BOS5-OFFLINE-EVAL-SPEC.md').read(); body='\n'.join(l for l in t.splitlines() if not l.strip().startswith('#')); assert 'offline-eval.schema.json' in t, 'links machine schema'; assert all(e in t for e in ['ips','snips','dr','dm','fqe']), 'all 5 estimators in table'; assert all(s in body.lower() for s in ['estimator','propensity','no leakage','as-of','gate','migration']), 'required section keywords'; assert all(k in t for k in ['EvalDatasetSpec','PolicyEvalReport','policy_context','no_leakage_check']), 'record + cross-phase refs'; assert 'as_of_cutoff' in t and 'outcome_as_of' in t, 'cutoff vs outcome-horizon distinction'; assert all(k in t for k in ['min_ope_lift','min_ci_lower','hard_gate']), '3-part gate shape'; print('offline-eval spec content checks pass')"</automated>
  </verify>
  <acceptance_criteria>
    - (ACC-15) `docs/BOS5-OFFLINE-EVAL-SPEC.md` exists, references `contracts/offline-eval.schema.json`, and contains: the admissible estimator family table (all of ips/snips/dr/dm/fqe), the propensity-logging requirement prose, the gate-criteria shape, a no-leakage join explanation for eval datasets (as_of_cutoff vs outcome_as_of), and a migration-notes section (keywords estimator / propensity / no leakage / as-of / gate / migration all present in body prose).
    - The doc states BOS5 NAMES the estimator family and BINDS NONE (D-14); BOS13 builds export/replay; BOS15 wires the gate.
    - The propensity section cross-references the BOS5-05 BOS4-follow-up amendment of `contracts/decision-ledger.schema.json` (policy_context) and states propensity=1.0 for current deterministic policies with the field still required.
    - The gate section documents the three D-16 parts (min_ope_lift, min_ci_lower at ci_level on the LIFT, hard-gate non-regression boolean) and states threshold VALUES are tunable team config / BOS5 locks the shape.
    - `git diff --quiet contracts/ PROTOCOL.md` exits 0 and `git diff --quiet voss/` exits 0 (Task 2 authors only the doc; it does not alter the schema).
  </acceptance_criteria>
  <done>The offline-eval spec exists, mirrors the schema's record shapes + estimator enum + gate-criteria shape, contains the admissible-estimator table, the propensity-logging requirement (with the BOS5-05 cross-phase reference), the EvalDatasetSpec no-leakage join (as_of_cutoff vs outcome_as_of), the three-part D-16 gate shape, and PROTOCOL.md-style versioning/migration notes; no existing source files modified.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (no runtime boundary in this phase) | Docs-only contract phase: no code executes, no inputs are processed at runtime. Threats are data-governance correctness, not classic appsec. |
| future BOS13 exporter/replay -> eval dataset + report (BOS13 era) | The schema IS the validation contract for that future boundary; BOS5 only authors the contract. The no_leakage_check + propensity requirement are the structural guarantees. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-BOS5-03-01 | Information disclosure | outcome leakage into eval datasets (outcome_as_of conflated with as_of_cutoff) | mitigate | PRIMARY modeled threat. Structural mitigation: EvalDatasetSpec.no_leakage_check makes outcome_as_of > as_of_cutoff explicit and required (RESEARCH Pitfall 9). Verified by BOS5-04 test_no_leakage_check_field_present + ACC-11 on the example record. |
| T-BOS5-03-02 | Tampering / Repudiation | premature binding of a single OPE estimator (violates D-14, masks bias) | mitigate | The admissible-estimator enum names exactly {ips,snips,dr,dm,fqe} and is NOT a const; bias_flags[] is a mandatory PolicyEvalReport field (bias disclosure). Verified by BOS5-04 ACC-10 (estimator enum coverage, not a const). |
| T-BOS5-03-03 | Tampering | gate bypass via CI-on-absolute-estimate instead of CI-on-lift, or skipping ESS | mitigate | ope_lift is pinned to point - baseline; ci_lower/ci_upper are on the LIFT (Pitfall 10); PromotionGateCriteria.min_effective_sample_size makes ESS a gate precondition (Pitfall 11). gate_result.all_hard_gates_non_regressed is a hard boolean (D-16). |
| T-BOS5-03-04 | Information disclosure | PII / individual-ranking fields in eval/report records | mitigate | Records key off policy_version + dataset_version + entity-derived aggregates, NOT engineer name/email; reward_objective_keys are team-level objectives. Schema introduces no engineer_id field. |
| T-BOS5-03-05 | Tampering | existing contract / harness source (outcomes/events/decision-ledger schemas, openapi.json, PROTOCOL.md, voss/**) | mitigate | Acceptance criteria assert `git diff --quiet` for those paths; BOS5-03 authors only the NEW sibling schema + doc. No exporter, replay harness, migrations, or runtime code. |
| T-BOS5-03-SC | Tampering | package installs | accept | No package-manager installs in this plan; `jsonschema` 4.26.0 already present in `.venv`. No legitimacy gate needed. Threats are data-governance, mitigated by contract structure. |
</threat_model>

<verification>
Run the per-task automated checks. After both tasks:
- `.venv/bin/python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/offline-eval.schema.json')))"` — schema lints clean (ACC-08).
- Both artifacts exist; the doc references the schema; all 5 estimators + the 3-part gate shape present in both (ACC-10/ACC-13/ACC-15).
- `git diff --quiet contracts/outcomes.schema.json contracts/events.schema.json contracts/decision-ledger.schema.json contracts/openapi.json PROTOCOL.md && git diff --quiet voss/` — no existing source modified.
</verification>

<success_criteria>
- `contracts/offline-eval.schema.json` authored, lints clean (Draft 2020-12), defines EvalDatasetSpec (+ no_leakage_check), PolicyEvalReport (all D-14 mandatory props + guardrail_deltas + 3-part D-16 gate_result), and PromotionGateCriteria (shape only); names the admissible estimator family as a closed 5-value enum binding none (D-14).
- `docs/BOS5-OFFLINE-EVAL-SPEC.md` authored, mirrors the schema, contains the estimator table, propensity-logging requirement (+ BOS5-05 cross-ref), EvalDatasetSpec no-leakage join, three-part gate shape, and migration notes.
- BOS-DATA-05 contract artifacts exist and are internally consistent (ACC-08, ACC-10, ACC-11, ACC-12, ACC-13, ACC-15 checkable on these artifacts).
- contracts/outcomes.schema.json, events.schema.json, decision-ledger.schema.json, openapi.json, PROTOCOL.md, and voss/harness/** unchanged.
</success_criteria>

<output>
Create `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-03-SUMMARY.md` when done.
</output>
