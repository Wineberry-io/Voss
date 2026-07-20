# Voss ADE Final Report: Synthesis and Adversarial Review

**Review date:** 2026-07-19  
**Reviewed:** `.planning/VOSS-ADE-DEEP-DIVE-JUL19.md`, local audit `00`, and research tracks `01` through `09`  
**Verdict:** **GO on the product direction; NO-GO on using the report as an implementation charter until the P0 corrections below are incorporated.**

The terminal-first, existing-CLI-first, Voss-optional thesis is coherent and well supported. The three-plane split, transport-neutral engine, tmux fidelity gate, neutral Git review model, and capability-driven UI are the right core decisions. The current report is not yet complete enough to govern implementation because it omits two concrete P0 security defects, chooses a tmux topology that conflicts with its managed-isolation claims, and binds review evidence only to `head_sha` even while supporting dirty and untracked changes.

## P0 Corrections Before Approval

### 1. Restore the omitted security findings

The report's local audit omits the two most direct code-level security findings from track `08`:

- The main webview currently has authority to invoke the full custom Tauri command surface. This includes arbitrary environment-variable reads, caller-supplied filesystem paths, PTY controls, file writes, and sidecar startup.
- `write_swarm_files` joins a caller-controlled filename beneath `.voss/swarm/tasks` without rejecting separators/traversal, allowing escape from the intended task directory.

These are not future hardening items. They are P0 defects in the current app. Add both to **Local Audit Findings**, then add Phase 0 work and tests for:

1. explicit Tauri command permissions;
2. Rust-owned canonical workspace/session handles rather than privileged caller-supplied absolute paths;
3. removal of general `get_env_var` in favor of narrow typed probes;
4. Rust-generated task filenames or strict typed task IDs, traversal/symlink rejection, and adversarial tests;
5. sidecar tokens retained in Rust rather than JavaScript state.

The architecture diagram should label the state broker as a **Rust authority boundary**. Otherwise the proposed broker can reproduce the current webview-authority problem under a cleaner name.

### 2. Resolve tmux topology versus security, rather than naming one default

The report maps one workspace to one tmux session on a Voss-owned server and treats the private socket as the default. That is operationally simple but conflicts with the report's managed-agent scope and cross-pane permission claims. Any same-user process that can find or inherit a tmux socket can control or capture every pane on that server. `$TMUX` removal alone is not isolation.

Replace the single topology decision with explicit trust domains:

| Mode | Suggested topology | Honest claim |
|---|---|---|
| Trusted raw terminals | One server per workspace or compatible user server | Durable, not isolated |
| Restricted/managed pane | One server per pane or per audited trust domain, socket hidden by OS policy | Isolated only when the OS boundary is verified |
| Imported user tmux | User-selected existing server | Voss receives full server authority; warn before attach |

Also introduce the **Terminal Group** concept from track `09`: a terminal group maps to tmux topology; Review, Orchestra, files, browser, and protocol views remain app surfaces and are not tmux panes. The current `Surface` object incorrectly suggests terminal and non-terminal surfaces may all have tmux-window bindings.

Prototype both mappings before locking the model:

1. one tmux window containing multiple terminal panes;
2. one tmux window per Voss terminal leaf.

The choice affects native attach fidelity, arbitrary GUI composition, resize behavior, and mixed terminal/non-terminal layouts. It cannot be resolved by the current one-line mapping table.

### 3. Fix candidate identity for dirty and untracked work

The report says evidence is bound to `head_sha`, while its neutral review surface explicitly includes staged, unstaged, and untracked changes. Those files can change without changing `HEAD`, leaving verification and approval falsely fresh.

Choose one invariant and state it consistently:

- **Commit invariant:** a candidate becomes reviewable only after producing an immutable commit/tree; or
- **Snapshot invariant:** bind evidence to a content-addressed snapshot/tree digest that includes staged, unstaged, and selected untracked content.

`head_sha` alone is insufficient. Update `Candidate`, `Verification`, `Review`, `Approval`, `GateEvaluation`, stale-evidence logic, Phase 3 exits, and success metrics accordingly.

### 4. Separate attachment from enforceable management

The report overstates what can happen when an arbitrary already-running CLI is promoted to `managed`. Binding a pane, worktree, task, candidate, and integration policy can happen without relaunch. Hard tool permissions, model budgets, scope enforcement, or semantic pause/resume generally cannot be imposed on an opaque existing TUI without a cooperative hook/protocol or a process boundary established at launch.

Add a per-capability authority rule:

- **Attached opaque CLI:** Voss can organize tasks, observe terminal/process facts, gate candidate integration, and record user decisions.
- **Cooperative adapter/ACP/server:** Voss can use only negotiated lifecycle, messaging, permission, and usage capabilities.
- **Voss-launched restricted or native run:** Voss can claim only the budgets, filesystem/network scope, and tool gates actually enforced by the launch boundary.

