# Voss ADE Deep Dive: Security, Remote Operation, and Distribution

> Research date: 2026-07-19 | Subtopic: 08 | Sources consulted: 46 | Evidence: static code inspection plus primary-source research

## Executive Decision

The tmux-backed terminal should be the product's durable process substrate, not its security boundary. The tmux maintainers explicitly state that anyone who can reach a tmux socket must be treated as fully trusted and can control the entire server; even tmux read-only access is a convenience, not a security mechanism. A Voss ADE that puts ordinary shells and restricted agents in the same reachable tmux server therefore cannot honestly claim pane-level isolation.

The defensible design has three independently activatable trust planes:

1. **Terminal plane, on by default.** Raw local or SSH terminals run with the user's normal authority. The ADE adds no Voss environment, credentials, repository files, network calls, or hooks. It makes no sandbox claim.
2. **Managed-agent plane, explicit per pane.** A user may opt a CLI agent into workspace restrictions, approvals, cross-pane observation, or Voss metadata. Managed panes must be placed in a tmux security domain whose socket is not reachable from the child process, and restrictions must be kernel-enforced or labeled unavailable.
3. **Voss orchestration plane, explicit per workspace/run.** The sidecar starts only after an orchestration action. Its token remains in Rust, its authority is bound to one canonical workspace, and its console can be closed without killing ordinary terminals.

This preserves the product requirement: Claude Code, Codex, Gemini, OpenCode, Aider, an unknown future CLI, and a plain shell remain first-class without Voss adoption. Voss becomes a capability provider rather than the terminal's identity system.

Before a public beta, Voss should fix the current webview-to-Rust authority surface, workspace path handling, sidecar scoping, sandbox claims, and release signing. These are more urgent than adding remote access or richer orchestration.

## Threat Model

### Assets

| Asset | Why it matters |
|---|---|
| Keystrokes and PTY input | Passwords, `sudo` prompts, API keys, and destructive commands pass through the terminal UI. |
| Scrollback and pane state | Output commonly contains source, tokens, logs, environment values, and customer data. |
| Workspace and Git state | Agents can alter code, hooks, worktrees, commits, remotes, and release artifacts. |
| Host secrets | `~/.ssh`, cloud credentials, keychains, environment variables, credential-helper sockets, and browser/session tokens. |
| tmux control socket | Possession means control of every pane in that tmux server, including capture, input, kill, and environment access. |
| Voss sidecar token | Grants the sidecar's session, memory, swarm, permission, and orchestration API authority. |
| Update/signing keys | Compromise converts the updater into a supply-chain delivery mechanism. |
| Remote host identity | A wrong or spoofed host turns every terminal and agent action into attacker-controlled execution. |

### Actors and failure modes

- A malicious repository containing shell initialization, task, hook, tool-description, or prompt-injection content.
- A compromised or malicious CLI agent, MCP server, plugin, skill, hook, or update.
- A malicious terminal program emitting OSC/DCS/CSI sequences, hyperlinks, titles, clipboard writes, or adversarial byte fragmentation.
- XSS or dependency compromise in the Tauri webview.
- Another local process running as the same user and probing loopback ports, app data, tmux sockets, or process environments.
- A compromised remote host, bastion, forwarded SSH agent socket, or stale host identity.
- Accidental cross-pane input, wrong-workspace routing, stale session reuse, or an operator misunderstanding a best-effort sandbox badge.

### Explicit non-goals

- An unmanaged terminal cannot be made less powerful than the shell the user chose to run.
- tmux cannot isolate mutually distrustful processes that can reach the same socket.
- A remote host's root user can observe or modify remote processes; SSH protects transport and host authentication, not a hostile endpoint.
- Model-level prompt-injection defenses do not replace OS filesystem, process, network, or credential boundaries.

## What the Primary Sources Establish

### tmux is suitable for durability, not isolation

tmux Control Mode is a text protocol designed for GUI clients and can be parsed over SSH. It reports pane output asynchronously, preserves raw escape sequences, and exposes stable pane IDs and commands such as `list-panes` and `switch-client` ([tmux Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode)). This is a strong fit for process survival, detach/reattach, and a native grid.

The security limit is unambiguous: tmux relies on filesystem permissions for its socket; any principal with socket access is fully trusted and can control the server. `server-access` and read-only flags do not form a security boundary ([tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ)). A managed agent that inherits `$TMUX` normally learns the socket path and can invoke `tmux capture-pane`, `send-keys`, or `kill-session` unless the OS sandbox prevents socket access.

