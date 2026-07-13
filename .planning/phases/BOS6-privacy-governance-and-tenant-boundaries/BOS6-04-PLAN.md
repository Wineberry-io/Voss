---
phase: BOS6
plan: 04
type: execute
wave: 2
depends_on: ["BOS6-02"]
files_modified:
  - contracts/decision-ledger.schema.json
  - .planning/schemas/examples/decision-autonomy-band.json
  - tests/planning/test_bos_governance_band_consistency.py
autonomous: true
requirements: [BOS-GOV-02]

must_haves:
  truths:
    - "CROSS-PHASE BOS4 FOLLOW-UP (D-16): the three free-string autonomy-band fields in contracts/decision-ledger.schema.json (top-level autonomy_band, AutonomyBandPayload.proposed_band, AutonomyBandPayload.current_band) are constrained to the canonical 4-value AutonomyBand enum that governance.schema.json owns"
    - "The amendment is the mirror-enum mechanism (inline enum on all three fields), NOT a cross-file $ref — so decision-ledger.schema.json stays standalone-lintable and no existing test suite couples to governance.schema.json (RESEARCH §D-16: mirror+consistency-test chosen over cross-file $ref)"
    - "The amendment is ADDITIVE and non-breaking: top-level additionalProperties:false still holds, the six payload $defs + the discriminator/oneOf + the twelve existing required fields are untouched; the enum only narrows three previously free-string fields"
    - "ACC-07 consistency test proves all three ledger enum arrays EQUAL the governance.schema.json AutonomyBand enum value set; the test fires if either file's band values are edited without the other (D-16, BOS-GOV-02)"
    - "An example autonomy_band decision record (proposed_band/current_band within the enum) validates against the amended schema, and a record with an out-of-enum band FAILS validation"
  artifacts:
    - path: "contracts/decision-ledger.schema.json"
      provides: "BOS4 decision-ledger amended (additively) so autonomy_band, AutonomyBandPayload.proposed_band, and AutonomyBandPayload.current_band are enum-constrained to the canonical AutonomyBand values (D-16 mirror)"
      contains: "auto_with_post_review"
      min_lines: 380
    - path: "tests/planning/test_bos_governance_band_consistency.py"
      provides: "ACC-07 cross-phase consistency test: the 3 ledger band-enum arrays == governance.schema.json AutonomyBand enum; the amended example round-trips; an out-of-enum band fails"
      contains: "AutonomyBand"
      min_lines: 30
    - path: ".planning/schemas/examples/decision-autonomy-band.json"
      provides: "An autonomy_band decision record with in-enum proposed_band/current_band validating against the amended schema"
      contains: "proposed_band"
      min_lines: 0
  key_links:
    - from: "contracts/decision-ledger.schema.json autonomy_band / proposed_band / current_band"
      to: "contracts/governance.schema.json #/$defs/AutonomyBand"
      via: "mirror-enum: the three fields carry the same 4 values; the ACC-07 test asserts equality (not a cross-file $ref)"
      pattern: "auto_with_post_review"
    - from: "tests/planning/test_bos_governance_band_consistency.py"
      to: "contracts/governance.schema.json + contracts/decision-ledger.schema.json"
      via: "loads both, asserts the AutonomyBand enum == each of the 3 ledger band-enum arrays"
      pattern: "AutonomyBand"
---

<objective>
CROSS-PHASE BOS4 FOLLOW-UP (driven by BOS6 D-16), DISTINCT from BOS5-05. Additively
amend the already-shipped BOS4 decision-ledger contract
(`contracts/decision-ledger.schema.json`) so its three currently free-string
autonomy-band fields — the top-level `autonomy_band`, `AutonomyBandPayload.proposed_band`,
and `AutonomyBandPayload.current_band` — are constrained to the canonical 4-value
`AutonomyBand` enum that `governance.schema.json` (BOS6-02) owns (D-16). The mechanism
is mirror-enum + a consistency test (RESEARCH §D-16 chose this over a cross-file `$ref`,
to keep the ledger standalone-lintable and avoid coupling existing test suites to
governance.schema.json). An ACC-07 consistency test asserts the two files' band values
stay identical.

