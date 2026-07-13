# Phase BOS5: Outcome Labels and Reward Model - Research

**Researched:** 2026-06-18
**Domain:** Outcome labeling, multi-objective reward design, Goodhart/guardrail patterns, and bitemporal outcome joins — for a docs-first JSON Schema contract.
**Confidence:** HIGH (internal codebase + upstream CONTEXT verified; theory confirmed against canonical references; no runtime code introduced)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Label Assignment Mechanics (BOS-DATA-03)**
- **D-01:** Deterministic derivation rules. BOS3 events → labels via declarative, reproducible, auditable rules. No human-in-the-loop labeling; rules are replayable.
- **D-02:** Observation windows + revisable append-only labels. Each label type declares an observation window; labels are append-only events that can be superseded by a later label as outcomes mature (clean merge → escaped defect → incident). As-of join always uses what was known at decision time.
- **D-03:** Labels anchor to the BOS3 entity (task/PR/correlation id). Decisions join via entity refs + as-of pointer. ONE outcome can inform MANY decisions. Outcomes stay observation-faithful; credit assignment is a reward-model concern (D-08).

**Label Schema Shape (BOS-DATA-03)**
- **D-04:** Two families — closed categorical label enum + continuous outcome measures. Cycle time is a measure, not a category. Mirrors the discriminated-union style in `contracts/events.schema.json`.
- **D-05:** Multi-label, append-only over the entity lifecycle. An entity accumulates multiple categorical label events over time; the reward model decides how to combine them.
- **D-06:** Optional graded severity on relevant labels (incident, escaped defect, rework). Other labels stay flat.

**Reward Model Structure (BOS-DATA-04)**
- **D-07:** Multi-objective vector + named scalarization function. Tradeoffs stay legible/explainable.
- **D-08:** Versioned team-level weights, per decision_type. Reward reproducible from (objective vector + named weight-set version). Credit weighting across co-located decisions expressed here.
- **D-09:** Reward as-of horizons + recomputable. Provisional reward at short horizon, recomputed (append-only) as late outcomes land.

**Guardrails & Bad-Proxy Detection (BOS-DATA-04)**
- **D-10:** Paired guardrail metrics (tension pairs). Each reward objective gets ≥1 named counter-metric. E.g. cycle-time↓ with escaped-defects↑ = gaming flag.
- **D-11:** Classify each guardrail: hard-gate (blocks autonomy/promotion in BOS15) vs dashboard (BOS-GOV-04). BOS5 defines metric + threshold shape + role; BOS15 wires the actual gate.
- **D-12:** BOS5 owns reward/outcome guardrails ONLY. Fairness, autonomy-creep, fatigue/nudge guardrails → BOS6 (BOS-GOV-04) / BOS17 (BOS-BEH-02).

**Carried forward (locked in earlier phases):**
- Outcome labels join to decisions by `decision_id` after the fact, never inline at decision time (BOS4 D-04 — hard no-leakage guard).
- Outcomes = separate later append-only events, bitemporal (`event_time` + `ingest_time`), as-of feature reconstruction (BOS3 D-02).
- Store = SQLite local-first, point-in-time-correct (BOS2 D-04).
- Contract mechanism = sibling JSON Schema under `contracts/` feeding CI drift gate, extending V13.1 artifact (BOS2 D-06).
- Language = TypeScript owns shared contracts (BOS-ARCH-02).
- Governance = team-level, explainable, human override, no individual ranking, no reward hacking (PROJECT.md Constraints §Trust/§Safety).
- No learned policy increases autonomy / reduces review / skips validation without offline eval + guardrail checks + human approval (PROJECT.md §Safety).

### Claude's Discretion
- Outcome/reward spec doc structure/format. Authoritative form = JSON Schema under `contracts/`.
- Exact field names (categorical label enum, measures family, reward objective vector, weight-set record, guardrail-metric record).
- Concrete default observation-window lengths and reward horizon value(s).
- Named objective set in the reward vector and named scalarization function form.
- Schema versioning notation — mirror PROTOCOL.md `v` + migration-note convention (as BOS3/BOS4 did).

### Deferred Ideas (OUT OF SCOPE)
- Concrete guardrail enforcement / policy-promotion gates — BOS15 (BOS-RL-02).
- Fairness, autonomy-creep, fatigue/nudge guardrails — BOS6 / BOS17.
- Statistical drift/anomaly monitors on top of tension pairs — later.
- Field-level labels for external sources (review/CI/validation/deploy/incident) — depend on BOS12.
- Reference/golden-label dataset + eval harness — BOS15.
- Actual reward weight VALUES and tuning — BOS13/14/15.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOS-DATA-03 | Voss specifies outcome labels for clean merge, rework, revert, failed validation, escaped defect, incident, cycle time, and human override. | §Outcome Label Definitions, §Label Schema Pattern, §Derivation Rules Pattern, §Observation Windows, §Common Pitfalls (label definitional ambiguity) |
| BOS-DATA-04 | Voss specifies reward and guardrail metrics before any learning system is introduced. | §Multi-Objective Reward Design, §Scalarization Patterns, §Reward Horizons, §Goodhart and Guardrail Patterns, §Tension-Pair Table, §Validation Architecture (tension-pair coverage check) |
</phase_requirements>

## Summary

BOS5 is a **docs-first contract phase** producing two artifacts: (1) a JSON Schema at `contracts/outcomes.schema.json` (sibling to the existing `events.schema.json`) defining the categorical label enum, the continuous outcome measures family, and the reward/guardrail metric record shapes; and (2) a supporting rationale document (markdown prose + tables) explaining derivation rules, observation windows, reward objectives, scalarization, and guardrail classification. No runtime code, no emitters, no migrations.

The most important structural insight is that BOS5's outcome schema is the downstream continuation of what BOS3 and BOS4 already established. BOS3 makes outcomes-as-separate-later-append-only-events the structural no-leakage guarantee. BOS4 bans outcome labels inline on decision records (D-04 hard guard). BOS5 specifies WHAT those later outcome events look like. The three schemas together form a coherent bitemporal data model: event → decision (point-in-time) → outcome label (later append) → reward (computed at horizon) — and the as-of join at every step is the same mechanism throughout.

The software-engineering analytics literature (DORA, SPACE, DevEx) converges on a small canonical set of outcome categories that map directly onto BOS-DATA-03's eight labels: clean merge corresponds to "deployment" or "successful change"; rework/revert/failed validation correspond to "change failure rate"; cycle time is the standard lead-time-to-change measure; escaped defect/incident correspond to "defect escape rate" and "mean time to restore." This is the standard DORA four-metric vocabulary plus two refinements (rework as a pre-escape defect signal; human override as a governance signal unique to AI-assisted workflows). The research confirms BOS-DATA-03's label set is grounded in prior art, not novel invention.

Multi-objective reward + named scalarization (D-07) is a well-established pattern in RL/multi-criteria decision-making literature. The key design insight is that the scalarization function should be **named and versioned** (not just a dot product with anonymous weights) so that reward reproducibility is achievable from (vector + weight-set-version) and governance explainability is satisfied. Linear weighted scalarization is the correct starting point for BOS5 — it is the simplest, most interpretable, and consistent with "team-level explainable" governance. Chebyshev / epsilon-constrained approaches are referenced as future options but not needed in the contract spec.

Goodhart's Law / reward hacking is addressed structurally via D-10 tension pairs. The research confirms this is the right approach: the software-engineering metrics community has well-documented counter-metric pairs (velocity vs defect rate, merge frequency vs escaped defect rate, cycle time vs rework rate) that exactly instantiate D-10. BOS5 should specify a minimum required tension-pair table as part of the contract; the planner can verify coverage with a structural check (every reward objective has ≥1 counter-metric named).

**Primary recommendation:** Two contract artifacts. (1) `contracts/outcomes.schema.json` — a discriminated-union JSON Schema with three top-level families: `categorical_label` (discriminated on `label_type`), `outcome_measure` (discriminated on `measure_type`), and `reward_record` (capturing objective vector + weight-set-version + horizon + recomputable provenance). A separate `guardrail_metric` definition (not an event — a config/spec record). (2) `docs/BOS5-OUTCOME-REWARD-SPEC.md` — prose rationale covering derivation rules, observation windows, reward objectives, scalarization, tension-pair guardrail table. Version the schema with `v: 1` + migration-note convention consistent with BOS3/BOS4 and PROTOCOL.md.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Outcome label schema definition | Shared contract (docs / `contracts/`) | — | BOS5 is contract-only; no runtime tier owns this yet. Sibling to `events.schema.json`. |
| Label derivation (event → label) | Backend/event service (future, not BOS5) | — | D-01 specifies RULES; the engine executing them is BOS11/12-era. BOS5 stays logical. |
| Reward computation | Backend/analytics service (future, BOS16 era) | — | D-07/D-08/D-09 specify the SHAPE of reward records; computation is a future concern. |
| Outcome label storage / as-of query | Backend/event store (SQLite local-first, BOS2) | — | BOS5 is logical-contract-only; store is BOS2 / later. |
| Guardrail threshold enforcement | BOS15 (offline eval / policy-promotion gates) | BOS6 (GOV-04 dashboard) | D-11: BOS5 defines metric + threshold shape + role; BOS15 wires enforcement. |
| Fairness / behavioral guardrails | BOS6 / BOS17 | — | D-12: explicitly out of BOS5 scope. |

## Standard Stack

This is a docs-only phase. There are no runtime libraries to install. The contract artifact is JSON Schema (consistent with the existing `contracts/events.schema.json` pattern). The only tooling used is:

| Tool | Purpose | Why |
|------|---------|-----|
| JSON Schema Draft 2020-12 | Normative schema artifact | Matches the existing discriminated-union pattern in `contracts/events.schema.json`; language-agnostic (TypeScript, Python, Go consumers); CI drift gate already exists for this file family |
| `jsonschema` (PyPI) or `ajv` (npm) | Schema linting + example validation in tests | Either works; Python `jsonschema` is already noted in BOS3-RESEARCH as project choice |

No new packages are introduced by BOS5. The schema file is a JSON document. Any validation tooling chosen should mirror the BOS3 approach.

## Package Legitimacy Audit

> BOS5 installs NO external packages. The deliverable is a JSON Schema document and a markdown rationale doc. No package legitimacy audit is required.

**Packages removed due to slopcheck [SLOP] verdict:** none — no packages recommended.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
BOS3 Event Log (append-only, bitemporal)
      │
      │  deterministic derivation rules (D-01)
      ▼
BOS5 Outcome Label Events (append-only, later)
  ├── CategoricalLabelEvent  { entity_id, label_type, severity?, obs_window_id, event_time, ingest_time }
  └── OutcomeMeasureEvent    { entity_id, measure_type, value, unit, obs_window_id, event_time, ingest_time }
      │
      │  as-of join by entity_id + decision entity_refs (BOS4 D-04)
      ▼
BOS4 Decision Record  (joined AFTER the fact, never inline)
  └── [decision_id, as_of_pointer, feature_snapshot, recommended_action, human_verdict, ...]
      │
      │  reward computation at horizon (D-07/D-08/D-09)
      ▼
RewardRecord  { decision_id, objective_vector, weight_set_version, horizon, scalarized_reward?, computed_at }
      │
      │  tension-pair check (D-10/D-11)
      ▼
GuardrailMetric (spec/config record, not an event)
  ├── hard-gate  → BOS15 enforcement
  └── dashboard  → BOS6 GOV-04
```

Data flows left-to-right / top-to-bottom. The no-leakage guarantee is structural: outcome events have `ingest_time` > decision `event_time`; as-of reconstruction filters them out when reconstructing the state the decision was made against.

### Recommended Project Structure

```
contracts/
├── events.schema.json          # existing — BOS3 event union (BOS3 owns)
├── decisions.schema.json       # BOS4 decision ledger (BOS4 owns)
└── outcomes.schema.json        # BOS5 outcome/reward/guardrail contract ← NEW