The engine must also be treated as an updateable security dependency. tmux 3.6b fixed CVE-2026-11623, a SIXEL image lifetime bug that could crash the server and was considered potentially security relevant; builds through 3.6a were affected when SIXEL was enabled ([oss-sec advisory](https://seclists.org/oss-sec/2026/q2/934)). Voss should bundle or validate a patched build, record compile features, and maintain an advisory response policy rather than assuming the system tmux is safe.

### SSH should remain the transport authority

OpenSSH provides encrypted transport, strong host/user authentication, forwarding, and connection multiplexing ([OpenSSH features](https://www.openssh.org/features.html)). Voss should delegate SSH config, `known_hosts`, hardware-backed keys, ProxyJump, and host verification to the installed OpenSSH client instead of implementing its own SSH stack.

Agent forwarding must be off by default. OpenSSH documented an exploitable `ssh-agent` RCE involving forwarded agent sockets in CVE-2023-38408, along with later destination-constraint flaws; OpenSSH's guidance supports destination-restricted keys but does not make a compromised remote host trustworthy ([OpenSSH security](https://www.openssh.org/security.html), [agent restrictions](https://www.openssh.org/agent-restrict.html)). Per-host opt-in is acceptable; a global `ForwardAgent yes` is not.

Warp provides a useful consent precedent: its tmux-powered SSH enhancement can be declined, hosts can be denylisted, and installing tmux or modifying a remote rcfile requires explicit consent. It uses tmux Control Mode for background remote tasks ([Warp SSH](https://docs.warp.dev/terminal/warpify/ssh)). Warp also documents important remote degradation: native indexing, diffs, editor, file tree, and code review are unavailable when it lacks direct remote filesystem access ([Warp feature support over SSH](https://docs.warp.dev/code/ssh-feature-support)). Voss should show the same honesty instead of silently mixing local and remote capabilities.

VS Code demonstrates the heavier alternative: install a matching server and remote extension host near the workspace, then communicate through the authenticated SSH tunnel ([VS Code Remote SSH](https://code.visualstudio.com/docs/remote/ssh), [remote extension architecture](https://code.visualstudio.com/api/advanced-topics/remote-extensions)). That model enables rich filesystem features but materially enlarges the remote trusted computing base. It is a later option for Voss, not a prerequisite for terminal-first remote tmux.

### Terminal output and the webview are mutually dangerous inputs

xterm.js warns that embedding a terminal in HTML gives page JavaScript access to shell input and keystrokes, while terminal output must be treated as untrusted when exposed through titles, buffers, parser hooks, and linkifiers ([xterm.js security](https://xtermjs.org/docs/guides/security/)). This makes a webview compromise equivalent to terminal-session compromise even if Rust itself is memory safe.

Escape-sequence abuse is not theoretical. CVE-2024-28085 let unprivileged users inject escape sequences into other users' terminals through `wall`, with plausible account-takeover paths ([NVD](https://nvd.nist.gov/vuln/detail/CVE-2024-28085), [Ubuntu advisory](https://ubuntu.com/security/notices/USN-6719-1)). OSC 52 can write or query clipboards depending on emulator policy; xterm disables it by default, while tmux can forward clipboard sequences ([tmux clipboard guidance](https://github.com/tmux/tmux/wiki/Clipboard), [Ghostty OSC 52 reference](https://ghostty.org/docs/vt/osc/52)). OSC 8 hyperlinks must require deliberate activation and scheme validation ([xterm.js link handling](https://xtermjs.org/docs/guides/link-handling/)).

Tauri improves the frontend/native boundary only when the application uses it. Tauri states that the Rust core has full system access and the webview reaches it through IPC, so boundary validation is the application's responsibility ([Tauri security model](https://tauri.app/es/security/)). By default, every app command registered with `invoke_handler` is callable by every app window/webview unless the app defines an `AppManifest` command permission model ([Tauri capabilities](https://v2.tauri.app/es/security/capabilities/)). Tauri command scopes are useful only when each command actually enforces them ([Tauri command scopes](https://v2.tauri.app/security/scope/)).

### Agent and plugin interoperability expands the trust graph

MCP roots communicate intended filesystem boundaries but are not enforcement; the official docs say enforcement must happen through OS permissions or sandboxing ([MCP client concepts](https://modelcontextprotocol.io/docs/learn/client-concepts), [MCP roots](https://modelcontextprotocol.io/specification/2025-03-26/client/roots)). The protocol also forbids token passthrough and requires audience validation and per-client consent to prevent confused-deputy attacks ([MCP authorization](https://modelcontextprotocol.io/specification/draft/basic/authorization), [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)). Tool annotations themselves must be treated as untrusted ([MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)).

The ecosystem evidence supports conservative defaults. A study of 1,899 open-source MCP servers found 7.2% with general vulnerabilities and 5.5% with MCP-specific tool poisoning ([research paper](https://arxiv.org/abs/2506.13538)). Another benchmark reported a 72.8% tool-poisoning attack success rate in one evaluated agent configuration; that number is experimental, not a universal ecosystem rate ([MCPTox](https://arxiv.org/abs/2508.14925)).

Zellij offers a useful capability taxonomy for terminal extensions: reading pane contents, writing stdin, intercepting input, opening files, running commands, full-disk access, clipboard writes, and starting a web server are separate permissions ([Zellij plugin permissions](https://zellij.dev/documentation/plugin-api-permissions.html)). Voss should adopt equivalent granularity even if it does not adopt Zellij's WASM plugin implementation.

Paneflow makes its cross-pane MCP surface read-only: agents can inspect pane scrollback but cannot type into it. It also states that existing CLIs keep their own accounts, model provider, and network path ([Paneflow overview](https://paneflow.dev/), [Paneflow docs](https://paneflow.dev/docs)). Read-only reduces integrity risk but not confidentiality risk, so scrollback sharing still needs an explicit grant and redaction controls.

BridgeSpace's public material is less technically verifiable. Its privacy policy says the app may access local files, terminals, clipboard, microphone, and accessibility permissions, and that prompts, history, and selected context may be sent to BridgeMind and model providers ([BridgeMind privacy policy](https://www.bridgemind.ai/privacy-policy)). Its product documentation claims 1-16 panes and agent workflows but does not publish a comparable isolation model or external audit ([BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace)). Treat these as product claims, not a security baseline.

## Static Security Audit of the Current Voss ADE

The following findings are grounded in the repository as inspected on 2026-07-19. This was not a penetration test.

### P0: webview authority is much broader than the UI requires

`apps/voss-app/src-tauri/build.rs` calls only `tauri_build::build()`. `src-tauri/src/lib.rs:1502-1567` registers every custom command, and no `AppManifest::commands` permissions are defined. Under Tauri's documented default, the main webview can call all of them.

That includes:

- `get_env_var(name)` at `lib.rs:807-810`, which returns any environment variable by caller-supplied name. An XSS or compromised dependency could retrieve inherited provider tokens, cloud credentials, or signing-related variables.
- `list_dir(path)` at `lib.rs:1192-1195`, which canonicalizes an arbitrary path but does not bind it to the active workspace.
- `start_voss_serve(cwd)` at `lib.rs:1447-1472`, which passes an empty allowed-root list and therefore accepts any existing directory.
- PTY write/kill commands keyed only by caller-supplied session ID, without a webview-side concept of pane ownership.
- file-writing commands that accept caller-supplied workspace paths.

**Required change:** define explicit application command permissions, but do not stop there. Rust must own a canonical workspace registry and derive paths from opaque workspace/session handles. The webview should never send an arbitrary absolute path for a privileged operation. Remove `get_env_var`; replace it with narrowly typed capability probes that return booleans or non-secret metadata.

### P0: `write_swarm_files` permits path traversal through task filenames

`src-tauri/src/lib.rs:813-840` joins each caller-provided `filename` directly under `.voss/swarm/tasks` and writes it. A value such as `../../../.git/hooks/pre-commit` escapes the task directory. The workspace path is also not canonicalized or authorized.

**Required change:** accept typed task IDs, generate filenames in Rust, reject separators and traversal, canonicalize the workspace, use `openat`-style directory-relative writes where available, reject symlinks, and add adversarial tests.

### P0: the Voss sidecar is authenticated but not workspace-confined

Positive controls exist: `voss serve` binds an ephemeral `127.0.0.1` port, generates a 32-byte URL-safe bearer token, prints a race-free handshake, restricts CORS to loopback/Tauri origins, and dies with its parent (`voss/harness/server/serve.py:39-74`; `app.py:496-537`). The frontend avoids logging the token.

The boundary is incomplete:

- `start_voss_serve` calls `validate_workspace_cwd(&cwd, &[])`, explicitly allowing any existing directory (`src-tauri/src/lib.rs:1447-1450`; `crates/voss-app-core/src/sidecar.rs:66-83`).
- The server is launched for one cwd, but endpoints accept new cwd values. `/memory` constructs a `MemoryStore` from any resolved query-path (`voss/harness/server/app.py:724-734`), and session/swarm creation similarly accepts request cwd.
- The bearer token is copied into JavaScript state and global Solid signals. XSS gains the sidecar's complete authority.
- CORS permits every localhost/loopback port and the Tauri CSP permits `http://127.0.0.1:*`, `http://localhost:*`, and an apparently unused `https://api.anthropic.com` egress target.

**Required change:** launch a sidecar with an immutable canonical root; remove cwd from ordinary endpoint inputs; reject any derived path outside that root; keep the token in Rust; proxy typed sidecar operations through narrow Tauri commands; rotate/revoke tokens when the workspace closes; and compile separate dev/prod origin policies.

### P0: current sandbox language overstates confidentiality and cross-pane safety

The implementation honestly downgrades the displayed tier to observe-only when the OS wrapper is unavailable (`src-tauri/src/lib.rs:289-375`). That is good.

The active policies are only write-blast-radius controls:

- macOS uses deprecated `/usr/bin/sandbox-exec`. Its profile starts with `(allow default)` and only denies writes outside the workspace/temp/device paths (`crates/voss-app-core/src/sandbox.rs:63-80`). It can still read SSH keys and other secrets, access the network, inspect reachable IPC, and potentially access the tmux socket.
- Linux `bwrap` read-only binds `/`, writable-binds the workspace and `/tmp`, and mounts `/dev` and `/proc`, but does not use `--unshare-all`, `--unshare-net`, `--new-session`, seccomp, or resource limits (`sandbox.rs:124-155`). bubblewrap itself warns it is a policy construction tool, not a complete sandbox, and requires `--new-session` unless `TIOCSTI` is filtered ([bubblewrap security notes](https://github.com/containers/bubblewrap)).
- Windows always receives `Unavailable`; there is no managed isolation implementation.

Apple documents App Sandbox as the supported application boundary, while the `sandbox-exec` man page marks the command deprecated ([Apple App Sandbox](https://developer.apple.com/documentation/security/app-sandbox), [sandbox-exec man page](https://man.freebsd.org/cgi/man.cgi?manpath=macOS+13.6.5&query=sandbox-exec&sektion=1)). A Mac App Store sandbox is also in tension with the product's need to execute arbitrary user-installed CLIs. Voss should plan direct signed/notarized distribution and label Seatbelt as best-effort defense-in-depth, not a complete agent sandbox.

### P1: terminal control sequences need a streaming security parser

`crates/voss-app-core/src/pty/reader.rs:17-30` searches one read buffer for one complete Voss OSC sequence. The comment claims fragmented input will be recovered by cumulative state, but the reader loop does not retain a partial frame across reads. Multiple or fragmented OSC messages may be dropped, leaked to display, or parsed inconsistently.

This is correctness and security-relevant because the same output stream contains untrusted control data. The tmux Control Mode parser will add another framing layer and must preserve arbitrary bytes without confusing tmux notifications, OSC, DCS, BEL, ST, UTF-8, or octal escaping.

**Required change:** a bounded incremental byte parser with fuzzing and corpus tests for fragmented, concatenated, oversized, malformed, binary, OSC 8, OSC 52, DCS/SIXEL, and tmux `%output` frames. Never place terminal-derived titles, URLs, paths, or HTML into the DOM without independent validation.

### P1: terminal-only mode is not currently free of Voss coupling

Every plain shell receives `VOSS_EMBEDDED=1` and usually `VOSS_AGENT_ID` (`src-tauri/src/lib.rs:605-628`). This violates the proposed zero-Voss terminal boundary, risks altering the behavior of an installed Voss-aware CLI, and places product identity into ordinary shells.

**Required change:** raw panes inherit the user's environment without Voss additions. Only an explicit “Enable Voss for this pane/run” action may inject Voss variables or start a sidecar.

### P1: same-workspace tmux would defeat managed-pane isolation unless designed explicitly

If a future tmux backend launches a managed agent inside the same tmux server as other panes and exposes the socket through `$TMUX`, the agent can control or capture sibling panes regardless of Voss UI permissions. Current Seatbelt and bwrap profiles do not close this channel.

**Required change:** make tmux topology a security decision, as described below.

### P1: distribution is not release-ready

`src-tauri/tauri.conf.json` has `bundle.macOS.signingIdentity: null`; the updater plugin is absent; and repository workflows do not run Voss app Vitest, Playwright, Tauri packaging, signing, or platform smoke jobs. Tauri requires signing and notarization for direct macOS distribution and signing to avoid Windows SmartScreen distrust ([Tauri distribution](https://v2.tauri.app/distribute/), [macOS signing](https://v2.tauri.app/distribute/sign/macos/), [Windows signing](https://v2.tauri.app/ko/distribute/sign/windows/)). Tauri's updater requires signed artifacts and does not permit disabling update signature verification ([Tauri updater](https://v2.tauri.app/ja/plugin/updater/)).

### Positive controls worth preserving

- PTY writes reject empty payloads and cap a single write at 1 MiB (`crates/voss-app-core/src/pty/writer.rs`).
- Managed launch uses argv arrays rather than shell interpolation and reports sandbox downgrade honestly.
- Sidecar startup canonicalizes existing directories, uses loopback, a random token, parent death handling, and avoids token logging.
- The Tauri CSP has restrictive `default-src` and `script-src` baselines; refine rather than remove it.
- Product documents say telemetry and crash reports are off by default. The code search found no current analytics/crash SDK integration, so this remains a policy to preserve when telemetry is implemented.

## Recommended Security Architecture

### 1. Separate lifecycle from authority

Define these Rust-owned objects:

```text
WorkspaceHandle -> canonical local/remote root + trust decision
TerminalHandle  -> backend + tmux domain + workspace + PTY/control client
AgentHandle     -> terminal + adapter + managed policy + grants
VossHandle      -> workspace + Rust-held sidecar token + explicit lifecycle
RemoteHandle    -> SSH config host + verified host-key identity + connection
```

The frontend receives opaque IDs and presentation data. It never supplies a new absolute path, process binary, tmux socket, sidecar base URL, or bearer token to privileged commands after creation. Every mutation checks the handle relationship in Rust.

### 2. Use tmux security domains, not one universal server

| Topology | Benefits | Security problem | Recommended use |
|---|---|---|---|
| One tmux server/session for all panes | Native tmux topology, simple attach, low overhead | Every socket-capable pane can control every other pane | Only for explicitly trusted raw shells |
| One server per workspace | Good durability and workspace restore | Agents within a workspace still share full control | Default compatibility mode for trusted panes |
| One server per managed pane | Strongest practical separation and independent teardown | More tmux/control clients; ADE owns layout | Restricted agents and high-risk tasks |
| One server per trust domain | Balanced overhead and isolation | Policy complexity; a mistake merges authority | Preferred mature design |

Use app-private socket directories with owner-only permissions. Do not attach to the user's existing tmux server by default. “Import existing tmux session” must warn that it grants Voss full control of that server. For managed panes, unset `$TMUX` for the child and enforce socket invisibility in the OS sandbox; environment removal alone is not sufficient because same-user processes can discover sockets.

Offer two configuration profiles:

- **Compatibility:** source the user's tmux config and plugins, treated as trusted code.
- **Managed-safe:** audited minimal tmux config, no automatic third-party plugins, restricted terminal features, patched/bundled tmux, and isolated socket.

### 3. Make cross-pane capabilities explicit

Adopt separate grants modeled after Zellij's permission vocabulary:

- view pane metadata
- read rendered scrollback
- read raw output
- send input
- interrupt/kill/restart
- access clipboard
- open local files/URLs
- expose environment metadata
- start another terminal/agent
- call Voss or MCP tools

Default unknown CLIs to none. Read-only pane inspection is safer than write access but can still expose secrets. Grant it per target pane or pane group, display an active indicator, redact high-confidence secrets, cap history, and record accesses in a local audit log. Never automatically feed all pane scrollback into a model.

### 4. Define honest execution modes

| Mode | Filesystem | Network | Credentials | tmux/cross-pane | Claim |
|---|---|---|---|---|---|
| Raw terminal | User authority | User authority | User environment | Trusted domain | “Normal shell” |
| Unmanaged CLI agent | User authority | Agent's own path | Agent's own auth | No Voss grants, but raw OS authority | “Not isolated” |
| Managed agent | Canonical workspace policy | Deny by default or explicit destinations | Brokered/minimal | Isolated tmux domain | “Restricted” only when kernel proof passes |
| Voss-native run | Managed policy plus typed Voss API | Explicit provider/tool routes | Rust/OS secret store | Audited grants | “Orchestrated” |

Do not silently downgrade a requested restricted run and continue. The existing UI downgrade is honest, but a security-sensitive launch should require the user to accept unmanaged execution or cancel.

### 5. Keep secrets out of terminal and webview state where possible

- Let third-party CLIs retain their own authentication and configuration. Do not import or proxy their API keys merely to show richer UI.
- Store Voss-owned long-lived secrets in the OS credential store or a cross-platform secret engine; Apple recommends Keychain for small encrypted secrets ([Apple Keychain guidance](https://developer.apple.com/documentation/Security/using-the-keychain-to-manage-user-secrets), [Tauri Stronghold](https://v2.tauri.app/es/plugin/stronghold/)).
- Keep sidecar bearer tokens and remote tunnel credentials in Rust memory; never serialize them into workspace state, logs, crash reports, URLs, or tmux environments.
- Treat environment variables as secret-bearing. Return capability booleans, not arbitrary values.
- Default persisted terminal scrollback to off. If enabled, store it in owner-only app data with retention controls, per-pane deletion, and an explicit warning that terminal output may contain secrets.

## Remote tmux Design

### Minimal remote mode

1. Invoke the user's OpenSSH binary with their config and host-key verification.
2. Probe `command -v tmux` and `tmux -V` without modifying the host.
3. If absent, show exact install commands and require approval; declining leaves a normal SSH terminal.
4. Start or attach `tmux -CC` in an app-namespaced remote socket/session.
5. Bind the saved session to SSH config alias, remote user, and verified host-key fingerprint, not hostname text alone.
6. Reconnect the control client after network loss; do not infer process death from SSH disconnect.

This mode needs no Voss installation and no remote daemon. It should be the first remote release.

### Optional remote orchestration

If the user explicitly enables Voss on a remote workspace, run the sidecar on remote loopback and tunnel only its ephemeral port through SSH. Keep its token on the local Rust side and bind it to the remote workspace identity. Never bind the remote sidecar to `0.0.0.0`, copy a token into pane environment, or reuse one token across hosts/workspaces.

VS Code's newer Agent Host architecture reinforces the useful separation: the host can continue without a UI client, and the UI reconnects over SSH or an authenticated tunnel ([VS Code Agent Host](https://code.visualstudio.com/docs/agents/concepts/agent-host)). Voss can apply that lifecycle principle without installing a general-purpose remote extension host.

### Remote defaults

- SSH agent forwarding: off.
- X11 forwarding: off.
- local/remote/dynamic port forwarding: off except typed Voss/dev-server grants.
- remote rcfile edits and tmux installation: explicit approval with command preview.
- clipboard integration and OSC 52: off or write-only by default for untrusted remote hosts.
- remote file indexing and cross-pane capture: off until separately granted.
- host-key change: hard stop, never an in-app “continue anyway” default.
- terminal mode must remain useful when every enhancement is declined.

## Sandboxing and Cross-Platform Constraints

### Linux

A defensible `bwrap` restricted mode needs an audited policy: new user/PID/mount/IPC/UTS namespaces, `--new-session`, no network namespace connectivity by default, minimal device exposure, a private temp directory, a read-only toolchain, only the workspace write-bound, no host credential sockets, and CPU/memory/process limits. bubblewrap explicitly says policy quality determines whether it forms a security boundary ([bubblewrap](https://github.com/containers/bubblewrap)). Test kernels where unprivileged user namespaces are disabled and report “unavailable,” not “restricted.”

### macOS

Direct-distribution Voss can run arbitrary external CLIs, but full App Sandbox distribution is likely incompatible with that core workflow. Code-sign and notarize the app and every bundled executable. Treat `sandbox-exec` as a deprecated, best-effort write guard, not protection from secret reads or network exfiltration. Offer a stricter container/VM-backed execution mode for users who require a credible isolation boundary.

### Windows

tmux is not a native Windows substrate. The honest choices are:

- tmux through WSL2, with an explicit WSL workspace/backend identity;
- tmux on a remote SSH host; or
- a non-tmux ConPTY fallback whose feature badge does not promise tmux persistence.

Windows AppContainer can restrict filesystem, registry, network, and user-data access, but launching arbitrary developer CLIs under a useful AppContainer policy is a separate engineering project ([Microsoft AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)). Until implemented and tested, managed isolation on native Windows is unavailable.

### Tauri/WebView matrix

Tauri uses the platform WebView rather than shipping one Chromium build, so security patches and rendering behavior differ across macOS, Windows, and Linux ([Tauri security](https://tauri.app/es/security/)). Release testing must cover WebKit/WKWebView, WebView2, and WebKitGTK, including xterm rendering, IME, clipboard, links, OSC handling, CSP, IPC permissions, and updater behavior.

## Privacy and Telemetry Contract

Terminal-first mode should be verifiably local:

- No account requirement for terminal use.
- No network request at startup except an explicit update check controlled by settings.
- Usage analytics and crash reports off by default, as the existing Voss product docs state.
- Never collect commands, terminal output, cwd, filenames, branch names, prompts, diffs, environment values, or pane titles as analytics.
- Crash reports require local redaction before transmission and a previewable payload.
- Provide a network activity log showing destination, feature, and data category.
- Separate local Voss history from cloud/model-provider transmission; show when context will leave the machine.

Warp is a useful transparency benchmark: it documents an exhaustive event table, offers a live network log, and allows telemetry opt-out while retaining product functionality ([Warp privacy](https://docs.warp.dev/support-and-community/privacy-and-security/privacy)). Its policy also shows why precise wording matters: local conversations are local by default, cloud sessions are necessarily stored remotely, and AI inputs follow distinct retention rules. Voss should publish a smaller, simpler contract rather than copy the data surface.

## Distribution and Supply-Chain Gates

- Reproducible CI builds for supported macOS architectures, Linux formats/architectures, and Windows/WSL paths.
- Developer ID signing and notarization on macOS; Authenticode signing on Windows; signed Linux packages where the channel supports it.
- Sign every bundled sidecar and tmux binary, not only the outer application.
- Updater metadata and artifacts signed with an offline-protected key; staged channels; rollback metadata; no silent downgrade.
- Generate SBOMs for Rust, Python, Node, bundled webview/runtime assumptions, tmux, and sidecars.
- Pin dependencies and GitHub Actions by immutable revision; run license and vulnerability scans.
- Publish a security policy, supported-version window, disclosure address, and emergency update process.
- Add artifact provenance/attestation and verify a downloaded release on clean machines before promotion.
- Never let project files or plugins alter updater endpoints, signing keys, or release channels.

## Security Anti-Patterns to Reject

1. **One tmux socket for mutually distrustful panes.** Socket access is full server control.
2. **UI-only permission checks.** A compromised webview calls IPC directly.
3. **Arbitrary absolute paths across IPC.** Use Rust-owned opaque handles and canonical roots.
4. **Sidecar token in JavaScript or pane environment.** Keep it in Rust and proxy typed operations.
5. **`allow default` described as a sandbox.** A write-only guard does not stop reads, network, IPC, or credential theft.
6. **Silent fallback from restricted to unrestricted.** Require a new informed decision.
7. **Universal agent argv/auth adapter.** Preserve each CLI's executable, account, config, and network path.
8. **Automatic scrollback sharing.** Read-only is still a confidentiality capability.
9. **Automatic remote install, rcfile edit, agent forwarding, or host-key acceptance.** All require explicit scope and consent.
10. **Remote sidecar on a public interface.** Use remote loopback plus an authenticated SSH tunnel.
11. **Terminal escape output treated as metadata.** Titles, links, clipboard requests, and parser hooks remain untrusted bytes.
12. **Unsigned beta auto-update.** A terminal has too much host authority for an informal distribution chain.

## Phased Release Gates

### Gate 0: boundary repair before feature expansion

- Remove arbitrary `get_env_var` access.
- Fix swarm task filename traversal and add path/symlink adversarial tests.
- Introduce Rust-owned workspace/session handles and root enforcement for every file and process command.
- Keep sidecar tokens in Rust and make server cwd immutable.
- Define Tauri app-command permissions/scopes and test denial from an unauthorized webview/window.
- Remove unused CSP egress; split dev/prod CSP.
- Replace the current OSC extractor with a bounded incremental parser and fuzz it.

**Exit evidence:** abuse-case tests pass; independent code review finds no unrestricted path/env/token primitive from the webview.

### Gate 1: local terminal alpha

- Implement tmux backend behind a terminal-engine interface.
- Prove detach/reattach, app restart, tmux server restart behavior, resizing, UTF-8/binary output, alternate screen, signals, and process exit.
- Use app-private sockets and show which tmux server/session owns each pane.
- Remove Voss environment and repository writes from terminal-only mode.
- Publish the unmanaged terminal trust statement.

**Exit evidence:** 24-hour multi-pane soak, crash/restart recovery, parser corpus/fuzz suite, zero network and zero `.voss` mutations in terminal-only tests.

### Gate 2: managed-agent beta

- Implement isolated tmux security domains and prevent child socket access.
- Complete Linux policy; label macOS policy best-effort; keep Windows unavailable until real enforcement exists.
- Add per-agent filesystem/network/scrollback/input grants and local audit events.
- Require confirmation when a requested enforcement mechanism is absent.
- Add prompt-injection and malicious MCP/plugin fixtures.

**Exit evidence:** adversarial agent cannot read a sibling pane, send keys, reach the tmux socket, write outside scope, read selected host secrets, or reach denied network destinations on a platform claimed “restricted.”

### Gate 3: remote preview

- Reuse OpenSSH config and host verification.
- Add explicit tmux probe/install/rcfile consent and host denylist.
- Reconnect Control Mode without killing remote jobs.
- Disable forwarding and clipboard enhancements by default.
- Bind saved state to host-key identity and distinguish local, WSL, and SSH backends.

**Exit evidence:** disconnect/reconnect and host-key-change tests; compromised-host documentation; no remote mutation when enhancement is declined.

### Gate 4: optional Voss orchestration

- Sidecar starts only on explicit workspace/run action.
- Rust-held, workspace-scoped, revocable token; remote use only through SSH tunnel.
- Console closure does not kill terminal processes; terminal use never requires Voss auth.
- Audit every orchestration action that writes files, sends pane input, approves a tool, or contacts a model/provider.

**Exit evidence:** terminal regression suite passes with Voss absent, disabled, misconfigured, and uninstalled.

### Gate 5: signed public release

- Green Rust, TypeScript, Playwright, packaging, install, upgrade, rollback, and platform smoke CI.
- Signed/notarized artifacts and signed updater metadata.
- SBOM, provenance, vulnerability response SLA, privacy disclosure, and opt-in telemetry verification.
- Independent security review of IPC, terminal parser, updater, sidecar, path handling, and managed sandbox.

## Evidence Quality and Open Questions

### High confidence

- tmux socket access is full trust: direct maintainer documentation.
- Control Mode is designed for GUI/SSH integration: direct protocol documentation.
- Current Voss IPC/path/sandbox/sidecar findings: direct static inspection with line-level anchors.
- Tauri app commands are globally exposed by default absent an app command manifest: official Tauri documentation.
- OS enforcement is required beyond MCP roots/model policy: official MCP documentation.

### Medium confidence

- Warp, Paneflow, Zellij, and VS Code behavior: official docs and, for open projects, source visibility, but no hands-on comparative penetration testing in this task.
- A per-trust-domain tmux topology is the best product/security balance: strong inference from tmux's socket model, but it needs a performance and compatibility prototype.

### Low confidence or missing evidence

- BridgeSpace security properties beyond its privacy policy and marketing/docs; no public independent audit or detailed technical threat model was found.
- Practical strength and forward compatibility of macOS Seatbelt policies for arbitrary third-party CLI agents.
- Native Windows managed-agent isolation compatible with normal developer tooling.
- Actual Voss behavior under hostile OSC/DCS streams, webview compromise, symlink races, malicious MCP servers, or a compromised remote host; dedicated testing is still required.

## Source Index

### Terminal, tmux, SSH

1. [tmux Control Mode](https://github.com/tmux/tmux/wiki/Control-Mode) — control protocol, output encoding, stable pane IDs, SSH suitability.
2. [tmux FAQ](https://github.com/tmux/tmux/wiki/FAQ) — socket trust model and environment behavior.
3. [tmux 3.6b / CVE-2026-11623](https://seclists.org/oss-sec/2026/q2/934) — current security-relevant crash fix.
4. [OpenSSH features](https://www.openssh.org/features.html) — authentication, forwarding, encrypted channels.
5. [OpenSSH security](https://www.openssh.org/security.html) — recent forwarding, agent, host-verification, and timing flaws.
6. [OpenSSH agent restrictions](https://www.openssh.org/agent-restrict.html) — destination-constrained agent design.
7. [xterm.js security](https://xtermjs.org/docs/guides/security/) — webview, keystroke, output, parser, and WebSocket risks.
8. [xterm.js link handling](https://xtermjs.org/docs/guides/link-handling/) — OSC 8 and activation behavior.
9. [tmux clipboard](https://github.com/tmux/tmux/wiki/Clipboard) — OSC 52 forwarding and emulator differences.
10. [Ghostty OSC 52](https://ghostty.org/docs/vt/osc/52) — clipboard read/write protocol semantics.
11. [NVD CVE-2024-28085](https://nvd.nist.gov/vuln/detail/CVE-2024-28085) — escape-sequence injection impact.
12. [Ubuntu USN-6719-1](https://ubuntu.com/security/notices/USN-6719-1) — vendor confirmation and remediation.

### Product and remote architecture

13. [Warp SSH](https://docs.warp.dev/terminal/warpify/ssh) — tmux Control Mode, install consent, decline path, denylist.
14. [Warp SSH feature support](https://docs.warp.dev/code/ssh-feature-support) — explicit remote feature limitations.
15. [Warp privacy](https://docs.warp.dev/support-and-community/privacy-and-security/privacy) — telemetry table, opt-out, network log.
16. [BridgeSpace docs](https://docs.bridgemind.ai/docs/bridgespace) — product terminal and agent claims.
17. [BridgeMind privacy policy](https://www.bridgemind.ai/privacy-policy) — local capabilities and AI/context processing disclosures.
18. [Paneflow overview](https://paneflow.dev/) — local CLI execution and read-only cross-pane MCP.
19. [Paneflow docs](https://paneflow.dev/docs) — independent CLI auth/provider/network path and platform support.
20. [VS Code Remote SSH](https://code.visualstudio.com/docs/remote/ssh) — remote server, secure tunnel, socket option, limitations.
21. [VS Code remote extension architecture](https://code.visualstudio.com/api/advanced-topics/remote-extensions) — local/remote execution boundary.
22. [VS Code Workspace Trust](https://code.visualstudio.com/docs/editing/workspaces/workspace-trust) — untrusted repo, terminal, task, and agent controls.
23. [VS Code agent trust and safety](https://code.visualstudio.com/docs/agents/concepts/trust-and-safety) — approvals and OS sandboxing.
24. [VS Code Agent Host](https://code.visualstudio.com/docs/agents/concepts/agent-host) — durable local/remote agent host and authenticated connection.
25. [Zellij plugin permissions](https://zellij.dev/documentation/plugin-api-permissions.html) — granular terminal extension capabilities.

### Framework, protocol, sandbox, distribution

26. [Tauri security model](https://tauri.app/es/security/) — Rust/webview/IPC trust boundary.
27. [Tauri capabilities](https://v2.tauri.app/es/security/capabilities/) — default app-command exposure and capabilities.
28. [Tauri command scopes](https://v2.tauri.app/security/scope/) — application-enforced allow/deny scopes.
29. [Tauri CSP](https://v2.tauri.app/ja/security/csp/) — remote content and XSS mitigation guidance.
30. [Tauri distribution](https://v2.tauri.app/distribute/) — platform packaging/signing requirements.
31. [Tauri updater](https://v2.tauri.app/ja/plugin/updater/) — mandatory update signatures.
32. [bubblewrap](https://github.com/containers/bubblewrap) — sandbox policy responsibilities and `TIOCSTI`/session warning.
33. [Apple App Sandbox](https://developer.apple.com/documentation/security/app-sandbox) — supported macOS sandbox boundary.
34. [Microsoft AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer) — native Windows process/resource isolation.
35. [MCP roots](https://modelcontextprotocol.io/specification/2025-03-26/client/roots) — declared filesystem boundaries.
36. [MCP client concepts](https://modelcontextprotocol.io/docs/learn/client-concepts) — need for OS-level enforcement.
37. [MCP authorization](https://modelcontextprotocol.io/specification/draft/basic/authorization) — audience validation and no token passthrough.
38. [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices) — consent, CSRF, SSRF, confused-deputy controls.
39. [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) — untrusted tool annotations.
40. [MCP ecosystem study](https://arxiv.org/abs/2506.13538) — empirical server security/maintainability findings.
41. [MCPTox](https://arxiv.org/abs/2508.14925) — experimental tool-poisoning benchmark.
42. [Apple Keychain guidance](https://developer.apple.com/documentation/Security/using-the-keychain-to-manage-user-secrets) — encrypted secret storage.
43. [Tauri Stronghold](https://v2.tauri.app/es/plugin/stronghold/) — cross-platform application secret store option.
44. [sandbox-exec man page](https://man.freebsd.org/cgi/man.cgi?manpath=macOS+13.6.5&query=sandbox-exec&sektion=1) — deprecation status of the command-line Seatbelt wrapper.
45. [Tauri macOS signing](https://v2.tauri.app/distribute/sign/macos/) — Developer ID signing and notarization requirements.
46. [Tauri Windows signing](https://v2.tauri.app/ko/distribute/sign/windows/) — Authenticode and SmartScreen distribution requirements.