Purpose: BOS-GOV-02 D-16 — governance owns the canonical band vocabulary; BOS4 conforms.
BOS4 is already executed, so this is an explicit, clearly-flagged additive amendment to a
shipped contract, NOT a side-effect of another plan. It is SEPARATE from BOS5-05 (which
adds `policy_context` to the same file): the two amendments are orthogonal — policy_context
is a new top-level field, this narrows three existing band fields — and are kept as
separate plans per RESEARCH §RQ-3 (narrow diffs, focused test files, independent
verification). DOCS-FIRST: a schema amendment + example + consistency test. No runtime
code, no migration script, no live writer, no pydantic model.

Output:
- `contracts/decision-ledger.schema.json` amended (3 band fields enum-constrained)
- `.planning/schemas/examples/decision-autonomy-band.json` (in-enum example)
- `tests/planning/test_bos_governance_band_consistency.py` (ACC-07)
</objective>

<execution_context>
@/Users/benjaminmarks/Projects/Voss/.claude/get-shit-done/workflows/execute-plan.md
@/Users/benjaminmarks/Projects/Voss/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

@.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-CONTEXT.md
@.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md
@.planning/phases/BOS4-decision-ledger-schema/BOS4-CONTEXT.md

<interfaces>
<!-- This plan AMENDS contracts/decision-ledger.schema.json (a shipped BOS4 artifact) and the
     canonical enum source is contracts/governance.schema.json (BOS6-02). Load BOTH directly for the
     exact current structure + the canonical enum; the amendment is ADDITIVE/NARROWING only. The
     three target fields + the mirror-enum mechanism are NORMATIVE (D-16, RESEARCH §D-16). -->

Canonical source (contracts/governance.schema.json, BOS6-02):
  $defs.AutonomyBand.enum = ["suggest_only","approve_required","auto_with_post_review","full_auto"]
  (governance.schema.json is the single source of truth; this plan MIRRORS that enum into the ledger.)

Current decision-ledger.schema.json (BOS4, shipped) — the THREE free-string band fields to constrain
(VERIFIED by codebase read; today none carry an enum):
  1. top-level properties.autonomy_band  — currently {type:string} free-string (no enum)
  2. $defs.AutonomyBandPayload.properties.proposed_band — currently {type:string} free-string
  3. $defs.AutonomyBandPayload.properties.current_band  — currently {type:string} free-string
  The schema has top-level additionalProperties:false; twelve top-level required fields (incl.
  autonomy_band); six closed payload $defs; decision_type discriminator + oneOf over the six payloads.
  AutonomyBandPayload.required currently = [decision_type, proposed_band].

Amendment (mirror-enum, RESEARCH §D-16 — NOT cross-file $ref):
  Add an inline "enum": ["suggest_only","approve_required","auto_with_post_review","full_auto"] to EACH
  of the three fields above (keep type:string; keep/extend each description to note it is constrained to
  the canonical BOS6 AutonomyBand enum, D-16, see governance.schema.json). Do NOT add a $ref to
  governance.schema.json (Pitfall 1: a cross-file $ref breaks standalone lint + couples the BOS4/BOS5
  test suites). Do NOT touch the six payload $defs structure, the discriminator/oneOf, or any of the
  twelve existing required fields; do NOT change AutonomyBandPayload.required. additionalProperties:false
  at top level must still hold (an enum is a narrowing annotation on an existing property, not a new
  property). Mirror the sibling $comment/migration-note convention: the schema narrows three previously
  free-string fields to the governance canonical enum (D-16); additive/narrowing, no new required field.

  ⚠ Pitfall 5 (RESEARCH): do NOT constrain only the top-level autonomy_band and miss the two payload
  fields. ALL THREE must be constrained, and ACC-07 asserts all three.

