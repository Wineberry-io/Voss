# Phase BOS6: Privacy, Governance, and Tenant Boundaries — Research (Plans 2–4)

**Researched:** 2026-06-20
**Domain:** JSON Schema contract authoring (Draft 2020-12), cross-file `$ref` mechanics in
Python `jsonschema` 4.26.0 + `referencing` library, pytest contract validation patterns,
cross-phase FK testing
**Confidence:** HIGH (all key technical claims verified against the live codebase and
installed tooling; no speculative library recommendations)

---

<user_constraints>

## User Constraints (from CONTEXT.md D-15..D-18)

### Locked Decisions

**D-15 — New governance.schema.json (5th contracts/ sibling)**
Add `contracts/governance.schema.json`. It encodes governance VOCABULARIES as `$defs`:
`AutonomyBand` enum (4 values), `PrivacyTier` enum (3 values), `DataClass`→tier mapping,
the `GuardrailDashboard` set (6 entries), and `min_aggregation_n`. PLUS a
`SurfaceGovernanceConfig` record `$def` (surface_id, autonomy_band, kill_switch_state) for
validating actual policy-state instances. Mirrors BOS5's vocab+record pattern. The shipped
prose `BOS6-GOVERNANCE-SPEC.md` stays the rationale; the schema is the enforceable contract.
Joins the existing CI drift gate (the pytest suite in `tests/planning/`).

**D-16 — Governance owns the canonical AutonomyBand enum; BOS4 conforms (CROSS-PHASE)**
`contracts/decision-ledger.schema.json` already has free-string `autonomy_band` fields
(top-level field + `AutonomyBandPayload.proposed_band` + `AutonomyBandPayload.current_band`)
with NO enum constraint. `governance.schema.json` becomes the single source of truth for
the four-value enum. A BOS4 follow-up constrains those free-string fields to reference the
canonical enum — via cross-file `$ref` OR mirror-enum + consistency test. Planner picks
the mechanism that keeps the CI drift gate simple. (Research section §D-16 Mechanism gives
the recommendation.)

**D-17 — Hybrid guardrail link — FK to BOS5 where BOS5 owns it, native otherwise**
The 6 BOS6 dashboard guardrails split: BOS5-owned (`escaped_defects`, `incidents`,
`reward_hacking`) carry a `linked_guardrail_id` FK → `outcomes.schema.json`
`GuardrailMetricSpec.guardrail_id`; BOS6-native (`fatigue`, `fairness`, `autonomy_creep`)
are self-contained entries tagged `source: "bos6"`. A test asserts FK validity for the
three linked entries via example fixtures.

**D-18 — Full BOS5-parity pytest suite + Nyquist**
A pytest contract suite in `tests/planning/test_bos_governance_schema.py` asserts: schema
Draft-2020-12 lint; `AutonomyBand` 4-value coverage; `PrivacyTier` 3-value coverage;
`GuardrailDashboard` 6-entry coverage; `min_aggregation_n` present and value ≥ 3;
`SurfaceGovernanceConfig` example round-trip; cross-phase band-enum consistency with BOS4
(D-16); guardrail FK validity with BOS5 (D-17). Schema joins the CI drift gate. Author
`BOS6-VALIDATION.md` with the ACC list.

### Claude's Discretion
- Exact `$def` / field names within `governance.schema.json`
- The cross-file-`$ref`-vs-mirror+consistency-test mechanism for D-16 (research
  recommends mirror+consistency-test; see §D-16 Mechanism)
- Schema versioning notation (mirror the `v` + migration-note convention the other
  `contracts/` siblings use)
- Governance-spec doc structure/format (already shipped as BOS6-01)

### Deferred Ideas (OUT OF SCOPE)
- Raw-content retention TTL window
- Reward/guardrail metric definitions (BOS5)
- Offline-eval gate mechanics (BOS15)
- Event data classes detail (BOS3)
- Cross-source identity resolution (BOS12)
- Kill-switch/autonomy-band RBAC actor/role model (BOS7)
- Runtime enforcement code of any kind

</user_constraints>

---

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOS-GOV-01 | Trust defaults: team-level reporting, no individual rankings, no raw activity scoring, no nudge-engagement optimization | §governance.schema.json Shape: `min_aggregation_n` const + `PrivacyTier` enum; §Anti-Patterns; §Prose↔Schema Drift Guard |
| BOS-GOV-02 | Human approval, override logging, autonomy bands, kill-switch expectations | §governance.schema.json Shape: `AutonomyBand` enum + `SurfaceGovernanceConfig`; §D-16 Mechanism |
| BOS-GOV-03 | Privacy boundaries for code, prompts, agent sessions, calendar/identity data, incident/deploy metadata | §governance.schema.json Shape: `PrivacyTier` enum + `DataClass→tier mapping` |
| BOS-GOV-04 | Guardrail dashboards: fatigue, fairness, escaped defects, incidents, autonomy creep, reward hacking | §governance.schema.json Shape: `GuardrailDashboard`; §D-17 Hybrid Guardrail FK Testing |

</phase_requirements>

---

## Summary

BOS6 plans 2–4 produce one new file (`contracts/governance.schema.json`, the 5th
`contracts/` sibling) and its pytest contract suite, plus a BOS4 cross-phase follow-up plan
that constrains the ledger's three free-string autonomy-band fields to the canonical enum.

