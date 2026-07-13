---
phase: BOS6
plan: 03
type: execute
wave: 2
depends_on: ["BOS6-02"]
files_modified:
  - .planning/schemas/examples/governance-surface-config.json
  - .planning/schemas/examples/governance-guardrail-fk.json
  - .planning/schemas/examples/governance-bos5-guardrail-ids.json
  - tests/planning/test_bos_governance_schema.py
  - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md
autonomous: true
requirements: [BOS-GOV-01, BOS-GOV-02, BOS-GOV-03, BOS-GOV-04]

must_haves:
  truths:
    - "contracts/governance.schema.json is lint-gated on every run of the new suite (ACC-01) — the same load+lint stability gate BOS5-02 used for outcomes.schema.json, since it has no pydantic source"
    - "The AutonomyBand 4-value (ACC-02), PrivacyTier 3-value (ACC-03), GuardrailDashboard 6-entry + source split (ACC-04), and min_aggregation_n >= 3 (ACC-05) coverages are each proven by an automated test (BOS-GOV-01..04)"
    - "A valid SurfaceGovernanceConfig example fixture round-trips against the schema (ACC-06, BOS-GOV-02)"
    - "Guardrail FK validity is proven (ACC-08, D-17): every linked_guardrail_id in the bos5-linked example entries resolves to an id in the governance-bos5-guardrail-ids.json forward-declaration fixture; the 3 bos6-native entries carry no linked_guardrail_id"
    - "Prose<->schema value consistency is guarded (ACC-09): BOS6-GOVERNANCE-SPEC.md contains the 4 band names, 3 tier names, 6 guardrail prose names, and the N=3 token, and the schema enums equal those value sets"
    - "BOS6-VALIDATION.md exists with ACC-01..ACC-10 listed and flags the governance-bos5-guardrail-ids.json forward-declaration as the BOS13 coordination point (ACC-10, D-18)"
  artifacts:
    - path: "tests/planning/test_bos_governance_schema.py"
      provides: "BOS-GOV contract suite (ACC-01..06, 08, 09): schema load+lint stability gate, AutonomyBand/PrivacyTier/GuardrailDashboard/min_aggregation_n coverage, SurfaceGovernanceConfig round-trip, guardrail FK validity vs the forward-declared BOS5 id set, prose<->schema drift grep"
      contains: "Draft202012Validator"
      min_lines: 110
    - path: ".planning/schemas/examples/governance-surface-config.json"
      provides: "Valid SurfaceGovernanceConfig record for the ACC-06 round-trip"
      contains: "kill_switch_state"
      min_lines: 0
    - path: ".planning/schemas/examples/governance-guardrail-fk.json"
      provides: "Full 6-entry GuardrailDashboard example: 3 bos5-linked (linked_guardrail_id) + 3 bos6-native (source bos6, no FK)"
      contains: "linked_guardrail_id"
      min_lines: 0
    - path: ".planning/schemas/examples/governance-bos5-guardrail-ids.json"
      provides: "Forward-declared BOS5/BOS13 guardrail-id set the FK test resolves against (escaped_defects/incidents/reward_hacking); the BOS13 coordination point"
      contains: "guardrail_ids"
      min_lines: 0
    - path: ".planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md"
      provides: "ACC-01..ACC-10 list + the BOS13 guardrail-id coordination note (the VALIDATION doc BOS6 lacked)"
      contains: "ACC-10"
      min_lines: 30
  key_links:
    - from: "tests/planning/test_bos_governance_schema.py"
      to: "contracts/governance.schema.json"
      via: "loads + Draft-2020-12-lints the schema and validates the example records against its $defs"
      pattern: "governance.schema.json"
    - from: "tests/planning/test_bos_governance_schema.py"
      to: ".planning/schemas/examples/governance-bos5-guardrail-ids.json"
      via: "ACC-08 resolves every bos5-linked linked_guardrail_id against this forward-declared id set"
      pattern: "guardrail_ids"
    - from: "tests/planning/test_bos_governance_schema.py"
      to: ".planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-GOVERNANCE-SPEC.md"
      via: "ACC-09 greps the prose for the band/tier/guardrail/N tokens to catch prose<->schema drift"
      pattern: "GOVERNANCE-SPEC"
