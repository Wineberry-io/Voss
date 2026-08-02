# BOS5 Outcome & Reward Spec

**Phase:** BOS5-outcome-labels-and-reward-model
**Requirements covered:** BOS-DATA-03 (outcome labels + cycle time), BOS-DATA-04 (reward + guardrail metrics, bad-proxy detection)
**Machine source of truth:** `contracts/outcomes.schema.json` (sibling to `contracts/events.schema.json`; JSON Schema Draft 2020-12; `v: 1`).
**Driving decisions:** D-01..D-12 from `BOS5-CONTEXT.md`, cited per section below.

This is the normative human spec mirroring `contracts/outcomes.schema.json`. Where the schema is machine-readable, this doc is the rationale: derivation rules, observation windows, reward objectives, scalarization, tension-pair guardrails, and migration notes. The schema field names and enums used here are exactly those in the schema; this prose does not contradict the contract.

BOS5 is a docs-first contract phase. No runtime emitters, derivation engines, reward computers, migrations, or storage are specified here. BOS5 defines the SHAPE; downstream phases (BOS11/12 label writers, BOS15 eval/gates, BOS16 reward computation, BOS6/BOS17 guardrail consumers) wire the runtime.

---

## 1. Outcome label catalog (D-04, D-06)

The categorical label family is a closed 7-variant enum discriminated on `label_type`; the continuous measure family is open (cycle_time now, additive later). Each variant composes the shared `OutcomeEnvelope` (`contracts/outcomes.schema.json#/$defs/OutcomeEnvelope`) requiring `v`, `outcome_id`, `entity_id`, `entity_type` (`task | pr | session | external_reserved`), `trace_id`, `event_time` (valid time), `ingest_time` (transaction time, >= event_time), `obs_window_id`, and `source_rule`. `supersedes_outcome_id` is OPTIONAL on every label (D-02 supersession pointer). The envelope carries NO decision reference and NO `recommended_action` field (BOS4 D-04 no-leakage guard carried); the join runs decision -> outcome by `entity_id` + as-of, never the reverse.

### Categorical labels (D-04 closed enum, 7 variants)

| `label_type` | Meaning | Primary BOS3 source event(s) | Severity? (D-06) | Notes |
|---|---|---|---|---|
| `clean_merge` | A merged PR/commit that has not generated rework, revert, escaped defect, or incident within the observation window. The default positive outcome. | `pr.merged` (BOS3 reserved CI/review slot; internal analogue: `swarm.worker_done` + no failure). | No | Provisional; starts at merge, may be superseded (D-02). |
| `rework` | Work on the same entity required because earlier work was insufficient (follow-up PR on same files within the observation window). `[CITED: DORA Change Failure Rate; DevEx quality dimension]` | A second `pr.merged` or `task.completed` touching the same files within window, linked by correlation/entity. | Yes — optional `low\|medium\|high` | Distinguished from `escaped_defect` in that it is caught before deployment or surfaced by the team. |
| `revert` | A commit/PR that explicitly reverts a previous merge. `[CITED: DORA Change Failure Rate]` | `git.revert` event or PR with "revert" in title linked to the original entity (BOS12 source for external repos; internal analogue is session-killed/abort). | No | Strong negative signal; presence alone is significant. |
| `failed_validation` | CI/validation run triggered by the entity's changes that did not pass; caught before merge. `[CITED: DORA]` | `ci.failed` / `validation.failed` (BOS3 reserved external slots); internal: `swarm.gate(gate_type=reviewer_reject)` + `RunRecord.failures[]`. | No | May occur multiple times on the same entity (CI flap vs real failure); each failure is a separate append-only label event (D-05). |
| `escaped_defect` | A defect not caught by validation/CI that reached production or was found by users/monitors after merge. `[CITED: DORA Change Failure Rate — external component]` | Incident linked back to entity via `trace_id`/correlation; bug report linked to a PR; post-deploy alerting event (BOS12 external sources). | Yes — optional `low\|medium\|high` | Most delayed label — drives the long-horizon reward recomputation (D-09). |
| `incident` | A production incident attributed to the entity's changes (broader than `escaped_defect` — may include deploy failures, performance degradation). `[CITED: DORA MTTR; SRE incident taxonomy]` | `incident.opened` linked to deploy or PR (BOS12 external); or internal `RunRecord` with `failures[]` matching incident criteria. | Yes — optional `low\|medium\|high` | Highest negative signal; a `high` severity incident dominates scalar reward regardless of weights. |
| `human_override` | A human explicitly overrode a system recommendation for this entity (BOS4 D-05/D-06 `human_verdict = "override"`). Unique to AI-assisted workflow context; captures divergence between recommended and actual action (override-as-signal). | BOS4 decision record where `human_verdict = "override"` for a decision targeting this entity. | No | Not a quality failure per se; a governance signal. |