Rename `off | observed | managed` as **integration modes**, or make `observed` explicitly app-local and sidecar-free. The current “optional Voss process” wording makes ordinary observation look like implicit Voss enrollment. State that moving a current direct-PTY process into tmux is not possible in place; only later Voss attachment to an already tmux-owned pane is non-disruptive.

## Architecture Coherence Corrections

1. **Cross-pane access defaults conflict.** “Read-only pane inspection is the correct default bridge” can be read as automatic access. The security research correctly says unknown CLIs get no cross-pane grant by default. Change this to: after explicit enrollment, the least-privileged bridge is bounded read-only access; without a grant there is no access.
2. **Repo-local audit storage is inconsistent.** The report says repo-local state requires a separate explicit action, but later says managed audit data belongs in `.voss`. Managed enrollment must not implicitly commit logs, prompts, evidence, or audit history. Keep audit app-local by default; export/share only through a distinct, previewed action.
3. **Current enforcement is overstated.** “The native Voss board already models ... scope enforcement” should say it models relevant gates in Voss-native paths; the external CLI path currently bypasses them.
4. **Process authority and policy authority need separate arrows.** Voss should request typed actions through the Rust broker and Git/evidence engine. It must not gain raw tmux or arbitrary filesystem authority merely because a workspace is managed.
5. **Environment freshness is absent.** A long-lived tmux server retains environment state. `SpawnSpec` must construct each pane's environment intentionally, define login-shell behavior, and test refreshed credentials/toolchain variables rather than relying on the server snapshot.
6. **Compatibility versus determinism is unresolved.** A minimal Voss tmux config improves reproducibility but discards user plugins and habits. Define separate `managed-safe` and `compatibility` profiles, with different support/security promises.

## tmux Feasibility Caveats to Add

The report correctly uses a fidelity spike as a go/no-go gate, but the matrix is narrower than the terminal research. Add tests or explicit unsupported labels for:

- `TERM`/terminfo and truecolor/styled underline/cursor capability negotiation;
- IME, Unicode width, combining characters, emoji, large paste, and invalid UTF-8 byte paths;
- OSC 8 links, OSC 52 clipboard, DCS passthrough, synchronized output, Kitty keyboard protocol, SIXEL/Kitty graphics, and application notifications;
- copy/search/selection behavior when tmux history is canonical but xterm is the viewport;
- external-client resize policies (`smallest`, `largest`, `latest`, or manual) and focus ownership;
- tmux config/plugin failure, server upgrade, socket ownership/permissions, stale sockets, and environment refresh;
- nested tmux, SSH-inside-local-tmux versus remote-tmux, and an agent invoking tmux commands from inside its pane.

`capture-pane` is a repair source, not proof that full terminal-emulator state can be restored. It does not by itself establish every cursor, private mode, graphics, clipboard, or passthrough state. Qualify “recovery through `capture-pane`” and make the spike prove snapshot-plus-incremental-output correctness.

Use correct attach examples: `tmux -L <socket-name> attach-session -t <session>` for a named socket, or `tmux -S <socket-path> attach-session -t <session>` for a path. The report currently writes `tmux -L <socket> attach`, which conflates the two.

## Roadmap Dependency and Order Corrections

1. **Security must enter Phase 0.** Broad IPC authority, path traversal, Rust-held sidecar tokens, canonical root handles, and terminal-control-sequence validation cannot wait for release hardening.
2. **Do not wire fake semantics before the engine boundary.** In Phase 0, hide/remove restart, detach, pause, and placement controls that lack authority. Implement stable handles and capability reporting in Phase 1, then reintroduce each control with an acknowledged backend operation.
3. **Split the first implementation slice.** Steps 1-3 describe P0 repair plus a standalone codec spike, while step 4 requires a working app-integrated `TmuxEngine`, persistent identities, Git candidate flow, and Voss detachment. That is not one smallest slice. Define:
   - Slice A: neutrality/security/build repair, `DirectPtyEngine` extraction, headless Control Mode differential harness.
   - Slice B: one app-integrated tmux terminal group proving detach/reattach, then one preserved Git candidate.
4. **Move production distribution earlier than remote.** Signed/notarized packages, updater integrity, desktop CI, rollback, and supply-chain evidence are prerequisites for a credible daily-driver beta, not the last phase after orchestration. Keep remote operation late, but create a release gate after the local persistent terminal beta.
5. **Defer imported-user-tmux support until the managed socket is stable.** Import introduces arbitrary configs/plugins, full-server authority, and external topology/resize writers. It should not share the initial beta exit gate.
6. **Phase 3 attention depends on Phase 2 signals.** Define which terminal-native sources ship before promising completion notifications. Shell integration can be opt-in and agent-neutral; it need not wait for vendor adapters in Phase 4.

