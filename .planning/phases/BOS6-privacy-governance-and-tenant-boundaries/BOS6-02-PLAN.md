---
phase: BOS6
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - contracts/governance.schema.json
autonomous: true
requirements: [BOS-GOV-01, BOS-GOV-02, BOS-GOV-03, BOS-GOV-04]

must_haves:
  truths:
    - "contracts/governance.schema.json exists as the 5th contracts/ sibling and lints clean against the JSON Schema Draft 2020-12 meta-schema (D-15)"
    - "AutonomyBand $def is the canonical enum of exactly the 4 values suggest_only, approve_required, auto_with_post_review, full_auto (D-15, BOS-GOV-02); decision-ledger mirrors it in BOS6-04"
    - "PrivacyTier $def is the enum of exactly the 3 values team_shareable, team_private, never_leaves_local, and DataClassTierMap constrains every data-class value to a PrivacyTier $ref (D-15, BOS-GOV-03)"
    - "GuardrailDashboard $def is a closed object of exactly 6 required entries (fatigue, fairness, autonomy_creep, escaped_defects, incidents, reward_hacking); each entry carries source (bos5|bos6) and an if/then requiring linked_guardrail_id when source=bos5 (D-15/D-17, BOS-GOV-04)"
    - "min_aggregation_n $def encodes the N=3 floor (minimum: 3) so a value below 3 cannot validate (D-15/D-12, BOS-GOV-01)"
    - "SurfaceGovernanceConfig $def is a closed record with required surface_id, autonomy_band ($ref AutonomyBand), kill_switch_state ($ref KillSwitchState), v, effective_from (D-15, BOS-GOV-02)"
  artifacts:
    - path: "contracts/governance.schema.json"
      provides: "BOS6 governance vocabulary $defs (AutonomyBand, PrivacyTier, DataClassTierMap, KillSwitchState, GuardrailDashboard, GuardrailDashboardEntry, min_aggregation_n) + SurfaceGovernanceConfig state record; the 5th hand-authored contracts/ sibling, Draft 2020-12; canonical source of the AutonomyBand enum (D-16 mirror target)"
      contains: "SurfaceGovernanceConfig"
      min_lines: 120
  key_links:
    - from: "contracts/governance.schema.json SurfaceGovernanceConfig.autonomy_band"
      to: "contracts/governance.schema.json #/$defs/AutonomyBand"
      via: "$ref constrains the state record's band to the canonical enum"
      pattern: "AutonomyBand"
    - from: "contracts/governance.schema.json GuardrailDashboardEntry"
      to: "contracts/outcomes.schema.json GuardrailMetricSpec.guardrail_id"
      via: "linked_guardrail_id is the FK string (value-FK validated by example fixtures in BOS6-03, D-17)"
      pattern: "linked_guardrail_id"
---

<objective>
Author `contracts/governance.schema.json`, the 5th hand-authored `contracts/`
sibling, encoding the BOS6 governance policy vocabularies as Draft-2020-12 `$defs`
plus a validatable `SurfaceGovernanceConfig` state record (D-15). This is the
machine-checkable counterpart of the shipped prose `BOS6-GOVERNANCE-SPEC.md`: the
schema encodes the SAME band/tier/guardrail/N values the prose states. It becomes
the canonical source of truth for the `AutonomyBand` enum that BOS6-04 mirrors into
the BOS4 decision-ledger (D-16).

Purpose: BOS-GOV-01..04 — turn the governance policy from prose into a structural
contract every later BOS surface can validate against. DOCS-FIRST: a hand-authored
JSON Schema document only. No runtime enforcement code, no migration, no pydantic
model, no live service.

Output:
- `contracts/governance.schema.json` (vocab `$defs` + `SurfaceGovernanceConfig` record)
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
@.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-GOVERNANCE-SPEC.md