docs/
└── BOS5-OUTCOME-REWARD-SPEC.md # supporting prose/tables rationale doc ← NEW
```

Both artifacts are BOS5 deliverables. The JSON Schema is the authoritative contract (CI drift gate). The markdown is the human-readable rationale (derivation rules, observation-window table, reward objective set, tension-pair table).

### Pattern 1: Discriminated-Union Outcome Schema (mirrors `events.schema.json`)

The existing `contracts/events.schema.json` uses a `oneOf` + `discriminator` on the `type` field with a `const` per variant (e.g. `"type": {"const": "swarm.assign"}`). Every variant carries `v: int` for versioning. BOS5 should follow EXACTLY this pattern.

The top-level schema defines two discriminated unions (categorical labels and outcome measures) plus a non-event record type for reward and guardrail spec.

**Recommended schema skeleton** `[ASSUMED — field names are discretionary; pattern confirmed from codebase]`:

```json
// contracts/outcomes.schema.json (top-level structure)
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://voss.dev/contracts/outcomes.schema.json",
  "description": "BOS5 outcome label, measure, reward, and guardrail contract. v: 1.",
  "title": "OutcomeContract",

  "$defs": {
    // --- Shared envelope fields (all outcome event records) ---
    "OutcomeEnvelope": {
      "type": "object",
      "required": ["v", "outcome_id", "entity_id", "entity_type", "trace_id",
                   "event_time", "ingest_time", "obs_window_id"],
      "properties": {
        "v":             { "type": "integer", "const": 1 },
        "outcome_id":    { "type": "string", "description": "Stable UUID for this outcome event." },
        "entity_id":     { "type": "string", "description": "BOS3 stable entity id (task/PR/correlation id)." },
        "entity_type":   { "type": "string", "enum": ["task", "pr", "session", "swarm_assignment"] },
        "trace_id":      { "type": "string", "description": "BOS3 root correlation/trace id." },
        "event_time":    { "type": "string", "format": "date-time", "description": "When the outcome occurred in the world (valid time)." },
        "ingest_time":   { "type": "string", "format": "date-time", "description": "When BOS recorded this outcome (transaction time). Always >= event_time." },
        "obs_window_id": { "type": "string", "description": "Identifies the observation window definition that triggered this label." },
        "source_rule":   { "type": "string", "description": "The derivation rule ID (D-01) that produced this label." }
      }
    },

    // --- Categorical Label family (discriminated on label_type) ---
    "CleanMergeLabel":       { "$comment": "label_type: clean_merge" },
    "ReworkLabel":           { "$comment": "label_type: rework — optional severity" },
    "RevertLabel":           { "$comment": "label_type: revert" },
    "FailedValidationLabel": { "$comment": "label_type: failed_validation" },
    "EscapedDefectLabel":    { "$comment": "label_type: escaped_defect — optional severity" },
    "IncidentLabel":         { "$comment": "label_type: incident — optional severity" },
    "HumanOverrideLabel":    { "$comment": "label_type: human_override — BOS4 override-as-signal" },

    // --- Continuous Measure family (discriminated on measure_type) ---
    "CycleTimeMeasure":      { "$comment": "measure_type: cycle_time — value in seconds, float" },

    // --- Reward record (not an event — computed, append-only) ---
    "RewardRecord":          { "$comment": "Computed at horizon; append-only; never mutates decision row." },

    // --- Guardrail metric spec record (config/contract record, not a runtime event) ---
    "GuardrailMetricSpec":   { "$comment": "Defines counter-metric, role (hard_gate|dashboard), threshold shape, linked reward objective." }
  },

  // Top-level union for outcome events
  "oneOf": [
    { "$ref": "#/$defs/CategoricalLabelEvent" },
    { "$ref": "#/$defs/OutcomeMeasureEvent" }
  ]
}
```

`[ASSUMED — field names are discretionary per CONTEXT.md]`

### Pattern 2: Append-Only Superseding Labels (D-02/D-05)

Labels are events, not mutable state. When a `clean_merge` label is later superseded by an `escaped_defect`, the schema does NOT update the original record. Instead a new `escaped_defect` label event is appended, carrying the same `entity_id` and a `supersedes_outcome_id` pointer to the earlier label. Consumers reconstruct the label history by ordering all label events for an entity by `ingest_time` and selecting those with `ingest_time ≤ T` (the as-of filter).

```json
// Example: superseding label record
{
  "v": 1,
  "outcome_id": "label-999",
  "label_type": "escaped_defect",
  "entity_id": "task-abc123",
  "supersedes_outcome_id": "label-111",   // ← the clean_merge label being superseded
  "event_time": "2026-06-25T10:00:00Z",
  "ingest_time": "2026-06-25T14:23:00Z",  // ← always >= event_time
  "obs_window_id": "defect-escape-30d",
  "source_rule": "rule:pr_linked_incident"
}
```

`[ASSUMED — field names discretionary]`

### Pattern 3: Versioned Weight-Set Record (D-08)

The weight-set is a versioned team config record, NOT embedded in the schema. The schema defines its shape; the values are set per team + per `decision_type`. Reproducibility = (reward_vector + weight_set_version) fully reconstructs any scalar reward.

```json
// WeightSetRecord shape (spec, not event — could live in team config)
{
  "weight_set_id": "ws-v1-task-to-agent",
  "decision_type": "task_to_agent",
  "schema_version": 1,
  "objectives": {
    "throughput":    0.3,
    "quality":       0.4,
    "rework_cost":   0.2,
    "flow":          0.1
  },
  "scalarization": "linear_weighted",  // named function
  "effective_from": "2026-07-01",
  "notes": "Initial baseline weights for task delegation."
}
```

`[ASSUMED — field names discretionary]`

### Anti-Patterns to Avoid

- **Writing outcome labels inline on the decision record at decision time.** This is the hard no-leakage guard (BOS4 D-04). The schema should have no outcome field on the decision record, and BOS5 should not introduce one.
- **Collapsing multi-label history to a single dominant label per entity.** D-05 requires append-only accumulation. Discarding the `clean_merge` → `escaped_defect` progression loses early signal and violates append-only semantics.
- **Making severity a separate measure rather than an optional field.** D-06 decided severity belongs on the categorical label record as an optional field — not as a parallel continuous measure — for relevant label types (incident, escaped_defect, rework).
- **Embedding scalarization weights directly in the schema as fixed constants.** D-08 requires weights to be versioned team config, separate from the contract schema, so reward is reproducible from (vector + weight-set-version).
- **Defining observation windows as hard-coded constants in the schema.** Observation windows should be named/referenced in the schema (via `obs_window_id`), with the actual window lengths living in a config table documented in the rationale spec. This makes window lengths tunable without a schema version bump.
- **Conflating a reward record with an outcome event.** Reward records are computed/derived artifacts; outcome events are observed facts. They are different record types and should be different schema definitions, even though both are append-only.

## Outcome Label Definitions

> This section is the semantic core that the planner needs to write precise derivation rules. Every label in BOS-DATA-03 is defined here with its conventional meaning, derivation trigger, and observation window guidance. `[ASSUMED]` where convention differs across organizations; `[CITED: DORA, DevEx literature]` for well-established definitions.

### Categorical Labels (the closed enum — D-04)

| Label | `label_type` value | Conventional Meaning | Primary BOS3 Source Event(s) | Observation Window | Notes |
|-------|-------------------|----------------------|-----------------------------|--------------------|-------|
| **Clean merge** | `clean_merge` | A merged PR/commit that has not generated rework, revert, escaped defect, or incident within the observation window. | `pr.merged` (BOS3 reserved CI/review slot; internal analogue: `swarm.worker_done` + no failure) | 7–30 days `[ASSUMED]` (see window guidance below) | Provisional — starts at merge, may be superseded. The "default positive outcome." |
| **Rework** | `rework` | Work on the same entity (PR/file/task) required because earlier work was insufficient — e.g. a follow-up PR fixing the same code within the observation window. `[CITED: DORA Change Failure Rate; DevEx "quality" dimension]` | A second `pr.merged` or `task.completed` touching the same files within window, linked by correlation/entity | 14 days `[ASSUMED]` | Optional severity: `minor` / `moderate` / `major` (D-06). Distinguished from escaped_defect in that it is caught before deployment or surfaced by the team (not a production user). |
| **Revert** | `revert` | A commit/PR that explicitly reverts a previous merge. `[CITED: DORA Change Failure Rate]` | `git.revert` event or PR with "revert" in title linked to the original entity (BOS12 source for external repos; internal task-level analogue is session-killed/abort) | 30 days `[ASSUMED]` | Strong negative signal; typically not graded (presence alone is significant). Optional severity can capture blast radius. |
| **Failed validation** | `failed_validation` | CI/validation run triggered by the entity's changes that did not pass. Caught before merge. `[CITED: DORA]` | `ci.failed` / `validation.failed` (BOS3 reserved external slots); internal: `swarm.gate(gate_type=reviewer_reject)` + `RunRecord.failures[]` | At merge time (no window — immediate) | May occur multiple times on the same entity (CI flap vs real failure). Append-only: each failure is a label event. |
| **Escaped defect** | `escaped_defect` | A defect that was not caught by validation/CI and reached production or was found by users/monitors after merge. `[CITED: DORA Change Failure Rate — the external-facing component]` | Incident linked back to entity via trace_id/correlation; bug report linked to a PR; post-deploy alerting event (BOS12 external sources) | 30–90 days `[ASSUMED]` (defects may surface slowly) | Optional severity (D-06): maps to incident severity scale (sev1..sev3 or P0..P3). This is the most delayed label — drives the long-horizon reward recomputation (D-09). |
| **Incident** | `incident` | A production incident attributed to the entity's changes (broader than escaped_defect — may include non-defect incidents like deploy failures, performance degradation). `[CITED: DORA Mean Time to Restore; SRE incident taxonomy]` | `incident.opened` linked to deploy or PR (BOS12 external); or internal `RunRecord` with failures[] matching incident criteria | 30–90 days `[ASSUMED]` | Optional severity (D-06): sev1..sev3 or equivalent. Highest negative signal; a sev1 incident should dominate scalar reward regardless of weights. |
| **Human override** | `human_override` | A human explicitly overrode a system recommendation for this entity (BOS4 D-05/D-06 `human_verdict = "override"`). `[ASSUMED — unique to AI-assisted workflow context; no DORA analogue]` | BOS4 decision record where `human_verdict = "override"` for a decision targeting this entity | At override time (no window — immediate) | The "override-as-signal" idea from BOS4 D-06. Not a quality failure per se; captures divergence between recommended and actual action. Severity not needed. |

### Continuous Measures (D-04 second family)

| Measure | `measure_type` value | Definition | Unit | BOS3 Source | Window |
|---------|---------------------|------------|------|-------------|--------|
| **Cycle time** | `cycle_time` | Time from task/story creation (or first commit) to merge/done. `[CITED: DORA Lead Time for Changes — the most granular decomposition]` | seconds (float) | `task.created_at` → `pr.merged_at` (or `swarm.worker_done.ts`) | Point-in-time measurement; no observation window needed — measured at merge |

**Cycle time definitional pitfall:** "Cycle time" has three common definitions in the literature `[ASSUMED — varies by org]`: (1) time from task-start to merge, (2) time from first commit to merge, (3) time from PR-open to merge. The spec MUST pick one and document it. Recommendation: time from `task.created_at` (or `swarm.task.ts`) to `pr.merged_at` (or `swarm.worker_done.ts`) — the widest measure, consistent with DORA Lead Time decomposition and most useful for delegation reward (captures the full AI-assisted work cycle, not just review lag).

### Severity Scale (D-06 — optional field on relevant labels)

For labels where severity applies (incident, escaped_defect, rework), the spec should define a 3-level ordinal scale: `[ASSUMED — 3-level is a common convention; exact labels are discretionary]`

| Value | Conventional Meaning |
|-------|---------------------|
| `low` | Minor impact; localized; quick fix |
| `medium` | Moderate impact; multiple users or systems affected; hours to resolve |
| `high` | Major impact; service degradation or outage; extended resolution time |

Alternative: numeric `1..3` (higher = worse) matching internal incident severity conventions. Either works; the schema should make it an `enum` on the field so it is validated.

## Observation Window Guidance

Observation windows define how long BOS waits before treating a label as "mature" (i.e., unlikely to be superseded). `[ASSUMED — industry conventions vary; these are sensible starting points]`

| Label | Recommended Default Window | Rationale | Supersession Risk After Window |
|-------|---------------------------|-----------|-------------------------------|
| clean_merge | 30 days | Most rework and escaped defects surface within a month | Low (very late incidents still possible — see D-09 long horizon) |
| rework | 14 days | Rework is usually identified within the same sprint | Very low |
| revert | Immediate (0 days) | A revert is a concrete observed event | None |
| failed_validation | Immediate (0 days) | CI/gate failure is a concrete observed event | None |
| escaped_defect | 90 days | Defects may surface slowly in production | Medium (rare very-late defects) |
| incident | 90 days | Incident attribution may require post-mortem linkage | Medium |
| human_override | Immediate (0 days) | Override is a concrete observed event | None |
| cycle_time | At merge/done (point-in-time) | Not a window — measured at the moment of completion | None |

**Key spec requirement:** Every observation window should be named in a config table (not hard-coded) so teams can tune them. The schema references `obs_window_id`; the rationale doc provides the default window table. This avoids a schema version bump when a team adjusts a window.

**Observation window vs finality tradeoff:** A shorter window gives faster reward signal but more supersessions (more label churn). A longer window gives more reliable labels but delays reward feedback. The spec should state the default + note this tradeoff explicitly — it affects BOS15's choice of evaluation horizon.

## Derivation Rules Pattern (D-01)

The spec must define the mapping from BOS3 event(s) → outcome label as named, declarative rules. Each rule has: a trigger (which BOS3 event type(s) and conditions), the output label type, the entity it attaches to, and the source rule ID (for auditability/replayability). `[ASSUMED — rule form is discretionary per CONTEXT.md; the pattern below is recommended]`

### Rule Table Template

| Rule ID | Trigger BOS3 Event(s) | Conditions | Output Label | Entity Anchor | Notes |
|---------|----------------------|------------|--------------|---------------|-------|
| `rule:pr_merge_clean` | `pr.merged` | No `rework`/`revert`/`escaped_defect`/`incident` within obs window | `clean_merge` | PR entity | Provisional; superseded if a later label arrives |
| `rule:pr_revert` | `pr.merged` where title matches revert pattern OR `git.revert` event | Linked to prior merge | `revert` | Original PR entity (the thing being reverted) | Severity optional |
| `rule:ci_failure` | `ci.failed` or `validation.failed` | Linked to PR/task entity | `failed_validation` | PR or task entity | Each occurrence is a separate label event |
| `rule:rework_followup` | Second `pr.merged` touching same files, same entity correlation | Within 14-day window | `rework` | Original PR/task entity | Severity optional |
| `rule:incident_attribution` | `incident.opened` | Linked to deploy or PR via trace_id | `incident` on linked entity; `escaped_defect` if defect-type | PR/task entity | Severity required (high/medium/low) |
| `rule:human_override` | BOS4 `DecisionRecord` with `human_verdict = "override"` | Any decision targeting the entity | `human_override` | Entity targeted by the decision | No severity |

For BOS3's current state (where external CI/deploy/incident slots are reserved, not field-detailed), the derivation rules for labels that depend on external events (`ci.failed`, `incident.opened`, `pr.merged`) should be specced now with a note that they activate when BOS12 fills the reserved slots. Internal-only derivation rules (`rule:human_override`, `rule:swarm_task_failure` from `RunRecord.failures[]`) activate immediately.

## Multi-Objective Reward Design

### Named Objective Set (D-07 discretion — recommended starting set)

`[ASSUMED — names are discretionary; set is a discretionary recommendation]`

| Objective Name | What It Measures | Higher is Better? | Primary Labels/Measures It Aggregates |
|---------------|-----------------|-------------------|--------------------------------------|
| `throughput` | Rate of clean merges / completed tasks per time window | Yes | `clean_merge` count; `cycle_time` (inverse — shorter = higher throughput) |
| `quality` | Absence of defects and failures | Yes (higher = fewer defects) | 1 - weighted(escaped_defect, incident, failed_validation); revert rate |
| `rework_cost` | Proportion of rework relative to total output | No (lower is better → invert in scalarization) | `rework` label frequency; rework cycle_time proportion |
| `flow` | Smoothness of delivery — low cycle time variance, few human overrides indicating friction | Yes | cycle_time stddev (inverse); human_override frequency (inverse) |

This four-objective set (throughput / quality / rework_cost / flow) provides a minimal coverage of DORA's four metrics translated into reward objectives. Each maps to observable outcome labels or measures. The planner should present these as a recommended starting set and note they are tunable — D-08's versioned weight-set mechanism handles evolution without a schema change.

### Scalarization Patterns

**Linear weighted scalarization** is the correct starting choice for BOS5 `[ASSUMED — confirmed as the standard interpretable baseline in MORL literature]`. Formula: `R = Σ(wᵢ × oᵢ)` where `wᵢ` is the weight for objective `i` and `oᵢ` is the normalized objective value.

Why linear over alternatives at this stage:
- Interpretable: any team member can verify "we weighted quality 40%, throughput 30%, rework_cost 20%, flow 10%"
- Reproducible: (vector + weight_set_version) fully determines the scalar — satisfies D-08
- Explainable: governance constraint satisfied without statistical opacity
- Matches the trust model: team-level, no black-box optimization

**Alternative scalarization forms to reference (but defer):**

| Form | When useful | Why not now |
|------|-------------|-------------|
| Chebyshev / min-max | When no objective should be sacrificed below a floor | More complex; min-tracking requires sorted scores; premature at contract spec time |
| Epsilon-constrained | When one objective is primary, others are constraints | Requires threshold calibration data that doesn't exist yet |
| Rank-based (Borda) | Robust to objective scale differences | Less transparent; harder to explain to a team |

The spec should name `linear_weighted` as the initial scalarization function, document that the `scalarization` field on the `WeightSetRecord` is a named string (not a lambda), and reserve `chebyshev` and `epsilon_constrained` as valid future values with a migration note.

### Reward Horizons and Recomputation (D-09)

The spec must define at least two named horizons: `[ASSUMED — specific values are discretionary]`

| Horizon Name | Default Duration | Purpose |
|--------------|-----------------|---------|
| `short` | 7 days | Provisional reward computed soon after merge; captures fast feedback (CI failures, immediate reverts). Used for early policy signal. |
| `long` | 90 days | Full reward including escaped defects and incidents. Used for policy evaluation (BOS15) and final reward attribution. |

**Recomputation semantics:** A `RewardRecord` is always append-only. When a new outcome label arrives for an entity after the short horizon has already been computed, a NEW `RewardRecord` is appended (same `decision_id`, higher `ingest_time`, updated `horizon` = `long`, recalculated `objective_vector`). The original short-horizon reward record is never mutated. This is the same append-only semantics as BOS3 outcome events — reward is itself a kind of "later arriving information."

**Point-in-time-correct reward:** To reconstruct the reward that was available at policy-evaluation time T, select `RewardRecord` entries where `ingest_time ≤ T`. This means BOS15 offline eval can pick either the short or long horizon by setting T appropriately. The spec should make this explicit.

## Goodhart and Guardrail Patterns

### The Core Anti-Goodhart Pattern (D-10)

Goodhart's Law: "When a measure becomes a target, it ceases to be a good measure." In software-engineering reward models, the canonical failure modes are `[CITED: DevEx literature; platform engineering community consensus; DORA acceleration trap warnings]`:

- Optimizing merge frequency → increasing superficial small commits ("commit stuffing")
- Optimizing cycle time → abandoning code review, cutting testing corners
- Optimizing throughput objectives → reducing review depth, increasing escaped defects
- Optimizing quality gate pass rates → disabling tests, marking failures as flaky

BOS5's structural defense is D-10: **every reward objective must have ≥1 named counter-metric in tension with it.** This makes gaming detectable by construction, not by chance.

### Tension-Pair Table (D-10 — required in the spec)

The spec must include a complete tension-pair table. Each reward objective must appear exactly once as the "optimized" axis with ≥1 named counter-metric. This table is the machine-checkable deliverable for D-10.

`[ASSUMED — specific metric names are discretionary; the structure and coverage rule are normative]`

| Reward Objective | Counter-Metric (guardrail) | Gaming Pattern Detected | Guardrail Role (D-11) | Threshold Shape |
|-----------------|---------------------------|------------------------|----------------------|-----------------|
| `throughput` ↑ | `rework_rate` = rework_count / merge_count (window) | Merging low-quality work quickly → rework surge | hard-gate | > X% in rolling 30d window |
| `throughput` ↑ | `escaped_defect_rate` = escaped_defect_count / merge_count | Merging without adequate review → defect escape | hard-gate | > Y% in rolling 90d window |
| `quality` ↑ | `validation_bypass_rate` = tasks with no CI run / total tasks | Avoiding validation to maintain clean-merge rate | hard-gate | > 0% (zero tolerance) |
| `rework_cost` ↓ | `human_override_rate` = override_count / recommendation_count | System learns to avoid hard tasks (reduces rework by delegating less) | dashboard | Monitor trend; alert if > Z% in 30d |
| `flow` ↑ | `revert_rate` = revert_count / merge_count | Reducing human override friction by deploying risky work → reverts | hard-gate | > W% in rolling 30d window |
| `cycle_time` ↓ (measure, not objective, but often used as proxy) | `rework_rate` AND `escaped_defect_rate` | Cutting cycle time by reducing review/testing | dashboard (both above hard-gates cover it) | Covered by throughput hard-gates |

**D-11 classification guidance:**
- **hard-gate** = if breached, BOS15 blocks autonomy increase / policy promotion. These are the minimum safety bars.
- **dashboard** = surfaced in BOS6 GOV-04 governance dashboard; triggers human review, does not auto-block.

The spec should note that thresholds are `[ASSUMED — discretionary starting points; teams set actual values]` and that the schema defines the threshold SHAPE (e.g. `{"type": "rate", "window_days": 30, "max_value": 0.05}`) not the value. Actual values are team config, versioned alongside weight sets.

### GuardrailMetricSpec Record Shape

```json
// GuardrailMetricSpec (config/spec record — not a runtime event)
{
  "guardrail_id": "gmspec-rework-rate",
  "label": "Rework Rate",
  "counter_metric_formula": "rework_count / merge_count",
  "window_days": 30,
  "linked_reward_objective": "throughput",
  "role": "hard_gate",            // "hard_gate" | "dashboard"
  "threshold_shape": {
    "type": "rate",
    "max_value": null             // null = teams configure; shape is fixed by contract
  },
  "enforcement_phase": "BOS15",   // BOS5 defines the spec; BOS15 wires enforcement
  "governance_consumer": "BOS6"   // for dashboard-role metrics
}
```

`[ASSUMED — field names discretionary]`

## Point-in-Time-Correct Outcome Joins (Anti-Leakage)

This is the most technically critical section for correctness. The no-leakage requirement (PROJECT.md §Data; BOS4 D-04) means: when BOS15 reconstructs the training dataset for offline evaluation, the outcome labels visible for a decision at time T must be exactly those labels with `ingest_time ≤ T_decision`. Labels that arrived after the decision was made must be invisible — even if they describe events that happened before the decision (late-arriving information).

The bitemporal join pattern (from BOS3 research) is the standard mechanism `[CITED: martinfowler.com/articles/bitemporal-history.html; BOS3-RESEARCH §Bitemporal Pattern]`:

```
Training row for decision D made at time T_decision:
  Features = {BOS3 events with event_time ≤ T_decision AND ingest_time ≤ T_decision}
  Label    = {BOS5 outcome events with entity_id ∈ D.entity_refs
                AND ingest_time ≤ T_eval_horizon
                AND ingest_time > T_decision}  ← outcome must have arrived AFTER decision
