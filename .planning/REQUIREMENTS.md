# Requirements: Voss

**Defined:** 2026-05-10
**Core Value:** An engineering team can route AI-assisted work through bounded, reviewable execution and convert the outcomes into a trustworthy decision dataset for better delegation, review, validation, and flow.
**Source:** `.vscode/voss_v_0_1_scope_lock.md` (v0.1), BOS milestone discussion (2026-06-18), BOS track restart (2026-06-20), `.planning/seeds/SEED-001-coordination-bus.md`, V25 server-native swarm runtime context.

## v0.2 BOS Implementation Requirements

These requirements are active across BOS1-BOS18. The track uses only BOS phase
and plan names; no split-prefix requirement namespace remains active.

### Product Boundary

- [x] **BOS-PROD-01**: Voss defines the Behavioral OS as a team control plane over AI-assisted engineering work, not as a generic project management clone. ✓ BOS1 product brief
- [x] **BOS-PROD-02**: Voss defines the initial wedge around delegation/review/validation decisions that can be observed through the existing ADE and swarm runtime. ✓ BOS1 product brief
- [x] **BOS-PROD-03**: Voss documents the ICP, buyer/user split, and first design-partner validation questions for engineering teams using multiple coding agents. ✓ BOS1 product brief + discovery script
- [ ] **BOS-PROD-04**: Voss defines what belongs in desktop ADE, web control plane, backend services, and local harness runtime.

### Planning System

- [x] **BOS-PLAN-01**: Planning docs introduce `BOS` phase prefixes for Behavioral OS work. ✓ BOS1-01 (verified)
- [x] **BOS-PLAN-02**: Stale planning documents are audited and indexed before archival, deletion, or supersession. ✓ BOS1-01
- [x] **BOS-PLAN-03**: The BOS roadmap is split into enough phases to avoid combining product thesis, stack architecture, data modeling, governance, RL, and PM-suite expansion into one phase. ✓ BOS1-01 (verified-adequate)
- [x] **BOS-PLAN-04**: Existing Voss tracks are mapped into BOS as substrate, dependency, historical context, or explicitly out-of-scope. ✓ BOS1-01

### Data And Learning

- [x] **BOS-DATA-01**: Voss specifies a point-in-time-correct engineering event schema covering tasks, sessions, swarm events, files, reviews, CI, validation, deploys, and incidents. ✓ BOS3-01
- [x] **BOS-DATA-06**: Voss projects existing `SessionRecord`, `RunRecord`, and swarm JSONL events into BOS event-schema dictionaries without mutating source records. ✓ BOS3 runtime projection
- [x] **BOS-DATA-07**: Voss persists projected BOS events in a local append-only ledger with duplicate-safe replay, filters, and torn-line tolerance. ✓ BOS3 local ledger
- [x] **BOS-DATA-02**: Voss specifies a decision ledger for task-to-agent, autonomy band, review depth, validation depth, escalation, and no-action decisions. ✓ BOS4-01..05
- [ ] **BOS-DATA-03**: Voss specifies outcome labels for clean merge, rework, revert, failed validation, escaped defect, incident, cycle time, and human override.
- [ ] **BOS-DATA-04**: Voss specifies reward and guardrail metrics before any learning system is introduced.
- [ ] **BOS-DATA-05**: Voss specifies offline-evaluation requirements for heuristic policies, contextual bandits, and later RL policies.

### Swarm And ADE Integration

- [ ] **BOS-SWARM-01**: Voss maps V25 server-native swarm events into BOS event and decision records.
- [ ] **BOS-SWARM-02**: Voss treats `.voss/swarm/` files as audit/shared host records, not as BOS runtime transport.
- [ ] **BOS-SWARM-03**: Voss reframes `SEED-001` as future external-agent CLI verbs over the existing server/SSE plane.
- [ ] **BOS-SWARM-04**: Voss defines how desktop ADE sessions become local worker nodes for a future shared team control plane.

### Work Model And Recommendations

