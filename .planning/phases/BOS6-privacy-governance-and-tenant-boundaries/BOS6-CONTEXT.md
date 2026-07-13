# Phase BOS6: Privacy, Governance, and Tenant Boundaries - Context

**Gathered:** 2026-06-18 · **Scope added:** 2026-06-20 (machine-checkable governance contract)
**Status:** Ready for planning (plans 2-4 — governance schema + contract suite — pending)

<domain>
## Phase Boundary

BOS6 produces TWO artifacts: (1) the **governance spec** prose (`BOS6-GOVERNANCE-SPEC.md`, SHIPPED by BOS6-01) — the rationale/policy contract; and (2) a **machine-checkable governance contract** `contracts/governance.schema.json` + pytest contract suite (ADDED 2026-06-20, plans 2-4) that encodes the enforceable-shaped parts of the policy as a 5th `contracts/` sibling. Together they cover BOS-GOV-01..04: trust model, privacy defaults + data-sensitivity classes, autonomy bands + kill-switch model, anti-surveillance reporting rule, guardrail-dashboard set.

It defines the POLICY/TRUST contract every later BOS surface must honor. It does **not** implement enforcement code (the schema is a *contract*, validated in CI, not runtime enforcement), define the event schema (BOS3), the decision ledger runtime (BOS4 — schema done), outcome labels/reward metrics (BOS5), or the offline-eval gates (BOS15). Governance policy + boundaries + the contract that encodes them.

**Scope note (2026-06-20):** BOS6-01 shipped prose-only (no schema, no tests, no VALIDATION.md) — diverging from the BOS5 contract pattern. Second discuss pass adds the machine-checkable contract (plans 2-4) so downstream phases enforce the policy structurally, not by reading prose. See D-15..D-18.

**Note on order:** BOS3 (events) and BOS5 (outcomes/rewards) are not locked. References to event data classes and guardrail *metrics* are recorded as **assumptions / cross-phase boundaries** — BOS6 owns the governance dashboard + policy; BOS5 owns the underlying reward/guardrail metric definitions; BOS15 owns the eval gates. See `<deferred>`.
</domain>

<decisions>
## Implementation Decisions

### Autonomy Bands & Kill-Switch (BOS-GOV-02)
- **D-01:** **Four autonomy bands:** `suggest_only` → `approve_required` → `auto_with_post_review` → `full_auto`. Each recommendation surface is assigned a current band.
- **D-02:** **Kill-switch at BOTH scopes:** a global kill-switch (halts all recommendation/auto action) AND a per-surface kill-switch. Either drops the affected surface(s) to a safe state (effectively `suggest_only`/off).
- **D-03:** **Autonomy increase is gated** (matches PROJECT.md §Safety): moving a surface to a higher band requires (a) an offline-eval pass (BOS15), (b) a guardrail check, and (c) explicit human approval. Decreases/kill are always immediate and unilateral. The spec states this gate; BOS15 owns the eval mechanics.

### Privacy Classes & Tenant Boundary (BOS-GOV-03)
- **D-04:** **Three data-sensitivity tiers:** `team_shareable` / `team_private` / `never_leaves_local`.
- **D-05:** **Private-by-default for sensitive content:** code, prompts, and agent-session transcripts default to the most-restrictive tier — they stay local (SQLite, BOS2 D-04) and **never cross to shared Postgres unless explicitly promoted**. Only derived metadata + decision/outcome records cross the local→shared boundary (consistent with BOS2 D-05 one-directional projection).
- **D-06:** **Calendar/identity data = minimal**; cross-source identity resolution is deferred to BOS12 (BOS-INT-03). Incident/deploy metadata = team-shareable (operational, not individual-attributing).
- **D-07:** **Tenant = the team.** No multi-tenant SaaS / cross-team sharing in v0.2 (Out-of-Scope); the spec defines the team as the isolation unit and the boundary rule, nothing cross-team.