---

<objective>
Build the contract-validation harness for `contracts/governance.schema.json` (authored
in BOS6-02): the three example fixtures (a valid SurfaceGovernanceConfig record, a
full 6-entry GuardrailDashboard with the bos5/bos6 source split, and the forward-declared
BOS5 guardrail-id set) and the BOS-GOV pytest suite
(`tests/planning/test_bos_governance_schema.py`) proving the schema lints, the four
vocabulary coverages hold, the SurfaceGovernanceConfig round-trips, the guardrail FK
resolves (D-17), and the prose<->schema values do not drift (D-15/D-18). Author
`BOS6-VALIDATION.md` (the ACC list — BOS6 has none today) — ACC-10.

Purpose: BOS-GOV-01..04 — make the BOS6-02 governance contract machine-verifiable and
regression-guarded so downstream phases (BOS7 control-plane, BOS9 review surface,
BOS13/BOS15) inherit a proven governance substrate. This validates the REAL artifacts
from BOS6-02 — no xfail/skip scaffolding, no fictional API. Mirrors the BOS5-04
validation discipline exactly. The ACC-07 band-enum consistency test + the BOS4
amendment are owned by BOS6-04 (clean file ownership; this suite does NOT author them).

Output:
- `.planning/schemas/examples/governance-surface-config.json`
- `.planning/schemas/examples/governance-guardrail-fk.json`
- `.planning/schemas/examples/governance-bos5-guardrail-ids.json`
- `tests/planning/test_bos_governance_schema.py` (ACC-01..06, 08, 09)
- `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md` (ACC-10)
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
<!-- The artifacts under test were authored in BOS6-02. Load contracts/governance.schema.json
     directly for the exact $def/field names + enums; do NOT re-derive them. The ACC ids below
     are NORMATIVE (BOS6-RESEARCH §RQ-5 Validation Architecture). The sibling suite to MATCH in
     shape is tests/planning/test_bos_outcome_schema.py (BOS5-02) and the round-trip/FK discipline
     in tests/planning (BOS5-04 style): pathlib+json+jsonschema loaders, structural assertions,
     example round-trips. tests/planning/__init__.py already exists — do NOT recreate it. -->

Schema under test: contracts/governance.schema.json (Draft 2020-12; authored BOS6-02).

ACC checks OWNED by THIS suite (BOS6-RESEARCH §RQ-5 — names recommended, ACC ids normative):
  test_schema_is_valid                  (ACC-01; doubles as the load+lint stability gate — the schema
                                         has no pydantic source so it canNOT join tests/harness/server/
                                         test_contract_drift.py; this is its drift gate)
  test_autonomy_band_4_coverage         (ACC-02 — $defs.AutonomyBand.enum == the 4 values, exactly)
  test_privacy_tier_3_coverage          (ACC-03 — $defs.PrivacyTier.enum == the 3 values, exactly)
  test_data_class_tier_map_shape        (ACC-03 — DataClassTierMap values all $ref PrivacyTier)
  test_guardrail_dashboard_6_coverage   (ACC-04 — exactly 6 required keys, closed set)
  test_bos6_native_guardrails           (ACC-04 — fatigue/fairness/autonomy_creep example entries are
                                         source:bos6 with NO linked_guardrail_id)
  test_bos5_linked_guardrails_require_fk (ACC-04 — escaped_defects/incidents/reward_hacking example
                                         entries are source:bos5 WITH linked_guardrail_id; and the
                                         schema if/then makes a bos5 entry missing the FK fail validation)
  test_min_aggregation_n_gte_3          (ACC-05 — $defs.min_aggregation_n.minimum == 3; a value below 3
                                         fails validation against that $def)
  test_surface_governance_config_shape  (ACC-06 — $def required keys present)
  test_surface_governance_config_round_trip (ACC-06 — the example fixture validates against the $def)
  test_guardrail_fk_validity_with_bos5  (ACC-08 — every bos5-linked linked_guardrail_id in the FK example
                                         resolves to an id in governance-bos5-guardrail-ids.json; bos6
                                         entries carry no FK)
  test_prose_schema_value_consistency   (ACC-09 — grep BOS6-GOVERNANCE-SPEC.md for the tokens below AND
                                         assert the schema enums equal the same value sets)