```

The `ingest_time > T_decision` condition on outcome events is the no-leakage guard. It is implemented by the as-of query engine (BOS2 / SQLite store layer), not by the schema itself — but the **schema must carry both `event_time` and `ingest_time` on every outcome record** to make this query possible. This is already established by BOS3 D-02; BOS5 inherits it and must carry both timestamps on every `CategoricalLabelEvent` and `OutcomeMeasureEvent`.

**Credit assignment across multiple decisions (D-03/D-08):** One outcome label event can inform many decisions (e.g. a single PR's `clean_merge` label informs the `task_to_agent` decision, the `review_depth` decision, and the `validation_depth` decision on that PR). Credit assignment — how much each decision "deserves" the outcome — is a reward model concern (D-08 weight config), not a label schema concern. The label schema should carry the entity anchor and entity type, not a list of credited decision IDs. The join is always "decisions that targeted this entity in this time window."

## Common Pitfalls

### Pitfall 1: Cycle-Time Definitional Ambiguity
**What goes wrong:** "Cycle time" has three common definitions (task-start-to-merge, first-commit-to-merge, PR-open-to-merge). If undefined, different implementations compute different values, making the reward metric non-reproducible and the tension-pair guardrail meaningless.
**Why it happens:** The term is used loosely across DORA, DevEx, Agile, and Lean literature — each gives a slightly different definition.
**How to avoid:** The spec must pick ONE definition and name the exact BOS3 event timestamps used to compute it. Recommendation: `task.created_at` → `pr.merged_at` (or `swarm.task.ts` → `swarm.worker_done.ts`). Document the choice in the rationale doc and add it to the schema description field.
**Warning signs:** The measure record has no `measurement_definition_id` → ambiguity. Fix: add a `measure_definition_id` field referencing the named definition in the spec.

### Pitfall 2: Missing Supersession Pointer on Label Events
**What goes wrong:** A `clean_merge` label is appended, then an `escaped_defect` label supersedes it, but neither carries a pointer to the other. Consumers cannot reconstruct the progression chain and cannot detect which clean_merge events have been superseded.
**Why it happens:** Treating the label log as a simple flat sequence rather than a linked revision history.
**How to avoid:** Every label that supersedes a prior label must carry `supersedes_outcome_id` referencing the earlier label's `outcome_id`. Consumers can then build the full maturation chain. Add this field as optional (null for first-time labels) in the schema.
**Warning signs:** Two label events with the same `entity_id` and no `supersedes_outcome_id` → unlinked progression history.

### Pitfall 3: Conflating Reward Record with Outcome Event
**What goes wrong:** The reward is computed and stored as a mutation to the decision record, or as a new outcome event, rather than as a distinct append-only reward record.
**Why it happens:** It is tempting to update the BOS4 decision record with its reward once it is known — this is exactly what BOS4 D-04 bans.
**How to avoid:** Reward records are a SEPARATE schema family. They reference `decision_id` but are stored in a separate record type. A decision record NEVER gains a reward field. Enforce this in the schema: the `decisions.schema.json` (BOS4) must have `additionalProperties: false` or a documented "no outcome/reward field" constraint; the `outcomes.schema.json` (BOS5) defines `RewardRecord` as its own top-level type.

### Pitfall 4: Observation Window as Hard-Coded Schema Constant
**What goes wrong:** The schema embeds `"observation_window_days": 30` as a fixed constant on the `CleanMergeLabel` record shape. When a team wants to tune it, a schema version bump is required.
**Why it happens:** It seems convenient to put policy config in the schema.
**How to avoid:** Use an `obs_window_id` string field on every outcome event, referencing a named entry in the observation-window config table (documented in the rationale spec). The schema validates the field exists; the config table holds the value. Window tuning = config change, not schema change.

### Pitfall 5: Severity Scale Mismatch with Internal Incident Taxonomy
**What goes wrong:** BOS5 defines `severity: "high"/"medium"/"low"` but the organization uses `sev1`/`sev2`/`sev3`/`sev4`. The mismatch creates a translation step for every incident attribution rule.
**Why it happens:** BOS5 introduces its own convention without checking what upstream incident sources use.
**How to avoid:** Check whether the project has an existing incident severity convention (BOS12 external sources will use their own). Recommendation: define the severity field as a flexible enum that can be aliased (e.g. `"sev1" | "sev2" | "sev3"` matching the SRE convention rather than abstract high/medium/low). Document the mapping in the rationale spec. `[ASSUMED — the project's specific convention is not established yet; BOS5 should pick one and note it's tunable]`

### Pitfall 6: Multi-Decision Credit Assignment Leaking into the Label Schema
**What goes wrong:** The label schema carries a `credited_decision_ids: [...]` list, which requires the labeling system to know about decisions at label time — creating a circular dependency and potentially leaking BOS4 decision structure into the label schema.
**Why it happens:** It seems convenient to pre-compute credit assignment at label time.
**How to avoid:** D-03 says: labels anchor to the entity; decisions JOIN to labels via entity refs + as-of. Credit assignment is expressed in D-08 weight config, not in the label record. The schema should have NO `decision_ids` field on label events.

### Pitfall 7: Omitting the Tension-Pair Table
**What goes wrong:** The spec defines reward objectives and guardrail metrics separately, with no explicit pairing. D-10 requires every objective to have ≥1 counter-metric, but without the table, coverage is untestable.
**Why it happens:** The tension-pair requirement feels like governance commentary, not a structural spec element.
**How to avoid:** The tension-pair table is a REQUIRED section in the rationale spec (BOS5-OUTCOME-REWARD-SPEC.md). It must be machine-checkable: every `GuardrailMetricSpec` record carries a `linked_reward_objective` field; a validation script can verify that every named reward objective appears in ≥1 `GuardrailMetricSpec.linked_reward_objective`. Add this check to the CI validation suite (see §Validation Architecture, ACC-05).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bitemporal outcome join | Custom leakage-prevention logic bolted on at query time | Structural: BOS3 bitemporal model (`event_time` + `ingest_time`) + as-of query on both axes | The structure IS the guarantee; post-hoc validation is weaker and can be bypassed |
| Severity scale | Custom bespoke scale per label type | One shared ordinal scale for all severity-carrying labels (low/medium/high or sev1..sev3) | Multiple scales create translation complexity for guardrail threshold computation |
| Schema versioning | Bespoke BOS5 version scheme | Mirror `v: 1` + inline migration-note (PROTOCOL.md convention, adopted by BOS3/BOS4) | Consistency across all Voss contracts; reviewers already know the pattern |
| Reward scalarization code | Custom weighted-sum implementation | Name `linear_weighted` in the contract; delegate computation to the future analytics service | Contract specifies the SHAPE; implementation is BOS15/16 era |
| Counter-metric detection | Ad-hoc Goodhart monitoring | Structural tension-pair table with named counter-metrics and explicit linkage to reward objectives | Machine-checkable; named pairs are auditable; prevents gaming by construction |

**Key insight:** BOS5's contract work is almost entirely *naming and connecting things* — naming outcome labels (semantic decisions), naming reward objectives (aggregation decisions), naming scalarization (reproducibility decisions), and naming counter-metrics (anti-gaming decisions). The structural machinery (bitemporal append-only events, as-of joins, CI drift gate) already exists from BOS3/BOS4. BOS5 fills in the semantics.

## Code Examples

Verified patterns from codebase and prior BOS research:

### Example 1: Discriminated-union variant in `events.schema.json` (the pattern to mirror exactly)

```json
// From contracts/events.schema.json — SwarmAssign discriminated variant
"SwarmAssign": {
  "properties": {
    "swarm_id": { "title": "Swarm Id", "type": "string" },
    "task_id":  { "title": "Task Id",  "type": "string" },
    "session_id":{ "title": "Session Id", "type": "string" },
    "role":     { "title": "Role", "type": "string" },
    "type":     { "const": "swarm.assign", "default": "swarm.assign", "type": "string" },
    "v":        { "default": 1, "title": "V", "type": "integer" }
  },
  "required": ["swarm_id", "task_id", "session_id", "role", "type"],
  "title": "SwarmAssign",
  "type": "object"
}
```

BOS5 categorical labels should follow this EXACT pattern:
- `label_type` plays the role of `type` as the discriminator
- `v: 1` present on every variant
- `const` on `label_type` value per variant
- All required fields in `"required"` array
- Optional fields (severity, supersedes_outcome_id) NOT in required

### Example 2: Round-trip validation scenario (BOS3 event → label → joined to decision → reward)

```
T=0: task-abc123 created (BOS3 task.created event, event_time=T0, ingest_time=T0)