- [ ] **BOS-WORK-01**: Voss specifies the team, project, task, PR, service, incident, agent-run, and engineer entities needed by the Behavioral OS.
- [ ] **BOS-WORK-02**: Voss specifies work intake and lifecycle states for engineering tasks without requiring a full PM suite.
- [ ] **BOS-WORK-03**: Voss specifies how work items connect to sessions, swarm tasks, files, reviews, validations, and outcomes.
- [ ] **BOS-REC-01**: Voss specifies a recommendation review surface with approve, override, dismiss, and do-nothing actions.
- [ ] **BOS-REC-02**: Voss specifies rationale, confidence, policy version, and training-signal logging for each recommendation.
- [ ] **BOS-REC-03**: Voss specifies output contracts for delegation, review-depth, validation-depth, and escalation recommendations.

### External Integrations

- [ ] **BOS-INT-01**: Voss specifies ingestion boundaries for GitHub/GitLab, Jira/Linear, CI, deploy, observability, and incident systems.
- [ ] **BOS-INT-02**: Voss specifies identity and entity resolution across tasks, PRs, commits, sessions, agent runs, deploys, incidents, services, and teams.
- [ ] **BOS-INT-03**: Voss specifies historical backfill and ongoing ingestion requirements without pulling secrets, credentials, or sensitive production records into planning artifacts.

### Policy And Evaluation

- [ ] **BOS-POL-01**: Voss specifies a heuristic delegation policy baseline before any learned delegation policy.
- [ ] **BOS-POL-02**: Voss specifies review-depth and validation-depth policy baselines before any learned reduction in human review or test coverage.
- [ ] **BOS-POL-03**: Voss specifies policy versioning, replay, holdouts, and shadow-mode requirements.
- [ ] **BOS-RL-01**: Voss specifies the Python learning/eval lab boundary and how it consumes exported event/decision/outcome data.
- [ ] **BOS-RL-02**: Voss specifies offline replay, counterfactual evaluation, and guardrail gates before contextual bandits or RL.
- [ ] **BOS-RL-03**: Voss specifies that online learning and autonomy increases are future work gated by enough logged decisions and safety review.

### Behavioral Science

- [ ] **BOS-BEH-01**: Voss specifies behavioral interventions as optional recommendations, not coercive automation.
- [ ] **BOS-BEH-02**: Voss specifies fatigue, mute, sentiment, fairness, and focus-time guardrails for nudges and alerts.
- [ ] **BOS-BEH-03**: Voss specifies team working-agreement primitives that can later support behavioral recommendations.

### Stack Architecture

- [x] **BOS-ARCH-01**: Voss documents the target monorepo shape for desktop app, web app, backend/event services, shared contracts, SDKs, and RL/eval services. ✓ BOS2-01
- [x] **BOS-ARCH-02**: Voss decides which languages own each layer: TypeScript for web/shared contracts, Python for learning/eval, existing Python harness/server for local runtime, Rust/Tauri for desktop shell, and Go/Rust SDKs where already established. ✓ BOS2-01
- [x] **BOS-ARCH-03**: Voss defines package/workspace evolution for the current pnpm workspace and any future Turborepo-style orchestration. ✓ BOS2-01
- [x] **BOS-ARCH-04**: Voss documents data-store options and migration boundaries for local-first event logs, team-shared data, and analytics/offline-eval workloads. ✓ BOS2-01

### Governance

- [ ] **BOS-GOV-01**: Voss documents trust defaults: team-level reporting, no individual rankings, no raw activity scoring, and no nudge-engagement optimization.
- [ ] **BOS-GOV-02**: Voss documents human approval, override logging, autonomy bands, and kill-switch expectations for every recommendation surface.
- [ ] **BOS-GOV-03**: Voss documents privacy boundaries for code, prompts, agent sessions, calendar/identity data, and incident/deploy metadata.
- [ ] **BOS-GOV-04**: Voss defines guardrail dashboards for fatigue, fairness, escaped defects, incidents, autonomy creep, and reward hacking.

### Future PM Suite Path

- [ ] **BOS-PM-01**: Voss defines the future path from recommendation/control plane into engineering-specific project management without committing to a Jira replacement in v0.2.
- [ ] **BOS-PM-02**: Voss defines which PM primitives are first-class engineering objects: tasks, PRs, services, teams, incidents, agent runs, decisions, and outcomes.
- [ ] **BOS-PM-03**: Voss documents which Atlassian-like capabilities are deferred until the decision/outcome dataset exists.

