# Voss ADE Deep Research 06: Review, Verification, and Integration

**Research date:** 2026-07-19  
**Scope:** Diff review, testing, approval, merge/PR, and cleanup workflows in agentic development environments and tmux/worktree tools  
**Product constraint:** The terminal must be a complete daily driver for arbitrary shells and CLI agents. Voss review, budgets, and gates are optional capabilities, never an adoption requirement.  
**Evidence base:** 34 sources, primarily official documentation, project repositories, Git/GitHub documentation, and recent empirical research. Product claims were treated as claims unless corroborated by docs, source, or implementation history.

## Executive Summary

The winning workflow is not "agent finishes, click merge." It is a versioned evidence pipeline:

`worktree candidate -> scoped diff -> verification at a recorded SHA -> human and/or optional agent review -> repository policy -> integration -> post-integration verification -> cleanup`

Five conclusions are well supported:

1. **Git state, not agent state, is the authority.** "Done" in a CLI, a terminal becoming idle, or a Kanban card moving to Review is only an attention signal. A candidate becomes integrable only through a recorded diff, commit/head SHA, verification results, review disposition, and target branch state.
2. **Worktree isolation is necessary but not sufficient.** dmux, workmux, Paneflow, Zed, Windsurf/Devin Desktop, Cursor, Codemux, and JetBrains Air all converge on isolated branches or worktrees. Worktrees prevent concurrent filesystem collisions, but do not prevent semantic conflicts, merge conflicts, stale-base failures, broken setup, or post-merge regressions.
3. **Review must be useful without a proprietary agent.** Warp, Paneflow, workmux, and JetBrains Air show the value of an always-available diff surface. Paneflow is especially aligned with the Voss requirement: it can open plain shells or arbitrary supported CLI reviewers and only prefills a review prompt, leaving submission to the user.
4. **Verification evidence must be bound to a commit.** A green test run becomes stale when the branch changes. Local checks and hosted CI should be shown together but remain distinguishable. Required reviews, status checks, and merge queues should remain the repository's final authority where configured.
5. **Voss should be a review provider, not the merge owner.** Voss can add A/B reviewers, confidence, budget envelopes, human approval, audit records, and retry policies after explicit opt-in. It should consume the same neutral candidate/evidence objects as plain terminal workflows. It must not intercept ordinary agent configuration, silently start a sidecar, or make non-Voss work unreviewable.

The current Voss codebase has useful parts but a dangerous split. The native board implements independent A/B verification and human approval gates. The arbitrary-CLI swarm path, however, auto-stages, commits, merges each member into the main checkout, marks the task done, and removes the worktree before that review model governs integration. The ADE's `review` route mounts the orchestration cockpit rather than a general branch/worktree diff and verification surface. The immediate priority is to introduce a neutral candidate/evidence/integration state machine and stop auto-merging CLI swarm output.

## Research Questions

1. What review and integration behaviors have become table stakes in agentic development environments?
2. Which features work for arbitrary existing CLI agents, and which require a proprietary agent protocol?
3. How should local tests, remote CI, AI review, human approval, budgets, and repository rules compose without creating false assurance?
4. What should Voss implement first to become a terminal-first daily driver with an optional orchestration console?

## Market Findings

### Capability Matrix