The critical technical question is **D-16: cross-file `$ref` vs mirror-enum + consistency
test.** Research resolves this clearly: Python `jsonschema` 4.26.0 + the `referencing`
library fully support multi-schema registries with cross-file `$ref` via `$id`-based URI
resolution — technically feasible. However, the existing hand-authored schemas in
`contracts/` are tested standalone (each schema's pytest suite loads one file), and the
live drift gate for `events.schema.json` is code-generated from Pydantic, not cross-file
JSON-Schema `$ref`. Introducing a cross-file `$ref` into `decision-ledger.schema.json`
requires every test and linter that loads it to also register `governance.schema.json` —
coupling the two schemas' test suites. The mirror-enum + consistency-test approach keeps
files independently lintable with zero test-suite coupling, and a single consistency test
(loads both files, asserts the two enum value arrays are identical) provides the same
machine-checkable guarantee with far less friction. **Recommendation: mirror-enum +
consistency test.** This matches the BOS5-05 precedent (that plan additively amends
`decision-ledger.schema.json` without introducing cross-file `$ref`).

The guardrail FK (D-17) is **not statically checkable** via JSON Schema alone, because
`linked_guardrail_id` values are runtime string identifiers, not `$defs` names. The correct
mechanism is example-fixture-based: a test loads example `GuardrailDashboard` records whose
`linked_guardrail_id` points to example `GuardrailMetricSpec` records from `outcomes.schema.json`,
and asserts every linked ID resolves. This is the same pattern BOS5's ACC-05 uses for
tension-pair coverage.

**Primary recommendation:** One new schema (`contracts/governance.schema.json`) with all
vocabulary `$defs` + `SurfaceGovernanceConfig`; one pytest suite asserting all ACC checks;
one BOS4 follow-up plan that mirrors the `AutonomyBand` enum into `decision-ledger.schema.json`
as a constrained field (additive); one `BOS6-VALIDATION.md`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Governance vocabulary enums | Shared contract (`contracts/`) | — | Language-agnostic; all BOS phases must read the same enum values |
| `SurfaceGovernanceConfig` state shape | Shared contract (`contracts/`) | BOS7 (enforcer) | BOS6 defines the shape; BOS7 web control-plane owns the registry |
| GuardrailDashboard definitions | Shared contract (`contracts/`) | BOS5 (FK target for 3 entries) | BOS6 owns the dashboard definitions; BOS5 owns the underlying metric specs |
| Kill-switch / band change RBAC | BOS7 | — | Explicitly deferred to BOS7 per D-14 |
| Band-enum enforcement at runtime | BOS4 follow-up (schema) | BOS7 (control plane) | Schema constraint is statically checkable; runtime enforcement is BOS7 |
| Guardrail trip condition evaluation | BOS15 (hard-gates) | BOS6 dashboard (display) | BOS6 defines dashboard entries and trip conditions; BOS15 wires gates |

---

## Standard Stack

This is a docs-first contract phase. No new runtime libraries.

### Core

| Tool | Version | Purpose | Why |
|------|---------|---------|-----|
| JSON Schema Draft 2020-12 | — | Normative schema artifact | Matches all 4 existing `contracts/` siblings; language-agnostic |
| `jsonschema` (PyPI) | 4.26.0 [VERIFIED: codebase] | Schema lint + example round-trip tests | Already installed in `.venv`; used by BOS5 suite |
| `referencing` (PyPI) | bundled with jsonschema 4.26 [VERIFIED: codebase] | Multi-schema registry (needed only for D-16 cross-file option, which is NOT recommended) | Available but not needed under mirror+consistency approach |
| pytest | project standard [VERIFIED: codebase] | Contract test runner | Matches BOS5 `tests/planning/test_bos_outcome_schema.py` pattern exactly |

### No New Packages

The governance schema and its test suite require zero new dependencies. Everything needed is
already in `.venv`. [VERIFIED: codebase]

---

## Package Legitimacy Audit

No external packages are installed by this phase. The deliverable is a hand-authored JSON
Schema document and a pytest file. No package legitimacy audit is required.

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

---

## Architecture Patterns

### System Architecture Diagram

```
BOS6-GOVERNANCE-SPEC.md (prose rationale — SHIPPED)
      │  values must match exactly
      ▼
contracts/governance.schema.json (D-15 — NEW)
  $defs:
  ├── AutonomyBand       enum [suggest_only, approve_required,
  │                            auto_with_post_review, full_auto]
  ├── PrivacyTier        enum [team_shareable, team_private, never_leaves_local]
  ├── DataClassTierMap   object { code, prompts, transcripts, ... } -> PrivacyTier
  ├── GuardrailDashboard object (6 entries, 2 sources: bos5-linked | bos6-native)
  ├── min_aggregation_n  const: 3
  └── SurfaceGovernanceConfig { surface_id, autonomy_band, kill_switch_state }
      │
      │  D-16: mirror AutonomyBand enum into ↓
      ▼
contracts/decision-ledger.schema.json (BOS4 — ADDITIVE AMENDMENT)
  autonomy_band: { enum: [same 4 values] }   ← was free-string
  AutonomyBandPayload.proposed_band: { enum: [same 4 values] }
  AutonomyBandPayload.current_band:  { enum: [same 4 values] }
      │
      │  D-17: GuardrailDashboard entries that are bos5-linked carry ↓
      ▼
contracts/outcomes.schema.json (BOS5 — READ ONLY, no amendments)
  GuardrailMetricSpec.guardrail_id  ← FK target for escaped_defects / incidents
                                       / reward_hacking dashboard entries

tests/planning/test_bos_governance_schema.py (D-18 — NEW)
  ├── schema lint
  ├── enum coverage (4 bands, 3 tiers, 6 guardrails)
  ├── min_aggregation_n ≥ 3
  ├── SurfaceGovernanceConfig round-trip
  ├── band-enum consistency with BOS4 (D-16)
  └── guardrail FK validity with BOS5 examples (D-17)

BOS6-VALIDATION.md (ACC list — NEW)
```

### Recommended Project Structure

```
contracts/
├── events.schema.json             # existing — BOS3 (code-generated)
├── openapi.json                   # existing — BOS3 (code-generated)
├── decision-ledger.schema.json    # existing — BOS4 (hand-authored; amended by D-16)
├── outcomes.schema.json           # existing — BOS5 (hand-authored; read-only here)
└── governance.schema.json         # NEW — BOS6 (hand-authored)

tests/planning/
├── test_bos_outcome_schema.py     # existing — BOS5 suite
└── test_bos_governance_schema.py  # NEW — BOS6 suite (D-18)

.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/
├── BOS6-GOVERNANCE-SPEC.md        # existing — prose rationale (BOS6-01)
└── BOS6-VALIDATION.md             # NEW — ACC list

.planning/schemas/examples/
├── outcome-*.json                 # existing — BOS5 fixtures
├── governance-surface-config.json # NEW — SurfaceGovernanceConfig round-trip fixture
└── governance-guardrail-fk.json   # NEW — GuardrailDashboard FK validity fixture
```

---

## RQ-1: governance.schema.json Shape (D-15)

**Confidence:** HIGH — all values taken directly from `BOS6-GOVERNANCE-SPEC.md` (SHIPPED) and
`BOS6-CONTEXT.md` D-01/D-04/D-08/D-10/D-12. No values invented here.

### Top-Level Schema Identity

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://voss.dev/contracts/governance.schema.json",
  "title": "GovernanceContract",
  "description": "BOS6 governance policy vocabularies + surface config record (BOS-GOV-01..04). v: 1. Defines: AutonomyBand enum (4 values), PrivacyTier enum (3 values), DataClass→tier mapping, GuardrailDashboard set (6 entries), min_aggregation_n (const 3), SurfaceGovernanceConfig record. The canonical source of truth for AutonomyBand values; contracts/decision-ledger.schema.json mirrors this enum under D-16. Prose rationale: BOS6-GOVERNANCE-SPEC.md.",
  "type": "object",
  "additionalProperties": false,
  "$comment": "schema_version=1; additive changes (new DataClass key in DataClassTierMap, new GuardrailDashboard entry) do NOT bump this version; breaking changes (altering an existing enum value, renaming a $def) increment the version and require a migration note in BOS6-GOVERNANCE-SPEC.md.",
  ...
}
```

### `$defs` Block — Complete Field Layout

#### `AutonomyBand` enum

Canonical; 4 values from GOVERNANCE-SPEC §Autonomy Bands table + D-01.

```json
"AutonomyBand": {
  "title": "AutonomyBand",
  "description": "The four autonomy bands for BOS recommendation surfaces (BOS-GOV-02, D-01). Canonical source of truth; decision-ledger.schema.json mirrors this enum under D-16. Ordered from most constrained to most autonomous.",
  "type": "string",
  "enum": [
    "suggest_only",
    "approve_required",
    "auto_with_post_review",
    "full_auto"
  ]
}
```

#### `PrivacyTier` enum

3 values from GOVERNANCE-SPEC §Privacy Tiers + D-04.

```json
"PrivacyTier": {
  "title": "PrivacyTier",
  "description": "Three data-sensitivity tiers (BOS-GOV-03, D-04). Ordered from least to most restrictive.",
  "type": "string",
  "enum": [
    "team_shareable",
    "team_private",
    "never_leaves_local"
  ]
}
```

#### `DataClassTierMap` — DataClass→PrivacyTier Mapping

Models the D-04/D-05 "private-by-default" rule as a validated object. Each property's value
is a `$ref` to `PrivacyTier`. `additionalProperties: true` so new data classes are additive.
[ASSUMED: specific property names below match GOVERNANCE-SPEC §Privacy Tiers + §Private-by-default;
planner may rename individual keys]

```json
"DataClassTierMap": {
  "title": "DataClassTierMap",
  "description": "Mapping of data-class identifiers to their default PrivacyTier (BOS-GOV-03, D-04/D-05). Values MUST be PrivacyTier enum members. additionalProperties: true to allow additive data-class additions without a schema version bump.",
  "type": "object",
  "properties": {
    "code":               { "$ref": "#/$defs/PrivacyTier" },
    "prompts":            { "$ref": "#/$defs/PrivacyTier" },
    "agent_transcripts":  { "$ref": "#/$defs/PrivacyTier" },
    "calendar_identity":  { "$ref": "#/$defs/PrivacyTier" },
    "incident_deploy":    { "$ref": "#/$defs/PrivacyTier" },
    "decision_outcomes":  { "$ref": "#/$defs/PrivacyTier" }
  },
  "required": [
    "code", "prompts", "agent_transcripts",
    "calendar_identity", "incident_deploy", "decision_outcomes"
  ],
  "additionalProperties": {
    "$ref": "#/$defs/PrivacyTier"
  }
}
```

Default values (from GOVERNANCE-SPEC, not embedded in the schema — they belong in the
`SurfaceGovernanceConfig` example or a prose table): `code`/`prompts`/`agent_transcripts` →
`never_leaves_local`; `calendar_identity` → `team_private`; `incident_deploy` →
`team_shareable`; `decision_outcomes` → `team_shareable` (derived, not raw).

#### `KillSwitchState` enum

Two states: enabled (all clear) or tripped (surface halted). Name chosen to match D-02
semantics. [ASSUMED: exact names are Claude's Discretion]

```json
"KillSwitchState": {
  "title": "KillSwitchState",
  "description": "The current kill-switch state for a surface (BOS-GOV-02, D-02). enabled = surface is operating normally; tripped = kill-switch is active, surface is in safe state (suggest_only or off).",
  "type": "string",
  "enum": [
    "enabled",
    "tripped"
  ]
}
```

#### `GuardrailDashboard` — 6-entry set

Models the 6 guardrails from GOVERNANCE-SPEC §Guardrail Dashboards + D-10/D-11/D-17.
Represented as an object whose properties are the 6 guardrail identifiers, each with a
`GuardrailDashboardEntry` shape. All 6 are required. `additionalProperties: false` locks
the set; additive extensions require a schema version bump with migration note.

**GuardrailDashboardEntry shape (the `$def` used for all 6 entries):**

```json
"GuardrailDashboardEntry": {
  "title": "GuardrailDashboardEntry",
  "description": "A single governance dashboard guardrail entry (BOS-GOV-04, D-10/D-11). Entries that reference a BOS5 GuardrailMetricSpec carry linked_guardrail_id; BOS6-native entries carry source: 'bos6'.",
  "type": "object",
  "properties": {
    "description": {
      "type": "string",
      "description": "What this guardrail measures (from GOVERNANCE-SPEC)."
    },
    "trip_condition": {
      "type": "string",
      "description": "The trip/alert condition for this dashboard guardrail."
    },
    "source": {
      "type": "string",
      "description": "Ownership tag. 'bos5' = underlying metric owned by BOS5 (linked_guardrail_id required); 'bos6' = self-contained, BOS6 owns the metric definition.",
      "enum": ["bos5", "bos6"]
    },
    "linked_guardrail_id": {
      "type": "string",
      "description": "FK → outcomes.schema.json GuardrailMetricSpec.guardrail_id. Present when source='bos5'; absent when source='bos6'. Validated by example-fixture test (D-17)."
    }
  },
  "required": ["description", "trip_condition", "source"],
  "additionalProperties": false,
  "if": { "properties": { "source": { "const": "bos5" } } },
  "then": { "required": ["linked_guardrail_id"] }
}
```

**GuardrailDashboard object (6 required entries, locked set):**

```json
"GuardrailDashboard": {
  "title": "GuardrailDashboard",
  "description": "The complete set of 6 governance dashboard guardrails (BOS-GOV-04, D-10). Source split (D-11/D-17): fatigue/fairness/autonomy_creep are bos6-native; escaped_defects/incidents/reward_hacking link to BOS5 GuardrailMetricSpec.",
  "type": "object",
  "properties": {
    "fatigue":         { "$ref": "#/$defs/GuardrailDashboardEntry" },
    "fairness":        { "$ref": "#/$defs/GuardrailDashboardEntry" },
    "autonomy_creep":  { "$ref": "#/$defs/GuardrailDashboardEntry" },
    "escaped_defects": { "$ref": "#/$defs/GuardrailDashboardEntry" },
    "incidents":       { "$ref": "#/$defs/GuardrailDashboardEntry" },
    "reward_hacking":  { "$ref": "#/$defs/GuardrailDashboardEntry" }
  },
  "required": [
    "fatigue", "fairness", "autonomy_creep",
    "escaped_defects", "incidents", "reward_hacking"
  ],
  "additionalProperties": false
}
```

#### `min_aggregation_n`

Hard floor from D-12: value is exactly 3.

```json
"min_aggregation_n": {
  "title": "MinAggregationN",
  "description": "k-anonymity-style minimum aggregation floor (BOS-GOV-01, D-08/D-12). A team metric is NEVER reported for fewer than this many contributors. Hard floor = 3; deployments may raise it but never lower it below 3.",
  "type": "integer",
  "const": 3,
  "minimum": 3
}
```

Note: `const: 3` and `minimum: 3` together express both the fixed default and the
directional constraint. Using `const` alone would prevent a deployment from raising N;
using `minimum: 3` alone loses the canonical value. Both together — `const` as the schema
expression of the fixed default, `minimum` as a separate annotation — is the right
approach for this "hard floor but configurable upward" semantics. In JSON Schema
Draft-2020-12, `const` and `minimum` can coexist; the `const: 3` is the normative default
and the `minimum: 3` documents the floor. [ASSUMED: exact keyword combination; planner
may instead use `minimum: 3` only with a description stating "default is 3"]

#### `SurfaceGovernanceConfig` record

The validatable policy-state instance record for a single recommendation surface.

```json
"SurfaceGovernanceConfig": {
  "title": "SurfaceGovernanceConfig",
  "description": "A validated governance-state record for one BOS recommendation surface (D-15). Captures the surface's current autonomy band and kill-switch state. Not a runtime event — a config/policy state record validated against this schema before being committed to the BOS7 control-plane registry.",
  "type": "object",
  "properties": {
    "v": {
      "type": "integer",
      "const": 1,
      "default": 1,
      "description": "Schema version. Mirrors BOS4/BOS5 versioning convention."
    },
    "surface_id": {
      "type": "string",
      "description": "Stable unique identifier for the recommendation surface. E.g. 'delegation', 'review_depth', 'validation_depth'."
    },
    "autonomy_band": {
      "$ref": "#/$defs/AutonomyBand",
      "description": "The surface's current autonomy band (constrained to the canonical AutonomyBand enum)."
    },
    "kill_switch_state": {
      "$ref": "#/$defs/KillSwitchState",
      "description": "The surface's current kill-switch state."
    },
    "effective_from": {
      "type": "string",
      "format": "date-time",
      "description": "When this config became effective. Used for audit / policy versioning."
    }
  },
  "required": ["v", "surface_id", "autonomy_band", "kill_switch_state", "effective_from"],
  "additionalProperties": false
}
```

### Top-Level Schema Properties

The schema root exposes the vocab definitions as named top-level properties (same pattern as
`outcomes.schema.json` exposing `categorical_label`, `outcome_measure`, etc.):

```json
"properties": {
  "autonomy_band":         { "$ref": "#/$defs/AutonomyBand" },
  "privacy_tier":          { "$ref": "#/$defs/PrivacyTier" },
  "data_class_tier_map":   { "$ref": "#/$defs/DataClassTierMap" },
  "guardrail_dashboard":   { "$ref": "#/$defs/GuardrailDashboard" },
  "min_aggregation_n":     { "$ref": "#/$defs/min_aggregation_n" },
  "surface_governance_config": { "$ref": "#/$defs/SurfaceGovernanceConfig" }
}
```

No `required` at the top level — the schema is primarily a `$defs` registry; individual
`$defs` are referenced from tests and from the BOS4 follow-up.

---

## RQ-2 & RQ-3: D-16 Cross-File Mechanism and BOS4 Follow-Up

**Confidence:** HIGH — verified against installed `jsonschema` 4.26.0, `referencing`
library, and existing `contracts/` test patterns. [VERIFIED: codebase probe 2026-06-20]

### Technical Feasibility of Cross-File `$ref`

Python `jsonschema` 4.26.0 ships the `referencing` library which supports multi-schema
registries. A test can register multiple schemas by `$id` and resolve cross-file `$ref`
pointers:

```python
import json, pathlib
import referencing, referencing.jsonschema as rj
from referencing import Registry