## Voss-Off Boundary Corrections

- Replace “no ... network calls” with “no Voss sidecar, Voss credential, Voss telemetry, or Voss service network calls.” An independently configured update check is a separate product policy and should be documented rather than accidentally forbidden by an overly broad invariant.
- State that raw/unmanaged CLIs retain normal user filesystem and network authority. “Voss off” means no extra Voss authority or mutation; it does not imply sandboxing.
- No `.voss`, hooks, shell rc edits, MCP registration, adapter install, terminal capture, or repo audit export may occur merely because the user opened an observed surface.
- Closing Orchestra must be UI-only. Disabling Voss must revoke adapters/tools/sidecar access while preserving tmux processes; cleanup of Voss records is a separate explicit choice.
- Provider auth/config/billing ownership is well stated and should remain unchanged.

## Unsupported or Overstated Market Claims

The conclusions are directionally sound, but several sentences need evidence labels:

- “Control Mode is the proven integration boundary” should be “a proven integration boundary used by iTerm2, subject to Voss's fidelity spike.” It is not proof of xterm/webview equivalence.
- “Paneflow demonstrates the strongest neutrality contract” is a ranking based primarily on first-party documentation. Use “the clearest documented neutrality contract among reviewed products” and label runtime behavior vendor-reported unless independently tested.
- Warp user criticism is mentioned without a citation. Cite the specific issues/community evidence and label it anecdotal, not prevalence data.
- BridgeSpace runtime, scale, memory, and swarm capabilities are vendor claims. The report handles this in prose but the capability matrix should carry an evidence label or footnote.
- The competitor matrix makes uncited claims for Warp persistence, Flowmux, Codemux, BridgeSpace, and Paneflow. Add a citation per row and distinguish product docs, public code, changelog, and user report.
- “58,000 lines” and every local P0/P1 finding need code path/line references or a link to `00-local-code-audit.md`; currently the final report is not independently auditable without searching the repository.

## Citation and Source Coverage

**Coverage result: insufficient for a final deep-dive report, adequate only as an executive synthesis.**

- The final report contains 13 inline links.
- The nine research notes contain roughly 261 distinct URL strings before excluding localhost/example/config strings and duplicate variants.
- The report has no categorized source register, no per-row competitor citations, and no direct references to most code findings.
- Primary sources are strong in the underlying notes: tmux manuals/wiki, Git docs, vendor protocol/docs, ACP/MCP specifications, Tauri/security docs, public repositories, and issue trackers.
- Community criticism is appropriately treated as failure-mode evidence in the notes, but that evidence labeling is mostly lost in the final report.

Recommended correction: add a compact **Evidence and Sources** appendix grouped by terminal/tmux, agents/protocols, worktrees/review, competitors, and security/distribution. Cite every competitor row and every security claim near the text. Link the detailed research tracks for full source inventories. Do not paste all 261 URLs into the main narrative, but report the deduplicated consulted-source count only after excluding non-source literals and confirming fetch/inspection status.

## Missing High-Impact Risks and Features

- Tauri IPC least privilege, path traversal prevention, sidecar token custody, and opaque Rust handles.
- tmux trust domains and the fact that same-user socket access is total server control.
- content-addressed dirty-worktree snapshots or a commit-before-review rule.
- managed sandbox truth: current macOS/Linux wrappers are write guards, not confidentiality/network boundaries; Windows restricted mode is unavailable.
- remote security defaults: OpenSSH config/host-key authority, forwarding off, remote-root binding, Rust-held tunneled sidecar tokens, and no automatic remote mutation.
- privacy contract: no terminal commands/output/cwd/diffs/pane titles in analytics; redacted previewable crash reports; network activity visibility.
- distribution gates: SBOM/provenance, dependency scanning, signed updater, rollback, migration tests, and platform webview matrix.
- migration behavior for existing direct-PTY sessions: they cannot become tmux-owned live processes without restart, and copy/reconstruction must not be called adoption or reattachment.

## Final Assessment

**Strategic direction: GO.** The report answers the user's core question with a strong position: Voss should earn adoption as a terminal, preserve arbitrary CLI ownership, and offer orchestration as an attachable evidence/governance layer.

**Architecture authorization: CONDITIONAL GO** after the tmux topology/trust-domain and immutable-candidate corrections.

**Implementation authorization: NO-GO** until the omitted P0 security issues are placed in Phase 0, the first slice is split into achievable increments, and the final report gains auditable source/code references.

After those corrections, the report is suitable to supersede the older ADE planning direction and drive implementation spikes.
