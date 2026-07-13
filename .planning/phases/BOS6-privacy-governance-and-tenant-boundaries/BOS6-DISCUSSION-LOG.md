# Phase BOS6: Privacy, Governance, and Tenant Boundaries - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** BOS6-privacy-governance-and-tenant-boundaries
**Areas discussed:** Autonomy bands & kill-switch, Privacy classes & tenant boundary, Anti-surveillance aggregation rule, Guardrail dashboards + scope boundary

---

## Autonomy Bands & Kill-Switch

| Option | Description | Selected |
|--------|-------------|----------|
| 4 bands + global & per-surface kill-switch, increase gated | suggest_only→approve_required→auto_with_post_review→full_auto; kill-switch both scopes; increase needs BOS15 eval + guardrail + approval | ✓ |
| 3 bands + global kill-switch only | suggest/approve/auto; single global kill-switch | |
| You decide | — | |

**User's choice:** 4 bands + global & per-surface kill-switch, increase gated (recommended)
**Notes:** Decrease/kill immediate + unilateral; increase gated (asymmetry intentional). Matches PROJECT.md §Safety.

---

## Privacy Classes & Tenant Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Tiered classes, private-by-default for code/prompts/sessions | team_shareable/team_private/never_leaves_local; code+prompts+sessions stay local unless promoted; only derived metadata + decision/outcome cross to Postgres; tenant = team | ✓ |
| Single team-scope, all team-visible | One boundary, everything team-visible | |
| You decide | — | |

**User's choice:** Tiered classes, private-by-default (recommended)
**Notes:** Rides BOS2 D-04/D-05 SQLite→Postgres boundary. Identity resolution → BOS12. No multi-tenant SaaS in v0.2.

---

## Anti-Surveillance Aggregation Rule

| Option | Description | Selected |
|--------|-------------|----------|
| Min-aggregation floor (k≥N) + no cross-individual reports; self-view allowed | Metric never reported for <N contributors; no ranking; self-view ok; stored≠cross-reported | ✓ |
| Aggregate-only, no individual data retained | Strictly aggregate; conflicts with BOS4 actor field + self-view | |
| You decide | — | |

**User's choice:** Min-aggregation floor + no cross-individual reports; self-view allowed (recommended)
**Notes:** Reconciled with BOS4 ledger actor field (stored for audit/training, never ranked). Value of N = open question.

---

## Guardrail Dashboards + Scope Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Define each guardrail + trip condition now; BOS6 owns dashboard, refs BOS5 metrics | 6 guardrails (fatigue, fairness, escaped defects, incidents, autonomy creep, reward hacking) each w/ measure + trip condition; BOS6=dashboard, BOS5=metrics, BOS15=gates | ✓ |
| Envelope + list now, thresholds deferred | Name 6 + dashboard exists; defer measurement/thresholds | |
| You decide | — | |

**User's choice:** Define each guardrail + trip condition now (recommended)
**Notes:** Explicit scope boundary BOS6/BOS5/BOS15 stated in spec.

---

## Follow-up Session — Resolving Open Questions (2026-06-20)

Re-opened BOS6 (already discussed + executed) to resolve the three spec Open Questions.

| Open question | Options | Selected |
|--------|-------------|----------|
| Min-aggregation N | 3 (hard floor) / 5 / configurable floor-3 / stay undecided | **3 (hard floor)** |
| Retention/deletion | tiered / single global window / defer | **Tiered retention** |
| Kill-switch + band RBAC | confirm defer to BOS7 / minimal v0.2 rule now / define full roles now | **Confirm defer to BOS7** |

**Notes:** N=3 = smallest floor blocking pair/individual re-identification, usable for small teams, raisable not lowerable (D-12). Tiered retention = raw sensitive content bounded TTL + right-to-delete; decision/outcome corpus retained + de-identifiable, not deletable (D-13); exact TTL window stays deployment-config. RBAC = BOS6 states access-controlled+audit-logged requirement; actor/role model owned by BOS7 (D-14). Folded into GOVERNANCE-SPEC.md (Trust Model, new Retention and Deletion section, Autonomy authorization boundary, Open Questions) and CONTEXT.md (D-12..D-14).

