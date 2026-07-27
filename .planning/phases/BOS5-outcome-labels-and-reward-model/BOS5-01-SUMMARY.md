---
phase: BOS5-outcome-labels-and-reward-model
plan: 01
status: done
artifacts:
  - contracts/outcomes.schema.json
  - docs/BOS5-OUTCOME-REWARD-SPEC.md
requirements: [BOS-DATA-03, BOS-DATA-04]
---

# BOS5-01 Summary

## What shipped

Two normative contract artifacts for the BOS5 outcome/reward model:

1. **`contracts/outcomes.schema.json`** — machine-readable JSON Schema (Draft 2020-12), sibling to `contracts/events.schema.json`. `v: 1`.
2. **`docs/BOS5-OUTCOME-REWARD-SPEC.md`** — human-readable rationale spec mirroring the schema.

## contracts/outcomes.schema.json

Mirrors `events.schema.json`'s discriminated-union pattern ($defs + discriminator.mapping + oneOf). `$schema: https://json-schema.org/draft/2020-12/schema`. Lints clean against the Draft 2020-12 meta-schema (ACC-01).

**Shared envelope** `OutcomeEnvelope` (composed by every label and measure via `allOf`):
- Required: `v` (const 1), `outcome_id`, `entity_id`, `entity_type` (enum: `task | pr | session | external_reserved`), `trace_id`, `event_time` (date-time, valid time), `ingest_time` (date-time, transaction time, >= event_time), `obs_window_id`, `source_rule`.
- Optional: `supersedes_outcome_id` (D-02/D-05 supersession pointer).
- **No-leakage guard (BOS4 D-04 carried):** the envelope defines NO `decision_id` and NO `recommended_action` field. Every composed label/measure variant sets `unevaluatedProperties: false`, so stray keys (including either leakage field) are rejected after `allOf` evaluation.
- Bitemporal: `event_time` + `ingest_time` on every record (BOS3 D-02 inherited).

**7 categorical labels** (D-04 closed enum, `label_type` discriminator):
`CleanMergeLabel`, `ReworkLabel`, `RevertLabel`, `FailedValidationLabel`, `EscapedDefectLabel`, `IncidentLabel`, `HumanOverrideLabel`. Each carries `label_type` as `const` + `v` const 1; `oneOf` length 7; `discriminator.mapping` over all 7.
- **Optional `severity` (enum `low|medium|high`, D-06)** ONLY on `ReworkLabel`, `EscapedDefectLabel`, `IncidentLabel`. The other 4 carry no `severity` field (verified by jq: only those 3 `$defs` have a `severity` property).

**Continuous measure family** (`measure_type` discriminator, open for additive variants):
- `CycleTimeMeasure` — `measure_type` const `cycle_time`, required `value` (number, seconds), `unit` const `seconds`, `measure_definition_id` (Pitfall 1 — pins the `task.created_at -> pr.merged_at` definition so the measurement is reproducible).

**RewardRecord** (D-07/D-08/D-09, computed/derived — NOT an outcome event, Pitfall 3):
- Required: `v` (const 1), `reward_id`, `decision_id`, `objective_vector` (object: name -> number, `additionalProperties: number`), `weight_set_version`, `horizon` (enum `short|long`), `computed_at`, `ingest_time`. Optional: `scalarized_reward` (number).
- **MAY carry `decision_id`** (reward is computed FOR a decision after the fact) — this is the ONLY record family in this schema with `decision_id`. `additionalProperties: false`.
- Append-only recomputation (D-09): later horizon = NEW RewardRecord, same `decision_id`, higher `ingest_time`; the original is never mutated.

**WeightSetRecord** (D-08, versioned team-level config, per `decision_type`):
- Required: `weight_set_id`, `weight_set_version`, `decision_type`, `objectives` (object: name -> number weight), `scalarization` (enum MUST include `linear_weighted`; reserves `chebyshev`, `epsilon_constrained` as valid future values — additive, no version bump), `effective_from`. `additionalProperties: false`.
- BOS5 locks the SHAPE only; concrete weight values are team config set per team and refined in BOS13/14/15.
- Recommended objective keys (D-07 discretion): `throughput`, `quality`, `rework_cost`, `flow`.