| Product | Candidate isolation | Diff/review | Verification evidence | Integration | Human control | Relevance to Voss |
|---|---|---|---|---|---|---|
| Warp | Native worktrees; local agent changes reflected live | Real-time uncommitted/branch/base diffs; inline comments; hunk/file/all revert; comments batched back to Warp Agent | Terminal commands and normal CI, but review docs do not describe a durable SHA-bound evidence model | Normal Git workflow | Explicitly frames Interactive Code Review as developer-controlled | Best example of a polished diff-feedback loop, but feedback application is coupled to Warp Agent |
| BridgeSpace | Workspace/terminal oriented; docs do not document per-task Git isolation | Kanban has `In Review`; editor/file watcher; command blocks show exit status | Command exit codes only in public docs | Not documented | Task approval is implied by board states | Weak evidence for a production review/integration pipeline; mostly workflow presentation |
| dmux | One branch/worktree per task/pane | Read-only file browser with file diff mode | `run_test` and `pre_merge` hooks; callback mechanism | Two-phase main->worktree then worktree->main; PR creation; cleanup | Merge action is explicit; failing pre-merge hook aborts | Strong tmux-native lifecycle and conflict containment; review depth is lighter than Warp/Paneflow |
| workmux | One worktree and tmux window/session per task | WIP/committed diffs, hunk navigation/comments, patch/staging mode | Configurable `pre_merge` hook; PR and CI status in dashboard | Merge/rebase/squash, stacked targets, keep-after-merge, PR flow | User-configurable dashboard actions and confirmation safeguards | Strongest terminal-first evidence that review can be useful without owning the agent |
| Paneflow | Project and sibling worktree views | Multi-branch split/unified diffs; changed files; branch-base picker; plain terminal or selected CLI review terminals | Agents can read test panes; no claim of a generalized durable test ledger | Docs emphasize review before normal Git merge/ship | Review prompt is prefilled but never submitted automatically | Closest UX match for arbitrary-CLI-compatible review; deliberately honest about renderer limits |
| Codemux | Prompt creates isolated branch/worktree | Marketing surface shows changes; detailed review workflow is not documented | Claims test and browser verification; evidence model not documented | Claims clean merges through OpenFlow | Operator can observe and intervene | Useful direction, low-confidence implementation evidence for review and merge guarantees |
| Cursor | Remote isolated machines, separate branches, GitHub handoff | Bugbot reviews PR diffs and comments; web can review PRs | Background agents can run tests automatically | Pushes branches; web supports PR creation/review/merge | Foreground approval differs from autonomous background execution | Shows PR-native review and remote handoff, but requires cloud/GitHub permissions and has prompt-injection exposure |
| Windsurf / Devin Desktop | Per-conversation worktrees | Source-control panel plus Command Center status `ready for review` | Agent can build/test in isolated worktree | A `merge` action incorporates worktree changes | Command Center does not replace editor; user can make last-mile edits | Shows orchestration as optional overview, but public docs do not define strong verification or review evidence |
| Zed | Linked worktrees; native, ACP external, and raw terminal threads coexist | Git panel, branch diff review action, agent review thread | Terminal commands; granular tool permissions | Normal Git workflow | External/terminal agents own auth/config; normal merge workflow remains | Strong architectural precedent for progressive enhancement without replacing CLI agents |
| JetBrains Air | Local workspace, worktree, or Docker per task | Manual unified/side-by-side review, line comments, fresh-agent review | Agents run terminal/tests; result can be reviewed before apply | Apply as uncommitted changes, checkout task branch, or PR normally | User accepts review comments and chooses apply path | Most complete documented separation of implementation, independent review, human triage, and application |

### Patterns Worth Adopting

#### 1. A diff surface independent of agent ownership

Warp's Code Review panel follows filesystem and Git changes made by the user, external editors, or agents. It supports uncommitted changes, comparison against the default or arbitrary base branch, direct edits, hunk/file/all reverts, and attaching diffs to an agent. Its interactive review adds line-anchored, batch feedback to the agent. [Warp Code Review](https://docs.warp.dev/code/code-review), [Warp Interactive Code Review](https://docs.warp.dev/agent-platform/local-agents/interactive-code-review)

Paneflow compares each branch's merge-base against a selected base through the working tree, including committed changes, tracked uncommitted changes, and untracked files. It supports multi-project and sibling-worktree comparison, split/unified layouts, synchronized scrolling, and plain terminals alongside review agents. It documents size caps and tells users to use raw Git when the renderer truncates. [Paneflow Review](https://paneflow.dev/docs/review), [Paneflow product](https://paneflow.dev/)