<interfaces>
<!-- The form governance.schema.json takes is the existing hand-authored sibling pattern.
     Load contracts/outcomes.schema.json directly for the exact $schema + $id + title +
     description + $comment(schema_version) + top-level-properties-exposing-$defs convention.
     All VALUES below are NORMATIVE — taken verbatim from the shipped BOS6-GOVERNANCE-SPEC.md
     (ACC-09 in BOS6-03 greps the prose to guard against drift). The exact $def/field NAMES
     are Claude's Discretion (CONTEXT D-15..D-18), but the names below match BOS6-RESEARCH §RQ-1
     and the downstream BOS6-03/BOS6-04 tests reference them — use these names. -->

Sibling pattern to mirror (contracts/outcomes.schema.json):
  $schema = "https://json-schema.org/draft/2020-12/schema"
  $id     = "https://voss.dev/contracts/governance.schema.json"
  title   = "GovernanceContract"
  top-level "type": "object"; a top-level "properties" block that exposes each vocab $def
  by a snake_case key ($ref into $defs); a "$comment" stating schema_version=1 + the
  additive-vs-breaking migration rule (mirror the outcomes.schema.json $comment wording).

NORMATIVE values (verbatim from BOS6-GOVERNANCE-SPEC.md):
  AutonomyBand enum (exactly 4, ordered): suggest_only, approve_required,
    auto_with_post_review, full_auto  (spec §Autonomy Bands table)
  PrivacyTier enum (exactly 3, ordered): team_shareable, team_private,
    never_leaves_local  (spec §Privacy Tiers table)
  GuardrailDashboard keys (exactly 6): fatigue, fairness, autonomy_creep (source=bos6);
    escaped_defects, incidents, reward_hacking (source=bos5)  (spec §Guardrail Dashboards)
  min_aggregation_n floor = 3  (spec: "`N` defaults to **3**")
  KillSwitchState enum: enabled, tripped (D-02 semantics; names are Discretion)