## v0.1 Requirements

### Scope Lock

- [ ] **SCOPE-01**: Planning docs state that Voss v0.1 ships as an AI-native coding harness with `.voss` as the workflow control layer.
- [ ] **SCOPE-02**: Roadmap uses M-prefixed phases (`M0` through `M5`) that match the v0.1 scope-lock document.
- [ ] **SCOPE-03**: Planning docs clearly preserve compiler verbs separately from harness verbs.
- [ ] **SCOPE-04**: Planning docs explicitly defer Rust, MCP bridge, tree-sitter, VSCode marketplace, Linguist upstream, and full telemetry until after the Python harness proves real usage.

### CLI Harness

- [ ] **CLIH-01**: `voss` launches an interactive harness REPL.
- [ ] **CLIH-02**: `voss chat` launches the same REPL explicitly.
- [ ] **CLIH-03**: `voss do "<task>"` runs a one-shot natural-language agent task.
- [ ] **CLIH-04**: `voss edit <path>` starts a scoped edit session for a requested path.
- [ ] **CLIH-05**: `voss resume [id]` resumes a saved harness session.
- [ ] **CLIH-06**: `voss sessions` lists saved sessions.
- [ ] **CLIH-07**: `voss tools` lists registered harness tools.
- [ ] **CLIH-08**: `voss doctor` diagnoses setup.
- [ ] **CLIH-09**: `voss config` opens or reports harness configuration.
- [ ] **CLIH-10**: `voss run <file.voss>` remains reserved for `.voss` programs and does not collide with natural-language task execution.

### Project Cognition

- [ ] **COG-01**: Voss creates and maintains `.voss/project.json`.
- [ ] **COG-02**: Voss creates or updates `.voss/architecture.md` from repo analysis.
- [ ] **COG-03**: Voss stores constraints, permissions, and validation config under `.voss/constraints.yml`, `.voss/permissions.yml`, and `.voss/validation.yml`.
- [ ] **COG-04**: Voss stores plans under `.voss/plans/`.
- [ ] **COG-05**: Voss stores sessions under `.voss/sessions/`.
- [ ] **COG-06**: Voss stores decisions under `.voss/decisions/`.
- [ ] **COG-07**: Voss uses `.voss-cache/` only for rebuildable state such as repo indexes, generated harness artifacts, and temporary files.
- [ ] **COG-08**: Every agent run records task goal, plan, inspected files, changed files, avoided files, assumptions, decisions, risks, validation commands, failures, final diff summary, and follow-up recommendations.

### Controlled Execution

- [ ] **CTRL-01**: Harness exposes `fs_read`, `fs_glob`, `fs_grep`, `fs_write`, and `fs_edit`.
- [ ] **CTRL-02**: Harness exposes `shell_run` with shell allowlist and timeout controls.
- [ ] **CTRL-03**: Harness exposes `git_status` and `git_diff`.
- [ ] **CTRL-04**: Harness exposes `voss_check`.
- [ ] **CTRL-05**: Execution modes `plan`, `edit`, and `auto` are available and permissioned.
- [ ] **CTRL-06**: Tool execution is jailed to `--cwd`.
- [ ] **CTRL-07**: Risky operations require permission prompts with deny, allow once, and allow always choices.
- [ ] **CTRL-08**: Voss shows a diff preview before applying edits.
- [ ] **CTRL-09**: Session payloads never include provider API keys or equivalent secrets.

### Language Control Layer

- [ ] **LANG-01**: `.voss` is positioned and implemented as an AI workflow control language, not a general Python replacement.
- [ ] **LANG-02**: Parser/analyzer/codegen preserve `probable<T>` and confidence gates.
- [ ] **LANG-03**: Parser/analyzer/codegen preserve `ctx(budget: N tokens)`.
- [ ] **LANG-04**: Parser/analyzer/codegen preserve `within budget(...) { } fallback { }`.
- [ ] **LANG-05**: Parser/analyzer/codegen preserve `match similar(...)`.
- [ ] **LANG-06**: Parser/analyzer/codegen preserve `agent`, `spawn`, and `gather`.
- [ ] **LANG-07**: Parser/analyzer/codegen preserve `memory.episodic`, `memory.semantic`, and `memory.working`.
- [ ] **LANG-08**: Parser/analyzer/codegen preserve `@tool`, `prompt`, `try/catch`, and `use`.
- [ ] **LANG-09**: `voss check samples/classify.voss`, `samples/support.voss`, and `samples/research.voss` pass.
- [ ] **LANG-10**: At least one representative sample runs through `voss run` and demonstrates that `.voss` makes AI workflow code materially shorter and readable.