NOT owned here (BOS6-04 owns them, clean file ownership):
  ACC-07 band-enum consistency with BOS4 (the decision-ledger amendment + its consistency test live in
  BOS6-04's own test file). This suite does NOT load or amend decision-ledger.schema.json.

ACC-09 prose tokens (VERIFIED verbatim in BOS6-GOVERNANCE-SPEC.md — use these EXACT strings):
  bands (lowercase, as in the spec table): suggest_only, approve_required, auto_with_post_review, full_auto
  tiers (lowercase): team_shareable, team_private, never_leaves_local
  guardrail prose names (Title Case as in the §Guardrail Dashboards table — NOT the snake_case schema keys):
    "Fatigue", "Fairness", "Escaped defects", "Incidents", "Autonomy creep", "Reward hacking"
  N=3 token (exact prose, backtick + bold): `N` defaults to **3**
  Grep the spec for the prose forms; separately assert the schema $defs hold the snake_case/enum forms —
  do NOT try to match prose Title Case against schema snake_case with one string (RESEARCH §RQ-6).

Example fixtures to author (BOS6-RESEARCH §RQ-4 Required Fixtures):
  governance-surface-config.json: a valid SurfaceGovernanceConfig — v:1, surface_id (e.g. "delegation"),
    autonomy_band:"approve_required", kill_switch_state:"enabled", effective_from (RFC3339 date-time).
  governance-guardrail-fk.json: a full GuardrailDashboard object, all 6 keys. The 3 bos6-native
    (fatigue, fairness, autonomy_creep): source:"bos6", description + trip_condition, NO linked_guardrail_id.
    The 3 bos5-linked (escaped_defects, incidents, reward_hacking): source:"bos5", description +
    trip_condition + linked_guardrail_id matching an id in governance-bos5-guardrail-ids.json.
  governance-bos5-guardrail-ids.json: {"guardrail_ids": [<3 ids>]} — the FORWARD-DECLARED BOS5 guardrail
    id set (e.g. "gmspec-escaped-defects","gmspec-incidents","gmspec-reward-hacking"). These ids are NOT yet
    established in BOS5/BOS13 (RESEARCH §RQ-4 + Pitfall 4 — no BOS5 guardrail fixtures exist today). Treat
    as a forward declaration; BOS6-VALIDATION.md MUST flag that BOS13 must use these same ids when it
    creates GuardrailMetricSpec records.

Grep-hygiene (project rule): when counting tokens in a file, filter comment/prose lines so a header that
mentions a token does not self-satisfy the gate; the FK + prose tests assert resolution/value-equality, not
bare line counts.

Do NOT modify contracts/* (the suite only READS governance.schema.json + outcomes.schema.json), do NOT add
a pydantic model, do NOT wire into export_contract.py. Do NOT author the BOS4 decision-ledger amendment or
the ACC-07 consistency test (BOS6-04 owns them). NO git add/commit/push.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bundle the governance example fixtures (.planning/schemas/examples/governance-*.json)</name>
  <files>.planning/schemas/examples/governance-surface-config.json, .planning/schemas/examples/governance-guardrail-fk.json, .planning/schemas/examples/governance-bos5-guardrail-ids.json</files>
  <read_first>
    - contracts/governance.schema.json (authored BOS6-02 — the fixtures MUST validate against its $defs; copy the exact required field names + enum values for SurfaceGovernanceConfig and GuardrailDashboardEntry)
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md (§RQ-4 Required Fixtures — the 3 fixture shapes + the forward-declared BOS5 id approach + Pitfall 4 (do not invent IDs without flagging coordination))
    - .planning/schemas/examples/outcome-reward.json (the sibling BOS5-02 example formatting/style to match — record conventions, RFC3339 timestamps)
  </read_first>
  <action>
    Create three records under `.planning/schemas/examples/`:

    - `governance-surface-config.json` (SurfaceGovernanceConfig): v=1, surface_id (e.g.
      "delegation"), autonomy_band="approve_required" (a valid AutonomyBand value),
      kill_switch_state="enabled" (a valid KillSwitchState value), effective_from an RFC3339
      date-time (e.g. "2026-07-01T00:00:00Z"). MUST validate against
      `#/$defs/SurfaceGovernanceConfig`.
    - `governance-guardrail-fk.json` (a full GuardrailDashboard object, all 6 keys): the 3
      bos6-native entries fatigue/fairness/autonomy_creep each {description, trip_condition,
      source:"bos6"} with NO linked_guardrail_id; the 3 bos5-linked entries escaped_defects/
      incidents/reward_hacking each {description, trip_condition, source:"bos5",
      linked_guardrail_id:<an id present in governance-bos5-guardrail-ids.json>}. MUST validate
      against `#/$defs/GuardrailDashboard` (the entry if/then will reject a bos5 entry missing
      the FK).
    - `governance-bos5-guardrail-ids.json`: {"guardrail_ids": [ three ids, e.g.
      "gmspec-escaped-defects", "gmspec-incidents", "gmspec-reward-hacking" ]} — the
      forward-declared BOS5/BOS13 guardrail-id set the FK test resolves against. The three
      linked_guardrail_id values in governance-guardrail-fk.json MUST be exactly these three ids.

    These ids are a FORWARD DECLARATION (no BOS5 guardrail fixtures exist yet — Pitfall 4);
    Task 3 records the BOS13 coordination note in BOS6-VALIDATION.md. Do NOT modify the schema
    or any contracts/* file — these examples are CONSUMERS of the contract. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json,jsonschema; s=json.load(open('contracts/governance.schema.json')); v_sc=jsonschema.Draft202012Validator({**s,'\$ref':'#/\$defs/SurfaceGovernanceConfig'}); v_gd=jsonschema.Draft202012Validator({**s,'\$ref':'#/\$defs/GuardrailDashboard'}); sc=json.load(open('.planning/schemas/examples/governance-surface-config.json')); gd=json.load(open('.planning/schemas/examples/governance-guardrail-fk.json')); ids=set(json.load(open('.planning/schemas/examples/governance-bos5-guardrail-ids.json'))['guardrail_ids']); v_sc.validate(sc); v_gd.validate(gd); bos5={'escaped_defects','incidents','reward_hacking'}; bos6={'fatigue','fairness','autonomy_creep'}; assert set(gd)==bos5|bos6, 'all 6 guardrail keys'; assert all(gd[k]['source']=='bos5' and gd[k]['linked_guardrail_id'] in ids for k in bos5), 'bos5 entries linked to declared ids'; assert all(gd[k]['source']=='bos6' and 'linked_guardrail_id' not in gd[k] for k in bos6), 'bos6 entries native, no FK'; print('3 governance fixtures validate; FK ids resolve; source split correct')"</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/schemas/examples/` contains the three records governance-surface-config.json, governance-guardrail-fk.json, governance-bos5-guardrail-ids.json.
    - (ACC-06) governance-surface-config.json validates against `#/$defs/SurfaceGovernanceConfig` (v=1, surface_id, a valid autonomy_band, a valid kill_switch_state, effective_from date-time).
    - (ACC-08 setup) governance-guardrail-fk.json validates against `#/$defs/GuardrailDashboard`; the 3 bos5-linked entries carry `linked_guardrail_id` values that all appear in governance-bos5-guardrail-ids.json `guardrail_ids`; the 3 bos6-native entries carry `source:"bos6"` and no `linked_guardrail_id`.
    - `git diff --quiet contracts/` exits 0 and `git diff --quiet voss/` exits 0 (Task 1 adds only example files; no schema or runtime source touched).
  </acceptance_criteria>
  <done>Three governance example records exist: a SurfaceGovernanceConfig that round-trips, a full 6-entry GuardrailDashboard with the correct bos5/bos6 source split and resolvable FKs, and the forward-declared BOS5 guardrail-id set; schema + contracts untouched.</done>
</task>

<task type="auto">
  <name>Task 2: Author the BOS-GOV contract suite + lint-gate governance.schema.json</name>
  <files>tests/planning/test_bos_governance_schema.py</files>
  <read_first>
    - contracts/governance.schema.json + .planning/schemas/examples/governance-*.json (the artifacts under test, from BOS6-02 + Task 1)
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-GOVERNANCE-SPEC.md (the ACC-09 grep target — read it to confirm the EXACT prose tokens: the lowercase band/tier values, the Title-Case guardrail names "Fatigue"/"Fairness"/"Escaped defects"/"Incidents"/"Autonomy creep"/"Reward hacking", and the N=3 token `N` defaults to **3**)
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md (§RQ-5 Validation Architecture — the ACC-01..09 test map + the recommended test names; §RQ-6 prose<->schema drift guard (prose Title Case vs schema snake_case); §RQ-4 the FK test pattern)
    - tests/planning/test_bos_outcome_schema.py (REFERENCE — the sibling BOS5-02 suite shape to MATCH: pathlib+json+jsonschema schema loader, parametrized example round-trips, structural assertions, the load+lint stability gate for a hand-authored schema; tests/planning/__init__.py already exists, do NOT recreate it)
  </read_first>
  <action>
    Create `tests/planning/test_bos_governance_schema.py` implementing the ACC-01..06, 08, 09
    checks against `contracts/governance.schema.json` and the
    `.planning/schemas/examples/governance-*.json` records, loaded via pathlib + json +
    jsonschema (reuse the existing tests/planning/__init__.py package marker — do NOT recreate it).
    Implement these test functions (names from RESEARCH §RQ-5):
    - test_schema_is_valid: jsonschema.Draft202012Validator.check_schema on the schema (ACC-01);
      this IS the load+lint stability gate for governance.schema.json (it has no pydantic source,
      so it canNOT join the pydantic regeneration gate).
    - test_autonomy_band_4_coverage: $defs.AutonomyBand.enum == exactly the 4 values (ACC-02).
    - test_privacy_tier_3_coverage: $defs.PrivacyTier.enum == exactly the 3 values (ACC-03).
    - test_data_class_tier_map_shape: every value in DataClassTierMap.properties (and
      additionalProperties) is a $ref to PrivacyTier (ACC-03).
    - test_guardrail_dashboard_6_coverage: GuardrailDashboard.required is exactly the 6 keys,
      additionalProperties is false (closed set) (ACC-04).
    - test_bos6_native_guardrails: in governance-guardrail-fk.json, fatigue/fairness/autonomy_creep
      are source:"bos6" with no linked_guardrail_id (ACC-04).
    - test_bos5_linked_guardrails_require_fk: in the example, escaped_defects/incidents/reward_hacking
      are source:"bos5" with linked_guardrail_id; AND a synthetic bos5 entry missing linked_guardrail_id
      FAILS validation against #/$defs/GuardrailDashboardEntry (proves the schema if/then, ACC-04).
    - test_min_aggregation_n_gte_3: $defs.min_aggregation_n.minimum == 3; a value of 2 FAILS validation
      against that $def, a value of 3 passes (ACC-05).
    - test_surface_governance_config_shape: SurfaceGovernanceConfig.required == the 5 keys, its
      autonomy_band/kill_switch_state are $refs to the AutonomyBand/KillSwitchState $defs (ACC-06).
    - test_surface_governance_config_round_trip: governance-surface-config.json validates against
      #/$defs/SurfaceGovernanceConfig (ACC-06).
    - test_guardrail_fk_validity_with_bos5: load governance-guardrail-fk.json + the guardrail_ids set
      from governance-bos5-guardrail-ids.json; for every entry with source=="bos5", assert
      linked_guardrail_id is present AND in the id set; for source=="bos6", assert no linked_guardrail_id
      (ACC-08, D-17).
    - test_prose_schema_value_consistency: read BOS6-GOVERNANCE-SPEC.md; assert each of the 4 lowercase
      band tokens, 3 lowercase tier tokens, 6 Title-Case guardrail prose names, and the N=3 token
      `N` defaults to **3** is present in the prose; AND assert the schema's AutonomyBand/PrivacyTier
      enums equal the 4/3 value sets and GuardrailDashboard.required equals the 6 snake_case keys (ACC-09).
      Grep the prose for the Title-Case forms and the schema for the snake_case forms separately — do
      NOT match prose Title Case against schema snake_case with one string.
    Use `.venv/bin/python -m pytest`. Do NOT add a pydantic model, do NOT modify export_contract.py or
    any contracts/* file, do NOT author the BOS4 amendment or the ACC-07 consistency test (BOS6-04 owns
    them). Do NOT recreate tests/planning/__init__.py. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/planning/test_bos_governance_schema.py -x -q</automated>
  </verify>
  <acceptance_criteria>
    - `tests/planning/test_bos_governance_schema.py` exists and `.venv/bin/python -m pytest tests/planning/test_bos_governance_schema.py -q` passes with 0 failures/errors.
    - (ACC-01) test_schema_is_valid lints contracts/governance.schema.json against Draft 2020-12 (the stability/drift gate for the hand-authored sibling schema).
    - (ACC-02/03) test_autonomy_band_4_coverage + test_privacy_tier_3_coverage prove the enums are exactly the 4 / 3 values; test_data_class_tier_map_shape proves all DataClassTierMap values are PrivacyTier $refs.
    - (ACC-04) test_guardrail_dashboard_6_coverage proves the closed 6-key set; test_bos6_native_guardrails + test_bos5_linked_guardrails_require_fk prove the source split and that a bos5 entry missing linked_guardrail_id fails validation.
    - (ACC-05) test_min_aggregation_n_gte_3 proves minimum:3 (a value of 2 fails, 3 passes).
    - (ACC-06) test_surface_governance_config_shape + test_surface_governance_config_round_trip prove the record shape and the example round-trip.
    - (ACC-08) test_guardrail_fk_validity_with_bos5 proves every bos5-linked linked_guardrail_id resolves against governance-bos5-guardrail-ids.json and bos6-native entries carry no FK.
    - (ACC-09) test_prose_schema_value_consistency proves the spec prose contains the 4 band / 3 tier / 6 Title-Case guardrail / N=3 tokens and the schema enums equal the same value sets.
    - The suite does NOT load or amend contracts/decision-ledger.schema.json (ACC-07 is BOS6-04's). `git diff --quiet contracts/ .planning/schemas/examples/governance-surface-config.json .planning/schemas/examples/governance-guardrail-fk.json .planning/schemas/examples/governance-bos5-guardrail-ids.json` exits 0 and `git diff --quiet voss/` exits 0 (the suite reads, does not modify, those artifacts).
  </acceptance_criteria>
  <done>The BOS-GOV contract suite exists and passes against the real BOS6-02 schema + Task 1 fixtures; governance.schema.json is lint-gated on every run (ACC-01); the AutonomyBand/PrivacyTier/GuardrailDashboard/min_aggregation_n coverages (ACC-02..05), the SurfaceGovernanceConfig round-trip (ACC-06), the guardrail FK validity (ACC-08), and the prose<->schema drift guard (ACC-09) are all proven; the BOS4 amendment + ACC-07 are left to BOS6-04.</done>
</task>

<task type="auto">
  <name>Task 3: Author BOS6-VALIDATION.md (ACC-01..ACC-10 + BOS13 coordination note)</name>
  <files>.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md</files>
  <read_first>
    - .planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md (§RQ-5 the ACC-01..ACC-10 list verbatim + the Per-Requirement Test Map + the Sampling Rate + §RQ-4 Pitfall 4 the BOS13 forward-declaration coordination note)
    - .planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-VALIDATION.md (REFERENCE — the sibling VALIDATION doc structure to MATCH: frontmatter incl. nyquist_compliant, the ACC list, the per-task verification map, the per-requirement test map)
    - tests/planning/test_bos_governance_schema.py (authored in Task 2 — list its actual test function names + the commands in the verification map)
  </read_first>
  <action>
    Create `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md`
    mirroring the structure of BOS5-VALIDATION.md: frontmatter (including `nyquist_compliant: true`),
    the ACC-01..ACC-10 acceptance-criteria list (verbatim from RESEARCH §RQ-5 — ACC-01 schema lint,
    ACC-02 AutonomyBand 4-coverage, ACC-03 PrivacyTier 3-coverage, ACC-04 GuardrailDashboard 6 + source
    split, ACC-05 min_aggregation_n >= 3, ACC-06 SurfaceGovernanceConfig round-trip, ACC-07 band-enum
    consistency with BOS4 [owned by BOS6-04], ACC-08 guardrail FK validity, ACC-09 prose<->schema
    consistency, ACC-10 this VALIDATION doc + governance.schema.json joined to the CI gate), a
    per-requirement test map (BOS-GOV-01..04 -> the test functions + the
    `.venv/bin/python -m pytest tests/planning/test_bos_governance_schema.py -q` command and, for ACC-07,
    BOS6-04's test), and the sampling rate (per-commit suite run, per-wave full tests/planning/ run, phase
    gate = all ACC green). Include a clearly-marked CROSS-PHASE COORDINATION section stating: the BOS5
    guardrail ids in governance-bos5-guardrail-ids.json (escaped_defects/incidents/reward_hacking) are a
    FORWARD DECLARATION — no BOS5 guardrail fixtures exist yet — and BOS13 MUST use these same
    guardrail_id values when it creates GuardrailMetricSpec records, or the FK link drifts (Pitfall 4).
    Note that ACC-07 + the decision-ledger band-enum amendment are delivered by BOS6-04. NO git add/commit/push.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import re,pathlib; t=pathlib.Path('.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md').read_text(); body='\n'.join(l for l in t.splitlines() if not l.strip().startswith('#')); assert all(f'ACC-{n:02d}' in t for n in range(1,11)), 'ACC-01..10 listed'; assert 'governance-bos5-guardrail-ids' in t and 'BOS13' in t, 'BOS13 forward-declaration coordination note present'; assert 'BOS6-04' in t, 'ACC-07/ledger amendment attributed to BOS6-04'; assert 'test_bos_governance_schema' in t, 'suite referenced'; print('BOS6-VALIDATION.md has ACC-01..10 + BOS13 coordination note + BOS6-04 attribution')"</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-VALIDATION.md` exists and lists ACC-01 through ACC-10 (ACC-10, D-18).
    - It contains a per-requirement test map tying BOS-GOV-01..04 to the test functions in tests/planning/test_bos_governance_schema.py and the pytest command, with ACC-07 attributed to BOS6-04.
    - It contains a CROSS-PHASE COORDINATION note flagging governance-bos5-guardrail-ids.json as a forward declaration that BOS13 must honor when creating GuardrailMetricSpec records (Pitfall 4).
    - `git diff --quiet contracts/ tests/ .planning/schemas/examples/` exits 0 (Task 3 adds only the VALIDATION doc) and `git diff --quiet voss/` exits 0.
  </acceptance_criteria>
  <done>BOS6-VALIDATION.md exists (the doc BOS6 lacked), listing ACC-01..ACC-10 with the per-requirement test map and sampling rate, attributing ACC-07 + the ledger amendment to BOS6-04, and flagging the BOS5/BOS13 guardrail-id forward declaration as the explicit coordination point; no other artifact modified.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (no runtime boundary in this phase) | Docs-only contract validation. The suite reads JSON Schema + example records + the prose spec and asserts structural/value properties; no service, network, or untrusted input at runtime. Threats are governance-contract correctness. |
| example/test author -> existing source artifacts | The plan must NOT cross into contracts/governance.schema.json (BOS6-02), decision-ledger.schema.json (BOS6-04), the other contracts/* files, openapi.json, export_contract.py, or voss/** — fixtures + tests + the VALIDATION doc are new consumers only. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-BOS6-03-01 | Tampering | governance vocabulary coverage erosion (a band/tier/guardrail dropped or an extra one added) | mitigate | ACC-02/03/04 assert the AutonomyBand/PrivacyTier enums and the closed 6-key GuardrailDashboard set are EXACTLY the expected values; any drift fails CI. |
| T-BOS6-03-02 | Tampering / Spoofing | guardrail dashboard FK drift from BOS5 metric ids | mitigate | ACC-08 (test_guardrail_fk_validity_with_bos5) fires if a bos5-linked linked_guardrail_id stops resolving against the declared id set; BOS6-VALIDATION.md flags the BOS13 coordination requirement. |
| T-BOS6-03-03 | Tampering | prose<->schema drift (spec says one value, schema encodes another) | mitigate | ACC-09 greps BOS6-GOVERNANCE-SPEC.md for the band/tier/guardrail/N tokens AND asserts the schema enums equal those sets; a one-sided edit fails CI. |
| T-BOS6-03-04 | Tampering | weakening the anti-surveillance floor (min_aggregation_n below 3) | mitigate | ACC-05 asserts minimum:3 and that a value of 2 fails validation; the floor cannot silently erode. |
| T-BOS6-03-05 | Tampering | silent drift of the hand-authored governance.schema.json | mitigate | ACC-01 (test_schema_is_valid) loads + Draft-2020-12-lints the schema on every run — the drift gate for a schema with no pydantic source. |
| T-BOS6-03-SC | Tampering | package installs | accept | No package-manager installs; `jsonschema` 4.26.0 + pytest already in `.venv` (RESEARCH §Package Legitimacy Audit: no external packages). No legitimacy gate needed. |
</threat_model>

<verification>
- `.venv/bin/python -m pytest tests/planning/test_bos_governance_schema.py -x -q` — full BOS-GOV suite green (ACC-01..06, 08, 09).
- `.venv/bin/python -m pytest tests/planning/ -x -q` — the full planning suite (BOS5 suites + this BOS-GOV suite) green; no regression.
- BOS6-VALIDATION.md verify one-liner — ACC-01..10 listed + BOS13 coordination note + BOS6-04 attribution present.
- `git diff --quiet contracts/ && git diff --quiet voss/` — no contract or runtime source modified by this plan.
</verification>

<success_criteria>
- Three governance example fixtures authored (SurfaceGovernanceConfig, full 6-entry GuardrailDashboard with the bos5/bos6 source split, forward-declared BOS5 id set), each consistent with the BOS6-02 schema.
- BOS-GOV pytest suite authored under tests/planning/ and passing (ACC-01, 02, 03, 04, 05, 06, 08, 09).
- contracts/governance.schema.json lint-gated on every run (ACC-01).
- BOS6-VALIDATION.md authored with ACC-01..ACC-10, the per-requirement test map, and the BOS13 forward-declaration coordination note (ACC-10).
- ACC-07 + the decision-ledger amendment left to BOS6-04; no contracts/* file, openapi.json, export_contract.py, or voss/** modified.
</success_criteria>

<output>
Create `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-03-SUMMARY.md` when done.
</output>