governance = json.loads(pathlib.Path("contracts/governance.schema.json").read_text())
ledger = json.loads(pathlib.Path("contracts/decision-ledger.schema.json").read_text())

r_gov = rj.DRAFT202012.create_resource(governance)
r_led = rj.DRAFT202012.create_resource(ledger)

registry = Registry().with_resources([
    (governance["$id"], r_gov),
    (ledger["$id"],     r_led),
])
```

This works. Cross-file `$ref` in the form
`"$ref": "https://voss.dev/contracts/governance.schema.json#/$defs/AutonomyBand"`
from within `decision-ledger.schema.json` would resolve correctly when both schemas are
registered. [VERIFIED: codebase probe — registry construction succeeds]

### Why Cross-File `$ref` is NOT Recommended (D-16)

Despite technical feasibility, cross-file `$ref` introduces three practical problems for
this codebase:

1. **Test-suite coupling.** The existing `test_bos_outcome_schema.py` suite loads one
   schema file via `json.loads(SCHEMA_PATH.read_text())` and calls
   `jsonschema.Draft202012Validator.check_schema(schema)` — a standalone lint. If
   `decision-ledger.schema.json` contains a `$ref` to `governance.schema.json`, every
   test and linter that loads the ledger schema also needs `governance.schema.json`
   registered in the same registry. The BOS4 test suite `test_bos_decision_policy_context.py`
   does not yet use a multi-schema registry and would break on any `$ref` resolution check.

2. **`additionalProperties: false` complexity.** The ledger schema has
   `"additionalProperties": false` at the top level. Adding a `$ref` in a `properties`
   value alongside a `type: "string"` constraint requires Draft-2020-12 `$ref` +
   sibling-keyword semantics, which is valid but harder to read and more error-prone than
   an inline `enum`.

3. **Standalone lintability.** Each hand-authored schema in `contracts/` is designed to be
   lint-checkable in isolation (`jsonschema.Draft202012Validator.check_schema(schema)` on
   one loaded JSON document). A `$ref` to an external URI makes the standalone lint
   incomplete: the check_schema meta-validation passes, but a `RefResolver` / multi-schema
   registry is needed to validate example instances. This makes CI gate behavior
   inconsistent across schemas.

### Recommended Mechanism: Mirror-Enum + Consistency Test

**Recommended:** Add an inline `enum` constraint to the three autonomy-band fields in
`decision-ledger.schema.json` with the same four values, then write one consistency test
that asserts the two enum value arrays are identical.

**BOS4 follow-up amendment — three fields to constrain:**

1. Top-level `autonomy_band` property:
```json
"autonomy_band": {
  "title": "Autonomy Band",
  "description": "The autonomy band in effect for this decision (D-06). Constrained to the canonical BOS6 AutonomyBand enum (D-16). See governance.schema.json.",
  "type": "string",
  "enum": [
    "suggest_only",
    "approve_required",
    "auto_with_post_review",
    "full_auto"
  ]
}
```

2. `AutonomyBandPayload.proposed_band`:
```json
"proposed_band": {
  "title": "Proposed Band",
  "description": "The autonomy band the recommendation proposed. Constrained to the canonical BOS6 AutonomyBand enum (D-16).",
  "type": "string",
  "enum": ["suggest_only", "approve_required", "auto_with_post_review", "full_auto"]
}
```

3. `AutonomyBandPayload.current_band`:
```json
"current_band": {
  "title": "Current Band",
  "description": "The autonomy band in effect before this decision. Constrained to the canonical BOS6 AutonomyBand enum (D-16).",
  "type": "string",
  "enum": ["suggest_only", "approve_required", "auto_with_post_review", "full_auto"]
}
```

**Consistency test (the machine-checkable guard):**

```python
# In tests/planning/test_bos_governance_schema.py — ACC-07
def test_band_enum_consistent_with_bos4_ledger(schema, defs):
    """D-16: governance.schema.json is canonical; decision-ledger mirrors the enum."""
    gov_band_values = set(defs["AutonomyBand"]["enum"])

    ledger_schema = json.loads((REPO / "contracts" / "decision-ledger.schema.json").read_text())
    ledger_ab = ledger_schema["properties"]["autonomy_band"].get("enum")
    payload_proposed = ledger_schema["$defs"]["AutonomyBandPayload"]["properties"]["proposed_band"].get("enum")
    payload_current  = ledger_schema["$defs"]["AutonomyBandPayload"]["properties"]["current_band"].get("enum")

    assert set(ledger_ab) == gov_band_values, "autonomy_band enum mismatch with governance canonical"
    assert set(payload_proposed) == gov_band_values, "proposed_band enum mismatch with governance canonical"
    assert set(payload_current)  == gov_band_values, "current_band enum mismatch with governance canonical"
