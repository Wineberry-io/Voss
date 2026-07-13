---
phase: BOS5
plan: 05
type: execute
wave: 2
depends_on: ["BOS5-03"]
files_modified:
  - contracts/decision-ledger.schema.json
  - .planning/schemas/examples/decision-policy-context.json
  - tests/planning/test_bos_decision_policy_context.py
autonomous: true
requirements: [BOS-DATA-05]

must_haves:
  truths:
    - "The BOS4 decision-ledger schema carries a required policy_context object with propensity (number 0..1), action_space (array), exploration_flag (boolean), and policy_version (string) — so OPE is possible later (D-15)"
    - "The amendment is ADDITIVE and does not break the schema: additionalProperties:false still holds, all six closed payload $defs and the existing twelve required fields are untouched, and the discriminated-union pattern is intact"
    - "A deterministic example decision record (propensity=1.0, exploration_flag=false, policy_version='heuristic-v1') validates against the amended schema, proving the log-now-to-eval-later requirement is satisfiable today"
    - "An automated presence test (ACC-14) proves policy_context is present AND required (not optional) on the decision-ledger schema, guarding against the field being dropped or made optional"
  artifacts:
    - path: "contracts/decision-ledger.schema.json"
      provides: "BOS4 decision record amended (additively) with a required policy_context {propensity, action_space, exploration_flag, policy_version} for OPE propensity logging (D-15)"
      contains: "policy_context"
      min_lines: 380
    - path: ".planning/schemas/examples/decision-policy-context.json"
      provides: "Deterministic example decision record (propensity=1.0) validating against the amended schema"
      contains: "policy_context"
      min_lines: 0
    - path: "tests/planning/test_bos_decision_policy_context.py"
      provides: "ACC-14 presence test: policy_context present + required with the four sub-fields; deterministic example round-trips"
      contains: "policy_context"
      min_lines: 30
  key_links:
    - from: "contracts/offline-eval.schema.json (BOS5-03)"
      to: "contracts/decision-ledger.schema.json policy_context.propensity"
      via: "EvalDatasetSpec.propensity_coverage_pct requires propensity logged on every decision record"
      pattern: "propensity"
    - from: "tests/planning/test_bos_decision_policy_context.py"
      to: "contracts/decision-ledger.schema.json"
      via: "asserts policy_context is in properties AND in required, with the four sub-fields"
      pattern: "policy_context"
---

<objective>
CROSS-PHASE BOS4 FOLLOW-UP (driven by BOS5 DATA-05 D-15). Additively amend the
already-shipped BOS4 decision-ledger contract
(`contracts/decision-ledger.schema.json`) with a required `policy_context` field
carrying the behavior policy's action propensity + exploration metadata at decision
time. Off-policy evaluation (OPE, the BOS5 DATA-05 requirement) is impossible unless
this is logged at decision time — even though current policies are deterministic
(argmax -> propensity=1.0), the field MUST exist now so historical decisions stay
evaluable when policies become stochastic. This is the log-now-to-eval-later
counterpart of the BOS4 D-04 no-leakage guard.

Purpose: BOS-DATA-05 D-15 — the propensity-logging requirement at its source (the
BOS4 decision record). BOS4 is already executed, so this is an explicit, clearly
flagged additive amendment to a shipped contract, NOT a side-effect of another plan.
DOCS-FIRST: a schema amendment + example + presence test. No runtime code, no
migration script, no live writer.

Output:
- `contracts/decision-ledger.schema.json` amended with required `policy_context`
- `.planning/schemas/examples/decision-policy-context.json` (deterministic example, propensity=1.0)
- `tests/planning/test_bos_decision_policy_context.py` (ACC-14 presence test)
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
@.planning/phases/BOS4-decision-ledger-schema/BOS4-CONTEXT.md