T=3d: swarm.worker_done for task-abc123 (BOS3 event, event_time=T3, ingest_time=T3)

T=4d: BOS4 DecisionRecord created: task_to_agent for task-abc123
       as_of_pointer=T3, feature_snapshot={...}, recommended=delegate_to_claude

T=4d: CycleTimeMeasure emitted for task-abc123
       event_time=T3 (when done), ingest_time=T4, value=3*86400 (seconds)

T=4d: Provisional CleanMergeLabel emitted for task-abc123
       event_time=T3, ingest_time=T4, obs_window_id="clean-merge-30d"

T=4d: Short-horizon RewardRecord computed for decision D
       horizon="short", objective_vector={throughput:0.9, quality:1.0, rework_cost:0.0, flow:0.85}
       weight_set_version="ws-v1-task-to-agent"
       scalarized_reward=0.91 (linear_weighted)

T=25d: EscapedDefectLabel emitted for task-abc123
        event_time=T24 (incident opened), ingest_time=T25
        supersedes_outcome_id="label-123" (the clean_merge label)
        severity="medium"

T=25d: Long-horizon RewardRecord APPENDED for same decision D (NOT a mutation)
        horizon="long", objective_vector={throughput:0.9, quality:0.1, rework_cost:0.2, flow:0.85}
        weight_set_version="ws-v1-task-to-agent" (same version — reproducible)
        scalarized_reward=0.48 (quality drop dominates)

Training query at T=90d with as_of=T_decision=T4:
  → Sees features: BOS3 events with ingest_time ≤ T4 ✓
  → Sees labels: BOS5 events with entity=task-abc123 AND ingest_time ≤ T90 ← analyst picks T90
  → Does NOT see EscapedDefectLabel as part of "decision context" (ingest_time=T25 > T4) ✓
  → CAN use EscapedDefectLabel as the OUTCOME LABEL for training (it arrived after decision) ✓