### Continuous measure (D-04 second family)

| `measure_type` | Definition (pinned, Pitfall 1) | Unit | BOS3 source | `measure_definition_id` |
|---|---|---|---|---|
| `cycle_time` | Time from `task.created_at` to `pr.merged_at` (the widest measure, consistent with DORA Lead Time for Changes decomposition). This is the definition pinned in the spec; alternative definitions (first-commit-to-merge, PR-open-to-merge) are NOT used. | `seconds` (float) | `task.created_at` -> `pr.merged_at` (or `swarm.task.ts` -> `swarm.worker_done.ts` for internal-only flows) | A string pinning this named definition; the schema requires `measure_definition_id` on every `CycleTimeMeasure` so the measurement is reproducible (Pitfall 1). |

The cycle time family is open: additional `measure_type` variants (e.g. review-lag, pick-up time) are additive and do NOT bump `schema_version`.

---

## 2. Derivation rules (D-01)

Outcome labels are produced by **deterministic derivation rules** (D-01): declarative, reproducible, auditable mappings from BOS3 events to labels. No human-in-the-loop labeling. Each outcome event carries its `source_rule` (the rule id that produced it), so the labeling pass is replayable.

| Rule id (`source_rule`) | Trigger BOS3 event(s) | Conditions | Output `label_type` | Entity anchor | Activates |
|---|---|---|---|---|---|
| `rule:pr_merge_clean` | `pr.merged` | No `rework` / `revert` / `escaped_defect` / `incident` within the observation window | `clean_merge` | PR entity | When BOS12 fills the `pr.merged` reserved external slot; internal analogue via `swarm.worker_done` activates now. |
| `rule:pr_revert` | `pr.merged` with title matching revert pattern, OR `git.revert` event | Linked to prior merge on same entity | `revert` | Original PR entity (the thing being reverted) | When BOS12 fills external `git.revert`; internal session-killed/abort analogue activates now. |
| `rule:ci_failure` | `ci.failed` or `validation.failed` | Linked to PR/task entity | `failed_validation` | PR or task entity | When BOS12 fills reserved external CI slots; internal `swarm.gate(reviewer_reject)` + `RunRecord.failures[]` activate now. |
| `rule:rework_followup` | Second `pr.merged` touching same files, same entity correlation | Within 14-day observation window | `rework` | Original PR/task entity | When BOS12 fills `pr.merged`; internal follow-up task analogue activates now. |
| `rule:incident_attribution` | `incident.opened` | Linked to deploy or PR via `trace_id` | `incident` on linked entity; `escaped_defect` if defect-type | PR/task entity | When BOS12 fills `incident.opened` external slot; internal `RunRecord` failures matching incident criteria activate now. |
| `rule:human_override` | BOS4 `DecisionRecord` with `human_verdict = "override"` | Any decision targeting the entity | `human_override` | Entity targeted by the decision | Activates immediately — internal BOS4 ledger is the only source. |

Internal-only rules (`rule:human_override`, the internal `swarm.gate` / `RunRecord.failures` analogues) activate now. Rules that depend on external sources (`pr.merged`, `ci.failed`, `incident.opened`, `git.revert`) are specced now but activate when BOS12 ingestion fills BOS3's reserved external slots. The derivation rule form is fixed by BOS5; the runtime engine executing them is a future concern (BOS11/12 era).

---

## 3. Observation windows (D-02)

Each label type declares an observation window (D-02): how long BOS waits before treating a label as mature (unlikely to be superseded). Windows are **named and referenced by `obs_window_id`**, not hard-coded as schema constants (Pitfall 4) — so a team can tune a window via a config change without a schema version bump. The schema validates the `obs_window_id` is present; the rationale spec provides the default window table.