workmux demonstrates that this can remain terminal-native: its dashboard distinguishes uncommitted from committed changes, supports hunk comments and interactive staging, shows diff statistics/conflicts/ahead-behind state, and can expose PR/CI status. [workmux changelog](https://workmux.raine.dev/changelog), [workmux repository](https://github.com/raine/workmux)

**Voss implication:** Build the review surface on `git diff`, worktree metadata, and recorded verification runs. Agent integration is an optional action on that surface, not its data source.

#### 2. Review feedback as a portable artifact

Warp batches inline comments into one agent turn. JetBrains Air lets a fresh review session leave line comments, then requires the user to accept which comments become follow-up instructions for the main task. Paneflow prefills a structured prompt and leaves it for the user to edit and submit. [JetBrains Air quickstart](https://www.jetbrains.com/help/air/quick-start-with-air.html)

These suggest a neutral model:

- Store comments as `{path, side, line, head_sha, body, author, disposition}`.
- Export selected comments as Markdown or a temporary file.
- Send them to any terminal pane through normal paste/input after a user action.
- Use ACP or a Voss session only when the selected pane supports structured delivery.
- Preserve the comments even if no agent is attached.

This is more durable than tying review comments to a chat vendor or assuming every CLI accepts the same follow-up syntax.

#### 3. Worktree lifecycle and integration are separate decisions

dmux has a useful two-phase merge: update the candidate branch from main inside the isolated worktree, then merge candidate into main. Conflicts stay out of the main checkout. A non-zero `pre_merge` hook can abort. It can create a PR instead of locally merging. [dmux documentation](https://dmux.ai/)

workmux supports merge, rebase, squash, stacked targets, pre-merge checks, keeping the worktree after merge, and PR workflows. Its own documentation also states the key limitation: worktrees do not prevent merge conflicts, and ignored files, dependencies, port allocation, and build caches require explicit handling. [workmux repository](https://github.com/raine/workmux), [Git worktree documentation](https://git-scm.com/docs/git-worktree.html)

**Voss implication:** `Approve candidate`, `Integrate`, and `Clean up` must be three separately recorded actions. Cleanup should be reversible or delayed until integration and post-integration verification are confirmed.

#### 4. Repository policy remains the final gate

GitHub protected branches can require approving reviews, code-owner review, successful status checks, current base state, and merge queues. A merge queue tests the proposed change against the latest target state and preceding queued changes. GitHub CLI supports auto-merge and `--match-head-commit`, which prevents merging a head different from the reviewed one. [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches), [GitHub merge queues](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue), [GitHub CLI `gh pr merge`](https://cli.github.com/manual/gh_pr_merge)

**Voss implication:** The ADE can display and help satisfy repository gates. It should not duplicate or bypass them. A Voss pass is advisory unless a repository explicitly configures it as a required check.

#### 5. Test output should be inspectable evidence, not a green badge alone

GitHub check runs support detailed annotations tied to files/lines, while workflow artifacts can retain test output, logs, screenshots, coverage, and binaries. [GitHub Checks API](https://docs.github.com/v3/checks), [GitHub workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts), [GitHub workflow monitoring](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/monitor-workflows)

A Voss ADE verification record should minimally include:

```text
verification_id
candidate_id
repo_id
head_sha
base_sha
command
cwd
started_at / ended_at
exit_code
source = manual | hook | agent | voss | ci
log_ref
artifact_refs[]
environment_fingerprint?  # opt-in and bounded
```

The UI should mark results stale as soon as `head_sha` changes. Local and CI checks should be grouped but visually distinct because they ran in different environments and may enforce different policies.

## Voss Codebase Assessment

### Existing strengths

1. **The native board has substantive gates.** `voss/harness/board/gates.py` defines separate code and AI Done predicates. Code completion requires human approval for critical work, clean scope, Reviewer A verification, Reviewer B pass, and tests passing. Predicate ordering puts the human gate before paid reviewers for critical tasks.
2. **Review has an audit representation.** `voss/harness/board/machine.py` persists review sidecars and verdict snapshots, supports pass/fail/block, retry ceilings, and terminal blocking.
3. **External CLI work is isolated during execution.** `voss/harness/swarm_worktree.py` creates per-role worktrees and aborts conflicts cleanly. `swarm_runtime.py` detects changed paths and reverts ownership violations before fan-in.
4. **The protocol already has opt-in primitives.** `.planning/PROTOCOL.md` defines additive budget, confidence, permission, and gate events/endpoints instead of overloading the shared protocol.
5. **The desktop app already has orchestration review views.** `OrgViewShell`, board summaries, verdict panels, review sidecars, audit data, and operator gates are useful optional-console assets.

### Critical gaps

#### P0: CLI swarm integration bypasses the review model

`run_cli_member()` currently performs this sequence:

1. Launch arbitrary CLI in an isolated worktree.
2. Revert out-of-scope writes after process exit.
3. `git add -A` and create a commit.
4. Merge that branch into the main checkout.
5. Mark the task done.
6. Force-remove the worktree and delete the branch.

This occurs inside `voss/harness/swarm_runtime.py:242-250`; the merge and cleanup are implemented by `voss/harness/swarm_worktree.py:189-223`. The separate board gate machinery cannot meaningfully approve a candidate that has already landed and been destroyed. The reviewer role is also treated as another non-native CLI role zipped to a task, rather than a guaranteed barrier over the aggregate candidate.

**Required change:** End a CLI member at `candidate_ready`, preserving branch/worktree and emitting its base/head SHA and diff summary. A coordinator may collect candidates, but only an explicit integration command can merge them. Optional Voss review consumes candidates before integration.

#### P0: There is no universal review surface

In `apps/voss-app/src/App.tsx`, the portal `reviewSlot` mounts `OrgViewShell`. That surface presents Voss run/board/audit information, not a neutral Git branch/worktree diff, local check history, remote CI status, or integration controls. A user who runs Codex, Claude Code, Aider, or a plain shell without adopting Voss should still have a complete review flow.

**Required change:** Make Review a Git-native surface first. Add a secondary, clearly labeled Voss Review section only after the user enables it for a candidate or workspace.

#### P0: "Tests passed" is not a durable claim

The native board can gate on `tests_passed`, but the reviewed code path does not establish a cross-surface record binding each test run to the exact candidate SHA, command, environment, and logs. The CLI swarm trusts agent exit plus a result file, then auto-merges. A CLI's prose assertion that tests passed must never be equivalent to captured test evidence.

**Required change:** Verification commands run as ADE-owned terminal jobs or imported CI checks. Store command, exit code, log reference, and SHA. Treat agent summaries as claims, not evidence.

#### P1: No post-fan-in verification barrier

Disjoint file ownership reduces textual conflict, but independently correct branches can interact semantically after fan-in. The current runtime merges members independently and emits `swarm.complete` after all return. It does not verify the aggregate tree after all merges.

**Required change:** Build an ephemeral integration branch/worktree, merge selected candidates in dependency order, run aggregate checks there, review the combined diff, then integrate. This is necessary even when all individual checks pass.

#### P1: Review identity and authority are conflated

Voss has reviewer roles, review sidecars, protocol permission gates, and a user-facing Run Review surface, but these do not yet resolve into a single rule for who may approve what. AI findings, deterministic checks, human disposition, and repository protection should be distinct facts.

**Required change:** Model each separately:

- `verification`: an executed check and result
- `review`: findings/comments from human or agent
- `approval`: a named human or policy decision
- `gate_evaluation`: a Voss policy decision over evidence
- `repository_status`: remote provider requirements and state
- `integration`: an attempt against an immutable candidate head

#### P1: Cleanup destroys useful recovery state too early

The CLI swarm force-removes the worktree and deletes its branch after merge. Mature tools expose keep/close/remove separately, warn on uncommitted or unmerged work, and support cleanup after a PR merges. The workmux changelog shows how many edge cases accumulate around races, checked-out target branches, stale state, and cleanup from inside a worktree. [workmux changelog](https://workmux.raine.dev/changelog)

**Required change:** Default to retaining the candidate until integration is verified. Store cleanup eligibility and reason; never infer it only from a terminal exit.

### Important product boundary

The native Voss board's review model should not become mandatory infrastructure for ordinary terminal work. Instead:

- Every Git-backed pane can produce a neutral candidate.
- Every candidate can use manual diff review and captured checks.
- Every candidate can open a PR or integrate locally without Voss.
- `Run Voss Review` explicitly starts the Voss sidecar/session for that candidate.
- Voss outputs reviews, gate evaluations, cost, confidence, and audit records back into the neutral evidence store.
- Disabling Voss hides those enhancements but leaves the entire terminal -> diff -> test -> PR/merge workflow intact.

## Target Workflow

### State model

Use a small Git/evidence lifecycle, independent of agent identity:

```text
working
  -> candidate_ready
  -> verifying
  -> review_ready
  -> changes_requested | approved
  -> integration_pending
  -> integrated
  -> cleanup_eligible

Any code change after verification/review:
  -> candidate_ready (prior evidence becomes stale)

Any target branch movement before local integration:
  -> integration_pending (rebase/merge preview and verification required)
```

Do not use `agent_done`, process exit, terminal idle, or a Voss task column as an alias for these Git states.

### Terminal-first daily flow

1. **Start anywhere.** Open a plain shell, attach an existing tmux pane, or launch any CLI command. No Voss variables, files, sidecar, or account required.
2. **Optionally isolate.** `New task worktree` creates a branch/worktree and tmux window/session. Existing worktrees can be adopted. Plain non-Git panes remain valid terminals.
3. **Inspect candidate.** A Git chip shows dirty files, commits ahead, base, conflict status, and stale verification count. Opening it shows a unified/split diff with a raw `git diff` escape hatch.
4. **Run checks.** The user runs any command in a verification pane or selects saved project commands. The ADE captures exit code, output, timing, artifacts, and candidate SHA. It never parses a CLI's prose as a pass.
5. **Review.** The user can comment/revert/stage hunks and make manual edits. Comments can be copied or sent to any selected terminal pane. No supported agent is required.
6. **Optionally add reviewers.** Choose any installed CLI as a review terminal, use ACP where supported, or select `Run Voss Review` with a visible budget and policy preview. The user chooses which findings become requested changes.
7. **Choose delivery.** Open/update a PR, export a patch, or integrate locally. Show exact base/head/target and what evidence is current.
8. **Reverify integration.** For local delivery, merge/rebase in an integration worktree first, run required aggregate checks, then update the target atomically. For PR delivery, surface provider checks and merge-queue status.
9. **Clean up separately.** Close terminals, archive session metadata, remove the worktree, and delete local/remote branches are individual actions or a confirmed bundle after integration.

### Optional Voss review flow

`Run Voss Review` should open a compact preflight:

- candidate/base/head and diff size
- review profile and deterministic commands
- model/provider selection or existing Voss defaults
- maximum tokens/USD and expected number of review passes
- files excluded/truncated
- human approval requirement
- whether results stay local or publish to a PR/check provider

Execution should produce:

1. Deterministic verification results.
2. Reviewer A findings grounded in diff, source, and captured results.
3. Reviewer B verdict that validates or rejects A's findings instead of merely generating more comments.
4. A signal-to-noise-oriented summary: confirmed blockers, accepted suggestions, dismissed/noisy findings, unresolved items.
5. A gate evaluation with explicit failing clauses and evidence references.
6. No merge unless the user separately invokes integration or repository policy performs it.

This leverages Voss's strongest capabilities while respecting existing agents and human authority.

## Recommended Data Contracts

### Candidate

```text
candidate_id
repo_root
worktree_path
branch
base_ref
base_sha
head_sha
working_tree_fingerprint
tmux_session/window/pane_refs[]
created_by = user | shell | external_cli | acp | voss
agent_hint?                 # display only, never authority
status
```

### Review finding

```text
finding_id
candidate_id
head_sha
path / side / line
severity
body
author_type = human | external_cli | acp | voss_a | voss_b
evidence_refs[]
disposition = open | accepted | dismissed | fixed | stale
```

### Gate evaluation

```text
evaluation_id
candidate_id
head_sha
policy_source = local | project | voss | repository
decision = pass | fail | block | needs_human
clauses[] = {name, decision, evidence_refs[]}
cost?
confidence?
evaluated_at
```

### Integration attempt

```text
integration_id
candidate_id
expected_head_sha
target_ref
target_sha_before
strategy = merge | rebase | squash | pr
preflight_verification_refs[]
approval_refs[]
repository_check_refs[]
result
target_sha_after?
post_integration_verification_refs[]
```

These records can live in app-local storage by default. Only explicitly shareable project policy or Voss audit artifacts should be written into the repository.

## Safety and Correctness Rules

1. **Immutable evidence key:** Review and verification are valid only for a specific `head_sha` plus working-tree fingerprint. Any mutation stales them.
2. **No implicit staging:** Never `git add -A` as an invisible side effect of process completion. Show untracked, ignored, staged, and unstaged scope separately.
3. **No implicit merge from agent exit:** Terminal exit is not approval.
4. **Optimistic concurrency:** Local target update must verify both expected candidate head and expected target head. Remote PR integration should use provider protections and head matching.
5. **Integration-tree verification:** Check the actual merge result, not only the isolated candidate.
6. **Evidence transparency:** A pass badge opens the command, logs, SHA, time, source, and environment. Agent-reported test claims are labeled as claims.
7. **Human authority:** AI reviewers can recommend pass/fail/block. They do not impersonate required human approval.
8. **Provider authority:** Required remote checks, approvals, and merge queues cannot be bypassed by an ADE-level green state.
9. **Failure preservation:** Conflict, failed check, or rejected review preserves the branch, worktree, logs, and comments.
10. **Cleanup idempotence:** Cleanup can be retried safely and never deletes the only reference to unmerged commits or untracked files.

## Anti-Patterns to Avoid

1. **Kanban theater:** A task entering `In Review` without a concrete candidate SHA, diff, and evidence does not improve correctness. BridgeSpace's public docs specify board states but not a review/integration contract. [BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace)
2. **Green-by-prose:** Treating "tests passed" in terminal output or an agent summary as executed, current evidence.
3. **Review by another model as approval:** Independent models can add diversity, but recent research finds a recall-versus-noise trade-off. AI review should feed human/policy decisions, not manufacture certainty. [CR-Bench](https://openreview.net/forum?id=6RmpFMEeOX)
4. **One-click merge plus cleanup:** Bundling commit, merge, pane close, worktree deletion, and branch deletion narrows recovery options and hides which step failed.
5. **Hooks as the only gate:** Hooks are useful but can be absent, skipped, locally modified, or unsafe across trust boundaries. workmux explicitly skips host hooks for sandbox RPC merges, illustrating why gate semantics must be visible and transport-aware. [workmux sandbox hook security](https://workmux.raine.dev/guide/sandbox/container)
6. **Review only the per-agent branches:** Parallel candidates can be individually valid and jointly broken. Review and test the combined integration tree.
7. **Destructive review defaults:** `Discard all`, force cleanup, and broad staging need confirmation plus a recoverable preview.
8. **Proprietary feedback channel:** Do not require Voss or a specific agent to receive review comments. Clipboard/file/pane input remains the baseline.
9. **Stale comments shown as current:** Line anchors and reviews must be versioned to the candidate SHA and visibly stale after edits.
10. **Local green presented as repository green:** Separate local commands, Voss checks, hosted CI, security scanning, and required provider status.

## Contradictions and Tensions

### Automation versus trustworthy endorsement

workmux skills can let a coordinator monitor and sequentially merge agents, while Cursor and Codemux emphasize autonomous delivery. Yet empirical study of five agent ecosystems found operational initiative can be agent-heavy while final merge governance remains overwhelmingly human. [Collaborator or Assistant?](https://arxiv.org/abs/2605.08017)

**Resolution for Voss:** Automate preparation, evidence collection, conflict preview, and PR creation. Keep endorsement and merge authority explicit and policy-driven.

### Two-model review versus false confidence

Voss's A/B review is directionally stronger than a single self-review, and JetBrains Air similarly uses a fresh review session. But CR-Bench reports that pushing reviewers to find more issues can reduce signal-to-noise through false positives. RepoAudit's validator approach also supports verifying findings rather than simply adding more agents. [CR-Bench](https://openreview.net/forum?id=6RmpFMEeOX), [RepoAudit](https://openreview.net/forum?id=TXcifVbFpG&noteId=Xwx9jr8IfB)

**Resolution for Voss:** Reviewer B should validate evidence and proposed findings. Track accepted/dismissed findings and usefulness over time, not only a binary verdict.

### Local merge convenience versus repository governance

dmux and workmux optimize fast local integration; GitHub protected branches and merge queues optimize shared-repository safety. Neither is universally correct.

**Resolution for Voss:** Support both delivery modes. Default to PR when the target is protected or a remote PR workflow is detected; offer local integration for solo/offline repositories with an explicit preflight.

### Worktree cleanup versus resumability

Windsurf/Devin Desktop automatically removes old worktrees and deletes the associated worktree when a conversation is deleted, while Zed can archive thread Git state and restore the worktree later. [Devin Desktop worktrees](https://docs.devin.ai/desktop/cascade/worktrees), [Zed Parallel Agents](https://zed.dev/docs/ai/parallel-agents)

**Resolution for Voss:** Archive metadata cheaply; preserve branches/commits; make disk cleanup policy visible. Conversation deletion must not silently destroy unique code.

### Hook execution versus sandbox trust

Pre-merge hooks provide flexible verification, but project-controlled hooks run host commands. workmux skips them for sandbox RPC merges to prevent a compromised guest from injecting host-side execution.

**Resolution for Voss:** Verification commands need provenance and execution location. Project-defined host hooks require trust. Sandboxed checks stay sandboxed; skipping a configured gate must be visible and block integration unless the user explicitly overrides it.

## Phased Priorities

### Phase 0: Stop unsafe fan-in and establish truth (P0)

- Change external CLI swarm completion from auto-merge/cleanup to `candidate_ready`.
- Add immutable candidate IDs with base/head SHA and worktree/tmux references.
- Add a neutral Git Review surface for every worktree/branch, independent of Voss.
- Capture verification commands, exit codes, logs, timestamps, and SHA.
- Mark evidence stale after any change.
- Separate `Integrate` from `Clean up` and preserve failures.

**Exit criteria:** A plain-shell user can create/adopt a worktree, inspect its complete diff, run a captured test command, integrate locally or open a PR, and clean up without starting or configuring Voss.

### Phase 1: Human review and safe integration (P0/P1)

- Add split/unified diffs, file tree, hunk navigation, staging/revert, and review comments.
- Export/send comments to any terminal pane via explicit user action.
- Add merge/rebase/squash/PR previews with exact base/head/target.
- Add an ephemeral integration worktree and aggregate verification.
- Integrate `gh` for PR state/checks when available; remain provider-neutral internally.
- Add optimistic head/target checks and post-integration verification.

**Exit criteria:** The ADE refuses to present a stale check or stale review as current and cannot silently merge a different head than the user approved.

### Phase 2: Optional Voss review provider (P1)

- Add `Run Voss Review` from a candidate with budget/policy preview.
- Adapt existing A/B verification, verdict, retry, confidence, and human gates to neutral candidate/evidence contracts.
- Persist findings with evidence references and human dispositions.
- Ensure Voss denial blocks only Voss-governed integration, not ordinary terminal use.
- Allow publishing Voss results to provider checks only after explicit configuration.

**Exit criteria:** Enabling Voss adds reviewers, budgets, gates, and auditability without changing the external CLI's auth, model, configuration, TUI, or command grammar.

### Phase 3: Team and remote policy (P2)

- Provider adapters for GitHub/GitLab checks, reviews, PRs, and merge queues.
- CODEOWNERS/approval visibility and policy profiles.
- Artifact/log retention and optional attestations for release workflows.
- Cross-candidate dependency graph and ordered integration queue.
- Team analytics based on stale checks, finding disposition, verification duration, and rollback/failure rates, not token volume alone.

**Exit criteria:** Repository policy is accurately reflected and cannot be bypassed through an ADE-only state transition.

## Feature Acceptance Criteria

1. Closing or idling an agent cannot move a candidate to Approved or Integrated.
2. Changing one byte after a check visibly stales that check.
3. A plain terminal with no recognized agent can complete the full review/test/PR/local-merge flow.
4. Voss processes and repo files are created only after explicit Voss opt-in or existing project configuration is deliberately activated.
5. A failed check, merge conflict, or rejected review leaves the candidate recoverable.
6. The UI exposes the exact command and log behind every verification badge.
7. Integration refuses an unexpected head or target SHA.
8. Local aggregate checks run on the proposed integrated tree.
9. Cleanup refuses unique uncommitted/unmerged work without explicit destructive confirmation.
10. Hosted required checks and approvals remain distinct from and authoritative over optional Voss results.

## Evidence Quality

### High confidence

- Git and GitHub behavior: official technical documentation.
- Warp, Paneflow, Windsurf/Devin Desktop, Zed, Cursor, and JetBrains capability descriptions: official product documentation.
- dmux and workmux lifecycle behavior: official docs plus public repositories and detailed changelogs.
- Voss gaps: direct inspection of local source paths named above.
- The need to distinguish AI review from approval: supported by product workflows and multiple recent empirical studies.

### Medium confidence

- Product maturity and reliability of fast-moving tools: public docs can lead released binaries, and some pages reflect 2026 features too new for broad independent evaluation.
- Codemux verification/persistence/integration claims: public product page and source availability, but limited detailed review/integration documentation.
- Cross-product qualitative comparison: feature presence is documented, but workflow quality has not been tested hands-on in this subtopic.

### Low confidence

- BridgeSpace's review correctness: the public page documents Kanban `In Review`, command exit indicators, editor, and task execution, but not candidate isolation, diff semantics, checks, PR policy, or merge safety.
- Vendor performance claims for AI reviewers: Cursor reports internal Bugbot gains, but those metrics are vendor-defined and not a substitute for repository-specific false-positive/false-negative evaluation. [Cursor Bugbot engineering](https://cursor.com/blog/building-bugbot)

## Research Gaps

- No hands-on fault-injection test was performed against competitor merge flows.
- GitLab, Bitbucket, Gerrit, and stacked-change systems need separate provider research before implementation.
- Large monorepo diff rendering, submodules, sparse checkouts, LFS, nested repositories, and partial clone behavior need dedicated acceptance testing.
- Windows tmux alternatives and remote-filesystem semantics require substrate-specific validation.
- Voss's board A/B review was inspected structurally, not executed end-to-end against an external CLI candidate in this research pass.

## Sources

### Product and tool sources

1. [Warp Code Review](https://docs.warp.dev/code/code-review)
2. [Warp Interactive Code Review](https://docs.warp.dev/agent-platform/local-agents/interactive-code-review)
3. [Warp Planning](https://docs.warp.dev/agent-platform/capabilities/planning)
4. [BridgeSpace documentation](https://docs.bridgemind.ai/docs/bridgespace)
5. [dmux documentation](https://dmux.ai/)
6. [dmux repository](https://github.com/standardagents/dmux)
7. [workmux repository and reference](https://github.com/raine/workmux)
8. [workmux changelog](https://workmux.raine.dev/changelog)
9. [workmux skills and orchestration](https://workmux.raine.dev/guide/skills)
10. [workmux sandbox hook security](https://workmux.raine.dev/guide/sandbox/container)
11. [Paneflow product](https://paneflow.dev/)
12. [Paneflow Review](https://paneflow.dev/docs/review)
13. [Codemux product and architecture claims](https://codemux.org/)
14. [Cursor Background Agents](https://docs.cursor.com/background-agent)
15. [Cursor Bugbot](https://docs.cursor.com/bugbot)
16. [Cursor web/mobile PR workflow](https://docs.cursor.com/en/background-agent/web-and-mobile)
17. [Devin Desktop / Windsurf worktrees](https://docs.devin.ai/desktop/cascade/worktrees)
18. [Devin Desktop Agent Command Center](https://docs.devin.ai/desktop/agent-command-center)
19. [Zed Parallel Agents](https://zed.dev/docs/ai/parallel-agents)
20. [Zed Tool Permissions](https://zed.dev/docs/ai/tool-permissions)
21. [JetBrains Air quickstart and review workflow](https://www.jetbrains.com/help/air/quick-start-with-air.html)

### Platform and primary technical sources

22. [Git worktree documentation](https://git-scm.com/docs/git-worktree.html)
23. [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
24. [GitHub merge queues](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue)
25. [GitHub CLI `gh pr merge`](https://cli.github.com/manual/gh_pr_merge)
26. [GitHub Checks API](https://docs.github.com/v3/checks)
27. [GitHub workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)
28. [GitHub workflow monitoring](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/monitor-workflows)

### Research and criticism

29. [CR-Bench: Evaluating the Real-World Utility of AI Code Review Agents](https://openreview.net/forum?id=6RmpFMEeOX)
30. [Why Are Agentic Pull Requests Merged or Rejected?](https://arxiv.org/abs/2605.22534)
31. [Collaborator or Assistant? How AI Coding Agents Partition Work Across Pull Request Lifecycles](https://arxiv.org/abs/2605.08017)
32. [Beyond Bug Fixes: Post-Merge Code Quality in Agent-Generated Pull Requests](https://arxiv.org/abs/2601.20109)
33. [RepoAudit: An Autonomous LLM-Agent for Repository-Level Code Auditing](https://openreview.net/forum?id=TXcifVbFpG&noteId=Xwx9jr8IfB)
34. [Cursor: Building a Better Bugbot](https://cursor.com/blog/building-bugbot)