### Anti-Surveillance Reporting Rule (BOS-GOV-01)
- **D-08:** **Minimum-aggregation floor:** a team metric is NEVER reported for fewer than **N** contributors (k-anonymity-style floor). Value of N is an open question (see `<deferred>`) — the rule is structural regardless of N.
- **D-09:** **No per-individual cross-comparison or ranking, ever.** Individual data MAY be stored and an individual MAY see their OWN data (self-view), but it is never surfaced to others as a ranking/leaderboard/comparison. "Stored ≠ cross-reported." This reconciles with the BOS4 decision-ledger storing `actor` on verdicts: the actor field is for audit/training, never for individual ranking output.

### Guardrail Dashboards & Scope Boundary (BOS-GOV-04)
- **D-10:** **Define all six guardrails + a trip/alert condition for each now:** fatigue, fairness, escaped defects, incidents, autonomy creep, reward hacking. For each, the spec states what it measures and the alert/trip condition.
- **D-11:** **Scope boundary:** BOS6 owns the governance/trust **dashboard** definition + trip conditions; it **references** the underlying reward/guardrail **metric** definitions from BOS5 (does not redefine them); **eval gates** stay in BOS15. The spec must cite these boundaries explicitly.

### Resolved Open Questions (2026-06-20)
- **D-12:** **Minimum-aggregation floor N = 3** (hard floor). Smallest N that blocks pair/individual re-identification while staying usable for small teams. A deployment may raise N but never lower it below 3. Resolves the D-08 open value.
- **D-13:** **Tiered retention + deletion.** Raw sensitive content (code/prompts/transcripts, `never_leaves_local`) gets a bounded, deployment-configurable TTL plus right-to-delete. Decision/outcome records (audit/training corpus) are retained longer and are **de-identifiable, not individually deletable** (strip actor attribution, preserve signal). Honors both privacy and training-signal integrity; preserves "stored ≠ cross-reported." Exact TTL window stays a deployment-config value (see `<deferred>`).
- **D-14:** **Kill-switch / autonomy-band RBAC deferred to BOS7.** BOS6 states the requirement that these control actions are access-controlled and audit-logged; the actor/role model (who may flip a kill-switch or change a band) is owned by the BOS7 web control-plane. BOS6 does not define roles.

### Machine-Checkable Governance Contract (BOS-GOV-01..04) — added 2026-06-20
- **D-15:** **New sibling contract + state record.** Add `contracts/governance.schema.json` (5th
  `contracts/` sibling) encoding the policy VOCABULARIES as `$defs` — `AutonomyBand` enum (4 values),
  `PrivacyTier` enum (3 values), `DataClass`→tier mapping, the `GuardrailDashboard` set, and
  `min_aggregation_n` — PLUS a `SurfaceGovernanceConfig` record `$def` (`surface_id`, `autonomy_band`,
  `kill_switch_state`) for validating actual policy-state instances. Mirrors BOS5's vocab+record
  pattern. The shipped prose `BOS6-GOVERNANCE-SPEC.md` stays the rationale; the schema is the
  enforceable contract. Joins the existing CI drift gate. (Rejected: vocab-enums-only — no
  validatable governance-state record; full policy-config registry incl. kill-switch registry +
  band-transition log — pulls BOS7 control-plane state forward.)
- **D-16:** **Governance owns the canonical AutonomyBand enum; BOS4 conforms.** ⚠ CROSS-PHASE.
  `contracts/decision-ledger.schema.json` already has an `autonomy_band` field + `AutonomyBandPayload`
  but does NOT enumerate the 4 values (free-string today). `governance.schema.json` becomes the single
  source of truth for the `AutonomyBand` enum (`suggest_only` / `approve_required` /
  `auto_with_post_review` / `full_auto`); a **BOS4 follow-up** constrains the ledger's `autonomy_band`
  to it — via cross-file `$ref` OR mirror-enum + a consistency test (planner picks the mechanism that
  keeps the CI drift gate simple). **Implication:** a BOS4 follow-up plan. Same cross-phase shape as
  BOS5's D-15 propensity follow-up. (Rejected: duplicate enum + leave BOS4 free-string — silent drift;
  prose map only — no enforcement.)
