# BOS6 Governance Spec

This spec is the policy and trust contract for BOS recommendation surfaces, policies, and evaluation. Governance is foundational for Voss as a Behavioral OS: later phases inherit these boundaries before they design review surfaces, learned or heuristic policies, eval gates, or enforcement wiring.

BOS6 is docs-only. It defines trust, privacy, autonomy, tenant, and guardrail boundaries. It does not implement code, define schemas, specify BOS3 event entities, define BOS5 reward or guardrail metrics, or design BOS15 eval mechanics.

## Trust Model and Anti-Surveillance Reporting

BOS defaults to team-level reporting, explainable recommendations, human override, and auditability. It must not become an individual surveillance or productivity-scoring system.

Hard bans:

- No individual rankings, leaderboards, or cross-person comparisons.
- No raw activity scoring.
- No keystroke telemetry or productivity telemetry.
- No nudge-engagement optimization.

Structural reporting guarantees:

- **Minimum aggregation floor:** a team metric is never reported for fewer than `N` contributors, k-anonymity-style. `N` defaults to **3** — the smallest floor that blocks pair or individual re-identification and still works for small teams. A deployment may raise `N` but never lower it below 3.
- **No cross-individual ranking:** BOS never reports an individual as better, worse, faster, slower, more productive, or less productive than another individual.
- **Self-view permitted:** an individual may see their own data when the surface is scoped to that person.
- **Stored != cross-reported:** data may be stored for audit, training-signal capture, or replay, but storage does not authorize individual-level team reporting.

BOS4 stores a human verdict `actor_id` on `human_verdict` and records the `autonomy_band` in effect for a decision. BOS6 reconciles that ledger contract with the anti-surveillance rule: actor attribution is for audit, traceability, replay, and training-signal integrity only. It is never surfaced as an individual ranking, leaderboard, comparative productivity output, or raw activity score.

## Autonomy Bands and Kill-Switch

Every BOS recommendation surface has a current autonomy band:

| Band | Meaning |
|---|---|
| `suggest_only` | The system may suggest an action, but it does not request approval or act. |
| `approve_required` | The system may recommend an action, but a human must approve before action. |
| `auto_with_post_review` | The system may act within its approved scope, then requires post-action review. |
| `full_auto` | The system may act within its approved scope without routine per-action review. |

Kill-switches exist at both scopes:

- **Global kill-switch:** halts all recommendation or automatic action.
- **Per-surface kill-switch:** halts the affected recommendation surface.

Either kill-switch drops the affected surface to a safe state: effectively `suggest_only` or off.

Autonomy movement is intentionally asymmetric:

| Movement | Rule |
|---|---|
| Increase to a higher band | Requires an offline-eval pass owned by BOS15, a guardrail check, and explicit human approval. |
| Decrease to a lower band | Immediate and unilateral. |
| Kill-switch activation | Immediate and unilateral. |

Every recommendation surface must support human approval and override logging. Overrides are normal governance signals, not exceptions; they must remain auditable and available to downstream evaluation without authorizing individual ranking output.

**Authorization boundary:** flipping a kill-switch or changing a surface's autonomy band is an access-controlled, audit-logged control action. BOS6 requires that boundary; it does not define the actor/role model for who may perform these actions. That model is owned by the BOS7 web control-plane.

## Privacy Tiers and Tenant Boundary

BOS uses three data-sensitivity tiers:

| Tier | Handling |
|---|---|
| `team_shareable` | May appear in team-shared BOS state when it is operational and not individual-attributing. |
| `team_private` | Stays inside the team boundary and is not shared cross-team. |
| `never_leaves_local` | Remains local unless a later explicit promotion rule is approved. |

Private-by-default handling:

- Code, prompts, and agent-session transcripts default to the most restrictive tier, `never_leaves_local`.
- These sensitive contents stay local in SQLite per BOS2 D-04.
- They never cross to shared Postgres unless explicitly promoted.
- Only derived metadata plus decision and outcome records cross the local -> shared boundary.
- The local -> shared boundary is a one-directional projection per BOS2 D-05; shared state is downstream of local ADE operation, not a hard runtime dependency for local work.

Additional data handling:

- Calendar and identity data are minimal. Cross-source identity resolution is deferred to BOS12 and is not defined here.
- Incident and deploy metadata are `team_shareable` when they are operational and not individual-attributing.
- The tenant is the team. The team is the isolation unit.
- No cross-team reporting, cross-team sharing, or multi-tenant SaaS behavior is in scope for v0.2.

## Retention and Deletion

BOS uses tiered retention so privacy and training-signal integrity do not collide:

| Data class | Retention | Deletion |
|---|---|---|
| Raw sensitive content (code, prompts, agent-session transcripts; `never_leaves_local`) | Bounded TTL, deployment-configurable. | Right-to-delete: an individual or team may delete this local content. |
| Decision and outcome records (derived audit / training-signal corpus) | Retained beyond the raw-content TTL to preserve audit, replay, and training-signal integrity. | Not individually deletable; de-identifiable instead — actor attribution may be stripped while the decision/outcome signal is preserved. |

The exact raw-content TTL window is a deployment-configuration value, not fixed by this spec. De-identification preserves `stored != cross-reported`: a record kept for training never authorizes individual-level reporting.

## Guardrail Dashboards

BOS6 defines the governance dashboard set and trip conditions. BOS5 owns the underlying reward and guardrail metric definitions. BOS15 owns eval gates.

| Guardrail | What It Measures | Trip / Alert Condition |
|---|---|---|
| Fatigue | Whether recommendation volume, review requests, overrides, or nudges are creating operator load. | Alert when a surface shows sustained high review or override load, repeated dismissals, or muted/ignored recommendations that indicate fatigue risk. |
| Fairness | Whether recommendations, review depth, validation depth, or escalations are unevenly distributed across comparable teams, work types, or roles. | Alert when comparable cohorts receive materially different recommendation treatment without an explainable policy reason. |
| Escaped defects | Whether recommendations correlate with defects that escape normal review, validation, or CI. | Alert when accepted or automated recommendations are followed by escaped defects above the BOS5-defined threshold. |
| Incidents | Whether recommendations correlate with deploy, reliability, security, or operational incidents. | Alert immediately on incident linkage and require review before increasing autonomy for the affected surface. |
| Autonomy creep | Whether surfaces are moving toward higher autonomy without the required gates. | Alert on any autonomy increase missing a BOS15 offline-eval pass, guardrail check, or explicit human approval. |
| Reward hacking | Whether a policy appears to optimize the measured reward while degrading unmeasured quality, trust, safety, or team outcomes. | Alert when reward improvement coincides with worsening guardrail signals, high override/dismissal rates, or qualitative review concerns. |

BOS6 owns these dashboard definitions and trip conditions only. It references BOS5 for exact metric formulas and thresholds and BOS15 for the eval gates that block unsafe autonomy increases.

## Open Questions

1. **Raw-content retention TTL window:** the tiered-retention model is decided (see Retention and Deletion), but the exact TTL for raw sensitive content is a deployment-configuration value, not fixed by this spec.

**Previously open, now resolved:** minimum aggregation `N` defaults to 3 (Trust Model and Anti-Surveillance Reporting); data retention is tiered with right-to-delete on raw content and de-identification of the decision/outcome corpus (Retention and Deletion); kill-switch and autonomy-band changes are access-controlled and audit-logged here, with the actor/role model owned by BOS7 (Autonomy Bands and Kill-Switch).

## Cross-Phase Boundaries

- **BOS3:** owns the engineering event schema and event entities. BOS6 classifies sensitivity and reporting boundaries; it does not define BOS3 entities or events.
- **BOS5:** owns reward and guardrail metric definitions. BOS6 defines the guardrail dashboard set and trip conditions and references BOS5 metrics.
- **BOS12:** owns cross-source identity resolution. BOS6 requires minimal calendar and identity handling but does not define identity matching.
- **BOS15:** owns offline-eval gate mechanics. BOS6 states that autonomy increases require an offline-eval pass, but does not define the eval procedure.

BOS6 does not define the BOS3 event schema, BOS5 metric formulas, BOS12 identity model, or BOS15 eval gates.

## Downstream Consumers

This contract is inherited by BOS9 recommendation review surfaces, BOS13/BOS14 policy phases, and BOS15 evaluation. The existing PermissionGate and operator-gate substrate is the enforcement layer a future phase maps these autonomy bands, kill-switches, and privacy rules onto. BOS6 is policy-only.