| `label_type` | Recommended default observation window | Rationale | Supersession risk after window |
|---|---|---|---|
| `clean_merge` | 30 days | Most rework and escaped defects surface within a month. | Low (very late incidents still possible — see D-09 long horizon). |
| `rework` | 14 days | Rework is usually identified within the same sprint. | Very low. |
| `revert` | 0 days (immediate) | A revert is a concrete observed event. | None. |
| `failed_validation` | 0 days (immediate) | CI/gate failure is a concrete observed event. | None. |
| `escaped_defect` | 90 days | Defects may surface slowly in production. | Medium (rare very-late defects). |
| `incident` | 90 days | Incident attribution may require post-mortem linkage. | Medium. |
| `human_override` | 0 days (immediate) | Override is a concrete observed event. | None. |
| `cycle_time` (measure) | Point-in-time at merge/done | Not a window — measured at the moment of completion. | None. |

**Observation window vs finality tradeoff:** a shorter window gives faster reward signal but more supersessions (more label churn); a longer window gives more reliable labels but delays reward feedback. Defaults are tunable team config; this tradeoff affects BOS15's choice of evaluation horizon.

**Supersession model (D-02/D-05):** labels are append-only events that can be superseded by a later label as outcomes mature (clean_merge -> escaped_defect -> incident). The schema does NOT mutate the earlier record; instead a new label event is appended carrying the same `entity_id` and a `supersedes_outcome_id` pointer to the earlier label's `outcome_id`. Consumers reconstruct the maturation chain by ordering all label events for an entity by `ingest_time` and selecting those with `ingest_time <= T`.

**As-of no-leakage join (BOS4 D-04 carried):** when reconstructing the state a decision was made against at time `T_decision`, only outcome events with `ingest_time <= T_decision` are visible. Labels that arrived after the decision (even if their `event_time` predates the decision) are invisible to the decision-time feature reconstruction. The bitemporal envelope (`event_time` + `ingest_time`) is what makes this query possible; BOS5 inherits it from BOS3 D-02 and carries both timestamps on every categorical label and measure record.

---

## 4. Reward model (D-07, D-08, D-09)

### Named objective set (D-07 — recommended starting set)

Reward is a **vector** of named objectives (D-07), not a single opaque scalar. A **named, explicit scalarization function** combines the vector into a scalar when one is needed, keeping tradeoffs legible (governance: explainable). Recommended starting objective set (D-07 discretion):

| Objective | What it aggregates | Direction (higher is better?) | Primary labels / measures aggregated |
|---|---|---|---|
| `throughput` | Rate of clean merges / completed tasks per time window. | Yes | `clean_merge` count; `cycle_time` (inverse — shorter cycle = higher throughput). |
| `quality` | Absence of defects and failures. | Yes (higher = fewer defects) | 1 − weighted(`escaped_defect`, `incident`, `failed_validation`); `revert` rate. |
| `rework_cost` | Proportion of rework relative to total output. | No (lower is better — invert in scalarization) | `rework` label frequency; rework `cycle_time` proportion. |
| `flow` | Smoothness of delivery — low `cycle_time` variance, few `human_override` events indicating friction. | Yes | `cycle_time` stddev (inverse); `human_override` frequency (inverse). |

This four-objective set is a minimal coverage of DORA's four metrics translated into reward objectives. Each maps to observable outcome labels or measures. Objectives are tunable — D-08's versioned weight-set mechanism handles evolution without a schema change.

### Named scalarization (D-07)

The `WeightSetRecord.scalarization` field names the scalarization function as a string (not a lambda). `linear_weighted` is the initial interpretable baseline:

`R = Σ(wᵢ × oᵢ)` where `wᵢ` is the weight for objective `i` and `oᵢ` is the normalized objective value.

Why `linear_weighted` over alternatives at this stage:
- Interpretable: any team member can verify "we weighted quality 40%, throughput 30%, rework_cost 20%, flow 10%".
- Reproducible: (objective_vector + weight_set_version) fully determines the scalar — satisfies D-08.
- Explainable: governance constraint satisfied without statistical opacity.
- Matches the trust model: team-level, no black-box optimization.

Reserved valid future values in the enum (additive, no version bump; migration note added when first wired): `chebyshev` (min-max — when no objective should be sacrificed below a floor), `epsilon_constrained` (one objective primary, others as constraints — requires threshold calibration data that does not exist yet).

### WeightSetRecord shape (D-08)