- **D-17:** **Hybrid guardrail link — FK to BOS5 where BOS5 owns it, native otherwise.** The 6 BOS6
  dashboard guardrails split per the D-11/D-12 ownership boundary: the **BOS5-owned** ones
  (`escaped_defects`, `incidents`, `reward_hacking`) carry a `linked_guardrail_id` FK →
  `outcomes.schema.json` `GuardrailMetricSpec.guardrail_id` (which already tags `role: hard_gate|dashboard`
  and names BOS6 GOV-04 as the dashboard consumer); the **BOS6-native** ones (`fatigue`, `fairness`,
  `autonomy_creep`) are self-contained dashboard entries tagged `source: bos6`. A test asserts FK
  validity for the three linked. Structural single-source-of-truth, no redefining BOS5 metrics.
  (Rejected: independent BOS6 guardrail enum for all 6 — duplicates BOS5's three; prose-reference
  only — no machine-checkable link.)
- **D-18:** **Full BOS5-parity contract suite + Nyquist.** A pytest contract suite asserts: schema
  Draft-2020-12 lint; `AutonomyBand` 4-value coverage; `PrivacyTier` 3-value coverage;
  `GuardrailDashboard` 6-entry coverage; `min_aggregation_n` present and ≥ 3 (D-12); `SurfaceGovernanceConfig`
  example round-trip; **cross-phase band-enum consistency** with BOS4 (D-16); **guardrail FK validity**
  with BOS5 (D-17). Schema joins the CI drift gate; author `BOS6-VALIDATION.md` with the ACC list
  (BOS6 currently has none). (Rejected: lint+enum-coverage only — leaves the BOS4/BOS5 couplings, the
  whole point, unguarded; no tests — defeats the machine-checkable goal.)

### Carried Forward (locked elsewhere — NOT re-discussed)
- Hard bans (PROJECT.md Out-of-Scope + Constraints): no individual rankings, no raw activity scoring, no keystroke/productivity telemetry, no nudge-engagement optimization, no autonomy increase without offline eval. BOS6 restates and operationalizes these; it does not relitigate them.
- Store = SQLite local-first / Postgres shared, one-directional projection (BOS2 D-04/D-05).
- Governance is foundational, explainable, human-override, auditable (PROJECT.md Constraints §Trust).