<interfaces>
<!-- This plan AMENDS contracts/decision-ledger.schema.json (a shipped BOS4 artifact). Load it
     directly for the exact existing structure; the amendment is ADDITIVE only. The field shape
     below is from BOS5-RESEARCH §RQ-2 (RecQ-2 confirmed the field is ABSENT today by codebase read).
     Field names are RECOMMENDED (CONTEXT.md Claude's Discretion, A14); the four sub-fields + their
     types + the required-ness are NORMATIVE (D-15). -->

Current decision-ledger.schema.json (BOS4, shipped):
  top-level object, additionalProperties:false, twelve required fields (decision_id, decision_type,
  created_at, as_of, feature_snapshot, entity_ref, autonomy_band, recommended_action, human_verdict,
  actual_action, rationale, payload). $defs holds the six closed payload shapes. decision_type
  discriminator + oneOf over the six payload $refs. NO propensity / policy_context field today.

policy_context (D-15 additive amendment — top-level field, NOT inside payload):
  type object, additionalProperties:false, required all four:
    propensity        — number, minimum 0.0, maximum 1.0 (P(action|context; behavior_policy) at decision
                        time; deterministic argmax => 1.0; epsilon-greedy => the exploration probability)
    action_space      — array of string (candidate action ids considered; deterministic single-option =>
                        [chosen_action_id]; enables ESS + importance-weight clipping in OPE)
    exploration_flag  — boolean (true iff this was a non-greedy exploration action; false for all current
                        deterministic decisions)
    policy_version    — string (the behavior policy version that produced this decision; deterministic =>
                        e.g. "heuristic-v1"; learned (BOS13+) => a versioned model/policy id)
  Add policy_context to the top-level `properties` block AND to the top-level `required` array (D-15:
  required, not optional — Pitfall 8). Add a $comment / description noting this is the BOS5 DATA-05 D-15
  additive amendment and a migration note (the schema gains a required field; mirror the PROTOCOL.md `v`
  convention used by the sibling contracts).

Deterministic example (RESEARCH §RQ-2):
  policy_context = { "propensity": 1.0, "action_space": ["claude-opus-4"], "exploration_flag": false,
                     "policy_version": "heuristic-v1" }
  The full example decision record must also carry the twelve existing required fields with valid values
  (a task_to_agent decision is the natural fit; reuse the BOS4 payload shape).

ACC-14 (RESEARCH §RQ-6): contracts/decision-ledger.schema.json policy_context present with propensity
(number 0..1), action_space (array), exploration_flag (boolean), policy_version (string). This plan OWNS
the ACC-14 test (test_propensity_field_on_decision_record); BOS5-04 does NOT author it (clean file ownership).

Do NOT add a runtime writer, a migration script, or a pydantic model. Do NOT touch the six payload $defs,
the discriminator/oneOf, or any of the twelve existing required fields. Do NOT modify
contracts/offline-eval.schema.json, contracts/outcomes.schema.json, contracts/events.schema.json,
contracts/openapi.json, export_contract.py, PROTOCOL.md, or any voss/harness/** source.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Additively amend decision-ledger.schema.json with required policy_context + presence test</name>
  <files>contracts/decision-ledger.schema.json, tests/planning/test_bos_decision_policy_context.py</files>
  <behavior>
    - test_propensity_field_on_decision_record: policy_context is in the schema's top-level `properties` AND in the top-level `required` array (present AND required, not optional — ACC-14).
    - policy_context.properties carries propensity (type number, minimum 0.0, maximum 1.0), action_space (type array, items string), exploration_flag (type boolean), policy_version (type string); policy_context.required lists all four; policy_context.additionalProperties is false.
    - The amended schema still lints clean against Draft 2020-12 and the six payload $defs + discriminator/oneOf + the twelve existing required fields are unchanged (additive-only).
    - A record missing policy_context FAILS validation; a record with policy_context but missing propensity FAILS validation (proves required-ness, Pitfall 8).
  </behavior>
  <read_first>
    - contracts/decision-ledger.schema.json (the shipped BOS4 schema to amend — read the full current structure: top-level properties, the twelve required fields, the six payload $defs, the discriminator/oneOf; the amendment is ADDITIVE only)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md (§RQ-2 the exact policy_context shape + deterministic-population values + Pitfall 8 required-not-optional)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md (D-15 verbatim — the cross-phase mandate)
    - contracts/outcomes.schema.json (the sibling $comment migration-note convention to mirror for the amendment note)
    - tests/planning/test_bos_outcome_schema.py (REFERENCE — the sibling suite shape: pathlib+json+jsonschema schema loader + structural assertions; tests/planning/__init__.py already exists, do NOT recreate it)
  </read_first>
  <action>
    Amend `contracts/decision-ledger.schema.json` ADDITIVELY (D-15):
    (a) Add a top-level `policy_context` property: type object, additionalProperties:false, with a
        description noting it is the BOS5 DATA-05 D-15 additive amendment for OPE propensity logging
        (propensity=1.0 for current deterministic argmax policies; field required so historical decisions
        stay evaluable when policies become stochastic). Sub-properties: propensity (number, minimum 0.0,
        maximum 1.0), action_space (array, items type string), exploration_flag (boolean),
        policy_version (string). required: [propensity, action_space, exploration_flag, policy_version].
    (b) Add `policy_context` to the top-level `required` array (D-15: required, not optional — Pitfall 8).
    (c) Add/extend the top-level description (or a `$comment`) with a migration note: the schema gains a
        required policy_context field for OPE (BOS5 DATA-05 D-15); this is an additive amendment; mirror the
        PROTOCOL.md `v` + migration-note convention used by the sibling contracts.
    Do NOT alter the six payload $defs, the decision_type discriminator/oneOf, or any of the twelve existing
    required fields. The change is additive only — additionalProperties:false at top level must still hold.

    Then create `tests/planning/test_bos_decision_policy_context.py` (reuse the existing
    tests/planning/__init__.py marker) implementing test_propensity_field_on_decision_record per the
    <behavior> block: load contracts/decision-ledger.schema.json; assert policy_context is in properties AND
    in required; assert its four sub-fields + types (propensity number 0..1, action_space array, exploration_flag
    boolean, policy_version string) + policy_context.required covers all four + additionalProperties false;
    assert the schema lints clean (Draft 2020-12); assert a record missing policy_context fails validation and
    a record missing propensity (within policy_context) fails validation. Use `.venv/bin/python -m pytest`.
    Do NOT add a runtime writer/migration/pydantic model. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/decision-ledger.schema.json')); jsonschema.Draft202012Validator.check_schema(s); pc=s['properties']['policy_context']; assert 'policy_context' in s['required'], 'policy_context required at top level'; assert pc['additionalProperties'] is False; props=pc['properties']; assert props['propensity']['type']=='number' and props['propensity']['minimum']==0.0 and props['propensity']['maximum']==1.0, 'propensity number 0..1'; assert props['action_space']['type']=='array' and props['exploration_flag']['type']=='boolean' and props['policy_version']['type']=='string'; assert set(pc['required'])=={'propensity','action_space','exploration_flag','policy_version'}, 'all four required'; assert len(s['\$defs'])==6, 'six payload \$defs untouched'; print('policy_context required additive amendment + payload defs intact')" && .venv/bin/python -m pytest tests/planning/test_bos_decision_policy_context.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - (ACC-14) `contracts/decision-ledger.schema.json` carries a `policy_context` property with `propensity` (number, minimum 0.0, maximum 1.0), `action_space` (array of string), `exploration_flag` (boolean), `policy_version` (string); `policy_context` is in the top-level `required` array (required, not optional).
    - The amendment is additive: the schema still lints clean against Draft 2020-12, top-level `additionalProperties` is still false, the six payload `$defs` are unchanged (count == 6), and the twelve pre-existing required fields are all still present.
    - `tests/planning/test_bos_decision_policy_context.py` exists and `.venv/bin/python -m pytest tests/planning/test_bos_decision_policy_context.py -q` passes; it asserts policy_context present + required + the four sub-fields, and that a record missing policy_context (or missing propensity) fails validation.
    - `git diff --quiet contracts/offline-eval.schema.json contracts/outcomes.schema.json contracts/events.schema.json contracts/openapi.json PROTOCOL.md` exits 0 and `git diff --quiet voss/` exits 0 (only decision-ledger.schema.json amended; no other contract or harness source touched).
  </acceptance_criteria>
  <done>contracts/decision-ledger.schema.json carries a required, additive policy_context {propensity 0..1, action_space, exploration_flag, policy_version} for OPE propensity logging (D-15); the six payload $defs + discriminator + twelve existing required fields are untouched; the ACC-14 presence test passes and proves the field is required not optional; no other contract or runtime source modified.</done>
</task>

<task type="auto">
  <name>Task 2: Author the deterministic example decision record (propensity=1.0)</name>
  <files>.planning/schemas/examples/decision-policy-context.json</files>
  <read_first>
    - contracts/decision-ledger.schema.json (amended in Task 1 — the example MUST validate against it, including the new required policy_context and the twelve existing required fields)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md (§RQ-2 deterministic-population example: propensity=1.0, action_space=["claude-opus-4"], exploration_flag=false, policy_version="heuristic-v1")
    - .planning/schemas/examples/offline-eval-dataset-spec.json (REFERENCE — the sibling example formatting/style to match; same .venv jsonschema round-trip discipline)
  </read_first>
  <action>
    Create `.planning/schemas/examples/decision-policy-context.json`: a complete, valid BOS4 decision record
    (decision_type="task_to_agent" is the natural fit) carrying all twelve existing required fields with
    realistic values (decision_id, created_at, as_of, feature_snapshot, entity_ref, autonomy_band,
    recommended_action, human_verdict, actual_action, rationale, and a task_to_agent payload), PLUS the new
    required policy_context set to the deterministic values: propensity=1.0, action_space=["claude-opus-4"],
    exploration_flag=false, policy_version="heuristic-v1". The record MUST validate against the amended schema.
    This proves the log-now-to-eval-later requirement (D-15) is satisfiable today with deterministic policies.
    Do NOT modify the schema or any test — this example is a CONSUMER of the contract. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/decision-ledger.schema.json')); jsonschema.Draft202012Validator(s).validate(json.load(open('.planning/schemas/examples/decision-policy-context.json'))); r=json.load(open('.planning/schemas/examples/decision-policy-context.json')); pc=r['policy_context']; assert pc['propensity']==1.0 and pc['exploration_flag'] is False and pc['policy_version']=='heuristic-v1' and isinstance(pc['action_space'],list), 'deterministic policy_context values'; print('deterministic decision example validates against amended schema')"</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/schemas/examples/decision-policy-context.json` is a complete decision record validating against the amended `contracts/decision-ledger.schema.json` (all twelve existing required fields + the new required policy_context).
    - policy_context carries the deterministic values: propensity=1.0, action_space a non-empty array, exploration_flag=false, policy_version="heuristic-v1" (proving D-15 is satisfiable today).
    - `git diff --quiet contracts/ tests/planning/` exits 0 (Task 2 adds only the example; schema + tests unchanged) and `git diff --quiet voss/` exits 0.
  </acceptance_criteria>
  <done>A deterministic example decision record exists and validates against the amended schema, carrying policy_context with propensity=1.0 / exploration_flag=false / policy_version="heuristic-v1"; it proves OPE propensity logging is satisfiable today; schema + tests untouched.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (no runtime boundary in this phase) | Docs-only contract amendment. No code executes; no inputs processed at runtime. Threats are data-governance correctness. |
| future decision-ledger writer -> decision record (BOS4 runtime era) | The amended schema IS the validation contract for that future writer; making policy_context REQUIRED means a runtime writer canNOT skip logging propensity (D-15 / Pitfall 8). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-BOS5-05-01 | Repudiation / Information disclosure | un-evaluable historical decisions (propensity not logged at decision time) | mitigate | PRIMARY modeled threat. policy_context is made REQUIRED (not optional) on the decision record; a runtime writer canNOT omit it (Pitfall 8). ACC-14 test asserts present + required + a record missing it fails validation. |
| T-BOS5-05-02 | Tampering | breaking the shipped BOS4 contract (altering payload $defs / required fields) | mitigate | Amendment is additive only; the verify step asserts the six payload $defs count == 6 and the schema still lints; acceptance criteria assert `git diff --quiet` for all sibling contracts. No discriminator/oneOf/payload change. |
| T-BOS5-05-03 | Tampering | existing harness / runtime source or sibling contracts | mitigate | Acceptance criteria assert `git diff --quiet` for offline-eval/outcomes/events schemas, openapi.json, PROTOCOL.md, voss/**; only decision-ledger.schema.json is amended. No runtime writer, migration script, or pydantic model. |
| T-BOS5-05-SC | Tampering | package installs | accept | No package-manager installs; `jsonschema` 4.26.0 + pytest already in `.venv`. No legitimacy gate needed. Threats are data-governance, mitigated by contract structure + the required-ness of policy_context. |
</threat_model>

<verification>
- `.venv/bin/python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/decision-ledger.schema.json')))"` — amended schema lints clean.
- `.venv/bin/python -m pytest tests/planning/test_bos_decision_policy_context.py -x -q` — ACC-14 presence test green.
- `.venv/bin/python -m pytest tests/planning/ -x -q` — the full planning suite still green (no regression to BOS5-02/BOS5-04 suites).
- `git diff --quiet contracts/offline-eval.schema.json contracts/outcomes.schema.json contracts/events.schema.json contracts/openapi.json PROTOCOL.md && git diff --quiet voss/` — only decision-ledger.schema.json amended.
</verification>

<success_criteria>
- contracts/decision-ledger.schema.json additively amended with a required policy_context {propensity 0..1, action_space, exploration_flag, policy_version} (D-15); six payload $defs + twelve existing required fields untouched; schema lints clean.
- A deterministic example decision record (propensity=1.0) validates against the amended schema.
- ACC-14 presence test (test_propensity_field_on_decision_record) passes, proving policy_context present + required + the four sub-fields, and that a missing field fails validation.
- BOS-DATA-05 D-15 satisfied at its source; offline-eval/outcomes/events schemas, openapi.json, PROTOCOL.md, voss/harness/** unchanged.
</success_criteria>

<output>
Create `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-05-SUMMARY.md` when done.
</output>