```

This test fires if anyone edits the enum in either file without updating the other.

### Coordination with BOS5-05 (policy_context amendment to the same file)

BOS5-05 adds `policy_context` to `contracts/decision-ledger.schema.json`. The D-16 BOS4
follow-up adds `enum` constraints to the three `autonomy_band` fields in the same file.
These are **orthogonal amendments** — `policy_context` is a new required field at the top
level; the enum constraints touch existing field definitions.

**Recommendation: keep them as SEPARATE follow-up plans** (one for BOS5-05's
`policy_context`, one for BOS6's D-16 band-enum). Reasons:
- BOS5-05 may already be executed (it has a PLAN.md); merging the two would require
  amending an already-planned BOS4 follow-up
- The two amendments serve different purposes (OPE logging vs governance vocabulary); keeping
  them separate keeps each plan's `must_haves` narrow and its diff reviewable
- Each can be verified independently: the band-enum consistency test is in BOS6's test suite;
  the `policy_context` presence test is in its own `test_bos_decision_policy_context.py`

If BOS5-05 has already executed when BOS6's BOS4 follow-up runs, the follow-up simply amends
the already-amended file. The `additionalProperties: false` top-level constraint does not
interfere — enum constraints are not new properties, they are narrowing annotations on
existing properties.

---

## RQ-4: Guardrail FK Validity Testing (D-17)

**Confidence:** HIGH — the mechanism is definitively "example-fixture-based, not static
schema validation." This is a structural fact about how JSON Schema FK links work.

### What is Statically Checkable vs Example-Based

| Check | Statically Checkable in JSON Schema? | Mechanism |
|-------|-------------------------------------|-----------|
| `linked_guardrail_id` is a string | Yes | `"type": "string"` in `GuardrailDashboardEntry` |
| `source: "bos5"` requires `linked_guardrail_id` to be present | Yes | `if`/`then` in schema |
| `linked_guardrail_id` value resolves to an actual `GuardrailMetricSpec.guardrail_id` | NO — this is a value-to-value FK, not a `$defs` name | Example-fixture test (see below) |
| `source: "bos6"` entries have no `linked_guardrail_id` | Yes | Schema shape (`required` does not include `linked_guardrail_id` for bos6) |

JSON Schema cannot express "the value of field X must equal the value of field Y in another
document." FK validity is always example-based. This is the same constraint as BOS5's
ACC-05 (tension-pair coverage), which used example `GuardrailMetricSpec` records to verify
that `linked_reward_objective` values matched named objectives.

### FK Test Pattern

The test loads two fixtures and asserts every `linked_guardrail_id` in the BOS6 example
matches a `guardrail_id` in the BOS5 example set:

```python
# In tests/planning/test_bos_governance_schema.py — ACC-08
def test_guardrail_fk_validity_with_bos5(schema, defs):
    """D-17: BOS5-linked guardrail entries carry linked_guardrail_id that resolves
    to a guardrail_id in the BOS5 GuardrailMetricSpec example set."""
    # Load the BOS6 example GuardrailDashboard fixture
    dashboard_fixture = json.loads(
        (EXAMPLES_DIR / "governance-guardrail-fk.json").read_text()
    )
    # Load BOS5 example guardrail metric specs (the FK targets)
    bos5_guardrail_ids = _load_bos5_guardrail_ids()  # see below

    for key, entry in dashboard_fixture.items():
        if entry.get("source") == "bos5":
            lid = entry.get("linked_guardrail_id")
            assert lid is not None, f"{key}: source=bos5 requires linked_guardrail_id"
            assert lid in bos5_guardrail_ids, (
                f"{key}: linked_guardrail_id '{lid}' not found in BOS5 GuardrailMetricSpec examples"
            )
        else:  # source == "bos6"
            assert "linked_guardrail_id" not in entry or entry.get("linked_guardrail_id") is None, \
                f"{key}: source=bos6 must not carry linked_guardrail_id"