Coordination with BOS5-05 (same file, orthogonal): BOS5-05 adds a required top-level policy_context.
If BOS5-05 already executed, this plan simply amends the already-amended file — the enum narrowing does
not interact with policy_context (different fields). Keep the two as separate plans; do NOT merge.

ACC-07 (RESEARCH §D-16 / §RQ-5): a consistency test that loads governance.schema.json + decision-ledger.
schema.json and asserts set(governance AutonomyBand.enum) == set(ledger autonomy_band.enum) ==
set(proposed_band.enum) == set(current_band.enum). This plan OWNS this test (clean file ownership;
the BOS6-03 governance suite does NOT author it).

Example (RESEARCH): a decision_type="autonomy_band" record carrying the twelve existing required fields
(reuse the BOS4 AutonomyBandPayload shape) with proposed_band + current_band set to in-enum values
(e.g. proposed_band="auto_with_post_review", current_band="approve_required") and the top-level
autonomy_band also in-enum. The record MUST validate; a record with an out-of-enum band (e.g.
"yolo_mode") MUST fail.

Do NOT add a runtime writer, a migration script, or a pydantic model. Do NOT modify governance.schema.json,
outcomes.schema.json, events.schema.json, openapi.json, export_contract.py, PROTOCOL.md, the BOS6-03
fixtures/suite, or any voss/** source.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Mirror the AutonomyBand enum into the 3 decision-ledger band fields + ACC-07 consistency test</name>
  <files>contracts/decision-ledger.schema.json, tests/planning/test_bos_governance_band_consistency.py</files>
  <behavior>
    - test_band_enum_consistent_with_governance: governance.schema.json $defs.AutonomyBand.enum equals (as a set) the ledger's top-level autonomy_band.enum AND AutonomyBandPayload.proposed_band.enum AND AutonomyBandPayload.current_band.enum — all four arrays are the same 4-value set (ACC-07, D-16, Pitfall 5: all three ledger fields checked).
    - The amended decision-ledger.schema.json still lints clean against Draft 2020-12; top-level additionalProperties is still false; the six payload $defs count is unchanged (== 6); the twelve top-level required fields and AutonomyBandPayload.required are unchanged (additive/narrowing only).
    - A record with an out-of-enum band value (e.g. proposed_band="yolo_mode") FAILS validation; a record with all bands in-enum passes (proves the enum actually constrains).
  </behavior>
  <read_first>
    - contracts/decision-ledger.schema.json (the shipped BOS4 schema to amend — read the full current structure: the top-level autonomy_band property, the AutonomyBandPayload $def with proposed_band/current_band, the twelve required fields, the six payload $defs, the discriminator/oneOf; the amendment narrows the three band fields only)
    - contracts/governance.schema.json (BOS6-02 — the canonical $defs.AutonomyBand.enum to MIRROR; the ACC-07 test asserts equality against it)
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md (§RQ-2/§RQ-3 §D-16 Mechanism — why mirror-enum not cross-file $ref; the exact three-field amendment; Pitfall 1 (no cross-file $ref) + Pitfall 5 (all three fields))
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-CONTEXT.md (D-16 verbatim — the cross-phase mandate; the note that this is SEPARATE from BOS5-05)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-05-PLAN.md (REFERENCE — the cross-phase BOS4-amendment plan PATTERN to mirror: additive amendment + presence/consistency test + git diff --quiet sibling-contract assertions; note BOS5-05 amends a DIFFERENT field (policy_context) so there is no file-write conflict if not run concurrently)
    - tests/planning/test_bos_outcome_schema.py (REFERENCE — the sibling suite loader/assertion shape; tests/planning/__init__.py already exists, do NOT recreate it)
  </read_first>
  <action>
    Amend `contracts/decision-ledger.schema.json` ADDITIVELY/NARROWING (D-16, mirror-enum):
    add an inline `"enum": ["suggest_only","approve_required","auto_with_post_review","full_auto"]`
    (keep `"type": "string"`) to EACH of the three fields — the top-level `properties.autonomy_band`,
    `$defs.AutonomyBandPayload.properties.proposed_band`, and
    `$defs.AutonomyBandPayload.properties.current_band` — and extend each field's description to note it
    is constrained to the canonical BOS6 `AutonomyBand` enum (D-16; see governance.schema.json). Add/extend
    a top-level `$comment` migration note: three previously free-string band fields are narrowed to the
    governance canonical enum (BOS6 D-16); additive/narrowing, no new required field; mirror the sibling
    `$comment` convention. Do NOT add a cross-file `$ref` (Pitfall 1). Do NOT alter the six payload `$defs`
    structure, the decision_type discriminator/oneOf, AutonomyBandPayload.required, or any of the twelve
    existing top-level required fields. Constrain ALL THREE fields (Pitfall 5) — not just the top-level one.

    Then create `tests/planning/test_bos_governance_band_consistency.py` (reuse the existing
    tests/planning/__init__.py marker) implementing test_band_enum_consistent_with_governance per the
    <behavior> block: load governance.schema.json + decision-ledger.schema.json; assert
    set(governance.$defs.AutonomyBand.enum) equals each of the three ledger band-enum arrays (top-level
    autonomy_band, proposed_band, current_band); assert the ledger still lints clean (Draft 2020-12),
    top-level additionalProperties is false, len($defs)==6, and the twelve required fields are unchanged;
    assert a record with an out-of-enum band fails validation and an in-enum record passes. Use
    `.venv/bin/python -m pytest`. Do NOT author the example record here (Task 2). Do NOT add a runtime
    writer/migration/pydantic model, do NOT modify governance.schema.json or any other contracts/* file,
    do NOT recreate tests/planning/__init__.py. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; g=json.load(open('contracts/governance.schema.json')); l=json.load(open('contracts/decision-ledger.schema.json')); jsonschema.Draft202012Validator.check_schema(l); gb=set(g['\$defs']['AutonomyBand']['enum']); top=set(l['properties']['autonomy_band']['enum']); pay=l['\$defs']['AutonomyBandPayload']['properties']; pb=set(pay['proposed_band']['enum']); cb=set(pay['current_band']['enum']); assert gb==top==pb==cb=={'suggest_only','approve_required','auto_with_post_review','full_auto'}, 'all 3 ledger band fields == governance AutonomyBand enum'; assert l['additionalProperties'] is False and len(l['\$defs'])==6, 'additive: additionalProperties false + 6 payload defs intact'; print('D-16 mirror-enum on 3 ledger fields == governance canonical; additive')" && .venv/bin/python -m pytest tests/planning/test_bos_governance_band_consistency.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - (ACC-07) `contracts/decision-ledger.schema.json` constrains all three band fields — top-level `autonomy_band`, `AutonomyBandPayload.proposed_band`, `AutonomyBandPayload.current_band` — to the enum `["suggest_only","approve_required","auto_with_post_review","full_auto"]`, equal (as a set) to `contracts/governance.schema.json` `$defs.AutonomyBand.enum`.
    - The amendment is mirror-enum (inline enum), NOT a cross-file `$ref` (no `$ref` to governance.schema.json appears in decision-ledger.schema.json — Pitfall 1).
    - The amendment is additive/narrowing: the schema lints clean against Draft 2020-12, top-level `additionalProperties` is still false, the six payload `$defs` are unchanged (count == 6), the twelve top-level required fields and `AutonomyBandPayload.required` are unchanged.
    - `tests/planning/test_bos_governance_band_consistency.py` exists and `.venv/bin/python -m pytest tests/planning/test_bos_governance_band_consistency.py -q` passes; it asserts the three-field enum equality with the governance canonical and that an out-of-enum band fails validation.
    - `git diff --quiet contracts/governance.schema.json contracts/outcomes.schema.json contracts/events.schema.json contracts/openapi.json PROTOCOL.md` exits 0 and `git diff --quiet voss/` exits 0 (only decision-ledger.schema.json amended; no other contract or runtime source touched).
  </acceptance_criteria>
  <done>contracts/decision-ledger.schema.json has all three autonomy-band fields enum-constrained to the canonical governance AutonomyBand values via mirror-enum (no cross-file $ref); the amendment is additive (additionalProperties:false, 6 payload $defs, twelve required fields intact); the ACC-07 consistency test passes and proves the three ledger arrays equal the governance enum and that an out-of-enum band fails; no other contract or runtime source modified.</done>
</task>

<task type="auto">
  <name>Task 2: Author the in-enum autonomy_band example decision record</name>
  <files>.planning/schemas/examples/decision-autonomy-band.json</files>
  <read_first>
    - contracts/decision-ledger.schema.json (amended in Task 1 — the example MUST validate against it, including the now-enum-constrained band fields and the twelve existing required fields)
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md (§RQ-2 the autonomy_band decision record example values; in-enum proposed_band/current_band)
    - .planning/schemas/examples/decision-policy-context.json (REFERENCE — the sibling BOS4 decision-record example formatting/style to match; same .venv jsonschema round-trip discipline. NOTE: if BOS5-05 has executed this example carries policy_context; match the CURRENT schema's required fields)
  </read_first>
  <action>
    Create `.planning/schemas/examples/decision-autonomy-band.json`: a complete, valid BOS4 decision
    record with decision_type="autonomy_band" carrying all twelve existing required fields with realistic
    values (decision_id, created_at, as_of, feature_snapshot, entity_ref, the top-level autonomy_band set
    to an IN-ENUM value e.g. "auto_with_post_review", recommended_action, human_verdict, actual_action,
    rationale, and an AutonomyBandPayload payload with proposed_band="auto_with_post_review" +
    current_band="approve_required" — both in-enum — plus the payload's required decision_type). If the
    current schema (post BOS5-05) also requires policy_context, include it with the deterministic values
    (propensity=1.0, action_space=[...], exploration_flag=false, policy_version="heuristic-v1") so the
    record validates. The record MUST validate against the amended schema, proving the D-16 enum
    constraint is satisfiable with canonical band values. Do NOT modify the schema or any test — this
    example is a CONSUMER of the contract. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/decision-ledger.schema.json')); r=json.load(open('.planning/schemas/examples/decision-autonomy-band.json')); jsonschema.Draft202012Validator(s).validate(r); bands={'suggest_only','approve_required','auto_with_post_review','full_auto'}; assert r['autonomy_band'] in bands, 'top-level band in enum'; assert r['payload']['proposed_band'] in bands and r['payload']['current_band'] in bands, 'payload bands in enum'; print('in-enum autonomy_band decision example validates against amended schema')"</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/schemas/examples/decision-autonomy-band.json` is a complete decision_type="autonomy_band" record validating against the amended `contracts/decision-ledger.schema.json` (all twelve existing required fields + the AutonomyBandPayload + any currently-required field such as policy_context).
    - The top-level `autonomy_band`, payload `proposed_band`, and payload `current_band` are all in-enum canonical values (proving D-16 is satisfiable).
    - `git diff --quiet contracts/ tests/planning/` exits 0 (Task 2 adds only the example; schema + tests unchanged) and `git diff --quiet voss/` exits 0.
  </acceptance_criteria>
  <done>An autonomy_band decision example record exists and validates against the amended schema with in-enum top-level autonomy_band + payload proposed_band/current_band; it proves the D-16 enum constraint is satisfiable with canonical band values; schema + tests untouched.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (no runtime boundary in this phase) | Docs-only contract amendment. No code executes; no inputs processed at runtime. Threats are governance-vocabulary correctness. |
| future decision-ledger writer -> decision record (BOS4 runtime era) | The amended schema IS the validation contract for that future writer; the enum constraint means a runtime writer canNOT log an out-of-vocabulary autonomy band (D-16). |
| cross-phase contract author -> shipped BOS4 + BOS6 contracts | The plan amends ONLY decision-ledger.schema.json (mirror-enum); it must NOT cross into governance.schema.json (BOS6-02, the canonical source) or any other contract — a cross-file $ref is explicitly rejected (Pitfall 1). |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-BOS6-04-01 | Tampering / Elevation of privilege | a decision record logging an out-of-vocabulary autonomy band (silent band drift between ledger and governance) | mitigate | PRIMARY modeled threat. All three ledger band fields are enum-constrained to the governance canonical; ACC-07 asserts equality across both files and Task 1 proves an out-of-enum band fails validation. Drift in either file fails CI. |
| T-BOS6-04-02 | Tampering | partial amendment — constraining only the top-level field and leaving the payload fields free-string (Pitfall 5) | mitigate | ACC-07 explicitly asserts all THREE fields (autonomy_band, proposed_band, current_band) equal the governance enum; missing any one fails the test. |
| T-BOS6-04-03 | Tampering | breaking the shipped BOS4 contract (altering payload $defs / required fields) or coupling test suites via a cross-file $ref | mitigate | Amendment is narrowing-only; the verify asserts six payload $defs intact + additionalProperties:false + clean lint; no cross-file $ref (Pitfall 1) so decision-ledger stays standalone-lintable and existing BOS4/BOS5 suites do not couple to governance.schema.json. |
| T-BOS6-04-04 | Tampering | existing harness / runtime source or sibling contracts | mitigate | Acceptance criteria assert `git diff --quiet` for governance/outcomes/events schemas, openapi.json, PROTOCOL.md, voss/**; only decision-ledger.schema.json amended. No runtime writer, migration script, or pydantic model. |
| T-BOS6-04-SC | Tampering | package installs | accept | No package-manager installs; `jsonschema` 4.26.0 + pytest already in `.venv` (RESEARCH §Package Legitimacy Audit: no external packages). No legitimacy gate needed. |
</threat_model>

<verification>
- `.venv/bin/python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/decision-ledger.schema.json')))"` — amended ledger schema lints clean.
- `.venv/bin/python -m pytest tests/planning/test_bos_governance_band_consistency.py -x -q` — ACC-07 consistency test green.
- `.venv/bin/python -m pytest tests/planning/ -x -q` — the full planning suite (BOS5 suites + BOS6-03 governance suite + this consistency test) green; no regression.
- `git diff --quiet contracts/governance.schema.json contracts/outcomes.schema.json contracts/events.schema.json contracts/openapi.json PROTOCOL.md && git diff --quiet voss/` — only decision-ledger.schema.json amended.
</verification>

<success_criteria>
- contracts/decision-ledger.schema.json additively amended: all three autonomy-band fields (autonomy_band, proposed_band, current_band) enum-constrained to the canonical governance AutonomyBand values via mirror-enum (no cross-file $ref); six payload $defs + twelve required fields untouched; schema lints clean (D-16).
- An in-enum autonomy_band example decision record validates against the amended schema.
- ACC-07 consistency test (test_band_enum_consistent_with_governance) passes, proving the three ledger band-enum arrays equal the governance canonical enum and that an out-of-enum band fails validation.
- BOS-GOV-02 D-16 satisfied at its source (the BOS4 decision record); clearly flagged as a cross-phase BOS4 follow-up SEPARATE from BOS5-05; governance/outcomes/events schemas, openapi.json, PROTOCOL.md, voss/** unchanged.
</success_criteria>

<output>
Create `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-04-SUMMARY.md` when done.
</output>