### Dogfood

- [ ] **DOG-01**: `voss/harness/agent/loop.voss` exists.
- [ ] **DOG-02**: `voss/harness/agent/router.voss` exists.
- [ ] **DOG-03**: `voss/harness/agent/planner.voss` exists.
- [ ] **DOG-04**: `voss/harness/agent/executor.voss` exists.
- [ ] **DOG-05**: `voss/harness/agent/reviewer.voss` exists.
- [ ] **DOG-06**: `voss check voss/harness/agent/` is a CI gate.
- [ ] **DOG-07**: Bare `voss` can boot through compiled harness logic once the dogfood loop is enabled.
- [ ] **DOG-08**: Compiled harness artifacts cache under `.voss-cache/harness/`.

### Eval and Distribution Prep

- [ ] **EVAL-01**: Golden repo tasks exist for the canonical v0.1 demo workflow.
- [ ] **EVAL-02**: Evaluation tracks success rate.
- [ ] **EVAL-03**: Evaluation tracks mean cost.
- [ ] **EVAL-04**: Evaluation tracks confidence correlation against successful and failed runs.
- [ ] **EVAL-05**: Package install polish is verified after the Python harness loop works.

### npm Distribution

- [ ] **NPM-01**: An npm package named `voss` (or `@voss/cli`) is publishable and installable via `npm i -g voss` / `npx voss`.
- [ ] **NPM-02**: The npm package vendors a pinned Python interpreter + the v0.1 voss wheel per supported platform (darwin-arm64, darwin-x64, linux-x64, linux-arm64, win32-x64) via postinstall or per-platform optionalDependencies.
- [ ] **NPM-03**: The `voss` bin shim forwards all CLI arguments to the vendored `python -m voss.cli`, preserving exit codes, stdin/stdout/stderr, and signal forwarding.
- [ ] **NPM-04**: A packaging smoke test verifies that, in a fresh Node project, `npm install voss` then `npx voss --help`, `npx voss doctor`, `npx voss check <sample.voss>`, and `npx voss compile <sample.voss>` all exit 0.
- [ ] **NPM-05**: README primary install path is `npm i -g voss`; `pip install voss` is listed as the secondary path. v0.1 framing remains "Python harness; Rust shell later" — npm wrapper is distribution, not reimplementation.

### SDK Polish

Promoted from v0.2 candidate to formal M7 phase on 2026-05-13. Closes the
four public-API-shaped holes identified during the 2026-05-12 SDK contract
pass (`docs/sdk.md`) plus a stable provider registration entry point.
Embedders currently work around these by reaching into private paths
(`voss.harness.render`, `voss.harness.session`, `voss_runtime.providers`);
M7 promotes the missing names so private-path drift stops binding callers.

- [ ] **SDK-01**: Promote a `Renderer` protocol + `NullRenderer` implementation
  into `voss.harness.__all__`. Embedders that want silent or custom rendering
  currently import from the private `voss.harness.render` module.
- [ ] **SDK-02**: Add a `tool_entry_from_callable(fn, *, is_mutating, name=None,
  description=None)` factory to `voss.harness.__all__`. Wraps a plain Python
  callable as a `ToolEntry` without forcing embedders to author descriptors
  by hand.
- [ ] **SDK-03**: Promote a read-only session view type (`SessionView` / similar)
  that exposes session id, cwd, runs (timestamps, cost, confidence) without
  binding callers to the on-disk `SessionRecord` / `RunRecord` schema. The
  internal schema stays free to change; the embedder view stays stable.
- [ ] **SDK-04**: Add `RuntimeConfig.from_toml(path)` plus a `RuntimeConfig.default()`
  that resolves `~/.config/voss/config.toml` and env overrides, so embedders
  share the harness config file rather than reconstructing it field by field.