```

```python
def _load_bos5_guardrail_ids() -> set[str]:
    """Collect guardrail_ids from BOS5 example fixtures or the outcomes schema itself."""
    # Option A: load from example fixture files (if BOS5 shipped guardrail examples)
    # Currently no guardrail example fixtures exist in .planning/schemas/examples/
    # Option B: load from a dedicated BOS6 fixture that declares the expected BOS5 IDs
    # Option C: load from a hardcoded set derived from BOS5 spec
    # Recommendation: Option B — one fixture file defines the expected BOS5 guardrail IDs
    # (see Required Fixtures below)
    ids_fixture = json.loads(
        (EXAMPLES_DIR / "governance-bos5-guardrail-ids.json").read_text()
    )
    return set(ids_fixture["guardrail_ids"])
```

### Required Fixtures

| File | Purpose |
|------|---------|
| `.planning/schemas/examples/governance-surface-config.json` | A valid `SurfaceGovernanceConfig` record — used for ACC-06 round-trip test |
| `.planning/schemas/examples/governance-guardrail-fk.json` | Example `GuardrailDashboard` object with all 6 entries — 3 bos5-linked (with `linked_guardrail_id`), 3 bos6-native |
| `.planning/schemas/examples/governance-bos5-guardrail-ids.json` | The set of BOS5 `guardrail_id` values that BOS6 links to (e.g. `{"guardrail_ids": ["gmspec-rework-rate", "gmspec-escaped-defect-rate", "gmspec-reward-hacking"]}`) |

**Important:** The BOS5 guardrail IDs in the FK fixture must match the actual
`guardrail_id` values in any real BOS5 `GuardrailMetricSpec` examples, or in the BOS5
spec/implementation. As of 2026-06-20, no BOS5 guardrail example fixtures exist in
`.planning/schemas/examples/` [VERIFIED: codebase]. The BOS5 spec and
`outcomes.schema.json` define the `guardrail_id` field as a free string —
the actual IDs are populated by BOS13. For now, the fixture file establishes the
EXPECTED IDs that BOS6 plans to link to; BOS13 must use these same IDs when it creates
`GuardrailMetricSpec` records. This is an explicit cross-phase coordination point to note
in `BOS6-VALIDATION.md`.

---

## RQ-5: Validation Architecture (D-18)

**Confidence:** HIGH — mirrors BOS5's ACC pattern exactly; all commands verified against
project's pytest setup.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (project standard) |
| Config file | `pyproject.toml` (project root) |
| Quick run command | `.venv/bin/python -m pytest tests/planning/test_bos_governance_schema.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/planning/ -x` |

This is a docs/contract phase. All tests validate artifact consistency (schema lint,
example round-trips, coverage checks, cross-schema value consistency). No live services
required. All tests run in < 1 second each.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOS-GOV-01..04 | `contracts/governance.schema.json` is a valid Draft 2020-12 schema (meta-schema lint) | unit | `pytest tests/planning/test_bos_governance_schema.py::test_schema_is_valid -x` | ❌ Wave 0 |
| BOS-GOV-02 | `AutonomyBand` `$def` present with exactly 4 values: `suggest_only`, `approve_required`, `auto_with_post_review`, `full_auto` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_autonomy_band_4_coverage -x` | ❌ Wave 0 |
| BOS-GOV-03 | `PrivacyTier` `$def` present with exactly 3 values: `team_shareable`, `team_private`, `never_leaves_local` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_privacy_tier_3_coverage -x` | ❌ Wave 0 |
| BOS-GOV-03 | `DataClassTierMap` `$def` present; all values are `$ref` to `PrivacyTier` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_data_class_tier_map_shape -x` | ❌ Wave 0 |
| BOS-GOV-04 | `GuardrailDashboard` `$def` present with exactly 6 required entries: `fatigue`, `fairness`, `autonomy_creep`, `escaped_defects`, `incidents`, `reward_hacking` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_guardrail_dashboard_6_coverage -x` | ❌ Wave 0 |
| BOS-GOV-04 | 3 bos6-native entries (`fatigue`, `fairness`, `autonomy_creep`) have `source: "bos6"` and no `linked_guardrail_id` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_bos6_native_guardrails -x` | ❌ Wave 0 |
| BOS-GOV-04 | 3 bos5-linked entries (`escaped_defects`, `incidents`, `reward_hacking`) require `source: "bos5"` AND `linked_guardrail_id` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_bos5_linked_guardrails_require_fk -x` | ❌ Wave 0 |
| BOS-GOV-01 | `min_aggregation_n` `$def` present; its `minimum` is 3 (or `const` is 3) | unit | `pytest tests/planning/test_bos_governance_schema.py::test_min_aggregation_n_gte_3 -x` | ❌ Wave 0 |
| BOS-GOV-02 | `SurfaceGovernanceConfig` `$def` present with required fields: `v`, `surface_id`, `autonomy_band`, `kill_switch_state`, `effective_from` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_surface_governance_config_shape -x` | ❌ Wave 0 |
| BOS-GOV-02 | `SurfaceGovernanceConfig` example round-trip: a valid example fixture validates against the schema | unit | `pytest tests/planning/test_bos_governance_schema.py::test_surface_governance_config_round_trip -x` | ❌ Wave 0 |
| BOS-GOV-02 (D-16) | Band-enum consistency with BOS4: `governance.schema.json` `AutonomyBand.enum` == `decision-ledger.schema.json` `autonomy_band.enum` == `proposed_band.enum` == `current_band.enum` (all 4 fields must have the same 4 values) | unit | `pytest tests/planning/test_bos_governance_schema.py::test_band_enum_consistent_with_bos4_ledger -x` | ❌ Wave 0 |
| BOS-GOV-04 (D-17) | Guardrail FK validity: every `linked_guardrail_id` in the bos5-linked example entries resolves to a known BOS5 `guardrail_id` | unit | `pytest tests/planning/test_bos_governance_schema.py::test_guardrail_fk_validity_with_bos5 -x` | ❌ Wave 0 |
| BOS-GOV-01..04 | Prose↔schema consistency: `BOS6-GOVERNANCE-SPEC.md` contains the 4 band names, 3 tier names, 6 guardrail names, and the string "3" (for N=3) | unit (file grep) | `pytest tests/planning/test_bos_governance_schema.py::test_prose_schema_value_consistency -x` | ❌ Wave 0 |
| All | `BOS6-VALIDATION.md` exists and contains ACC-01 through ACC-09 | unit (file presence + grep) | `pytest tests/planning/test_bos_governance_schema.py::test_validation_doc_exists -x` | ❌ Wave 0 |