### Claude's Discretion
- Governance-spec doc structure/format.
- Exact band-transition table wording (within D-01/D-03).
- Exact data-class → handling matrix layout (within D-04/D-05).
- Guardrail trip-condition phrasing (within D-10), where the metric is owned by BOS5 (reference, don't redefine).
- (D-15..D-18) Exact `$def`/field names within `governance.schema.json` (AutonomyBand, PrivacyTier,
  DataClass mapping, GuardrailDashboard, SurfaceGovernanceConfig, min_aggregation_n, linked_guardrail_id,
  source, kill_switch_state); the cross-file-`$ref`-vs-mirror+consistency-test mechanism for the D-16
  BOS4 band-enum reconciliation; schema versioning notation (mirror the `v` + migration-note convention
  the other `contracts/` siblings use).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & trust constraints
- `.planning/REQUIREMENTS.md` — **BOS-GOV-01..04** (lines ~77-80, the target requirements).
- `.planning/PROJECT.md` — Constraints §Trust (team-level, explainable, human override, auditable), §Safety (no autonomy increase without offline eval/guardrail/approval), and Out-of-Scope (no individual ranking, no surveillance, no nudge-engagement optimization, no multi-tenant SaaS in v0.2).
- `.planning/ROADMAP.md` — BOS6 row + the BOS3-BOS6 "data and trust substrate" build-order note (~line 121, ~146).

### Cross-phase boundaries (referenced, not owned by BOS6)
- BOS5 Outcome Labels & Reward Model — owns the reward/guardrail **metric** definitions BOS6's dashboards reference (D-11). **Concrete FK target (D-17):** `contracts/outcomes.schema.json` `GuardrailMetricSpec.guardrail_id` (its description already names BOS6 GOV-04 as the dashboard consumer + tags `role: hard_gate|dashboard`). BOS6's `escaped_defects`/`incidents`/`reward_hacking` dashboards link to it.
- BOS15 Offline Evaluation & Policy Versioning (Pending) — owns the **eval gates** that gate autonomy increases (D-03).
- `.planning/phases/BOS4-decision-ledger-schema/BOS4-CONTEXT.md` + `contracts/decision-ledger.schema.json` — the ledger stores `actor` on verdicts (D-09: never cross-reported) AND an `autonomy_band` field that is **currently free-string**. **D-16 cross-phase target:** a BOS4 follow-up constrains `autonomy_band` to the canonical `AutonomyBand` enum that `governance.schema.json` defines.
- `.planning/phases/BOS2-monorepo-and-stack-architecture/BOS2-CONTEXT.md` — D-04/D-05 store + local→shared boundary the privacy tiers ride on.

### Existing contract substrate (the form governance.schema.json takes — D-15)
- `contracts/outcomes.schema.json`, `contracts/events.schema.json`, `contracts/decision-ledger.schema.json` — the Draft-2020-12 `$defs` + discriminated-union sibling pattern `governance.schema.json` mirrors. It becomes the 5th `contracts/` file; joins the same CI drift gate (D-18).
- `BOS6-GOVERNANCE-SPEC.md` (shipped, BOS6-01) — the prose rationale the schema makes machine-checkable; D-15/D-18 must keep the two consistent (band/tier/guardrail/N values identical in both).

### Existing substrate
- Voss already has PermissionGate / operator-gate + audit surfaces in the harness/server/swarm runtime (PROJECT.md Context). BOS6's autonomy bands + kill-switch are the policy layer above those existing gates; the planner/researcher should locate the actual PermissionGate implementation when this becomes enforcement (later phase), but BOS6 is policy-only.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **PermissionGate / operator gates + audit surfaces** (existing harness/server/V25 swarm runtime): the autonomy-band + kill-switch policy (D-01..D-03) is the governance layer that future enforcement maps onto. Docs-only here — no wiring.

### Established Patterns
- **Docs-first BOS track**: governance spec before any enforcement code. BOS6 is inherited by every recommendation surface (BOS9), policy (BOS13/14), and the eval phase (BOS15).
- **Local-first + one-directional projection** (BOS2): the privacy tiers (D-04/D-05) ride directly on the SQLite→Postgres boundary already decided.

### Integration Points
- None executed (docs-only). The spec frames the trust contract that BOS9 (review surface), BOS13/14 (policies), and BOS15 (eval) must honor.
</code_context>

<specifics>
## Specific Ideas

- The anti-surveillance rule (D-08/D-09) must be stated as a STRUCTURAL guarantee: "stored ≠ cross-reported," min-aggregation floor, self-view permitted, no ranking — explicitly reconciled with the BOS4 `actor` field so the two specs don't appear to conflict.
- Autonomy increases are gated; decreases/kill are immediate and unilateral (D-02/D-03) — asymmetry is intentional and must be explicit.
- Code/prompts/sessions are private-by-default and stay local unless explicitly promoted (D-05) — the strongest privacy default, stated up front.
</specifics>

<deferred>
## Deferred Ideas

- **Raw-content retention TTL window** — the tiered-retention model is decided (D-13); the exact TTL for raw sensitive content is a deployment-configuration value, not fixed by the spec.
- ~~Value of N (D-08)~~ — RESOLVED 2026-06-20: N = 3 hard floor (D-12).
- ~~Data retention / deletion policy~~ — RESOLVED 2026-06-20: tiered retention (D-13).
- ~~RBAC: who may flip kill-switch / change autonomy bands~~ — RESOLVED 2026-06-20: deferred to BOS7 as an explicit boundary (D-14).
- **Reward/guardrail metric definitions** — BOS5 (BOS6 references them, D-11).
- **Offline-eval gate mechanics** — BOS15 (BOS6 states the gate exists, D-03).
- **Event data classes detail** — BOS3 (BOS6 classifies sensitivity; BOS3 defines the event entities).
- **Cross-source identity resolution** — BOS12.

### Reviewed Todos (not folded)
None — no phase-matched todos surfaced for BOS6.
</deferred>

---

*Phase: BOS6-privacy-governance-and-tenant-boundaries*
*Context gathered: 2026-06-18 · machine-checkable governance contract added: 2026-06-20*