$defs to author (names from BOS6-RESEARCH §RQ-1; BOS6-03/04 tests depend on them):
  AutonomyBand            — string enum, the 4 values, description names it canonical + the
                            D-16 decision-ledger mirror.
  PrivacyTier             — string enum, the 3 values.
  DataClassTierMap        — object; properties code/prompts/agent_transcripts/calendar_identity/
                            incident_deploy/decision_outcomes each {$ref: #/$defs/PrivacyTier};
                            required all six; additionalProperties {$ref: #/$defs/PrivacyTier}
                            (additive data classes allowed, values still tier-constrained).
  KillSwitchState         — string enum [enabled, tripped].
  GuardrailDashboardEntry — object; properties description(string), trip_condition(string),
                            source(string enum [bos5, bos6]), linked_guardrail_id(string);
                            required [description, trip_condition, source];
                            additionalProperties:false;
                            if {properties:{source:{const:"bos5"}}} then {required:[linked_guardrail_id]}.
  GuardrailDashboard      — object; 6 properties (fatigue, fairness, autonomy_creep,
                            escaped_defects, incidents, reward_hacking) each {$ref: GuardrailDashboardEntry};
                            required all 6; additionalProperties:false (locked set).
  min_aggregation_n       — integer, minimum: 3 (a value < 3 must NOT validate; D-12 floor). Description
                            states default is 3, deployments may raise but never lower below 3.
  SurfaceGovernanceConfig — object; additionalProperties:false; properties v(integer const 1 default 1),
                            surface_id(string), autonomy_band({$ref AutonomyBand}),
                            kill_switch_state({$ref KillSwitchState}), effective_from(string format date-time);
                            required [v, surface_id, autonomy_band, kill_switch_state, effective_from].

The FK target for linked_guardrail_id is contracts/outcomes.schema.json
GuardrailMetricSpec.guardrail_id (a free string). JSON Schema canNOT express the value-FK;
BOS6-03 validates it via example fixtures (D-17). This schema only declares linked_guardrail_id
as a string + the if/then requiring it when source=bos5.

Do NOT add a pydantic model, do NOT wire governance.schema.json into export_contract.py or the
pydantic regeneration drift gate (tests/harness/server/test_contract_drift.py) — hand-authored
schemas get a load+lint stability gate via the BOS6-03 pytest suite, the same way
outcomes.schema.json does. Do NOT modify any other contracts/* file (outcomes, events,
decision-ledger, openapi). Do NOT author tests or fixtures here (BOS6-03 owns them).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author contracts/governance.schema.json (vocab $defs + SurfaceGovernanceConfig record)</name>
  <files>contracts/governance.schema.json</files>
  <read_first>
    - contracts/outcomes.schema.json (the sibling hand-authored Draft-2020-12 schema to MIRROR: $schema/$id/title/description/$comment schema_version convention + the top-level-properties-exposing-$defs pattern + GuardrailMetricSpec.guardrail_id, the FK target linked_guardrail_id points at)
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md (§RQ-1 governance.schema.json Shape — the complete $def field layout + the const/minimum discussion for min_aggregation_n + the GuardrailDashboardEntry if/then; §Common Pitfalls 2 (N as floor not free integer) + 3 (GuardrailDashboard must be a named-property object, not an array))
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-GOVERNANCE-SPEC.md (the SHIPPED prose — the band/tier/guardrail/N values the schema MUST encode identically; ACC-09 in BOS6-03 greps this file)
    - contracts/decision-ledger.schema.json (REFERENCE ONLY — the $comment/migration-note convention + the autonomy_band fields BOS6-04 will mirror this enum into; do NOT modify it here)
  </read_first>
  <action>
    Create `contracts/governance.schema.json` as a Draft-2020-12 hand-authored sibling
    mirroring `contracts/outcomes.schema.json`'s top-level shape: `$schema` =
    "https://json-schema.org/draft/2020-12/schema", `$id` =
    "https://voss.dev/contracts/governance.schema.json", `title` = "GovernanceContract",
    a `description` naming BOS-GOV-01..04 + stating it is the canonical source of the
    `AutonomyBand` enum that `decision-ledger.schema.json` mirrors under D-16, a `$comment`
    with `schema_version=1` + the additive-vs-breaking migration rule (mirror the
    outcomes.schema.json `$comment` wording: additive data-class/guardrail additions do NOT
    bump the version; altering an existing enum value or renaming a `$def` does + requires a
    migration note in BOS6-GOVERNANCE-SPEC.md), `"type": "object"`, and a top-level
    `properties` block exposing each vocab `$def` by a snake_case key
    (`autonomy_band`, `privacy_tier`, `data_class_tier_map`, `guardrail_dashboard`,
    `min_aggregation_n`, `surface_governance_config`), each a `$ref` into `$defs`.

    Author the `$defs` exactly per the `<interfaces>` block: `AutonomyBand` (string enum of
    the 4 values suggest_only/approve_required/auto_with_post_review/full_auto, description
    naming it canonical + the D-16 ledger mirror), `PrivacyTier` (string enum of the 3 values
    team_shareable/team_private/never_leaves_local), `DataClassTierMap` (object whose six
    required data-class properties code/prompts/agent_transcripts/calendar_identity/
    incident_deploy/decision_outcomes each `$ref` `#/$defs/PrivacyTier`, with
    `additionalProperties` also a PrivacyTier `$ref`), `KillSwitchState` (string enum
    [enabled, tripped]), `GuardrailDashboardEntry` (object with description/trip_condition/
    source(enum [bos5,bos6])/linked_guardrail_id(string); required [description, trip_condition,
    source]; additionalProperties:false; an `if` source==const "bos5" `then`
    required:[linked_guardrail_id] — encodes D-17 so a bos5 entry MUST carry the FK),
    `GuardrailDashboard` (closed object: the 6 properties fatigue/fairness/autonomy_creep/
    escaped_defects/incidents/reward_hacking each `$ref` GuardrailDashboardEntry; all 6 in
    `required`; additionalProperties:false — Pitfall 3: object not array so coverage is
    schema-enforced), `min_aggregation_n` (integer with `minimum: 3` so a value below 3 cannot
    validate — Pitfall 2; description: default 3, deployments may raise but never lower below 3),
    and `SurfaceGovernanceConfig` (closed object; required v/surface_id/autonomy_band/
    kill_switch_state/effective_from; v integer const 1 default 1; autonomy_band `$ref`
    AutonomyBand; kill_switch_state `$ref` KillSwitchState; effective_from string format
    date-time).

    All enum values MUST match the shipped BOS6-GOVERNANCE-SPEC.md verbatim (ACC-09 guards
    this). Do NOT author tests, fixtures, a pydantic model, or wire into export_contract.py /
    the pydantic drift gate. Do NOT modify any other contracts/* file. NO git add/commit/push —
    the operator commits manually.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/governance.schema.json')); jsonschema.Draft202012Validator.check_schema(s); d=s['\$defs']; assert d['AutonomyBand']['enum']==['suggest_only','approve_required','auto_with_post_review','full_auto'], 'AutonomyBand 4 ordered'; assert d['PrivacyTier']['enum']==['team_shareable','team_private','never_leaves_local'], 'PrivacyTier 3 ordered'; gd=d['GuardrailDashboard']; assert set(gd['required'])=={'fatigue','fairness','autonomy_creep','escaped_defects','incidents','reward_hacking'} and gd['additionalProperties'] is False, 'GuardrailDashboard 6 closed'; e=d['GuardrailDashboardEntry']; assert e['properties']['source']['enum']==['bos5','bos6'] and e['then']['required']==['linked_guardrail_id'], 'entry source enum + bos5 if/then FK'; assert d['min_aggregation_n']['minimum']==3, 'N floor 3'; sc=d['SurfaceGovernanceConfig']; assert sc['additionalProperties'] is False and set(sc['required'])=={'v','surface_id','autonomy_band','kill_switch_state','effective_from'} and sc['properties']['autonomy_band']['\$ref']=='#/\$defs/AutonomyBand', 'SurfaceGovernanceConfig closed + band ref'; print('governance.schema.json lints + all $defs shaped per D-15')"</automated>
  </verify>
  <acceptance_criteria>
    - (ACC-01, BOS6-03 gate) `contracts/governance.schema.json` exists and `jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/governance.schema.json')))` raises no error.
    - (ACC-02) `$defs.AutonomyBand.enum == ["suggest_only","approve_required","auto_with_post_review","full_auto"]` (exactly 4, ordered).
    - (ACC-03) `$defs.PrivacyTier.enum == ["team_shareable","team_private","never_leaves_local"]` (exactly 3); `$defs.DataClassTierMap` constrains all values (properties + additionalProperties) to a PrivacyTier `$ref`.
    - (ACC-04) `$defs.GuardrailDashboard` has exactly the 6 keys fatigue/fairness/autonomy_creep/escaped_defects/incidents/reward_hacking all in `required`, `additionalProperties:false`; `$defs.GuardrailDashboardEntry.properties.source.enum == ["bos5","bos6"]` and the `if source==bos5 then required:[linked_guardrail_id]` clause is present.
    - (ACC-05) `$defs.min_aggregation_n.minimum == 3` (a value below 3 cannot validate).
    - `$defs.SurfaceGovernanceConfig` is `additionalProperties:false` with required `[v, surface_id, autonomy_band, kill_switch_state, effective_from]`; `autonomy_band` is a `$ref` to `#/$defs/AutonomyBand` and `kill_switch_state` a `$ref` to `#/$defs/KillSwitchState`.
    - `git diff --quiet contracts/outcomes.schema.json contracts/events.schema.json contracts/decision-ledger.schema.json contracts/openapi.json` exits 0 and `git diff --quiet voss/` exits 0 (only the net-new governance.schema.json is added; no sibling contract or runtime source touched).
  </acceptance_criteria>
  <done>contracts/governance.schema.json exists as the 5th Draft-2020-12 sibling, lints clean, and carries the AutonomyBand (4) / PrivacyTier (3) / DataClassTierMap / KillSwitchState / GuardrailDashboard (6, closed, with the source if/then FK) / min_aggregation_n (floor 3) / SurfaceGovernanceConfig $defs per D-15; all values match the shipped GOVERNANCE-SPEC; no other contract or runtime source modified.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (no runtime boundary in this phase) | Docs-only contract authoring. No code executes; no inputs processed at runtime. The deliverable is a JSON Schema document; threats are governance-contract correctness, not runtime attack surface. |
| future BOS7 policy-state writer -> SurfaceGovernanceConfig record | The schema IS the validation contract for that future writer. `additionalProperties:false` + required fields + the AutonomyBand/KillSwitchState `$ref` enums mean a malformed or out-of-vocabulary governance-state record canNOT validate (V5 input-validation, ASVS). |
| schema author -> sibling contracts | The plan must NOT cross into outcomes/events/decision-ledger schemas, openapi.json, export_contract.py, or voss/** — governance.schema.json is a net-new file only. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-BOS6-02-01 | Tampering / Elevation of privilege | autonomy-band escalation via an out-of-vocabulary band value | mitigate | AutonomyBand is a closed 4-value enum and SurfaceGovernanceConfig.autonomy_band `$ref`s it; a record with an unknown band canNOT validate. The canonical enum is mirrored into the BOS4 ledger in BOS6-04 (D-16) so the two never drift. |
| T-BOS6-02-02 | Information disclosure | data-class misclassification leaking sensitive content past the local boundary | mitigate | DataClassTierMap constrains every data-class value to the PrivacyTier enum; never_leaves_local is the spec default for code/prompts/transcripts. Schema rejects any non-tier value. |
| T-BOS6-02-03 | Tampering | silent addition of a 7th guardrail / dropping a guardrail without governance review | mitigate | GuardrailDashboard is a closed named-property object (additionalProperties:false, all 6 required) — Pitfall 3 — so adding/removing a guardrail requires a schema edit caught by the BOS6-03 lint + coverage gate, not a silent data change. |
| T-BOS6-02-04 | Tampering | weakening the anti-surveillance floor below N=3 | mitigate | min_aggregation_n carries minimum:3; a value below 3 fails validation (Pitfall 2). |
| T-BOS6-02-05 | Tampering | silent drift of the hand-authored governance.schema.json | mitigate | The schema joins the load+lint stability gate authored in BOS6-03 (ACC-01) — loaded + Draft-2020-12-linted on every pytest run; a malformed edit fails CI. |
| T-BOS6-02-SC | Tampering | package installs | accept | No package-manager installs; `jsonschema` 4.26.0 + pytest already in `.venv` (RESEARCH §Package Legitimacy Audit: no external packages). No legitimacy gate needed. |
</threat_model>

<verification>
- `.venv/bin/python -c "import json,jsonschema; jsonschema.Draft202012Validator.check_schema(json.load(open('contracts/governance.schema.json')))"` — schema lints clean against Draft 2020-12.
- The Task 1 `<verify>` one-liner asserts every $def shape (4 bands, 3 tiers, 6 closed guardrails, source if/then FK, N floor 3, closed SurfaceGovernanceConfig with band/kill-switch refs).
- `git diff --quiet contracts/outcomes.schema.json contracts/events.schema.json contracts/decision-ledger.schema.json contracts/openapi.json && git diff --quiet voss/` — only governance.schema.json added.
</verification>

<success_criteria>
- contracts/governance.schema.json authored as the 5th hand-authored Draft-2020-12 sibling, lints clean (D-15).
- AutonomyBand (4) / PrivacyTier (3) / DataClassTierMap / KillSwitchState / GuardrailDashboard (6, closed, source if/then FK per D-17) / min_aggregation_n (floor 3, D-12) / SurfaceGovernanceConfig $defs present and shaped per the interfaces block.
- All enum values identical to the shipped BOS6-GOVERNANCE-SPEC.md (ACC-09 in BOS6-03 will guard this).
- No sibling contract, openapi.json, export_contract.py, or voss/** source modified; no pydantic model, no fixtures, no tests authored here.
</success_criteria>

<output>
Create `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-02-SUMMARY.md` when done.
</output>