### Acceptance Criteria (ACC) List

| ACC ID | Description |
|--------|-------------|
| ACC-01 | `contracts/governance.schema.json` exists and passes Draft 2020-12 meta-schema lint (`jsonschema.Draft202012Validator.check_schema`) |
| ACC-02 | `AutonomyBand` `$def` has exactly 4 values: `suggest_only`, `approve_required`, `auto_with_post_review`, `full_auto` |
| ACC-03 | `PrivacyTier` `$def` has exactly 3 values: `team_shareable`, `team_private`, `never_leaves_local` |
| ACC-04 | `GuardrailDashboard` `$def` has exactly 6 required property keys; all 6 entries validate against `GuardrailDashboardEntry`; `fatigue`/`fairness`/`autonomy_creep` are `source: "bos6"` with no `linked_guardrail_id`; `escaped_defects`/`incidents`/`reward_hacking` are `source: "bos5"` with `linked_guardrail_id` present |
| ACC-05 | `min_aggregation_n` `$def` has `minimum: 3` (value ≥ 3 enforced) |
| ACC-06 | `SurfaceGovernanceConfig` round-trip: example fixture at `.planning/schemas/examples/governance-surface-config.json` validates against the schema without errors |
| ACC-07 | Band-enum consistency: `governance.schema.json#/$defs/AutonomyBand/enum` == `decision-ledger.schema.json#/properties/autonomy_band/enum` == `decision-ledger.schema.json#/$defs/AutonomyBandPayload/properties/proposed_band/enum` == `decision-ledger.schema.json#/$defs/AutonomyBandPayload/properties/current_band/enum` (all four must be the same 4-value set) |
| ACC-08 | Guardrail FK validity: all `linked_guardrail_id` values in the bos5-linked governance example entries appear in the expected BOS5 guardrail ID set (loaded from `.planning/schemas/examples/governance-bos5-guardrail-ids.json`) |
| ACC-09 | Prose↔schema consistency: `BOS6-GOVERNANCE-SPEC.md` contains all 4 band values, all 3 tier values, all 6 guardrail key names, and the floor value "3" (prevents spec/schema drift) |
| ACC-10 | `BOS6-VALIDATION.md` exists with ACC-01..ACC-09 listed; `contracts/governance.schema.json` joined to the CI drift gate (present in `tests/planning/` which runs under `pytest -q -m "not live"`) |

### Sampling Rate

- **Per task commit:** `.venv/bin/python -m pytest tests/planning/test_bos_governance_schema.py -x`
- **Per wave merge:** `.venv/bin/python -m pytest tests/planning/ -x`
- **Phase gate:** All ACC-01..ACC-10 green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `contracts/governance.schema.json` — the normative governance vocab + state record schema
- [ ] `tests/planning/test_bos_governance_schema.py` — all governance contract tests
- [ ] `.planning/schemas/examples/governance-surface-config.json` — `SurfaceGovernanceConfig` round-trip fixture
- [ ] `.planning/schemas/examples/governance-guardrail-fk.json` — `GuardrailDashboard` FK validity fixture (6 entries)
- [ ] `.planning/schemas/examples/governance-bos5-guardrail-ids.json` — expected BOS5 `guardrail_id` set for FK test
- [ ] `BOS6-VALIDATION.md` — ACC-01..ACC-10 listed
- [ ] BOS4 follow-up plan: amend `contracts/decision-ledger.schema.json` with `enum` constraints on 3 autonomy-band fields + migration note

---

## RQ-6: Prose↔Schema Drift Guard (D-15/D-18)

**Confidence:** HIGH — grep-based file test is a standard pattern in this codebase.

The schema encodes values from `BOS6-GOVERNANCE-SPEC.md`. If someone updates the prose
without updating the schema (or vice versa), ACC-09 catches it. The test is a file-grep
check:

```python
# ACC-09 — in test_bos_governance_schema.py
SPEC_PATH = REPO / ".planning" / "phases" / "BOS6-privacy-governance-and-tenant-boundaries" \
            / "BOS6-GOVERNANCE-SPEC.md"

EXPECTED_IN_SPEC = [
    # AutonomyBand values
    "suggest_only", "approve_required", "auto_with_post_review", "full_auto",
    # PrivacyTier values
    "team_shareable", "team_private", "never_leaves_local",
    # GuardrailDashboard keys (as they appear in the spec prose)
    "Fatigue", "Fairness", "Escaped defects", "Incidents", "Autonomy creep", "Reward hacking",
    # Aggregation floor
    "N` defaults to **3**",   # exact prose from the spec
]

def test_prose_schema_value_consistency(defs):
    spec_text = SPEC_PATH.read_text()
    for token in EXPECTED_IN_SPEC:
        assert token in spec_text, f"BOS6-GOVERNANCE-SPEC.md missing expected token: {token!r}"

    # Also confirm schema has the same values
    assert set(defs["AutonomyBand"]["enum"]) == {
        "suggest_only", "approve_required", "auto_with_post_review", "full_auto"
    }
    assert set(defs["PrivacyTier"]["enum"]) == {
        "team_shareable", "team_private", "never_leaves_local"
    }