Scalarization weights are explicit **team-level** config (no individual ranking per PROJECT.md §Trust), **versioned** alongside policy versions, and may differ per `decision_type` (task_to_agent weights ≠ review_depth weights). Every reward is reproducible from (objective_vector + weight_set_version). Credit weighting across the many decisions a single outcome touches (D-03) is expressed here — outcomes stay observation-faithful; credit assignment is a reward-model concern.

Shape (BOS5 locks the shape, NOT the values; concrete weight values are team config, set per team and refined in BOS13/14/15):

| Field | Purpose |
|---|---|
| `weight_set_id` | Stable id for this weight set. |
| `weight_set_version` | Version string referenced by `RewardRecord.weight_set_version`. Reproducibility keys off this. |
| `decision_type` | The BOS4 `decision_type` this weight set applies to (per-type weights, D-08). |
| `objectives` | `objective-name -> numeric weight`. Recommended keys: `throughput`, `quality`, `rework_cost`, `flow`. |
| `scalarization` | Named scalarization function (enum: `linear_weighted` now; `chebyshev`, `epsilon_constrained` reserved). |
| `effective_from` | When this weight set version became effective. |

### Reward horizons and recomputation (D-09)

Reward is computed against an outcome **horizon** and is itself **revisable** (D-09). The spec declares the standard named horizons:

| Horizon name | Default duration | Purpose |
|---|---|---|
| `short` | 7 days | Provisional reward computed soon after merge; captures fast feedback (CI failures, immediate reverts). Early policy signal. |
| `long` | 90 days | Full reward including escaped defects and incidents. Used for policy evaluation (BOS15) and final reward attribution. |

**Recomputation semantics (append-only):** when a new outcome label arrives for an entity after the short-horizon reward has already been computed, a NEW `RewardRecord` is appended — same `decision_id`, higher `ingest_time`, updated `horizon` (= `long`), recalculated `objective_vector`. The original short-horizon reward record is NEVER mutated. This is the same append-only semantics as BOS3 outcome events: reward is itself a kind of later-arriving information.

**Point-in-time-correct reward:** to reconstruct the reward available at policy-evaluation time `T`, select `RewardRecord` entries with `ingest_time <= T`. BOS15 offline eval can pick either the short or long horizon by setting `T` appropriately.

**Reproducibility rule:** `scalarized_reward` (when present) is fully determined by `(objective_vector, weight_set_version)`. Given the same objective vector and the same weight-set version, any consumer recomputes the same scalar. This is the D-08 reproducibility guarantee.

---

## 5. Tension-pair / bad-proxy table (D-10, D-11)

**The core anti-Goodhart pattern (D-10).** Goodhart's Law: when a measure becomes a target, it ceases to be a good measure. Canonical software-engineering failure modes: optimizing merge frequency -> superficial small commits ("commit stuffing"); optimizing cycle time -> abandoning code review / cutting testing corners; optimizing throughput -> reducing review depth, increasing escaped defects; optimizing quality gate pass rates -> disabling tests / marking failures as flaky.

BOS5's structural defense is D-10: **every reward objective must have >=1 named counter-metric in tension with it.** Gaming is detectable by construction, not by chance. Each counter-metric is a `GuardrailMetricSpec` (config/spec record, NOT a runtime event) carrying `linked_reward_objective`, `role` (D-11), and `threshold_shape`.

**Coverage rule (ACC-05, normative):** every key named in `WeightSetRecord.objectives` MUST appear as `linked_reward_objective` on >=1 `GuardrailMetricSpec`. This is machine-checkable from the contract alone.

| Reward objective (optimized axis) | Counter-metric (`counter_metric_formula`) | Gaming pattern detected | Role (D-11) | Threshold shape (`type`, `window_days`, `max_value`) |
|---|---|---|---|---|
| `throughput` ↑ | `rework_rate` = `rework_count / merge_count` (rolling window) | Merging low-quality work quickly -> rework surge. | `hard_gate` | `{type: "rate", window_days: 30, max_value: null}` (team-configured). |
| `throughput` ↑ | `escaped_defect_rate` = `escaped_defect_count / merge_count` (rolling window) | Merging without adequate review -> defect escape. | `hard_gate` | `{type: "rate", window_days: 90, max_value: null}`. |
| `quality` ↑ | `validation_bypass_rate` = `tasks_with_no_ci_run / total_tasks` | Avoiding validation to maintain clean-merge rate. | `hard_gate` | `{type: "rate", window_days: 30, max_value: null}` (zero-tolerance intent; value team-configured). |
| `rework_cost` ↓ | `human_override_rate` = `override_count / recommendation_count` | System learns to avoid hard tasks (reduces rework by delegating less). | `dashboard` | `{type: "rate", window_days: 30, max_value: null}`. Monitor trend; alert if > team threshold. |
| `flow` ↑ | `revert_rate` = `revert_count / merge_count` (rolling window) | Reducing human-override friction by deploying risky work -> reverts. | `hard_gate` | `{type: "rate", window_days: 30, max_value: null}`. |