**GuardrailMetricSpec** (D-10/D-11, anti-Goodhart tension-pair counter-metric, config/spec record — NOT a runtime event):
- Required: `guardrail_id`, `counter_metric_formula`, `linked_reward_objective` (string), `role` (enum EXACTLY `hard_gate | dashboard` — verified by jq: only those two values), `threshold_shape` (object: `type`, `window_days`, and `max_value` required; `max_value` may be number or null = team-configured). `additionalProperties: false`.
- Coverage rule (ACC-05, normative): every key in `WeightSetRecord.objectives` MUST appear as `linked_reward_objective` on >=1 `GuardrailMetricSpec`. This is machine-checkable from the contract alone.
- Threshold VALUES are tunable team config (shape fixed by contract, values set in BOS15) — no day-count constants baked into the schema (Pitfall 4 avoided).

**Two outcome-event unions:**
- `CategoricalOutcomeEvent`: `oneOf` over 7 label `$ref`s with `discriminator` on `label_type` + `mapping`.
- `OutcomeMeasureEvent`: `oneOf` over measure `$ref`s with `discriminator` on `measure_type` + `mapping`.
- The root `oneOf` accepts one direct contract record: categorical outcome, continuous measure, reward, weight set, or guardrail spec.

**Migration note** (mirrors the `v` convention adopted by BOS3/BOS4): `$comment` states `schema_version=1`; additive changes (new `label_type`, new `measure_type`, new objective via new weight-set version, new horizon, new scalarization) do NOT bump; breaking changes increment + add a migration note in the rationale doc.

## docs/BOS5-OUTCOME-REWARD-SPEC.md

Normative human spec mirroring the schema's field set + enums. References `contracts/outcomes.schema.json` as the machine source of truth. Sections (each citing the driving D-ID):

1. **Outcome label catalog (D-04/D-06)** — table of the 7 categorical labels (label_type, meaning, primary BOS3 source, severity yes/no) + the `cycle_time` measure row (definition pinned to `task.created_at -> pr.merged_at` per Pitfall 1, unit seconds, `measure_definition_id`).
2. **Derivation rules (D-01)** — one row per rule: rule id (the `source_rule` value), trigger BOS3 event(s), conditions, output `label_type`, entity anchor, activates-now vs activates-when-BOS12-fills-reserved-slots. Uses the word "derivation".
3. **Observation windows (D-02)** — named window ids + default day-counts (clean_merge 30d, rework 14d, revert 0d, failed_validation 0d, escaped_defect 90d, incident 90d, human_override 0d), stated as tunable team config referenced by `obs_window_id` (NOT schema constants). Uses the phrase "observation window". Documents the supersession model (clean_merge -> escaped_defect via `supersedes_outcome_id`) and the as-of no-leakage join (labels visible only where `ingest_time <= T_decision`).
4. **Reward model (D-07/D-08/D-09)** — named objective table (throughput|quality|rework_cost|flow: what each aggregates, direction), named scalarization (`linear_weighted` initial; `chebyshev`/`epsilon_constrained` reserved), `WeightSetRecord` shape (versioned, team-level, per decision_type), reproducibility rule ((objective_vector + weight_set_version) => scalar), short/long horizons (7d/90d) with append-only recomputation semantics. Uses the word "objective".
5. **Tension-pair / bad-proxy table (D-10/D-11)** — REQUIRED. One row per (reward objective -> counter-metric -> gaming pattern -> role `hard_gate|dashboard` -> threshold shape). Covers every objective named in §4 (each appears as the optimized axis with >=1 counter-metric). Thresholds noted as tunable team config (shape fixed by contract, values set in BOS15). Uses the word "tension".
6. **Scope + downstream consumers (D-12)** — BOS5 owns reward/outcome guardrails ONLY; fairness/autonomy-creep/fatigue are BOS6 (BOS-GOV-04) / BOS17 (BOS-BEH-02); enforcement gates + horizon selection are BOS15; reward weight VALUES + tuning are BOS13/14/15. Listed as references, not built here.
7. **Versioning & migration notes** — `schema_version=1`; additive vs breaking rules matching BOS3/BOS4; deprecated approaches called out (individual-ranking reward; time-discounted reward; reward written back to decision record; single dominant label per entity). Uses the word "migration".

## Verification (all green)