---

## Claude's Discretion

- Governance-spec doc structure/format.
- Band-transition table wording.
- Data-class → handling matrix layout.
- Guardrail trip-condition phrasing (metric owned by BOS5).

## Deferred Ideas

- Value of N for the aggregation floor — open question.
- Data retention/deletion policy — flagged, undecided.
- RBAC: who flips kill-switch / changes bands — flagged, likely BOS7/later.
- Reward/guardrail metric definitions → BOS5.
- Offline-eval gate mechanics → BOS15.
- Event data classes detail → BOS3.
- Cross-source identity resolution → BOS12.

---

# Second pass — machine-checkable governance contract (added 2026-06-20)

**Date:** 2026-06-20
**Areas discussed:** Contract shape, Band enum source-of-truth (cross-phase BOS4), Guardrail FK to BOS5, Test suite + Nyquist
**Context:** BOS6-01 shipped prose-only (`BOS6-GOVERNANCE-SPEC.md`) — no schema, no tests, no VALIDATION.md, diverging from BOS5's contract pattern. Grounding found: BOS4 `decision-ledger.schema.json` has a free-string `autonomy_band` (unenumerated); BOS5 `outcomes.schema.json` `GuardrailMetricSpec.guardrail_id` already names BOS6 GOV-04 as dashboard consumer.

## Contract shape

| Option | Description | Selected |
|--------|-------------|----------|
| Vocabulary enums + state record | $defs for AutonomyBand/PrivacyTier/DataClass/GuardrailDashboard/min_aggregation_n + SurfaceGovernanceConfig record | ✓ |
| Vocabulary enums only | Authority enums/sets, no validatable state record | |
| Full policy-config registry | + kill-switch registry + band-transition log (pulls BOS7 forward) | |

**User's choice:** Vocabulary enums + state record → D-15

## Autonomy-band enum source of truth (cross-phase: BOS4)

| Option | Description | Selected |
|--------|-------------|----------|
| Governance owns it; BOS4 conforms | governance.schema.json = canonical AutonomyBand enum; BOS4 follow-up constrains decision-ledger autonomy_band via $ref or mirror+consistency-test | ✓ |
| Duplicate enum, leave BOS4 free-string | Define in governance only; BOS4 unconstrained (drift risk) | |
| Prose mapping only | No schema constraint | |

**User's choice:** Governance owns it; BOS4 conforms → D-16 (implies BOS4 follow-up plan)

## Guardrail dashboard link to BOS5

| Option | Description | Selected |
|--------|-------------|----------|
| Hybrid FK + native | escaped_defects/incidents/reward_hacking FK → outcomes.schema.json guardrail_id; fatigue/fairness/autonomy_creep native source:bos6 | ✓ |
| Independent BOS6 enum | All 6 native (duplicates BOS5's three) | |
| Prose-reference only | No structural FK | |

**User's choice:** Hybrid FK + native → D-17

## Test suite + Nyquist

| Option | Description | Selected |
|--------|-------------|----------|
| Full BOS5-parity suite | lint + band/tier/guardrail coverage + N>=3 + SurfaceGovernanceConfig round-trip + cross-phase band consistency (BOS4) + guardrail FK validity (BOS5) + CI drift gate + BOS6-VALIDATION.md | ✓ |
| Lint + enum coverage only | Skip cross-phase consistency/FK tests | |
| No tests (prose-checkable) | Schema only | |

**User's choice:** Full BOS5-parity suite → D-18

## Cross-phase / boundary notes (second pass)

- D-16 implies a BOS4 follow-up plan to constrain `decision-ledger.schema.json` `autonomy_band` to the governance `AutonomyBand` enum.
- D-15/D-18 must keep `BOS6-GOVERNANCE-SPEC.md` (prose) and `governance.schema.json` (contract) value-consistent (bands/tiers/guardrails/N=3 identical in both).
- Raw-content retention TTL stays deployment-config (unchanged); not encoded as a fixed schema value.