**D-11 classification:**
- `hard_gate` — a breach blocks autonomy increase / policy promotion (BOS15 wires the gate; BOS5 defines the metric + threshold shape + role only).
- `dashboard` — surfaced to BOS6 BOS-GOV-04 governance dashboard; triggers human review, does not auto-block.

Thresholds are tunable team config: the schema fixes the threshold SHAPE (`{type, window_days, max_value}` where `max_value` may be `null` = team-configured); the VALUES are set per team and refined in BOS15. BOS5 does not bake threshold values into the contract.

---

## 6. Scope and downstream consumers (D-12)

BOS5 owns reward/outcome guardrails ONLY (D-12). Specifically out of scope and referenced as downstream consumers (not built here):

| Downstream phase | Consumes |
|---|---|
| **BOS6 (BOS-GOV-04)** | Guardrail dashboards — consumes `dashboard`-role `GuardrailMetricSpec` records; defines fairness, autonomy-creep, fatigue/nudge guardrails separately. |
| **BOS13 / BOS14** | Heuristic delegation / review / validation policies — produce decisions whose rewards are computed via the D-07/D-08 reward model; set actual reward weight values per team. |
| **BOS15 (BOS-RL-02)** | Offline eval / policy-promotion gates — wires D-11 `hard_gate` guardrails (breach blocks promotion), picks reward horizons (D-09), runs tension-pair coverage checks; tunes threshold values. |
| **BOS17 (BOS-BEH-02)** | Behavioral guardrails (fatigue, fairness) — separate from reward guardrails; consumes these metrics but defines its own. |

BOS5 defines metric + threshold shape + role; it does NOT build enforcement mechanics, weight values, or horizon selection. Clean phase boundary, no scope creep.

---

## 7. Versioning & migration notes

**Schema versioning (mirrors the `v` + migration-note convention adopted by BOS3/BOS4).**

`schema_version = 1` (`v: const 1` on every variant).

- **Additive changes (do NOT bump the version):**
  - New `label_type` filling a reserved slot.
  - New `measure_type` in the measure family.
  - New reward objective via a new `WeightSetRecord` version (not a schema change).
  - New horizon name added to the enum (additive schema extension; no version bump).
  - New `scalarization` name (e.g. first wiring of `chebyshev` or `epsilon_constrained`).
- **Breaking changes (bump the version + add a migration note here):**
  - Altering an existing enum value (e.g. renaming `clean_merge`).
  - Removing a required field.
  - Renaming a discriminator (`label_type`, `measure_type`).
  - Altering the `OutcomeEnvelope` required set.

### Deprecated approaches to avoid

- **Individual-ranking reward.** Scoring individual engineers against each other by outcome rate. Out of scope per PROJECT.md §Trust and produces gaming behavior. BOS5 reward is team-level by design — outcome records anchor to BOS3 opaque `entity_id` (task / PR / session), NOT to engineer name/email; reward records are team-level aggregations. The schema introduces no `engineer_id` field.
- **Time-discounted reward.** Using an exponential decay factor to downweight late outcomes. Rejected in D-09 because it masks severe late incidents (a `high`-severity incident at day 89 should not be discounted to near-zero). Use explicit observation windows and horizon recomputation instead.
- **Reward written back to the BOS4 decision record.** Banned by BOS4 D-04. Reward records are a SEPARATE family (`RewardRecord`) that references `decision_id` after the fact; the decision record is never mutated.
- **Single dominant label per entity.** Rejected by D-05. Multi-label append-only accumulation with supersession chain preserves the full maturation signal (clean -> defect -> incident); collapsing to a single label discards early signal.

### Migration history

(none — `schema_version = 1` is the initial version.)