### Task 1 (schema)
- `jsonschema.Draft202012Validator.check_schema` passes (ACC-01).
- Root schema rejects `{}` and unknown wrapper objects; all 9 BOS5 examples validate as direct records.
- All 7 `label_type` consts present (ACC-02): clean_merge, rework, revert, failed_validation, escaped_defect, incident, human_override.
- `cycle_time` `measure_type` variant present (ACC-02).
- `CategoricalOutcomeEvent` `oneOf` length == 7; `OutcomeMeasureEvent` `oneOf` length == 1.
- `severity` property exists ONLY on `ReworkLabel`, `EscapedDefectLabel`, `IncidentLabel` (D-06).
- `OutcomeEnvelope` has NO `decision_id` field; direct label/measure validation rejects added `decision_id` and `recommended_action` keys.
- `RewardRecord` requires `decision_id`; `RewardRecord`, `WeightSetRecord`, `GuardrailMetricSpec` `$defs` all present.
- `WeightSetRecord.scalarization` enum includes `linear_weighted` + reserved `chebyshev`, `epsilon_constrained`.
- `GuardrailMetricSpec.role` enum EXACTLY `hard_gate`, `dashboard` (no other values).
- `GuardrailMetricSpec` requires `linked_reward_objective` (ACC-05 hook).
- `git diff --quiet contracts/events.schema.json contracts/openapi.json contracts/decision-ledger.schema.json` — clean (no existing contract touched).
- `git diff --quiet voss/` — clean (no harness source touched).

Re-execution recovery found that the earlier root wrapper accepted `{}` and arbitrary records while direct label `$defs` rejected valid composed records. The root is now the actual five-family record union, and label/measure variants use Draft 2020-12 `unevaluatedProperties: false` so envelope fields compose correctly without weakening unknown-field rejection.

### Task 2 (rationale spec)
- File exists and references `contracts/outcomes.schema.json` (ACC-07).
- All 7 categorical `label_type` values + `cycle_time` appear.
- Required section keywords present in body prose: `derivation`, `observation window`, `objective`, `tension`, `migration`.
- `linear_weighted` named; `hard_gate` and `dashboard` guardrail roles present; `supersedes_outcome_id` supersession model documented.
- Four distinct tables present: derivation-rules, observation-window, reward-objective, tension-pair; plus migration-notes section.
- `cycle_time` definition pinned (`task.created_at -> pr.merged_at`, Pitfall 1); severity documented as optional on rework/escaped_defect/incident only.
- Tension-pair table covers every reward objective named in §4 with >=1 counter-metric, each tagged `hard_gate` or `dashboard`.
- Scope section names BOS6/BOS17/BOS15/BOS13-14 as downstream consumers (D-12) without building them; deprecated individual-ranking + time-discounted reward called out.

## Threat model (per plan)

- **T-BOS5-01 (information disclosure / outcome leakage):** mitigated structurally — `OutcomeEnvelope` defines NO `decision_id`/`recommended_action`; `RewardRecord` is the only family with `decision_id`, computed after the fact. Verified by Task 1 acceptance plus negative validation of both forbidden fields on every label/measure example.
- **T-BOS5-02 (tampering / Goodhart):** mitigated by D-10 tension-pair coverage — every reward objective has >=1 `GuardrailMetricSpec.linked_reward_objective`; coverage is machine-checkable (ACC-05).
- **T-BOS5-03 (PII / individual-ranking):** mitigated — records anchor to BOS3 opaque `entity_id` (task/pr/session), NOT engineer name/email; reward is team-level; schema introduces no `engineer_id` field; rationale doc forbids individual-ranking + time-discounted reward.
- **T-BOS5-04 (tampering / existing source):** mitigated — `git diff --quiet` clean for `contracts/events.schema.json`, `contracts/openapi.json`, `contracts/decision-ledger.schema.json`, `voss/`; BOS5 authors only the NEW sibling schema + doc.
- **T-BOS5-SC (package installs):** accept — no installs; `jsonschema` 4.26.0 already in `.venv`.

## Downstream impact

- **BOS11/12 era** label-writer services validate against this contract; the derivation rules in §2 activate as BOS12 fills BOS3's reserved external event slots.
- **BOS5-02** supplies the 9 example records + 13-check pytest suite (ACC-01..ACC-07) used to validate these artifacts at runtime.
- **BOS6 (BOS-GOV-04)** consumes `dashboard`-role guardrails for governance dashboards.
- **BOS13/BOS14** heuristic policies produce decisions whose rewards are computed via D-07/D-08; set actual reward weight values per team.
- **BOS15 (BOS-RL-02)** wires `hard_gate` guardrails (breach blocks promotion), picks reward horizons, runs tension-pair coverage checks, tunes threshold values.
- **BOS16** reward computation emits `RewardRecord`s.
- **BOS17 (BOS-BEH-02)** behavioral guardrails (fatigue, fairness) consume these metrics but define their own.