- [ ] **SDK-05**: Document and stabilize the provider registration entry point
  (`voss_runtime.providers.register`) so third-party providers can be added
  without reaching into the private `voss_runtime.providers` submodule.

## Future Requirements

### Deferred Distribution

- **DIST-01**: Rust harness shell for startup performance and single-binary distribution.
- **DIST-02**: Homebrew distribution after Python harness usage is proven.
- **DIST-03**: MCP bridge after the harness product loop is proven.

### Deferred Editor and Ecosystem

- **EDIT-01**: Tree-sitter grammar.
- **EDIT-02**: VSCode marketplace release.
- **LING-01**: GitHub Linguist upstream PR.

### Deferred Product Surface

- **TEAM-01**: Cloud sync. v0.2 may define architecture, but not implementation.
- **TEAM-02**: Team collaboration. v0.2 may define control-plane requirements, but not implementation.
- **TEAM-03**: Account system. v0.2 may define tenant boundaries, but not implementation.
- **WEB-01**: Web UI. v0.2 may define the web control plane, but not implementation.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full Python language parity | v0.1 is a harness plus AI workflow control layer, not a Python replacement |
| Native LLVM/Wasm compilation | Python target is sufficient for current AI workflow ecosystem |
| TypeScript target | Defer until Python-targeted control layer proves usage |
| Package manager | Use Python packaging and repo-local state first |
| Debugger or full LSP | Generated Python, diagnostics, and harness validation are enough for v0.1 |
| Distributed or multi-machine agents | Local bounded execution first |
| Fine-tuning or training loops | v0.1 is inference and workflow control only |
| Cloud sync, teams, accounts, marketplace | Out of scope for v0.1 implementation; v0.2 may define future architecture only |
| Web UI or split-pane TUI | Out of scope for v0.1 implementation; BOS reopens web as a shared control-plane design question |
| Windows support | Defer until core loop works |
| Broad OSS launch campaign | Behavior must be proven first |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BOS-PROD-01..04, BOS-PLAN-01..04 | BOS1 | Active |
| BOS-ARCH-01..04, BOS-PROD-04 | BOS2 | Active |
| BOS-DATA-01, BOS-DATA-06, BOS-DATA-07 | BOS3 | Active; runtime projection and local ledger implemented |
| BOS-DATA-02 | BOS4 | Complete; schema, writer/builders, swarm assignment, and human permission verdict producers shipped |
| BOS-DATA-03..05 | BOS5 | Active |
| BOS-GOV-01..04 | BOS6 | Active |
| BOS-PROD-04, BOS-SWARM-04, BOS-WORK-03 | BOS7 | Active |
| BOS-WORK-01..03 | BOS8 | Active |
| BOS-POL-01..03, BOS-REC-01..03, BOS-BEH-01..03 | BOS9 | Active |
| BOS-SWARM-01..04 | BOS10 | Active |
| BOS-INT-01, BOS-INT-03 | BOS11 | Active |
| BOS-INT-02 | BOS12 | Active |
| BOS-DATA-05, BOS-POL-03, BOS-RL-02 | BOS13 | Active |
| BOS-RL-01..03 | BOS14 | Active |
| BOS-POL-03, BOS-REC-02 | BOS15 | Active |
| BOS-PROD-04, BOS-SWARM-04 | BOS16 | Active |
| BOS-PM-01..03 | BOS17 | Active |
| BOS-PM-01..03 | BOS18 | Active |
| SCOPE-01..04 | M0 | Pending |
| CLIH-01..10 | M1 | Pending |
| CTRL-01..09 | M1 | Pending |
| COG-01..08 | M2 | Pending |
| LANG-01..10 | M3 | Pending |
| DOG-01..08 | M4 | Pending |
| EVAL-01..05 | M5 | Pending |
| NPM-01..05 | M6 | Pending |
| SDK-01..05 | M7 | Pending |

**Coverage:**
- v0.2 BOS implementation requirements: 48 total
- v0.1 requirements: 64 total (54 original + 5 NPM-* M6 + 5 SDK-* M7)
- BOS requirements mapped to BOS1-BOS18: 48
- BOS requirements unmapped: 0

---
*Requirements defined: 2026-05-10*
*Last updated: 2026-06-20 after BOS track restart*