```

This round-trip example is the canonical acceptance criterion for BOS5 (see §Validation Architecture ACC-04).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single scalar reward (one opaque number) | Named multi-objective vector + named scalarization | BOS5 D-07 | Tradeoffs are explainable; governance audit is possible; weight disputes are resolvable |
| Fixed observation windows per label type | Named observation window config, referenced by ID | BOS5 | Teams can tune without schema version bump |
| Reward written back to the decision record | Separate append-only RewardRecord | BOS4 D-04 + BOS5 D-09 | Structural no-leakage; decisions are immutable |
| Ad-hoc Goodhart monitoring ("we'll notice") | Structural tension-pair table with hard-gate/dashboard classification | BOS5 D-10/D-11 | Machine-checkable coverage; gaming caught by construction |
| Single final label per entity | Multi-label append-only accumulation with supersession chain | BOS5 D-05 | Full maturation signal preserved; no information loss |

**Deprecated/outdated approaches to note in the spec:**
- **Individual-ranking reward:** Scoring individual engineers against each other by outcome rate. Out of scope (PROJECT.md Trust constraints) and produces gaming behavior. BOS5 reward is team-level by design.
- **Time-discounted reward:** Using an exponential decay factor to downweight late outcomes. Rejected in D-09 because it masks severe late incidents (a sev1 incident at day 89 should not be discounted to near-zero). Use explicit observation windows and horizon recomputation instead.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Observation window defaults (7d short, 30d clean_merge, 90d escaped_defect/incident) | Observation Window Guidance | Low — these are tunable team config; incorrect defaults get adjusted without a schema change |
| A2 | Named objective set: throughput / quality / rework_cost / flow | Multi-Objective Reward Design | Low — objectives are discretionary (CONTEXT.md Claude's Discretion); planner may alter names |
| A3 | Linear weighted scalarization as initial named function | Scalarization Patterns | Low — correct choice for interpretability at this stage; documented as extensible |
| A4 | Severity scale: low/medium/high (or sev1..sev3) on 3 levels | Severity Scale | Medium — if the project already has a 4-level scale (P0..P3), the enum needs adjustment; flag for planner to confirm |
| A5 | Cycle time definition: task.created_at → pr.merged_at (widest measure) | Outcome Label Definitions | Medium — other definitions are valid; the spec must pick one and document it; wrong choice creates a measure that doesn't match what teams expect |
| A6 | `contracts/outcomes.schema.json` as the schema file path | Architecture Patterns | Low — consistent with sibling `events.schema.json`; planner may choose a different path within `contracts/` |
| A7 | `docs/BOS5-OUTCOME-REWARD-SPEC.md` as the rationale doc path | Architecture Patterns | Low — arbitrary path; planner may choose differently |
| A8 | `RewardRecord` is defined in the outcomes schema (same file as labels) | Schema Pattern | Low — alternative is a separate `rewards.schema.json`; either is valid; single file simplifies the CI drift gate |
| A9 | `human_override` label severity is not needed (presence alone is significant) | Outcome Label Definitions | Low — could add severity to capture "forced vs exploratory" overrides; not needed now |
| A10 | The 4-objective reward vector is sufficient for v0.2 baseline | Multi-Objective Reward Design | Low — additional objectives (e.g. "agent_cost_efficiency") can be added as new weight-set versions without a schema version bump (additive-only rule) |

## Open Questions (RESOLVED)

> All four resolved during planning — see BOS5-CONTEXT.md and the BOS5-01/02 PLAN `<interfaces>` blocks.
> Resolutions: (1) severity = `low|medium|high`; (2) single `contracts/outcomes.schema.json`;
> (3) `entity_type` = `task|pr|session|external_reserved`; (4) two named reward horizons (`short`, `long`).

1. **Does the project have an existing incident severity convention (sev1..sev4, P0..P3, high/medium/low)?**
   - What we know: BOS5 must define an optional severity field on relevant labels (D-06). BOS12 will ingest external incident sources that carry their own severity.
   - What's unclear: Whether the project or its target customers have an established convention.
   - Recommendation: Default to `"low" | "medium" | "high"` (simplest; maps onto any existing scale); note in the spec that BOS12 ingestion adds a mapping layer.

2. **Should `RewardRecord` and `GuardrailMetricSpec` be in `outcomes.schema.json` or separate files?**
   - What we know: BOS2 D-06 established `contracts/` as the schema home; the CI drift gate covers the whole directory.
   - What's unclear: Whether a single `outcomes.schema.json` is cleanest or whether `rewards.schema.json` and `guardrails.schema.json` are clearer to downstream consumers.
   - Recommendation: Single `outcomes.schema.json` with clearly separated `$defs` sections. Cleaner CI gate surface; easier for BOS15/BOS16 to import one file.

3. **What `entity_type` values should be in the enum?**
   - What we know: BOS3 D-04 established stable entity IDs for task, session, swarm-assignment. External entities (PR, commit, service) are BOS12.
   - What's unclear: Whether `pr` and `commit` should be in BOS5's entity_type enum now (since they're the natural anchor for most outcome labels) or reserved for BOS12.
   - Recommendation: Include `task`, `pr`, and `session` as the initial enum (PRs are the primary outcome anchor; tasks are BOS3 native; sessions are BOS3 native); add `external_reserved` as a forward-compat slot. BOS12 extends with additional values.

4. **How should the `short` reward horizon interact with BOS15's offline evaluation?**
   - What we know: D-09 specifies short + long horizons; BOS15 can pick a horizon.
   - What's unclear: Whether BOS5 should define exactly two horizons or leave it open.
   - Recommendation: Define two named horizons as a normative baseline; allow additional named horizons in team config without a schema change (open-ended list, not a fixed enum).

## Environment Availability

> Docs-first phase. No external runtime services required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + .venv | Running JSON Schema validation tests | ✓ (project .venv) | project standard | — |
| `jsonschema` (PyPI) | Schema lint + example-event round-trip test | TBD (not verified installed) | — | Use AJV (npm) via existing contracts tooling; or pydantic round-trip |
| CI drift gate scripts | Schema joining CI gate (BOS2 D-06) | ✓ (existing for events.schema.json) | — | Extend existing gate rather than create new |

**Missing dependencies with no fallback:** none (docs deliverable).
**Missing dependencies with fallback:** `jsonschema` — if not installed, Wave 0 task adds it; fallback is AJV via the existing TypeScript contract tooling.

## Validation Architecture

> `nyquist_validation: true` in config — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (project standard; consistent with BOS3 approach) |
| Config file | project root (existing `tests/` tree) |
| Quick run command | `.venv/bin/python -m pytest tests/planning/test_bos_outcome_schema.py -x` |
| Full suite command | `.venv/bin/python -m pytest tests/planning/ -x` |

This is a docs/contract phase. "Tests" validate the artifact's internal consistency (schema validity, example round-trips, coverage checks), not runtime behavior. All checks are fast, deterministic, and require no live services.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOS-DATA-03 | The JSON Schema at `contracts/outcomes.schema.json` is itself valid (lints clean against Draft 2020-12 meta-schema) | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_schema_is_valid -x` | ❌ Wave 0 |
| BOS-DATA-03 | All 7 categorical label types are present in the schema as discriminated variants (clean_merge, rework, revert, failed_validation, escaped_defect, incident, human_override) | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_categorical_label_coverage -x` | ❌ Wave 0 |
| BOS-DATA-03 | Cycle time measure is present as a discriminated variant in the `outcome_measure` family | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_measure_coverage -x` | ❌ Wave 0 |
| BOS-DATA-03 | Example categorical label events round-trip: validate against the schema (one per label type) | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_label_examples_validate -x` | ❌ Wave 0 |
| BOS-DATA-03 | Bitemporal invariant: every example label carries both `event_time` and `ingest_time`; no label mutates a prior label record (append-only check on examples) | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_bitemporal_invariant -x` | ❌ Wave 0 |
| BOS-DATA-03 | No-leakage guard: label schema has no `decision_id` or `recommended_action` field (outcome labels do not reference decisions; join is the other direction) | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_no_decision_leakage_in_label -x` | ❌ Wave 0 |
| BOS-DATA-04 | RewardRecord schema is present with required fields: `decision_id`, `objective_vector`, `weight_set_version`, `horizon`, `computed_at` | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_reward_record_shape -x` | ❌ Wave 0 |
| BOS-DATA-04 | Decision record schema (BOS4 `contracts/decisions.schema.json`) has NO reward/outcome field — BOS5 does not retroactively add one | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_decision_schema_no_outcome_field -x` | ❌ Wave 0 |
| BOS-DATA-04 | Tension-pair coverage: every named reward objective in the `WeightSetRecord` schema appears as `linked_reward_objective` in at least one `GuardrailMetricSpec` definition | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_tension_pair_coverage -x` | ❌ Wave 0 |
| BOS-DATA-04 | Guardrail role enum is `"hard_gate"` or `"dashboard"` — no other values | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_guardrail_role_enum -x` | ❌ Wave 0 |
| BOS-DATA-04 | Named scalarization function field on WeightSetRecord is a string enum with `"linear_weighted"` present | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_scalarization_named -x` | ❌ Wave 0 |
| BOS-DATA-04 | Round-trip scenario: a sample BOS3 swarm.worker_done event → derived CycleTimeMeasure + CleanMergeLabel → both validate against outcomes schema | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_round_trip_scenario -x` | ❌ Wave 0 |
| BOS-DATA-03+04 | Schema versioning: `v: 1` present on every categorical and measure variant; rationale doc contains a migration-notes section | unit | `pytest tests/planning/test_bos_outcome_schema.py::test_versioning_present -x` | ❌ Wave 0 |

**Acceptance Criteria (ACC) — named for use in task acceptance criteria:**

| ACC ID | Description |
|--------|-------------|
| ACC-01 | `contracts/outcomes.schema.json` exists, passes Draft 2020-12 meta-schema lint |
| ACC-02 | All 7 categorical label types + cycle_time measure present as discriminated variants |
| ACC-03 | Every label variant carries `entity_id`, `event_time`, `ingest_time`, `obs_window_id`, `source_rule` |
| ACC-04 | Round-trip example: BOS3 event → CycleTimeMeasure + CleanMergeLabel → validates; SupersededBy scenario (CleanMerge → EscapedDefect) validates with `supersedes_outcome_id` present |
| ACC-05 | Tension-pair coverage: every named reward objective in the contract has ≥1 `GuardrailMetricSpec` with `linked_reward_objective` pointing to it |
| ACC-06 | CI drift gate includes `contracts/outcomes.schema.json` (same gate as `events.schema.json`) |
| ACC-07 | `docs/BOS5-OUTCOME-REWARD-SPEC.md` exists and contains: derivation rules table, observation window table, reward objective table, tension-pair table, migration notes |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/planning/test_bos_outcome_schema.py -x`
- **Per wave merge:** `.venv/bin/python -m pytest tests/planning/ -x`
- **Phase gate:** All ACC-01..ACC-07 green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/planning/test_bos_outcome_schema.py` — all schema validation tests above
- [ ] `contracts/outcomes.schema.json` — the normative outcome/reward/guardrail schema
- [ ] `docs/BOS5-OUTCOME-REWARD-SPEC.md` — rationale prose doc
- [ ] `.planning/schemas/examples/outcome_examples.json` — example label/measure/reward records (or inline fixtures in the test file)
- [ ] If `jsonschema` not installed: Wave-0 task to install it into `.venv` (or confirm AJV fallback)

*None of these exist yet — all are Wave 0 artifacts for BOS5.*

## Security Domain

> `security_enforcement` absent from config = enabled. BOS5 is a docs-only phase producing a JSON Schema and markdown. Security surface is minimal but assessed for completeness.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no auth in a schema doc |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a |
| V5 Input Validation | yes (indirectly) | The outcome schema IS the validation contract for the future outcome-label writer. Schema must NOT permit outcome fields that could carry credentials, tokens, API keys, or PII. Outcome records anchor to entity IDs (stable BOS3 IDs), not to raw engineer names, emails, or performance rankings. |
| V6 Cryptography | no | n/a |

### Known Threat Patterns for an outcome/reward schema

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PII/ranking leakage in outcome records | Information disclosure | Label records carry `entity_id` (BOS3 opaque ID), NOT engineer name/email. Reward records are team-level aggregations, not per-engineer scores. Schema must prohibit `engineer_id`, `engineer_name`, or equivalent individual-ranking fields. |
| Goodhart gaming through schema exploitation | Tampering / Repudiation | Tension-pair coverage check (ACC-05) is structural; hard-gate classification in `GuardrailMetricSpec` prevents schema-level bypass. BOS15 wires enforcement. |
| Outcome label injection (forged labels) | Tampering | Same append-only + immutable provenance as BOS3. Label records carry `source_rule` (the derivation rule that produced them) — auditable, not human-entered. Future: the label-writer service should validate `source_rule` against the registered rules table. |

## Sources

### Primary (HIGH confidence)
- `contracts/events.schema.json` — existing discriminated-union schema; the exact pattern BOS5 mirrors for `outcomes.schema.json`. Read 2026-06-18.
- `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md` — all 12 locked decisions (D-01..D-12). Read 2026-06-18.
- `.planning/phases/BOS4-decision-ledger-schema/BOS4-CONTEXT.md` — D-04 no-leakage guard; D-02 `decision_type` taxonomy. Read 2026-06-18.
- `.planning/phases/BOS3-engineering-event-schema/BOS3-CONTEXT.md` — D-02 bitemporal append-only; D-04 stable entity IDs. Read 2026-06-18.
- `.planning/phases/BOS3-engineering-event-schema/BOS3-RESEARCH.md` — bitemporal pattern canonical references; existing substrate enumeration. Read 2026-06-18.
- `.planning/PROJECT.md` — Constraints §Trust, §Safety, §Data (no leakage, team-level, no individual ranking). Read 2026-06-18.
- `.planning/REQUIREMENTS.md` — BOS-DATA-03, BOS-DATA-04. Read 2026-06-18.

### Secondary (MEDIUM confidence)
- DORA (DevOps Research and Assessment) four key metrics — lead time for change, deployment frequency, change failure rate, mean time to restore — map directly onto BOS-DATA-03 label set. `[ASSUMED — based on well-established training knowledge of DORA research; not re-verified via web search in this session]`
- Goodhart's Law counter-metric pattern (tension pairs) is standard practice in platform engineering / developer metrics programs. `[ASSUMED — confirmed by training knowledge + consistent with D-10's explicit rationale in CONTEXT.md]`
- Linear weighted scalarization as the interpretable baseline for multi-objective reward in RL. `[ASSUMED — standard MORL baseline; not re-verified via web search in this session]`
- Martin Fowler bitemporal history pattern — actual/record time, as-of reconstruction. `[CITED in BOS3-RESEARCH via martinfowler.com/articles/bitemporal-history.html]`

### Tertiary (LOW confidence)
- Specific observation window default values (7d/30d/90d) — `[ASSUMED]` reasonable starting points from convention; should be confirmed with team norms.
- Specific severity scale (low/medium/high vs sev1..sev3) — `[ASSUMED]`; depends on what the organization's incident management tooling uses.

## Metadata

**Confidence breakdown:**
- Schema design pattern: HIGH — directly mirrors the verified `contracts/events.schema.json` pattern
- Outcome label definitions (DORA-grounded): MEDIUM — well-established convention; specific derivation-rule triggers depend on BOS12 external sources not yet specced
- Multi-objective reward design: MEDIUM — sound theory + consistent with CONTEXT.md locked decisions; specific objective names are discretionary
- Goodhart/tension-pair patterns: MEDIUM — well-established in platform engineering community; specific thresholds are LOW
- Observation window defaults: LOW — reasonable starting points; teams should validate against their own incident rates
- Bitemporal join / no-leakage mechanism: HIGH — confirmed against BOS3 canonical references and CONTEXT.md structural decisions

**Research date:** 2026-06-18
**Valid until:** ~2026-12-18 (internal patterns stable; DORA metrics decades-stable; only observation window tuning and severity scale may need refinement based on team feedback)

---

## BOS-DATA-05 — Offline-Evaluation Requirements (added 2026-06-20)

**Confidence:** HIGH for OPE theory, propensity-field shape, and contract structure (confirmed against OPE canonical literature and the existing Voss schema substrate). MEDIUM for gate-criteria defaults and CI-bound values (tunable team config — all flagged [ASSUMED]).

> This section was added in a second discuss pass (plans 3-5). Plans BOS5-01/02 shipped DATA-03/04. Plans BOS5-03..05 ship DATA-05. All locked decisions (D-13..D-16) are in BOS5-CONTEXT.md §Offline-Evaluation Requirements.

### Scope recap

BOS5 (this section) = **the requirements contract** — two new JSON Schema records (`EvalDatasetSpec`, `PolicyEvalReport`) in `contracts/offline-eval.schema.json` + prose spec `docs/BOS5-OFFLINE-EVAL-SPEC.md`. BOS13 builds the export/replay machinery that produces and consumes those records. BOS15 wires the gate enforcement. BOS5 defines shapes and requirements only.

---

### RQ-1: OPE Estimator Family (D-14)

**Confidence:** HIGH [ASSUMED — based on canonical OPE literature; cross-verified against multiple sources in training data; the characterization below is well-established and stable]

Off-Policy Evaluation (OPE) estimates the value of a **target policy** π_new using data logged by a **behavior policy** π_b. The fundamental requirement enabling any OPE is that the behavior policy's action probabilities were logged at decision time — the propensity P(a | x; π_b). Without logged propensities, only direct-method estimators (which require a reward model) are feasible, and all importance-weighting estimators are blocked.

#### Admissible Estimator Family (D-14 — name these, bind none)

| Estimator | Abbreviation | Policy Class | What It Requires from Logged Data | What It Reports | Key Property |
|-----------|-------------|-------------|-----------------------------------|-----------------|--------------|
| Inverse Propensity Scoring | IPS | Contextual bandit (single-step) | Propensity p(a\|x) per logged decision; reward r | Point estimate, variance, ESS | Unbiased when propensities are correct; high variance with low overlap |
| Self-Normalized IPS (Weighted IPS) | SNIPS | Contextual bandit (single-step) | Same as IPS | Point estimate, lower variance, ESS | Lower variance than IPS via normalization; slight bias; more stable at low ESS |
| Doubly Robust | DR | Contextual bandit (single-step) | Propensity p(a\|x); reward model (direct-method baseline) | Point estimate, variance, ESS, model-bias term | Consistent if EITHER propensity OR reward model is correct; lower variance than IPS when reward model is good |
| Direct Method | DM | Any (no propensity required) | A reward model (regression over features → reward) | Point estimate | Consistent only if reward model is correct; biased by model misspecification; use when propensities are unavailable |
| Fitted Q-Evaluation | FQE | Sequential / RL (multi-step) | Trajectory data (s, a, r, s') tuples + propensity (for off-policy correction) | Q-value estimate, policy value | Handles temporal dependencies; requires more logged data; appropriate when decisions are sequential over an episode |

**Required properties any admitted estimator MUST report (D-14 mandates these, not an estimator):**

| Property | Why Required | How Expressed in PolicyEvalReport |
|----------|-------------|----------------------------------|
| Point estimate | The bottom-line value comparison (new policy vs baseline) | `ope_point_estimate` field |
| Confidence interval / uncertainty bound | No policy is promoted without a CI that clears the D-16 threshold shape | `ci_lower`, `ci_upper`, `ci_level` fields |
| Effective Sample Size (ESS) | Warns when high-variance propensity weights make the estimate unreliable | `effective_sample_size` field |
| Bias disclosure | Flag when the estimate relies on an unverified reward model (DM or DR model component) | `bias_flags[]` array |

**Policy-class guidance for BOS13 (informational — BOS5 does not bind):**

- Heuristic / argmax delegation (current, deterministic) → IPS is degenerate (propensity=1.0 for every logged action, ESS = N). DM is the practical estimator until policies become stochastic. Log the propensity=1.0 anyway — the field must exist.
- Contextual bandit (epsilon-greedy or softmax, BOS13/14) → IPS or SNIPS are the standard first choice; DR when a reward model is available.
- Sequential RL over multi-step episodes (BOS16+) → FQE.

**Anti-pattern to avoid:** Choosing an estimator in BOS5. D-14 explicitly rejects this. The requirements contract names the admissible family; BOS13 picks from it based on the actual logged data and policy class at build time.

---

### RQ-2: Propensity-Logging Field on the Decision Record (D-15)

**Confidence:** HIGH for field shape and placement. Confirmed by reading `contracts/decision-ledger.schema.json` — the field does NOT exist there today. [VERIFIED: codebase read 2026-06-20]

#### Current state of `contracts/decision-ledger.schema.json`

Read directly: the schema has `decision_id`, `decision_type`, `created_at`, `as_of`, `feature_snapshot`, `entity_ref`, `autonomy_band`, `recommended_action`, `human_verdict`, `actual_action`, `rationale`, `payload`. **No propensity, no exploration, no action-space fields.** The schema uses `additionalProperties: false` at the top level, so adding a field requires an explicit schema amendment — this is the BOS4 follow-up plan D-15 mandates.

#### Required new field shape (additive amendment to `contracts/decision-ledger.schema.json`)

`[ASSUMED — exact field names are Claude's Discretion per CONTEXT.md; the structure below is the recommended shape]`

```json
"policy_context": {
  "title": "Policy Context",
  "description": "Action-propensity and exploration metadata logged at decision time (BOS5 D-15). Required for OPE: the behavior policy's propensity P(action|context) must be logged at the moment of decision so historical decisions remain evaluable when policies become stochastic. Currently deterministic (argmax -> propensity=1.0); field must exist now so historical decisions are not stranded un-evaluable.",
  "type": "object",
  "properties": {
    "propensity": {
      "title": "Propensity",
      "description": "P(action | context; behavior_policy) at decision time. Range [0.0, 1.0]. For deterministic argmax policies: 1.0. For epsilon-greedy with epsilon=0.1 on the chosen action: (1 - epsilon) + epsilon/|A| if chosen action is greedy, else epsilon/|A|.",
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "action_space": {
      "title": "Action Space",
      "description": "The candidate action set considered at decision time. Array of action identifiers (agent ids, band strings, depth levels, etc.) appropriate to the decision_type. For deterministic argmax with one option: [chosen_action_id]. Enables ESS computation and importance-weight clipping in OPE.",
      "type": "array",
      "items": { "type": "string" }
    },
    "exploration_flag": {
      "title": "Exploration Flag",
      "description": "Whether this decision was an exploration action (not the greedy/argmax choice). False for all current deterministic decisions. When true, propensity reflects the exploration probability.",
      "type": "boolean"
    },
    "policy_version": {
      "title": "Policy Version",
      "description": "The behavior policy version that produced this decision. For deterministic heuristics: a named version string (e.g. 'heuristic-v1'). For learned policies (BOS13+): a versioned model/policy id. OPE requires knowing which policy produced each logged row.",
      "type": "string"
    }
  },
  "required": ["propensity", "action_space", "exploration_flag", "policy_version"],
  "additionalProperties": false
}
```

**Placement:** Top-level field on the decision record (alongside `rationale`, `recommended_action`), not inside `payload`, so it is available on every decision type without per-payload duplication.

**Schema amendment note:** Because `decision-ledger.schema.json` has `additionalProperties: false`, this field cannot be added silently. The BOS4 follow-up plan must: (1) add `policy_context` to the `properties` block, (2) add it to `required`, and (3) add a migration note in `BOS4-DECISION-LEDGER.md`. This is an additive change (new required field) — a schema version bump is appropriate per the `$comment` versioning convention in `outcomes.schema.json`.

**Deterministic policy population (current state):**

```json
"policy_context": {
  "propensity": 1.0,
  "action_space": ["claude-opus-4"],
  "exploration_flag": false,
  "policy_version": "heuristic-v1"
}
```

**OPE implication of propensity=1.0:** When propensity=1.0 for every logged decision (deterministic policy), IPS weights are all 1.0 and IPS degenerates to the empirical mean — it is not informative for counterfactual estimation. This is expected and correct: IPS-family estimators become useful only when the behavior policy has positive support over multiple actions. The field must still be logged now because: (a) DM estimators need it for completeness; (b) once the policy becomes stochastic, historical rows without propensities cannot be included in OPE datasets.

---

### RQ-3: EvalDatasetSpec Contract (D-13)

**Confidence:** HIGH (structural requirements follow directly from the no-leakage guarantee already established in BOS3/BOS4/BOS5 DATA-03/04; the fields below are the necessary and sufficient set for a valid OPE dataset given those upstream locks). `[ASSUMED — exact field names are Claude's Discretion]`

`EvalDatasetSpec` is a **frozen, point-in-time-correct snapshot description** — a record that a BOS13 dataset exporter must produce alongside each eval dataset. It is a contract record, not a runtime event. It answers: "What is in this dataset, and is it valid for OPE?"

#### Required fields

```json
// EvalDatasetSpec — shape (not a runtime event; a dataset-level manifest record)
{
  "spec_id":           string,          // stable unique id for this eval dataset spec
  "v":                 integer (const 1),
  "created_at":        date-time,       // when this spec was produced
  "dataset_version":   string,          // version/tag for the frozen dataset (e.g. "eval-2026-Q3-v1")
  "policy_version":    string,          // the behavior policy version whose decisions are in this dataset
  "as_of_cutoff":      date-time,       // T_eval: only decisions with created_at <= T_eval included
  "outcome_horizon":   string,          // "short" | "long" (or any named horizon from RewardRecord)
  "outcome_as_of":     date-time,       // T_outcome: outcome labels with ingest_time <= T_outcome included
  "no_leakage_check":  object,          // structural proof that outcome_as_of > as_of_cutoff (not a future filter)
  "decision_count":    integer,         // number of decision rows in the dataset
  "propensity_coverage_pct": number,    // % of rows with policy_context.propensity present (must be 100% for IPS-family)
  "estimator_eligibility": array,       // which estimator families are eligible given the data ["ips","snips","dr","dm","fqe"]
  "reward_objective_keys": array,       // the objective names present in RewardRecord.objective_vector for these rows
  "weight_set_version": string,         // the WeightSetRecord version used to compute rewards in this dataset
  "decision_types_included": array,     // which decision_type values are in this dataset (subset of the 6 types)
  "horizon_note":      string           // optional: prose note on horizon selection rationale
}
```

**The no-leakage invariant (required field `no_leakage_check`):**

```json
"no_leakage_check": {
  "outcome_as_of_after_as_of_cutoff": true,   // outcome_as_of > as_of_cutoff (outcomes are posterior to decisions)
  "all_outcomes_ingest_after_decision": true,  // all outcome ingest_times in dataset > corresponding decision created_at
  "verified_by": "BOS13-exporter"             // which component verified this invariant
}
```

This field makes the no-leakage guarantee explicit in the dataset manifest. BOS13's exporter writes it; the contract check (ACC-11) verifies it is present and `outcome_as_of_after_as_of_cutoff` is true in any example EvalDatasetSpec.

**`estimator_eligibility` logic (informational for BOS13):**

- `"ips"` eligible if `propensity_coverage_pct == 100` AND policy was stochastic (some propensity < 1.0)
- `"snips"` — same as IPS conditions
- `"dr"` — same as IPS conditions AND a reward model is available
- `"dm"` — always eligible (requires reward model, not propensities)
- `"fqe"` — eligible if decisions are sequential within episodes (multi-step)

For the current deterministic heuristic phase, `estimator_eligibility` will typically be `["dm"]` (or `["ips","snips","dr","dm"]` with the caveat that IPS is degenerate at propensity=1.0). The field is still required; BOS13 populates it from the dataset statistics.

---

### RQ-4: PolicyEvalReport Contract (D-13/D-14)

**Confidence:** HIGH for required fields (derived from D-14's mandatory properties + D-16's gate criteria shape). `[ASSUMED — exact field names are Claude's Discretion]`

`PolicyEvalReport` is what BOS13 emits after running an offline evaluation. It is the machine-readable result record that BOS15 reads to enforce the D-16 promotion gate. One report per (policy candidate × eval dataset × estimator run).

#### Required fields

```json
// PolicyEvalReport — shape (not a runtime event; an eval result record)
{
  "report_id":              string,        // stable unique id
  "v":                      integer (const 1),
  "created_at":             date-time,
  "eval_dataset_spec_id":   string,        // foreign key → EvalDatasetSpec.spec_id
  "candidate_policy_version": string,      // the new policy being evaluated (π_new)
  "baseline_policy_version":  string,      // the behavior/baseline policy (π_b, same as dataset's policy_version)
  "estimator":              string,        // which estimator was used: "ips" | "snips" | "dr" | "dm" | "fqe"
  "ope_point_estimate":     number,        // estimated value of candidate policy under this estimator
  "baseline_point_estimate": number,       // estimated value of baseline policy (for lift computation)
  "ope_lift":               number,        // ope_point_estimate - baseline_point_estimate (positive = improvement)
  "ci_level":               number,        // confidence level for the CI, e.g. 0.95 [ASSUMED default]
  "ci_lower":               number,        // lower bound of (ope_lift) confidence interval
  "ci_upper":               number,        // upper bound of (ope_lift) confidence interval
  "effective_sample_size":  number,        // ESS — key quality indicator for IPS-family; low ESS = unreliable estimate
  "bias_flags":             array,         // strings naming any known bias sources (e.g. "reward_model_not_validated", "low_ess", "deterministic_propensity")
  "guardrail_deltas":       array,         // per-guardrail metric delta between candidate and baseline (shape below)
  "gate_result":            object,        // did this report pass or fail the D-16 gate criteria? (shape below)
  "reward_objective_keys":  array,         // the objective keys from the eval dataset (cross-check with EvalDatasetSpec)
  "weight_set_version":     string,        // the WeightSetRecord version used for scalarized reward in this eval
  "horizon":                string,        // "short" | "long" — the outcome horizon used in this eval
  "notes":                  string         // optional: free-text rationale or caveats from the evaluator
}
```

**`guardrail_deltas` item shape (one per GuardrailMetricSpec in the dataset):**

```json
{
  "guardrail_id":     string,    // matches GuardrailMetricSpec.guardrail_id
  "role":             string,    // "hard_gate" | "dashboard"
  "candidate_value":  number,    // guardrail metric value for the candidate policy
  "baseline_value":   number,    // guardrail metric value for the baseline
  "delta":            number,    // candidate_value - baseline_value (negative = regression)
  "regression":       boolean    // true if delta indicates the guardrail worsened (direction depends on metric)
}
```

**`gate_result` shape (ties to D-16):**

```json
{
  "passed":                      boolean,    // overall pass/fail
  "lift_threshold_met":          boolean,    // ope_lift >= min_lift_threshold (D-16 shape; value is team config)
  "ci_bound_met":                boolean,    // ci_lower >= min_ci_lower_threshold (D-16 shape; value is team config)
  "all_hard_gates_non_regressed": boolean,   // no hard_gate guardrail has regression: true
  "blocking_reasons":            array       // string list of reasons if passed=false
}
```

---

### RQ-5: Promotion-Gate Criteria Shape (D-16)

**Confidence:** HIGH for structure. Threshold values are [ASSUMED] team config — not load-bearing for the contract shape.

D-16 defines the **shape** of the gate criteria: what a policy must satisfy to be promoted. BOS15 wires the actual enforcement. The contract must express these as a versioned configuration record (not hardcoded in the schema) so threshold values are tunable without a schema change.

#### PromotionGateCriteria record shape

```json
// PromotionGateCriteria — versioned team config record (not a runtime event)
{
  "criteria_id":          string,       // stable id for this criteria version
  "v":                    integer (const 1),
  "effective_from":       date-time,
  "min_ope_lift":         number,       // minimum required ope_lift (D-16 threshold shape). [ASSUMED default: 0.0 — positive lift required]
  "min_ci_lower":         number,       // minimum required ci_lower at ci_level. [ASSUMED default: 0.0 — CI lower bound must be non-negative]
  "ci_level":             number,       // required CI confidence level. [ASSUMED default: 0.95]
  "min_effective_sample_size": number,  // minimum ESS for the estimate to be trusted. [ASSUMED default: 30]
  "hard_gate_non_regression_required": boolean, // must be true (all hard_gate guardrails must not worsen). Always true.
  "required_estimators":  array,        // estimator(s) that must be run (e.g. ["dm"] for deterministic phase; ["ips","dr"] for bandit phase). [ASSUMED — teams configure per policy class]
  "notes":                string
}
```

**Three-part gate anatomy (D-16):**

1. **Minimum OPE-lift threshold** (`min_ope_lift`): The candidate policy must improve on the baseline by at least this amount under the OPE estimate. Shape is "a non-negative number"; the value is team config. `[ASSUMED default: 0.0 — any positive lift qualifies, teams can raise this bar]`

2. **CI/uncertainty bound** (`min_ci_lower` + `ci_level`): The lower bound of the confidence interval on the lift estimate must also be non-negative at the specified confidence level. This prevents promoting a policy where the CI spans zero (i.e., improvement is not statistically distinguishable from noise). `[ASSUMED default: ci_level=0.95, min_ci_lower=0.0]`

3. **D-11 hard-gate guardrail non-regression**: Every guardrail metric classified as `hard_gate` in `GuardrailMetricSpec.role` must NOT worsen (must have `regression: false` in `guardrail_deltas`). This is a boolean hard requirement, not a threshold — it mirrors D-11's "hard gate = blocks promotion" classification. BOS5 defines this requirement; BOS15 implements the check.

**Connection to D-11:** The D-11 hard-gate classification in `GuardrailMetricSpec` is the upstream of the D-16 gate. Every record in the outcomes schema with `role: "hard_gate"` automatically becomes a D-16 blocking check. The `PolicyEvalReport.gate_result.all_hard_gates_non_regressed` field is the aggregated result.

**ESS floor rationale:** A minimum effective sample size is required because IPS-family estimates with very low ESS (e.g., ESS < 10) are practically meaningless — the variance is so high that even a "positive" point estimate is noise. The contract should require `effective_sample_size >= min_effective_sample_size` as a precondition for a valid IPS/SNIPS/DR estimate. `[ASSUMED default: 30 — a conservative but not overly strict floor; teams may lower for early evals]`

---

### RQ-6: Validation Architecture Extension (Nyquist — DATA-05 additions)

The existing `tests/planning/test_bos_outcome_schema.py` + ACC-01..07 cover DATA-03/04. DATA-05 adds a new schema file (`contracts/offline-eval.schema.json`) and two new doc sections. The following extends the test map and ACC list.

**New test file for DATA-05:** `tests/planning/test_bos_offline_eval_schema.py`

#### Extended Phase Requirements → Test Map (BOS-DATA-05)

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOS-DATA-05 | `contracts/offline-eval.schema.json` exists and passes Draft 2020-12 meta-schema lint | unit | `.venv/bin/python -m pytest tests/planning/test_bos_offline_eval_schema.py::test_offline_eval_schema_is_valid -x` | ❌ Wave 0 |
| BOS-DATA-05 | `EvalDatasetSpec` and `PolicyEvalReport` are both present as named `$defs` in the offline-eval schema | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_record_types_present -x` | ❌ Wave 0 |
| BOS-DATA-05 | `EvalDatasetSpec` example round-trips: a minimal valid example validates against the schema | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_eval_dataset_spec_example_validates -x` | ❌ Wave 0 |
| BOS-DATA-05 | `PolicyEvalReport` example round-trips: a minimal valid example validates against the schema | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_policy_eval_report_example_validates -x` | ❌ Wave 0 |
| BOS-DATA-05 | `EvalDatasetSpec` carries `no_leakage_check` with `outcome_as_of_after_as_of_cutoff` field present | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_no_leakage_check_field_present -x` | ❌ Wave 0 |
| BOS-DATA-05 | `estimator_eligibility` is an array whose items are constrained to the D-14 admissible family enum (`ips`, `snips`, `dr`, `dm`, `fqe`) | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_estimator_family_enum_coverage -x` | ❌ Wave 0 |
| BOS-DATA-05 | `PolicyEvalReport.estimator` field is constrained to the same admissible estimator enum | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_report_estimator_enum -x` | ❌ Wave 0 |
| BOS-DATA-05 | `PolicyEvalReport` carries `ci_lower`, `ci_upper`, `ci_level`, `effective_sample_size`, `bias_flags`, `guardrail_deltas`, `gate_result` as required fields | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_policy_eval_report_required_fields -x` | ❌ Wave 0 |
| BOS-DATA-05 | `gate_result` sub-object has `passed`, `lift_threshold_met`, `ci_bound_met`, `all_hard_gates_non_regressed`, `blocking_reasons` | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_gate_result_shape -x` | ❌ Wave 0 |
| BOS-DATA-05 | `guardrail_deltas` item shape carries `guardrail_id`, `role` enum (`hard_gate`\|`dashboard`), `candidate_value`, `baseline_value`, `delta`, `regression` | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_guardrail_delta_shape -x` | ❌ Wave 0 |
| BOS-DATA-05 | `contracts/decision-ledger.schema.json` (BOS4 follow-up) carries `policy_context` with `propensity`, `action_space`, `exploration_flag`, `policy_version` | unit | `pytest tests/planning/test_bos_offline_eval_schema.py::test_propensity_field_on_decision_record -x` | ❌ Wave 0 (BOS4 follow-up) |
| BOS-DATA-05 | `docs/BOS5-OFFLINE-EVAL-SPEC.md` exists and contains the admissible estimator table, propensity-logging requirement, gate criteria shape, and a section on the no-leakage join | unit (file presence + section grep) | `pytest tests/planning/test_bos_offline_eval_schema.py::test_offline_eval_spec_doc_exists -x` | ❌ Wave 0 |

#### Extended Acceptance Criteria (ACC-08..ACC-14)

| ACC ID | Description |
|--------|-------------|
| ACC-08 | `contracts/offline-eval.schema.json` exists, passes Draft 2020-12 meta-schema lint |
| ACC-09 | `EvalDatasetSpec` and `PolicyEvalReport` both present as named `$defs`; both validate example round-trips |
| ACC-10 | `estimator_eligibility` and `PolicyEvalReport.estimator` both constrained to the D-14 admissible family enum (`ips`, `snips`, `dr`, `dm`, `fqe`) — no other values |
| ACC-11 | `EvalDatasetSpec.no_leakage_check` present with `outcome_as_of_after_as_of_cutoff` boolean field; example dataset spec has this field set to `true` |
| ACC-12 | `PolicyEvalReport` carries all D-14 mandatory properties: `ope_point_estimate`, `ci_lower`, `ci_upper`, `ci_level`, `effective_sample_size`, `bias_flags[]` |
| ACC-13 | `PolicyEvalReport.gate_result` carries all three D-16 gate check fields: `lift_threshold_met`, `ci_bound_met`, `all_hard_gates_non_regressed` |
| ACC-14 | `contracts/decision-ledger.schema.json` `policy_context` field present with `propensity` (number 0..1), `action_space` (array), `exploration_flag` (boolean), `policy_version` (string) — this is the BOS4 follow-up plan deliverable gated by ACC-14 |
| ACC-15 | `docs/BOS5-OFFLINE-EVAL-SPEC.md` exists and contains: admissible estimator family table, propensity-logging requirement prose, gate criteria shape table, no-leakage join explanation for eval datasets, and a migration notes section |
| ACC-16 | CI drift gate (`contracts/` drift check) extended to include `contracts/offline-eval.schema.json` |

**Updated Wave 0 Gaps (DATA-05 additions):**
- [ ] `tests/planning/test_bos_offline_eval_schema.py` — all DATA-05 schema validation tests above
- [ ] `contracts/offline-eval.schema.json` — new sibling contract (EvalDatasetSpec + PolicyEvalReport + PromotionGateCriteria)
- [ ] `docs/BOS5-OFFLINE-EVAL-SPEC.md` — normative prose: estimator family table, propensity requirement, gate criteria shape, no-leakage join, migration notes
- [ ] `.planning/schemas/examples/offline_eval_examples.json` — example EvalDatasetSpec + PolicyEvalReport records (or inline fixtures in test file)
- [ ] BOS4 follow-up plan: amend `contracts/decision-ledger.schema.json` to add `policy_context` field + migration note in `BOS4-DECISION-LEDGER.md`

---

### DATA-05 Common Pitfalls

#### Pitfall 8: Logging Propensity for Deterministic Policies and Thinking It's Useless
**What goes wrong:** Team skips adding the `policy_context` field because "we always pick argmax, so propensity=1.0 is meaningless." The field is omitted. When an epsilon-greedy bandit lands in BOS13, historical rows from the heuristic phase cannot be used in OPE datasets requiring propensity.
**Why it happens:** The field seems trivially informative when propensity=1.0 everywhere.
**How to avoid:** D-15 is explicit: the field MUST exist now. Propensity=1.0 is a valid value. The schema amendment to `decision-ledger.schema.json` adds `policy_context` as a required field — not optional — so runtime writers cannot skip it. The test ACC-14 checks the schema amendment, not just the value.
**Warning signs:** `policy_context` absent from `contracts/decision-ledger.schema.json`, or present but optional.

#### Pitfall 9: Confusing the Eval Dataset as-of Cutoff with the Outcome Horizon
**What goes wrong:** `EvalDatasetSpec.as_of_cutoff` (the decision-time boundary) and `EvalDatasetSpec.outcome_as_of` (the outcome-time boundary) are conflated. The exporter uses the same timestamp for both, creating a dataset where outcomes ingested at the same moment as decisions are included — violating the no-leakage invariant.
**Why it happens:** Both are timestamps; the distinction is "when were decisions made?" vs "how far into the future are outcomes observed?"
**How to avoid:** The `no_leakage_check.outcome_as_of_after_as_of_cutoff` field makes this explicit. The contract requires `outcome_as_of > as_of_cutoff`. ACC-11 checks this in example records.
**Warning signs:** `as_of_cutoff == outcome_as_of` in any EvalDatasetSpec example.

#### Pitfall 10: Reporting a CI on the Point Estimate Rather Than on the Lift
**What goes wrong:** `PolicyEvalReport` reports CI bounds on `ope_point_estimate` (the absolute value of the new policy) rather than on `ope_lift` (the delta between new and baseline). D-16's CI gate is on the lift, not the absolute value. A CI on the absolute value can pass D-16 erroneously when the baseline is high-variance.
**Why it happens:** CI-on-estimate is simpler to compute; CI-on-lift requires computing the baseline estimate and propagating its uncertainty.
**How to avoid:** The schema explicitly defines `ope_lift = ope_point_estimate - baseline_point_estimate` and `ci_lower`/`ci_upper` as bounds on the lift. The `gate_result.ci_bound_met` field checks `ci_lower >= min_ci_lower`, making it unambiguous that the CI is on lift.
**Warning signs:** `baseline_point_estimate` absent from `PolicyEvalReport`, or `ope_lift` not defined as the difference.

#### Pitfall 11: Treating ESS as Informational When It Should Block Promotion
**What goes wrong:** `effective_sample_size` is logged in `PolicyEvalReport` but not checked in `gate_result`. A report with ESS=3 and a technically positive `ci_lower` passes the gate, even though the estimate is unreliable.
**Why it happens:** ESS is treated as a diagnostic rather than a gate criterion.
**How to avoid:** `PromotionGateCriteria.min_effective_sample_size` adds ESS as a gate condition. `PolicyEvalReport.gate_result` should check it. The contract includes `min_effective_sample_size` in `PromotionGateCriteria` even if BOS5 leaves the value as team config.

#### Pitfall 12: Binding a Specific Estimator in the Contract (Violates D-14)
**What goes wrong:** The `offline-eval.schema.json` defines only `"estimator": {"const": "doubly_robust"}` or similar — locking one estimator prematurely.
**Why it happens:** It is tempting to pick a "best practice" estimator to reduce ambiguity.
**How to avoid:** D-14 is explicit: the contract names the admissible family (`ips`, `snips`, `dr`, `dm`, `fqe`) as an enum. The `PolicyEvalReport.estimator` field is constrained to this enum — not a single const. BOS13 picks from the enum at implementation time. ACC-10 checks that the enum covers all five values, not a single const.

---

### DATA-05 Cross-Phase Dependency Map

| Dependency | Direction | What BOS5 Produces | What Downstream Consumes |
|------------|-----------|-------------------|--------------------------|
| BOS4 decision-ledger schema | BOS5 → BOS4 follow-up | `policy_context` field requirement (D-15) | BOS4 follow-up plan amends `contracts/decision-ledger.schema.json`; BOS4 runtime writer populates it |
| BOS13 Offline Evaluation Export and Replay | BOS5 → BOS13 | `contracts/offline-eval.schema.json` (EvalDatasetSpec + PolicyEvalReport) | BOS13 exporter produces EvalDatasetSpec; BOS13 replay harness produces PolicyEvalReport |
| BOS15 policy-promotion gate | BOS5 → BOS15 | `PromotionGateCriteria` shape + D-16 gate check fields in PolicyEvalReport.gate_result | BOS15 reads PolicyEvalReport, enforces PromotionGateCriteria, blocks promotion on failure |
| BOS5 DATA-03/04 (this phase, already shipped) | Sibling | `GuardrailMetricSpec.role` classification of hard_gate metrics | PolicyEvalReport.guardrail_deltas items mirror GuardrailMetricSpec.guardrail_id + role |
| BOS-RL-02 (REQUIREMENTS) | Traceability | DATA-05 is dual-mapped BOS5 (contract) + BOS13 (build) | BOS-RL-02 is BOS15's gate-wiring requirement |

---

### DATA-05 Assumptions Log (additions to existing §Assumptions Log)

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A11 | `ci_level` default of 0.95 for the CI on OPE lift | RQ-4, RQ-5 | Low — 0.95 is the community standard CI level; teams can configure; shape is what the contract locks |
| A12 | `min_ope_lift` default of 0.0 (any positive lift) | RQ-5 PromotionGateCriteria | Medium — teams may want a minimum meaningful lift (e.g. 0.02); the shape is correct, the value is team config |
| A13 | `min_effective_sample_size` default of 30 | RQ-5 PromotionGateCriteria | Low — conservative floor; overly strict if data is scarce; teams can lower; the field is what matters |
| A14 | `policy_context` as the field name for the propensity/exploration group on the decision record | RQ-2 | Low — exact name is Claude's Discretion; shape is what matters |
| A15 | `ope_lift` defined as `ope_point_estimate - baseline_point_estimate` (absolute delta, not relative %) | RQ-4 | Medium — relative lift (%) is a valid alternative; the contract must pick one and define it; absolute delta is simpler and avoids division-by-zero edge cases |
| A16 | Admissible estimator enum is `["ips", "snips", "dr", "dm", "fqe"]` — exactly these 5 values | RQ-1 | Low — these are the canonical OPE estimator family; additional estimators (e.g. "model_selection") would be additive schema additions |

---

### DATA-05 Sources

#### Primary (HIGH confidence)
- `contracts/decision-ledger.schema.json` — verified absence of `policy_context` / propensity field. Read 2026-06-20. [VERIFIED: codebase read]
- `contracts/outcomes.schema.json` (BOS5 DATA-03/04, already shipped) — confirmed `GuardrailMetricSpec.role` enum (`hard_gate` | `dashboard`) and `guardrail_id` that DATA-05 `guardrail_deltas` mirror. Read 2026-06-20. [VERIFIED: codebase read]
- `.planning/phases/BOS5-outcome-labels-and-reward-model/BOS5-CONTEXT.md` — D-13..D-16 locked decisions. Read 2026-06-20. [VERIFIED: codebase read]
- `.planning/phases/BOS4-decision-ledger-schema/BOS4-CONTEXT.md` — confirmed `additionalProperties: false` on decision record, confirming the BOS4 follow-up requirement. Read 2026-06-20. [VERIFIED: codebase read]

#### Secondary (MEDIUM confidence)
- OPE estimator family (IPS, SNIPS/weighted IPS, Doubly Robust, Direct Method, FQE) — canonical offline RL/bandit evaluation literature. `[ASSUMED — well-established; consistent characterization across Precup 2000 (IPS), Dudik et al. 2011 (DR), Le Paine et al. 2020 (FQE); cross-verified against multiple training-data sources]`
- Effective Sample Size (ESS) as a required diagnostic for importance-weighting estimators — standard recommendation in Swaminathan & Joachims 2015 (SNIPS), Thomas & Brunskill 2016 (safe policy improvement). `[ASSUMED — well-established in OPE community; not re-verified via web search this session]`
- CI-on-lift (not CI-on-absolute-value) as the correct gate condition for safe policy improvement — standard in safe RL / offline RL gating literature. `[ASSUMED — follows from Thomas et al. 2015 "High Confidence Policy Improvement"; consistent with D-16's framing]`

---

## RESEARCH COMPLETE

DATA-05 additions: `contracts/offline-eval.schema.json` (EvalDatasetSpec + PolicyEvalReport + PromotionGateCriteria shapes), propensity field amendment to `contracts/decision-ledger.schema.json` (BOS4 follow-up), OPE admissible estimator family table (IPS/SNIPS/DR/DM/FQE), gate criteria shape (3-part: lift threshold + CI bound + hard-gate non-regression), and ACC-08..ACC-16 extending the existing Validation Architecture — all added to `BOS5-RESEARCH.md` as the `## BOS-DATA-05` section.