```

The guardrail names in the spec use Title Case prose ("Escaped defects") while the schema
uses snake_case keys (`escaped_defects`). The test should grep for the prose form in the
spec and separately check the schema keys — not try to match both with one string.

[ASSUMED: exact prose tokens in `BOS6-GOVERNANCE-SPEC.md` — verify against the actual file
before writing the test. The N=3 token `"N` defaults to **3**"` is taken directly from
the shipped spec text.]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-file enum enforcement | Custom runtime enum validator | Mirror-enum + consistency test in pytest | Static approach; fits existing standalone-lint pattern; zero coupling between test suites |
| FK validity | JSON Schema `$ref` to a runtime value | Example-fixture test asserting ID resolution | JSON Schema cannot express value-to-value FK; fixtures are the right mechanism |
| Guardrail metric definitions | Redefine escaped_defects/incidents/reward_hacking metric specs in BOS6 | `linked_guardrail_id` FK → `outcomes.schema.json` `GuardrailMetricSpec.guardrail_id` | BOS5 owns those definitions; duplication would drift |
| Prose↔schema sync | Manual audit on each change | ACC-09 grep test | Automated; fires on every CI run |
| Schema lint | Custom JSON parser | `jsonschema.Draft202012Validator.check_schema(schema)` | Already in `.venv`; same as BOS5 pattern |

---

## Common Pitfalls

### Pitfall 1: Cross-File `$ref` in decision-ledger.schema.json

**What goes wrong:** Planner chooses the cross-file `$ref` approach for D-16. The ledger
schema now requires `governance.schema.json` to be in the resolver registry for any
validation, including the ACC-14 standalone lint in `test_bos_decision_policy_context.py`.
That test breaks without changes.

**Why it happens:** Cross-file `$ref` feels like the "correct" single-source-of-truth
approach for an enum.

**How to avoid:** Use mirror-enum + consistency test (ACC-07). The consistency test IS the
machine-checkable link. [VERIFIED: this is the recommendation from researching the actual
test patterns in the codebase]

**Warning signs:** `"$ref": "https://voss.dev/contracts/governance.schema.json#/..."` in
`decision-ledger.schema.json`.

### Pitfall 2: Embedding the N=3 value as a tunable field rather than a `const`

**What goes wrong:** `min_aggregation_n` is defined as `"type": "integer", "minimum": 3`
without a `const`, making the schema accept any integer ≥ 3. A deployment writes
`min_aggregation_n: 1` and passes schema validation.

**Why it happens:** "Configurable upward" is interpreted as "no const needed."

**How to avoid:** Use `"const": 3` to express the canonical value AND `"minimum": 3` to
express the floor direction. The prose spec states N MAY be raised but never lowered;
the `minimum: 3` encodes that floor. A deployment config that wants N=5 creates a
deployment-specific override config, not a different schema value. [ASSUMED: `const`+`minimum`
co-usage — see RQ-1 §min_aggregation_n discussion]

### Pitfall 3: GuardrailDashboard as an Array Instead of an Object

**What goes wrong:** `GuardrailDashboard` is modeled as an array of 6 `GuardrailDashboardEntry`
objects. The coverage test counts array length; adding a 7th entry passes.

**Why it happens:** Arrays feel natural for "a set of N things."

**How to avoid:** Model as a named-property object with `additionalProperties: false` and all
6 keys in `required`. This makes coverage machine-checkable by schema (not just by test) and
prevents silent addition of new guardrails without a schema version bump.

### Pitfall 4: Omitting the BOS5-Guardrail ID Fixture and Assuming IDs

**What goes wrong:** The FK test hardcodes BOS5 guardrail IDs that were never actually
assigned by BOS5 (e.g. `"gmspec-escaped-defect-rate"`). When BOS13 creates actual
`GuardrailMetricSpec` records with different IDs, the FK link in BOS6's governance
contract is silently wrong.

**Why it happens:** No BOS5 guardrail example fixtures exist yet; it is tempting to
invent plausible IDs.

**How to avoid:** The `governance-bos5-guardrail-ids.json` fixture should be treated as
a PLACEHOLDER requiring coordination with the BOS5/BOS13 track. The BOS6-VALIDATION.md
should explicitly note this as an open coordination point: "BOS13 must use the
`guardrail_id` values listed in `governance-bos5-guardrail-ids.json` when creating
`GuardrailMetricSpec` records." [ASSUMED: the specific IDs are not yet established; this
fixture is a forward declaration that BOS13 must honor]

### Pitfall 5: Forgetting the Three-Field BOS4 Amendment

**What goes wrong:** The BOS4 follow-up constrains only the top-level `autonomy_band`
property and misses `AutonomyBandPayload.proposed_band` and
`AutonomyBandPayload.current_band`. The consistency test (ACC-07) only checks the
top-level field. The payload fields remain free-string.

**Why it happens:** The top-level `autonomy_band` field is the most obvious one; the
payload fields are inside a `$defs` block and easier to miss.

**How to avoid:** ACC-07 must explicitly assert all three fields: the top-level
`autonomy_band`, `AutonomyBandPayload.proposed_band`, and `AutonomyBandPayload.current_band`.
The BOS4 follow-up plan's `must_haves.truths` should enumerate all three amendment targets.

---

## Runtime State Inventory

SKIPPED — this is a greenfield docs/contract phase. No runtime state renaming or migration.
`contracts/governance.schema.json` does not exist yet; it is a net-new file.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + `.venv` | Running contract tests | ✓ | 3.13.5 [VERIFIED] | — |
| `jsonschema` (PyPI) | Schema lint + example round-trip | ✓ | 4.26.0 [VERIFIED] | — |
| `referencing` (PyPI) | Multi-schema registry (not needed for recommended approach) | ✓ | bundled [VERIFIED] | — |
| pytest | Test runner | ✓ | project standard [VERIFIED] | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `const: 3` + `minimum: 3` is the right JSON Schema expression for "fixed default = 3, floor = 3, no lower" | RQ-1 §min_aggregation_n | Low — planner may use `minimum: 3` only + description; either encodes the floor; no functional difference in the contract test |
| A2 | `DataClassTierMap` property names (`code`, `prompts`, `agent_transcripts`, `calendar_identity`, `incident_deploy`, `decision_outcomes`) | RQ-1 §DataClassTierMap | Low — names are Claude's Discretion; the schema pattern is correct regardless of the exact property names |
| A3 | `KillSwitchState` enum values are `enabled` / `tripped` | RQ-1 §KillSwitchState | Low — exact strings are Claude's Discretion; semantics from D-02 |
| A4 | Guardrail key names in the schema are snake_case: `fatigue`, `fairness`, `autonomy_creep`, `escaped_defects`, `incidents`, `reward_hacking` | RQ-1 §GuardrailDashboard | Low — names follow the prose section headers snake-cased; planner may choose different casing |
| A5 | The BOS5 guardrail IDs that BOS6 links to are not yet established; `governance-bos5-guardrail-ids.json` is a forward-declaration placeholder | RQ-4 §Required Fixtures | Medium — if BOS13 never creates `GuardrailMetricSpec` records with the expected IDs, the FK link is wrong; this is a cross-phase coordination risk |
| A6 | Prose↔schema grep tokens in ACC-09, specifically the N=3 token `"N\` defaults to **3**"` | RQ-6 §Prose Drift Guard | Low — verify exact prose text against `BOS6-GOVERNANCE-SPEC.md` before writing the test |
| A7 | BOS5-05 (policy_context BOS4 follow-up) is a separate plan from the D-16 BOS4 band-enum follow-up | RQ-3 §Coordination | Low — if BOS5-05 has not yet executed, the two can be combined in one amendment; keeping them separate is the recommended path |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-string `autonomy_band` in decision-ledger | Enum-constrained `autonomy_band` mirroring governance canonical | D-16 (BOS6 follow-up) | Silent drift between band names and the governance spec is caught at schema lint time |
| Prose-only governance policy | Machine-checkable governance schema + pytest suite | BOS6 plans 2-4 | Downstream phases can validate their policy-state instances against the schema |
| Ad-hoc guardrail dashboard definition | Structured `GuardrailDashboard` with FK link to BOS5 metrics | D-17 | Single source of truth for each metric; no duplication; FK test catches ID drift |

---

## Security Domain

BOS6 is a docs/contract phase. No runtime code, no auth, no user data flow.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a |
| V3 Session Management | no | n/a |
| V4 Access Control | no | schema models the access control POLICY; BOS7 enforces it |
| V5 Input Validation | yes (indirectly) | The governance schema is itself the validation contract for future BOS7 policy-state writers. Schema must use `additionalProperties: false` + required fields to reject malformed `SurfaceGovernanceConfig` records |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for Governance Contracts

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Band escalation without the required gate | Tampering / Elevation of privilege | `SurfaceGovernanceConfig` records validated against schema before commit; band-change audit-log requirement is in GOVERNANCE-SPEC; BOS7 owns RBAC |
| Individual attribution leakage via `DataClassTierMap` misclassification | Information disclosure | Schema enforces `PrivacyTier` enum on all `DataClassTierMap` values; `never_leaves_local` is the default for sensitive classes |
| Guardrail dashboard drift from BOS5 metric definitions | Tampering / Spoofing | ACC-08 FK test fires if `linked_guardrail_id` values diverge from BOS5 `guardrail_id` set |

---

## Sources

### Primary (HIGH confidence)

- `contracts/decision-ledger.schema.json` — verified `autonomy_band` is free-string (no enum); `additionalProperties: false` confirmed; 3 fields needing amendment identified. [VERIFIED: codebase read 2026-06-20]
- `contracts/outcomes.schema.json` — confirmed `GuardrailMetricSpec.guardrail_id` (FK target), `role` enum (`hard_gate`|`dashboard`), schema structure. [VERIFIED: codebase read 2026-06-20]
- `contracts/events.schema.json` — confirmed discriminated-union `$defs` pattern; Draft-2020-12 `$schema` + `$id` structure. [VERIFIED: codebase read 2026-06-20]
- `tests/planning/test_bos_outcome_schema.py` — confirmed BOS5 suite structure; standalone-schema-load pattern; ACC numbering approach. [VERIFIED: codebase read 2026-06-20]
- `tests/harness/server/test_contract_drift.py` — confirmed that the CI drift gate for `events.schema.json` is code-generation based (not cross-file `$ref`); hand-authored schemas use pytest as their drift gate. [VERIFIED: codebase read 2026-06-20]
- `.venv/bin/python -c "import jsonschema; ..."` + `referencing` library probe — confirmed jsonschema 4.26.0, `referencing` available, multi-schema registry construction works. [VERIFIED: codebase probe 2026-06-20]
- `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-GOVERNANCE-SPEC.md` — all schema values taken from shipped prose. [VERIFIED: codebase read 2026-06-20]
- `.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-CONTEXT.md` — D-01..D-18 locked decisions. [VERIFIED: codebase read 2026-06-20]
- `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-RESEARCH.md` — ACC pattern, BOS4 follow-up shape (BOS5-05), example-fixture FK testing approach. [VERIFIED: codebase read 2026-06-20]
- `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-05-PLAN.md` — cross-phase follow-up plan structure (the exact pattern for the D-16 BOS4 band-enum follow-up to mirror). [VERIFIED: codebase read 2026-06-20]

### Secondary (MEDIUM confidence)

- `const` + `minimum` co-usage for "fixed canonical value with directional floor" semantics in JSON Schema Draft 2020-12 — standard pattern, consistent with the JSON Schema spec's keyword composition rules. [ASSUMED: not re-verified via external source this session]

---

## Metadata

**Confidence breakdown:**
- Schema design pattern: HIGH — directly mirrors verified `contracts/outcomes.schema.json` and existing `contracts/` structure
- D-16 mechanism recommendation (mirror+consistency vs cross-file $ref): HIGH — verified by reading test code and probing the installed library
- Schema field shapes: HIGH for structure; MEDIUM/ASSUMED for exact field names (per CONTEXT.md, these are Claude's Discretion)
- Guardrail FK mechanism: HIGH — definitively example-fixture-based; no static alternative exists
- BOS5 guardrail IDs: LOW — not yet established; placeholder fixture needed
- ACC list: HIGH — derived from locked D-18 requirements + BOS5 precedent

**Research date:** 2026-06-20
**Valid until:** ~2026-09-20 (stable internal patterns; only BOS5 guardrail ID coordination is time-sensitive)

---

## RESEARCH COMPLETE

**Phase:** BOS6 (plans 2–4) — Machine-Checkable Governance Contract
**Confidence:** HIGH

### Key Findings

- **D-16 mechanism resolved:** Mirror-enum + consistency test is the correct approach. Cross-file `$ref` is technically feasible (verified against jsonschema 4.26.0 + `referencing` library) but introduces test-suite coupling incompatible with the existing standalone-lint pattern used across `contracts/`. The consistency test provides identical machine-checkable guarantees with zero coupling.
- **D-17 FK is example-fixture-based:** JSON Schema cannot express value-to-value FK constraints. A fixture pair (`governance-guardrail-fk.json` + `governance-bos5-guardrail-ids.json`) enables the ACC-08 test. The BOS5 guardrail IDs are not yet established; the fixture is a forward-declaration that BOS13 must honor.
- **BOS4 follow-up has three amendment targets:** The band-enum amendment touches `autonomy_band` (top-level), `AutonomyBandPayload.proposed_band`, and `AutonomyBandPayload.current_band` — all three free-string fields. Missing any one leaves a gap in enforcement.
- **Separate BOS4 follow-up plans for BOS5-05 and D-16:** The two amendments are orthogonal; keeping them as separate plans keeps each diff narrow and each test file focused.
- **ACC-09 prose↔schema test:** A grep-based test over `BOS6-GOVERNANCE-SPEC.md` fires if the band/tier/guardrail/N values drift between the prose and the schema. Verify exact prose tokens against the shipped spec before implementing.

### File Created

`.planning/phases/BOS6-privacy-governance-and-tenant-boundaries/BOS6-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Schema shape (D-15) | HIGH | All values from verified shipped prose; pattern from verified existing schemas |
| D-16 mechanism | HIGH | Verified against installed tooling and existing test patterns |
| D-17 FK testing | HIGH | Definitively example-fixture-based; no schema-level alternative |
| ACC list (D-18) | HIGH | Derived from locked decisions + BOS5 precedent |
| BOS5 guardrail IDs | LOW | Not yet established; placeholder approach documented |

### Open Questions (RESOLVED)

1. **BOS5 guardrail IDs for the FK fixture** — RESOLVED (plan): handled as a forward-declaration.
   The specific `guardrail_id` values BOS6 links to (`escaped_defects`, `incidents`,
   `reward_hacking` dashboard → BOS5 `GuardrailMetricSpec`) are not yet established, so
   `governance-bos5-guardrail-ids.json` is authored as a forward-declaration fixture (BOS6-03 T1)
   and the BOS13 coordination point is flagged in BOS6-VALIDATION.md (BOS6-03 T3). Not a blocker.

2. **`const: 3` + `minimum: 3` vs `minimum: 3` only for `min_aggregation_n`** — RESOLVED (plan):
   `minimum: 3` only, per the recommendation (simpler; avoids `const`/`minimum` interaction).
   BOS6-02 authors `minimum: 3` and BOS6-03 ACC-05 asserts the floor.

### Ready for Planning

Research complete. Planner can now create BOS6-02-PLAN.md (governance.schema.json),
BOS6-03-PLAN.md (pytest suite + VALIDATION.md), and BOS6-04-PLAN.md (BOS4 band-enum
follow-up).
