use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc, Mutex,
};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use tauri::Emitter;
use voss_app_core::agent_registry::{
    get_active_agents as registry_get_active_agents, global_registry_path, mark_stopped,
    open_registry, register_agent, registry_path, sweep_orphans, update_last_seen_all, AgentEntry,
};
use voss_app_core::appearance::{self, AppearanceSettings};
use voss_app_core::fonts;
use voss_app_core::grid::{self, GridState};
use voss_app_core::keymap::{self, KeymapOverrideFile, KeymapProfile, KeymapValidationResult};
use voss_app_core::layouts::{self, LayoutFile};
use voss_app_core::profiles::{self, ProfileFile};
use voss_app_core::project::{self, ProjectInfo};
use voss_app_core::pty::reader::start_reader;
use voss_app_core::pty::writer::validate_write;
use voss_app_core::pty::{
    foreground, spawn_command_session_managed, spawn_command_session_with_env, spawn_session,
};
use voss_app_core::session::{self, SessionFile};
use voss_app_core::sidecar::{
    python_path, spawn_voss_serve, validate_workspace_cwd, ServeHandshake, VossServe,
};
use voss_app_core::themes::{self, CustomThemeFile};
use voss_app_core::workspaces::{self, WorkspacesIndex};
use voss_app_core::{PtyEvent, PtyRegistry};

#[derive(Debug, Deserialize, Serialize, Clone)]
struct CustomAgent {
    name: String,
    command: String,
}

#[derive(Debug, Deserialize, Serialize, Default)]
struct SettingsFile {
    theme: Option<HashMap<String, String>>,
    custom_agents: Option<Vec<CustomAgent>>,
}

fn settings_path() -> PathBuf {
    // NOTE: build the path manually from home_dir() so it resolves to
    // ~/.config/voss-app/settings.json on every platform (CONTEXT D-08/D-09).
    // The `dirs` crate's platform-native config helper is intentionally NOT
    // used: on macOS it resolves to ~/Library/Application Support, which
    // diverges from the user-facing ~/.config path locked by D-08.
    // See A1-RESEARCH.md Pitfall 8 and A1-UI-SPEC.md Theme Override System Contract.
    dirs::home_dir()
        .unwrap_or_default()
        .join(".config")
        .join("voss-app")
        .join("settings.json")
}

#[tauri::command]
fn get_theme_overrides() -> HashMap<String, String> {
    let path = settings_path();
    if !path.exists() {
        return HashMap::new();
    }
    let raw = match std::fs::read_to_string(&path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[voss-app] failed to read settings: {e}");
            return HashMap::new();
        }
    };
    let settings: SettingsFile = match serde_json::from_str(&raw) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[voss-app] failed to parse settings: {e}");
            return HashMap::new();
        }
    };
    settings.theme.unwrap_or_default()
}

#[tauri::command]
fn load_custom_agents() -> Vec<CustomAgent> {
    let path = settings_path();
    if !path.exists() {
        return Vec::new();
    }
    let raw = match std::fs::read_to_string(&path) {
        Ok(s) => s,
        Err(_) => return Vec::new(),
    };
    let settings: SettingsFile = match serde_json::from_str(&raw) {
        Ok(s) => s,
        Err(_) => return Vec::new(),
    };
    settings.custom_agents.unwrap_or_default()
}

#[tauri::command]
fn save_custom_agents(agents: Vec<CustomAgent>) -> Result<(), String> {
    let path = settings_path();
    let mut settings: SettingsFile = if path.exists() {
        std::fs::read_to_string(&path)
            .ok()
            .and_then(|raw| serde_json::from_str(&raw).ok())
            .unwrap_or_default()
    } else {
        SettingsFile::default()
    };
    settings.custom_agents = Some(agents);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    std::fs::write(&path, json).map_err(|e| e.to_string())?;
    Ok(())
}

// ---- PTY commands ---------------------------------------------------------
// Thin app-level #[tauri::command] wrappers over the voss-app-core `pty`
// public API. They live in the APP crate (not voss-app-core) because
// `tauri::generate_handler!` can only resolve the hidden command helper
// macros generated in the SAME crate — a `pub use` of cross-crate commands
// does not bring those macros into scope. This keeps the frontend's bare
// `invoke('spawn_pty', …)` contract and app-managed `Arc<PtyRegistry>` state.

type Reg<'a> = tauri::State<'a, Arc<PtyRegistry>>;
type AgentRegistryMap = HashMap<PathBuf, Connection>;
type AgentDb<'a> = tauri::State<'a, Mutex<AgentRegistryMap>>;
struct VossServeEntry {
    id: String,
    root: PathBuf,
    serve: VossServe,
}

type VossServeMap<'a> = tauri::State<'a, Mutex<HashMap<String, VossServeEntry>>>;
type VossStreamTasks = Arc<Mutex<HashMap<String, tauri::async_runtime::JoinHandle<()>>>>;
type VossStreamMap<'a> = tauri::State<'a, VossStreamTasks>;

fn ensure_registry<'a>(
    db: &'a Mutex<AgentRegistryMap>,
    workspace_path: Option<&str>,
) -> Result<(std::sync::MutexGuard<'a, AgentRegistryMap>, PathBuf), String> {
    let mut guard = db
        .lock()
        .map_err(|_| "agent registry lock poisoned".to_string())?;
    let path = match workspace_path {
        Some(ws) => {
            let root = std::fs::canonicalize(ws)
                .map_err(|_| "workspace path does not exist".to_string())?;
            registry_path(&root)
        }
        None => global_registry_path(),
    };
    if !guard.contains_key(&path) {
        let conn = open_registry(&path).map_err(|e| e.to_string())?;
        guard.insert(path.clone(), conn);
    }
    Ok((guard, path))
}

fn is_voss_cli_binary(cli_binary: &str) -> bool {
    Path::new(cli_binary)
        .file_name()
        .and_then(|s| s.to_str())
        .is_some_and(|name| name == "voss" || name == "voss.exe")
}

/// Classify whether a Voss CLI invocation is interactive (→ full Textual TUI)
/// or one-shot (→ compact renderer).
///
/// Interactive commands that enter the REPL: `chat`, `resume`, `edit`, and bare
/// `voss` (no subcommand — click group defaults to `chat`).
fn is_interactive_voss_command(cli_args: &[String]) -> bool {
    match cli_args.first().map(|s| s.as_str()) {
        None => true, // bare `voss` → defaults to chat
        Some("chat" | "resume" | "edit") => true,
        _ => false,
    }
}

fn env_for_embedded_cli(
    cli_binary: &str,
    cli_args: &[String],
) -> Vec<(&'static str, &'static str)> {
    if !is_voss_cli_binary(cli_binary) {
        return Vec::new();
    }

    if is_interactive_voss_command(cli_args) {
        return vec![("VOSS_EMBEDDED", "1"), ("VOSS_FORCE_TUI", "1")];
    }

    vec![("VOSS_EMBEDDED", "1"), ("VOSS_RENDERER", "compact")]
}

/// VBUS-03: append the agent-identity slug to an owned env set. Owned
/// `(String, String)` because the slug is dynamic — `env_for_embedded_cli`'s
/// `&'static` return cannot carry it (V17 RESEARCH Pitfall 3).
fn build_env_with_agent_id(
    base: Vec<(String, String)>,
    voss_agent_id: Option<String>,
) -> Vec<(String, String)> {
    let mut env = base;
    if let Some(slug) = voss_agent_id {
        if !slug.is_empty() {
            env.push(("VOSS_AGENT_ID".to_string(), slug));
        }
    }
    env
}

fn clipboard_image_extension(mime_type: &str) -> Option<&'static str> {
    match mime_type.to_ascii_lowercase().as_str() {
        "image/png" => Some("png"),
        "image/jpeg" | "image/jpg" => Some("jpg"),
        "image/gif" => Some("gif"),
        "image/webp" => Some("webp"),
        "image/tiff" => Some("tiff"),
        _ => None,
    }
}

#[tauri::command]
fn save_clipboard_image(bytes: Vec<u8>, mime_type: String) -> Result<String, String> {
    if bytes.is_empty() {
        return Err("clipboard image was empty".to_string());
    }
    let ext = clipboard_image_extension(&mime_type)
        .ok_or_else(|| "unsupported clipboard image type".to_string())?;
    let dir = std::env::temp_dir().join("voss-app-pastes");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let path = dir.join(format!("paste-{}-{nanos}.{ext}", std::process::id()));
    std::fs::write(&path, bytes).map_err(|e| e.to_string())?;
    Ok(path.to_string_lossy().into_owned())
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
async fn spawn_agent(
    on_data: tauri::ipc::Channel<PtyEvent>,
    rows: u16,
    cols: u16,
    cwd: Option<String>,
    cli_binary: String,
    cli_args: Vec<String>,
    session_id: String,
    pane_id: String,
    workspace_path: Option<String>,
    voss_agent_id: Option<String>,
    db: AgentDb<'_>,
    pty_state: Reg<'_>,
) -> Result<String, String> {
    let (mut guard, registry_key) = ensure_registry(db.inner(), workspace_path.as_deref())?;
    let conn = guard
        .get_mut(&registry_key)
        .ok_or_else(|| "agent registry unavailable".to_string())?;

    let embedded_env = env_for_embedded_cli(&cli_binary, &cli_args);
    let full_env = build_env_with_agent_id(
        embedded_env
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect(),
        voss_agent_id,
    );
    let env_refs: Vec<(&str, &str)> = full_env
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();
    let (session, reader, pause_rx) =
        spawn_command_session_with_env(&cli_binary, &cli_args, &env_refs, rows, cols, cwd.clone())
            .map_err(|e| e.to_string())?;
    let registry: Arc<PtyRegistry> = Arc::clone(pty_state.inner());
    let pty_id = registry.insert(session);
    start_reader(pty_id.clone(), reader, pause_rx, on_data, registry);

    let cwd_str = cwd.as_deref().unwrap_or("");
    register_agent(
        conn,
        &pane_id,
        &session_id,
        &cli_binary,
        &cli_args,
        cwd_str,
        None,
        None,
        None,
    )
    .map_err(|e| e.to_string())?;

    Ok(pty_id)
}

/// VCKP-13 managed launch result. `tier` is the EFFECTIVE capability tier:
/// when no sandbox tool exists on this host the requested tier is downgraded
/// to "C" (observe-only) — the UI must never claim enforcement that is not
/// active (T-V14-03).
#[derive(Serialize, Clone)]
struct ManagedSpawnResult {
    pty_id: String,
    tier: String,
    sandboxed: bool,
}

/// VCKP-13: clone of `spawn_agent` that launches the CLI under the OS
/// scope-sandbox (Seatbelt/bwrap) from t0. Identical body except the spawn
/// goes through `spawn_command_session_managed` (per-run profile + wrapped
/// argv) and the effective tier is returned for honest recording. Bridge B
/// sessionId passthrough is preserved.
#[tauri::command]
#[allow(clippy::too_many_arguments)]
async fn spawn_managed_agent(
    on_data: tauri::ipc::Channel<PtyEvent>,
    rows: u16,
    cols: u16,
    cwd: Option<String>,
    cli_binary: String,
    cli_args: Vec<String>,
    session_id: String,
    pane_id: String,
    workspace_path: Option<String>,
    scope: String,
    tier: String,
    voss_agent_id: Option<String>,
    db: AgentDb<'_>,
    pty_state: Reg<'_>,
) -> Result<ManagedSpawnResult, String> {
    let (mut guard, registry_key) = ensure_registry(db.inner(), workspace_path.as_deref())?;
    let conn = guard
        .get_mut(&registry_key)
        .ok_or_else(|| "agent registry unavailable".to_string())?;

    let embedded_env = env_for_embedded_cli(&cli_binary, &cli_args);
    let full_env = build_env_with_agent_id(
        embedded_env
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect(),
        voss_agent_id,
    );
    let env_refs: Vec<(&str, &str)> = full_env
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();
    let ((session, reader, pause_rx), sandboxed) = spawn_command_session_managed(
        &cli_binary,
        &cli_args,
        &env_refs,
        rows,
        cols,
        cwd.clone(),
        &scope,
    )
    .map_err(|e| e.to_string())?;
    let registry: Arc<PtyRegistry> = Arc::clone(pty_state.inner());
    let pty_id = registry.insert(session);
    start_reader(pty_id.clone(), reader, pause_rx, on_data, registry);

    // Roster shows the REAL CLI, not the sandbox launcher argv.
    let cwd_str = cwd.as_deref().unwrap_or("");
    register_agent(
        conn,
        &pane_id,
        &session_id,
        &cli_binary,
        &cli_args,
        cwd_str,
        None,
        None,
        None,
    )
    .map_err(|e| e.to_string())?;

    // Honest tier: sandbox unavailable → downgrade to observe-only.
    let effective_tier = if sandboxed { tier } else { "C".to_string() };
    Ok(ManagedSpawnResult {
        pty_id,
        tier: effective_tier,
        sandboxed,
    })
}

#[cfg(test)]
mod tests {
    use super::{
        authorize_sidecar_cwd, build_env_with_agent_id, clipboard_image_extension,
        decode_sse_frame, ensure_registry, env_for_embedded_cli, is_interactive_voss_command,
        sidecar_url, take_sse_frame, SidecarHandle,
    };
    use voss_app_core::workspaces::{WorkspaceEntry, WorkspacesIndex, CURRENT_WORKSPACES_VERSION};

    fn workspace_index(project_path: Option<String>) -> WorkspacesIndex {
        WorkspacesIndex {
            version: CURRENT_WORKSPACES_VERSION,
            active_workspace_id: Some("workspace-1".into()),
            workspaces: vec![WorkspaceEntry {
                id: "workspace-1".into(),
                name: "Workspace".into(),
                project_path,
                accent_color: "#ff5b1f".into(),
                order: 0,
                active_layout_preset: None,
                pinned_profile: None,
            }],
        }
    }

    #[test]
    fn sidecar_cwd_must_equal_a_registered_project_root() {
        let root = std::env::temp_dir().join(format!(
            "voss-sidecar-auth-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let project = root.join("project");
        let child = project.join("child");
        let other = root.join("other");
        std::fs::create_dir_all(&child).unwrap();
        std::fs::create_dir_all(&other).unwrap();

        let index = workspace_index(Some(project.to_string_lossy().into_owned()));
        assert_eq!(
            authorize_sidecar_cwd(project.to_str().unwrap(), &index).unwrap(),
            std::fs::canonicalize(&project).unwrap()
        );
        assert!(authorize_sidecar_cwd(child.to_str().unwrap(), &index).is_err());
        assert!(authorize_sidecar_cwd(other.to_str().unwrap(), &index).is_err());
        assert!(authorize_sidecar_cwd(project.to_str().unwrap(), &workspace_index(None),).is_err());

        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn sidecar_handle_never_serializes_port_or_token() {
        let value = serde_json::to_value(SidecarHandle {
            sidecar_id: "opaque-id".into(),
        })
        .unwrap();
        assert_eq!(value, serde_json::json!({"sidecarId": "opaque-id"}));
    }

    #[test]
    fn sidecar_url_encodes_path_segments() {
        let url = sidecar_url(1234, &["session", "../other", "events"]).unwrap();
        assert!(!url.as_str().contains("/../"));
        assert!(url.as_str().contains("..%2Fother"));
    }

    #[test]
    fn sidecar_sse_parser_handles_chunked_crlf_frames() {
        let mut buffer =
            b"data: {\"type\":\"thinking\"}\r\n\r\ndata: {\"type\":\"final\"}".to_vec();
        let first = take_sse_frame(&mut buffer).unwrap();
        assert_eq!(
            decode_sse_frame(&first).unwrap()["type"],
            serde_json::json!("thinking")
        );
        assert!(take_sse_frame(&mut buffer).is_none());
    }

    /// VBUS-03 camelCase IPC round-trip guard (V14 AgentEntry lesson): a
    /// serde rename mismatch on `vossAgentId` would arrive here as `None`
    /// and silently skip injection — the Some case pins the env entry shape.
    #[test]
    fn agent_id_env_injected_when_some() {
        let base = vec![("VOSS_EMBEDDED".to_string(), "1".to_string())];
        let env = build_env_with_agent_id(base, Some("claude-1".to_string()));
        assert!(env.contains(&("VOSS_AGENT_ID".to_string(), "claude-1".to_string())));
        assert!(env.contains(&("VOSS_EMBEDDED".to_string(), "1".to_string())));
    }

    #[test]
    fn agent_id_env_absent_when_none_or_empty() {
        let env = build_env_with_agent_id(Vec::new(), None);
        assert!(!env.iter().any(|(k, _)| k == "VOSS_AGENT_ID"));
        let env = build_env_with_agent_id(Vec::new(), Some(String::new()));
        assert!(!env.iter().any(|(k, _)| k == "VOSS_AGENT_ID"));
    }

    const TUI_ENV: [(&str, &str); 2] = [("VOSS_EMBEDDED", "1"), ("VOSS_FORCE_TUI", "1")];
    const COMPACT_ENV: [(&str, &str); 2] = [("VOSS_EMBEDDED", "1"), ("VOSS_RENDERER", "compact")];

    #[test]
    fn interactive_commands_classified_correctly() {
        // Bare voss (no subcommand) defaults to chat
        assert!(is_interactive_voss_command(&[]));
        assert!(is_interactive_voss_command(&["chat".into()]));
        assert!(is_interactive_voss_command(&[
            "chat".into(),
            "--model".into(),
            "gpt-4o".into()
        ]));
        assert!(is_interactive_voss_command(&[
            "resume".into(),
            "session-123".into()
        ]));
        assert!(is_interactive_voss_command(&[
            "edit".into(),
            "file.py".into()
        ]));

        // Non-interactive
        assert!(!is_interactive_voss_command(&["do".into(), "task".into()]));
        assert!(!is_interactive_voss_command(&["doctor".into()]));
        assert!(!is_interactive_voss_command(&[
            "agent".into(),
            "spawn".into()
        ]));
        assert!(!is_interactive_voss_command(&["sessions".into()]));
        assert!(!is_interactive_voss_command(&["config".into()]));
    }

    #[test]
    fn voss_chat_command_gets_embedded_tui_env() {
        let args = vec!["chat".to_string()];
        assert_eq!(env_for_embedded_cli("voss", &args), TUI_ENV);
    }

    #[test]
    fn bare_voss_gets_embedded_tui_env() {
        assert_eq!(env_for_embedded_cli("voss", &[]), TUI_ENV);
    }

    #[test]
    fn voss_resume_gets_embedded_tui_env() {
        let args = vec!["resume".to_string(), "sess-abc".to_string()];
        assert_eq!(env_for_embedded_cli("voss", &args), TUI_ENV);
    }

    #[test]
    fn voss_edit_gets_embedded_tui_env() {
        let args = vec!["edit".to_string(), "main.py".to_string()];
        assert_eq!(env_for_embedded_cli("voss", &args), TUI_ENV);
    }

    #[test]
    fn voss_non_interactive_command_gets_compact_env() {
        let args = vec!["do".to_string(), "task".to_string()];
        assert_eq!(env_for_embedded_cli("voss", &args), COMPACT_ENV);
    }

    #[test]
    fn path_voss_binary_gets_env_but_other_agents_do_not() {
        let chat_args = vec!["chat".to_string()];
        let claude_args = vec!["--model=opus".to_string()];
        assert_eq!(env_for_embedded_cli("/opt/bin/voss", &chat_args), TUI_ENV);
        assert_eq!(env_for_embedded_cli("voss.exe", &chat_args), TUI_ENV);
        assert!(env_for_embedded_cli("claude", &claude_args).is_empty());
    }

    #[test]
    fn clipboard_image_extension_accepts_common_types_only() {
        assert_eq!(clipboard_image_extension("image/png"), Some("png"));
        assert_eq!(clipboard_image_extension("IMAGE/JPEG"), Some("jpg"));
        assert_eq!(clipboard_image_extension("image/webp"), Some("webp"));
        assert_eq!(clipboard_image_extension("text/plain"), None);
    }

    #[test]
    fn save_clipboard_image_writes_temp_file() {
        let path = super::save_clipboard_image(vec![1, 2, 3], "image/png".into()).unwrap();
        let path = PathBuf::from(path);
        assert_eq!(path.extension().and_then(|s| s.to_str()), Some("png"));
        assert_eq!(fs::read(&path).unwrap(), vec![1, 2, 3]);
        fs::remove_file(path).ok();
    }

    // ---- V11 ADE org integration data-layer tests --------------------------
    use std::fs;
    use std::path::PathBuf;
    use std::time::SystemTime;

    /// Unique temp dir without pulling in the `tempfile` crate (no new deps).
    fn unique_tmp(tag: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("voss_test_{tag}_{}_{}", std::process::id(), nanos))
    }

    #[test]
    fn registries_are_keyed_by_canonical_workspace() {
        let base = unique_tmp("registries");
        let first = base.join("first");
        let second = base.join("second");
        fs::create_dir_all(&first).unwrap();
        fs::create_dir_all(&second).unwrap();
        let registries = std::sync::Mutex::new(std::collections::HashMap::new());

        let (guard, first_key) =
            ensure_registry(&registries, first.to_str()).expect("first registry");
        drop(guard);
        let (guard, second_key) =
            ensure_registry(&registries, second.to_str()).expect("second registry");
        assert_ne!(first_key, second_key);
        assert_eq!(guard.len(), 2);
        drop(guard);

        fs::remove_dir_all(base).ok();
    }

    #[test]
    fn enumerate_runs_filters_flat_session_files() {
        let base = unique_tmp("enum");
        let sessions = base.join(".voss").join("sessions");
        let run_dir = sessions.join("abc123run456");
        fs::create_dir_all(&run_dir).unwrap();
        fs::write(run_dir.join("node1.json"), "{}").unwrap();
        // Legacy flat SessionRecord (Pitfall 1) — must be excluded.
        fs::write(sessions.join("legacyflat999.json"), "{}").unwrap();

        let runs = super::enumerate_runs(base.to_string_lossy().into_owned());
        let ids: Vec<String> = runs.iter().map(|r| r.run_id.clone()).collect();
        assert_eq!(ids, vec!["abc123run456".to_string()]);

        fs::remove_dir_all(&base).ok();
    }

    #[test]
    fn load_run_rejects_traversal() {
        let res = super::load_run("../etc".into(), "/tmp".into(), "voss".into());
        assert!(res.is_err());
    }

    #[cfg(unix)]
    #[test]
    fn run_decision_captures_nonzero_exit() {
        use std::os::unix::fs::PermissionsExt;
        let base = unique_tmp("decision");
        fs::create_dir_all(&base).unwrap();
        // Fake `voss` binary (filename passes is_voss_cli_binary) that exits 3.
        let fake = base.join("voss");
        fs::write(&fake, "#!/bin/sh\nexit 3\n").unwrap();
        fs::set_permissions(&fake, fs::Permissions::from_mode(0o755)).unwrap();

        let res = super::run_decision(
            fake.to_string_lossy().into_owned(),
            base.to_string_lossy().into_owned(),
            vec!["audit".into(), "deadbeef1234".into(), "--approve".into()],
        )
        .unwrap();
        assert!(!res.success);
        assert_eq!(res.exit_code, 3);

        fs::remove_dir_all(&base).ok();
    }
}

#[tauri::command]
fn get_active_agents(
    workspace_path: Option<String>,
    db: AgentDb<'_>,
) -> Result<Vec<AgentEntry>, String> {
    let Ok((mut guard, registry_key)) = ensure_registry(db.inner(), workspace_path.as_deref())
    else {
        return Ok(Vec::new());
    };
    let Some(conn) = guard.get_mut(&registry_key) else {
        return Ok(Vec::new());
    };
    Ok(registry_get_active_agents(conn).unwrap_or_else(|e| {
        eprintln!("[voss-app] get_active_agents failed: {e}");
        Vec::new()
    }))
}

#[tauri::command]
fn mark_agent_stopped(
    pane_id: String,
    workspace_path: Option<String>,
    db: AgentDb<'_>,
) -> Result<(), String> {
    let (mut guard, registry_key) = ensure_registry(db.inner(), workspace_path.as_deref())?;
    let conn = guard
        .get_mut(&registry_key)
        .ok_or_else(|| "agent registry unavailable".to_string())?;
    mark_stopped(conn, &pane_id).map_err(|e| e.to_string())
}

#[tauri::command]
fn update_agents_last_seen(workspace_path: Option<String>, db: AgentDb<'_>) -> Result<(), String> {
    let (mut guard, registry_key) = ensure_registry(db.inner(), workspace_path.as_deref())?;
    let conn = guard
        .get_mut(&registry_key)
        .ok_or_else(|| "agent registry unavailable".to_string())?;
    update_last_seen_all(conn).map_err(|e| e.to_string())
}

#[tauri::command]
fn sweep_orphan_agents(
    valid_pane_ids: Vec<String>,
    workspace_path: Option<String>,
    db: AgentDb<'_>,
) -> Result<usize, String> {
    let (mut guard, registry_key) = ensure_registry(db.inner(), workspace_path.as_deref())?;
    let conn = guard
        .get_mut(&registry_key)
        .ok_or_else(|| "agent registry unavailable".to_string())?;
    sweep_orphans(conn, &valid_pane_ids).map_err(|e| e.to_string())
}

#[tauri::command]
async fn spawn_pty(
    on_data: tauri::ipc::Channel<PtyEvent>,
    rows: u16,
    cols: u16,
    cwd: Option<String>,
    state: Reg<'_>,
) -> Result<String, String> {
    let (session, reader, pause_rx) = spawn_session(rows, cols, cwd).map_err(|e| e.to_string())?;
    let registry: Arc<PtyRegistry> = Arc::clone(state.inner());
    let id = registry.insert(session);
    start_reader(id.clone(), reader, pause_rx, on_data, registry);
    Ok(id)
}

#[tauri::command]
async fn pty_write(session_id: String, data: Vec<u8>, state: Reg<'_>) -> Result<(), String> {
    validate_write(&data)?;
    let session = state.get(&session_id).ok_or("unknown session")?;
    session.write(&data).map_err(|e| e.to_string())
}

#[tauri::command]
async fn pty_resize(
    session_id: String,
    rows: u16,
    cols: u16,
    state: Reg<'_>,
) -> Result<(), String> {
    let session = state.get(&session_id).ok_or("unknown session")?;
    session.resize(rows, cols).map_err(|e| e.to_string())
}

#[tauri::command]
async fn pty_pause(session_id: String, state: Reg<'_>) -> Result<(), String> {
    let session = state.get(&session_id).ok_or("unknown session")?;
    session.set_paused(true).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn pty_resume(session_id: String, state: Reg<'_>) -> Result<(), String> {
    let session = state.get(&session_id).ok_or("unknown session")?;
    session.set_paused(false).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn pty_kill(session_id: String, state: Reg<'_>) -> Result<(), String> {
    let session = state.get(&session_id).ok_or("unknown session")?;
    session.kill().map_err(|e| e.to_string())?;
    state.remove(&session_id);
    Ok(())
}

#[tauri::command]
async fn get_fg_process(session_id: String, state: Reg<'_>) -> Result<Option<String>, String> {
    let session = state.get(&session_id).ok_or("unknown session")?;
    let fd = match session.master_raw_fd() {
        Some(fd) => fd,
        None => return Ok(None),
    };
    Ok(foreground::get_foreground_name(fd))
}

// ---- Appearance settings + fonts (A8-04) ------------------------------------

#[tauri::command]
fn load_appearance_settings() -> AppearanceSettings {
    appearance::load_appearance_settings()
}

#[tauri::command]
fn save_appearance_settings(settings: AppearanceSettings) -> Result<(), String> {
    appearance::save_appearance_settings(&settings).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_system_fonts() -> Vec<String> {
    fonts::list_system_fonts()
}

// ---- Grid mirror commands (GRD-08) ----------------------------------------
// Thin app-level wrappers delegating to voss-app-core's plain `grid::overwrite`
// / `grid::snapshot` — same cross-crate `generate_handler!` constraint as the
// PTY commands above (the core's own `#[tauri::command]` macros are not in
// scope here). In-memory mirror only; zero disk I/O.

type GridSlot<'a> = tauri::State<'a, Mutex<GridState>>;

#[tauri::command]
fn sync_grid(state: GridSlot<'_>, new_state: GridState) -> Result<(), String> {
    grid::overwrite(state.inner(), new_state)
}

#[tauri::command]
fn get_grid(state: GridSlot<'_>) -> Result<GridState, String> {
    grid::snapshot(state.inner())
}

// ---- Layout persistence commands (A4-03, LAY-06/07) -----------------------
// Thin app-level wrappers over `voss_app_core::layouts`. Same cross-crate
// `generate_handler!` constraint as the PTY and grid commands above — the
// core's own `#[tauri::command]` macros are not in scope here.
//
// `workspace_path` is the absolute path to the open project root; the
// frontend resolves it via the A5 project-open seam (until A5 lands the
// frontend passes the CWD of the focused pane or the user's home).
// Errors propagate as `LayoutError`'s Display strings — those match the
// A4-UI-SPEC error copy exactly, so the renderer can surface them
// verbatim.

#[tauri::command]
fn save_layout(workspace_path: String, name: String, layout: LayoutFile) -> Result<(), String> {
    layouts::save_layout(Path::new(&workspace_path), &name, &layout).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_layout(workspace_path: String, name: String) -> Result<LayoutFile, String> {
    layouts::load_layout(Path::new(&workspace_path), &name).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_layouts(workspace_path: String) -> Result<Vec<String>, String> {
    layouts::list_layouts(Path::new(&workspace_path)).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_default_layout(workspace_path: String) -> Result<Option<LayoutFile>, String> {
    layouts::load_default_layout(Path::new(&workspace_path)).map_err(|e| e.to_string())
}

// ---- Context pin commands (F4-04) -------------------------------------------
// Write .voss/context-pins.json atomically (write-then-rename). The harness
// reads this file at iteration start (F4 D-20). ADE is the sole writer.

#[tauri::command]
fn write_context_pins(workspace_path: String, pinned_paths: Vec<String>) -> Result<(), String> {
    let voss_dir = Path::new(&workspace_path).join(".voss");
    std::fs::create_dir_all(&voss_dir).map_err(|e| e.to_string())?;
    let target = voss_dir.join("context-pins.json");
    let tmp = voss_dir.join("context-pins.json.tmp");
    let payload = serde_json::json!({ "pinned": pinned_paths });
    std::fs::write(&tmp, payload.to_string()).map_err(|e| e.to_string())?;
    std::fs::rename(&tmp, &target).map_err(|e| e.to_string())?;
    Ok(())
}

// ---- Swarm orchestration commands (A13) -------------------------------------

const SWARM_RESULT_EVENT: &str = "voss://swarm-result-added";

#[derive(Default)]
struct SwarmWatchState {
    stops: Mutex<HashMap<String, Arc<AtomicBool>>>,
}

fn emit_new_swarm_results(
    app: &tauri::AppHandle,
    swarm_id: &str,
    results_path: &Path,
    known: &mut HashSet<String>,
) {
    let entries = match std::fs::read_dir(results_path) {
        Ok(entries) => entries,
        Err(_) => return,
    };
    for entry in entries.filter_map(|entry| entry.ok()) {
        let is_file = entry
            .file_type()
            .map(|file_type| file_type.is_file())
            .unwrap_or(false);
        if !is_file {
            continue;
        }
        let filename = entry.file_name().to_string_lossy().into_owned();
        if !filename.ends_with(".result.md") || !known.insert(filename.clone()) {
            continue;
        }
        let payload = serde_json::json!({
            "swarmId": swarm_id,
            "resultFile": filename,
        });
        if let Err(e) = app.emit(SWARM_RESULT_EVENT, payload) {
            eprintln!("[voss-app] swarm result event failed: {e}");
        }
    }
}

#[tauri::command]
fn watch_swarm_results(
    app: tauri::AppHandle,
    state: tauri::State<'_, SwarmWatchState>,
    swarm_id: String,
    results_dir: String,
) -> Result<(), String> {
    let stop = Arc::new(AtomicBool::new(false));
    let previous = state
        .stops
        .lock()
        .map_err(|_| "could not watch swarm results".to_string())?
        .insert(swarm_id.clone(), Arc::clone(&stop));
    if let Some(previous) = previous {
        previous.store(true, Ordering::Relaxed);
    }

    let results_path = PathBuf::from(results_dir);
    std::thread::spawn(move || {
        let mut known = HashSet::new();
        emit_new_swarm_results(&app, &swarm_id, &results_path, &mut known);

        while !stop.load(Ordering::Relaxed) {
            std::thread::sleep(Duration::from_millis(500));
            emit_new_swarm_results(&app, &swarm_id, &results_path, &mut known);
        }
    });

    Ok(())
}

#[tauri::command]
fn stop_swarm_watcher(
    state: tauri::State<'_, SwarmWatchState>,
    swarm_id: String,
) -> Result<(), String> {
    if let Some(stop) = state
        .stops
        .lock()
        .map_err(|_| "could not stop swarm watcher".to_string())?
        .remove(&swarm_id)
    {
        stop.store(true, Ordering::Relaxed);
    }
    Ok(())
}

// ---- Project open commands (A5-02) ----------------------------------------
// Thin app-level wrappers over `voss_app_core::project`. Same cross-crate
// `generate_handler!` constraint as the PTY, grid, and layout commands above.

#[tauri::command]
fn open_project(path: String) -> Result<ProjectInfo, String> {
    project::open_project(Path::new(&path)).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_recents() -> Vec<String> {
    project::list_recents()
}

#[tauri::command]
fn default_cwd(project_path: Option<String>) -> String {
    project::default_cwd(project_path.as_deref().map(Path::new))
}

// ---- Session persistence commands (A6-01) -----------------------------------
// Thin app-level wrappers over `voss_app_core::session`. Same cross-crate
// `generate_handler!` constraint as the PTY, grid, layout, and project
// commands above. Project commands take `workspace_path`; global commands
// take no path argument.

#[tauri::command]
fn save_session(workspace_path: String, session: SessionFile) -> Result<(), String> {
    session::save_session(Path::new(&workspace_path), &session).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_session(workspace_path: String) -> Result<Option<SessionFile>, String> {
    session::load_session(Path::new(&workspace_path)).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_global_session(session: SessionFile) -> Result<(), String> {
    session::save_global_session(&session).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_global_session() -> Result<Option<SessionFile>, String> {
    session::load_global_session().map_err(|e| e.to_string())
}

// ---- Workspace index + project-less sessions (A8-02) ------------------------
// Thin wrappers over `voss_app_core::workspaces` and extended session paths.

#[tauri::command]
fn load_workspaces_index() -> WorkspacesIndex {
    workspaces::load_workspaces_index()
}

#[tauri::command]
fn save_workspaces_index(index: WorkspacesIndex) -> Result<(), String> {
    workspaces::save_workspaces_index(&index).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_workspaces() -> Vec<workspaces::WorkspaceEntry> {
    workspaces::list_workspaces()
}

#[tauri::command]
fn save_project_less_session(workspace_id: String, session: SessionFile) -> Result<(), String> {
    session::save_project_less_session(&workspace_id, &session).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_project_less_session(workspace_id: String) -> Result<Option<SessionFile>, String> {
    session::load_project_less_session(&workspace_id).map_err(|e| e.to_string())
}

// ---- Keymap commands (A7-03) ------------------------------------------------
// Thin wrappers over `voss_app_core::keymap`. Profile persistence uses
// `settings.json`; workspace overrides use `.voss/keymap.json`.

const KEYMAP_UPDATED_EVENT: &str = "voss://keymap-updated";

#[derive(Default)]
struct KeymapWatchState {
    stops: Mutex<HashMap<PathBuf, Arc<AtomicBool>>>,
}

#[derive(Debug, PartialEq)]
struct KeymapFileStamp {
    exists: bool,
    modified: Option<SystemTime>,
    len: Option<u64>,
}

fn keymap_file_stamp(path: &Path) -> KeymapFileStamp {
    match std::fs::metadata(path) {
        Ok(metadata) => KeymapFileStamp {
            exists: true,
            modified: metadata.modified().ok(),
            len: Some(metadata.len()),
        },
        Err(_) => KeymapFileStamp {
            exists: false,
            modified: None,
            len: None,
        },
    }
}

#[tauri::command]
fn load_keymap_profile() -> String {
    let profile = keymap::load_keymap_profile();
    serde_json::to_string(&profile).unwrap_or_else(|_| "\"vscode\"".into())
}

#[tauri::command]
fn save_keymap_profile(profile: KeymapProfile) -> Result<(), String> {
    keymap::save_keymap_profile(&profile).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_keymap_overrides(workspace_path: String) -> Option<KeymapOverrideFile> {
    keymap::load_keymap_overrides(Path::new(&workspace_path))
}

#[tauri::command]
fn validate_keymap_overrides(
    overrides: KeymapOverrideFile,
    known_command_ids: Vec<String>,
    known_chords: Vec<String>,
) -> KeymapValidationResult {
    keymap::validate_keymap_overrides(&overrides, &known_command_ids, &known_chords)
}

#[tauri::command]
fn watch_keymap_overrides(
    app: tauri::AppHandle,
    state: tauri::State<'_, KeymapWatchState>,
    workspace_path: String,
    known_command_ids: Vec<String>,
    known_chords: Vec<String>,
) -> Result<KeymapValidationResult, String> {
    let workspace = PathBuf::from(workspace_path);
    let keymap_path = keymap::keymap_override_path(&workspace);
    let initial =
        keymap::validate_workspace_keymap_overrides(&workspace, &known_command_ids, &known_chords);

    let stop = Arc::new(AtomicBool::new(false));
    let previous = state
        .stops
        .lock()
        .map_err(|_| "could not watch keymap settings".to_string())?
        .insert(workspace.clone(), Arc::clone(&stop));
    if let Some(previous) = previous {
        previous.store(true, Ordering::Relaxed);
    }

    std::thread::spawn(move || {
        let mut last = keymap_file_stamp(&keymap_path);
        while !stop.load(Ordering::Relaxed) {
            std::thread::sleep(Duration::from_millis(500));
            let next = keymap_file_stamp(&keymap_path);
            if next == last {
                continue;
            }
            last = next;
            std::thread::sleep(Duration::from_millis(75));
            let payload = keymap::validate_workspace_keymap_overrides(
                &workspace,
                &known_command_ids,
                &known_chords,
            );
            if let Err(e) = app.emit(KEYMAP_UPDATED_EVENT, payload) {
                eprintln!("[voss-app] keymap update event failed: {e}");
            }
        }
    });

    Ok(initial)
}

// ---- Theme persistence commands (A8-01) -------------------------------------
// Thin wrappers over `voss_app_core::themes`. Custom themes live under
// `<workspace>/.voss/themes/`; active theme id is in `settings.json`.

#[tauri::command]
fn list_custom_themes(workspace_path: String) -> Vec<String> {
    themes::list_custom_themes(Path::new(&workspace_path))
}

#[tauri::command]
fn load_custom_theme(workspace_path: String, name: String) -> Option<CustomThemeFile> {
    themes::load_custom_theme(Path::new(&workspace_path), &name)
}

#[tauri::command]
fn save_custom_theme(
    workspace_path: String,
    name: String,
    theme: CustomThemeFile,
) -> Result<(), String> {
    themes::save_custom_theme(Path::new(&workspace_path), &name, &theme).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_active_theme_id() -> Option<String> {
    themes::load_active_theme_id()
}

#[tauri::command]
fn save_active_theme_id(id: Option<String>) -> Result<(), String> {
    themes::save_active_theme_id(id.as_deref()).map_err(|e| e.to_string())
}

// ---- Profile persistence commands (A8-01) -----------------------------------
// Thin wrappers over `voss_app_core::profiles`. Snapshots live at
// `~/.config/voss-app/profiles/`; active profile id is in `settings.json`.

#[tauri::command]
fn list_profiles() -> Vec<String> {
    profiles::list_profiles()
}

#[tauri::command]
fn load_profile(name: String) -> Option<ProfileFile> {
    profiles::load_profile(&name)
}

#[tauri::command]
fn save_profile(name: String, profile: ProfileFile) -> Result<(), String> {
    profiles::save_profile(&name, &profile).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_active_profile_id() -> Option<String> {
    profiles::load_active_profile_id()
}

#[tauri::command]
fn save_active_profile_id(id: Option<String>) -> Result<(), String> {
    profiles::save_active_profile_id(id.as_deref()).map_err(|e| e.to_string())
}

// ---- File tree commands (A12-07) -------------------------------------------

#[derive(Debug, serde::Serialize)]
struct DirEntry {
    name: String,
    is_dir: bool,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    children: Vec<DirEntry>,
}

const SKIP_DIRS: &[&str] = &[
    "node_modules",
    "target",
    ".git",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".venv",
    ".tox",
    ".mypy_cache",
];

fn read_dir_shallow(path: &std::path::Path, depth: u32) -> Vec<DirEntry> {
    if depth == 0 {
        return Vec::new();
    }
    let rd = match std::fs::read_dir(path) {
        Ok(rd) => rd,
        Err(_) => return Vec::new(),
    };
    let mut entries: Vec<DirEntry> = rd
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let name = e.file_name().to_string_lossy().into_owned();
            // Skip hidden files/dirs
            if name.starts_with('.') {
                return None;
            }
            let is_dir = e.file_type().map(|t| t.is_dir()).unwrap_or(false);
            // Skip noise directories
            if is_dir && SKIP_DIRS.contains(&name.as_str()) {
                return None;
            }
            let children = if is_dir && depth > 1 {
                read_dir_shallow(&e.path(), depth - 1)
            } else {
                Vec::new()
            };
            Some(DirEntry {
                name,
                is_dir,
                children,
            })
        })
        .collect();
    // Sort: dirs first, then alphabetical
    entries.sort_by(|a, b| b.is_dir.cmp(&a.is_dir).then(a.name.cmp(&b.name)));
    entries
}

#[tauri::command]
fn list_dir(path: String) -> Result<Vec<DirEntry>, String> {
    let canonical = std::fs::canonicalize(&path).map_err(|e| e.to_string())?;
    Ok(read_dir_shallow(&canonical, 2))
}

#[derive(Debug, serde::Serialize)]
struct GitCommit {
    hash: String,
    message: String,
    timestamp_secs: i64,
}

#[tauri::command]
fn git_log(workspace_path: String, limit: usize) -> Result<Vec<GitCommit>, String> {
    let output = std::process::Command::new("git")
        .args([
            "-C",
            &workspace_path,
            "log",
            &format!("-{}", limit),
            "--format=%H %ct %s",
        ])
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        // Not a git repo or other git error — return empty gracefully
        return Ok(Vec::new());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let commits: Vec<GitCommit> = stdout
        .lines()
        .filter(|line| !line.is_empty())
        .filter_map(|line| {
            let mut parts = line.splitn(3, ' ');
            let hash = parts.next()?.to_string();
            let ts: i64 = parts.next()?.parse().ok()?;
            let message = parts.next().unwrap_or("").to_string();
            Some(GitCommit {
                hash,
                message,
                timestamp_secs: ts,
            })
        })
        .collect();

    Ok(commits)
}

// ---- ADE org integration commands (V11) ------------------------------------
// The single CLI-JSON data path for the org view. `load_run` aggregates a run's
// node files + review sidecars + audit JSON + run-final into one typed payload
// (D-01). `enumerate_runs` discovers V4+ session-tree dirs only (D-03).
// `run_decision` shells the voss CLI — the sole non-interactive write path —
// and captures stdout/stderr/exit (D-08). No `.voss/sessions` parsing happens
// in the frontend.

#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct RunData {
    run_id: String,
    session_tree: serde_json::Value,
    review: serde_json::Value,
    audit: serde_json::Value,
    run_final: serde_json::Value,
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
struct RunEntry {
    run_id: String,
    mtime_secs: u64,
    has_run_final: bool,
}

#[derive(Debug, serde::Serialize)]
struct DecisionResult {
    success: bool,
    stdout: String,
    stderr: String,
    exit_code: i32,
}

/// Reject run_ids that could escape the sessions directory (T-V11-03).
fn is_safe_run_id(run_id: &str) -> bool {
    !run_id.is_empty() && !run_id.contains('/') && !run_id.contains('\\') && !run_id.contains("..")
}

fn sessions_dir(cwd: &str) -> PathBuf {
    Path::new(cwd).join(".voss").join("sessions")
}

#[tauri::command]
fn load_run(run_id: String, cwd: String, cli_binary: String) -> Result<RunData, String> {
    // Path traversal guard BEFORE any filesystem access (mirror audit_cmd).
    if !is_safe_run_id(&run_id) {
        return Err(format!("invalid run_id: {run_id}"));
    }
    let run_dir = sessions_dir(&cwd).join(&run_id);
    if !run_dir.is_dir() {
        return Err(format!("run not found: {run_id}"));
    }

    // (a) node `.json` files (exclude run-final.json + *.review.json) and
    // (b) `*.review.json` sidecars keyed by node id — direct Rust read per
    // RESEARCH Open-Q2 (`voss board` has no JSON output; no session subprocess).
    let mut node_files: Vec<PathBuf> = Vec::new();
    let mut review = serde_json::Map::new();
    if let Ok(rd) = std::fs::read_dir(&run_dir) {
        for entry in rd.filter_map(|e| e.ok()) {
            let name = entry.file_name().to_string_lossy().into_owned();
            if !name.ends_with(".json") || name == "run-final.json" {
                continue;
            }
            if name.ends_with(".review.json") {
                if let Ok(raw) = std::fs::read_to_string(entry.path()) {
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
                        let node_id = name.trim_end_matches(".review.json").to_string();
                        review.insert(node_id, val);
                    }
                }
                continue;
            }
            node_files.push(entry.path());
        }
    }
    node_files.sort();
    let mut nodes: Vec<serde_json::Value> = Vec::new();
    for path in node_files {
        if let Ok(raw) = std::fs::read_to_string(&path) {
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
                nodes.push(val);
            }
        }
    }
    let session_tree = serde_json::json!({ "root_id": run_id, "nodes": nodes });

    // (c) audit section: shell `voss audit <run_id> --cwd <cwd> --format json`
    // via Command::args (NOT a shell string — T-V11-04). Degrade to null.
    let audit = match std::process::Command::new(&cli_binary)
        .args([
            "audit",
            run_id.as_str(),
            "--cwd",
            cwd.as_str(),
            "--format",
            "json",
        ])
        .output()
    {
        Ok(out) if out.status.success() => serde_json::from_slice::<serde_json::Value>(&out.stdout)
            .unwrap_or(serde_json::Value::Null),
        _ => serde_json::Value::Null,
    };

    // (d) optional run-final.json (Pitfall 5 — absence tolerated).
    let run_final = std::fs::read_to_string(run_dir.join("run-final.json"))
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .unwrap_or(serde_json::Value::Null);

    Ok(RunData {
        run_id,
        session_tree,
        review: serde_json::Value::Object(review),
        audit,
        run_final,
    })
}

#[tauri::command]
fn enumerate_runs(cwd: String) -> Vec<RunEntry> {
    let dir = sessions_dir(&cwd);
    let rd = match std::fs::read_dir(&dir) {
        Ok(rd) => rd,
        Err(_) => return Vec::new(),
    };
    let mut entries: Vec<RunEntry> = rd
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            // Pitfall 1: flat `.json` files are legacy SessionRecords, not runs.
            let is_dir = e.file_type().map(|t| t.is_dir()).unwrap_or(false);
            if !is_dir {
                return None;
            }
            let path = e.path();
            // Require at least one node `.json` file inside (V4+ session tree).
            let has_node = std::fs::read_dir(&path)
                .ok()?
                .filter_map(|f| f.ok())
                .any(|f| {
                    let n = f.file_name().to_string_lossy().into_owned();
                    n.ends_with(".json") && n != "run-final.json"
                });
            if !has_node {
                return None;
            }
            let mtime_secs = e
                .metadata()
                .ok()
                .and_then(|m| m.modified().ok())
                .and_then(|t| t.duration_since(SystemTime::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
                .unwrap_or(0);
            Some(RunEntry {
                run_id: e.file_name().to_string_lossy().into_owned(),
                mtime_secs,
                has_run_final: path.join("run-final.json").is_file(),
            })
        })
        .collect();
    entries.sort_by_key(|e| std::cmp::Reverse(e.mtime_secs));
    entries
}

#[tauri::command]
fn run_decision(
    cli_binary: String,
    cwd: String,
    args: Vec<String>,
) -> Result<DecisionResult, String> {
    // Only the voss CLI may be exec'd (T-V11-06).
    if !is_voss_cli_binary(&cli_binary) {
        return Err(format!("not a voss CLI binary: {cli_binary}"));
    }
    // Validate run_id-shaped positionals — reject traversal (T-V11-03).
    for arg in &args {
        if arg.starts_with('-') {
            continue;
        }
        if arg.contains('/') || arg.contains('\\') || arg.contains("..") {
            return Err(format!("invalid argument: {arg}"));
        }
    }
    // Command::args(vector) — never shell string interpolation (T-V11-04).
    let output = std::process::Command::new(&cli_binary)
        .args(&args)
        .current_dir(&cwd)
        .output()
        .map_err(|e| e.to_string())?;
    Ok(DecisionResult {
        success: output.status.success(),
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
        exit_code: output.status.code().unwrap_or(-1),
    })
}

// ---- voss serve sidecar (V15) ----------------------------------------------
// VLIVE-01: lazily spawn one `voss serve` per workspace cwd, reuse it while
// alive, and reap all on app exit (map entries drop with the managed state —
// kill_on_drop, T-V15-02). Only the Tauri side can spawn the server (V14
// Pitfall 4 — the webview launcher imports node:child_process).

fn authorize_sidecar_cwd(cwd: &str, index: &WorkspacesIndex) -> Result<PathBuf, String> {
    let canonical = validate_workspace_cwd(cwd, &[])?;
    let registered = index
        .workspaces
        .iter()
        .filter_map(|workspace| workspace.project_path.as_deref())
        .filter_map(|path| std::fs::canonicalize(path).ok())
        .any(|path| path == canonical);
    if !registered {
        return Err("workspace is not a registered project".to_string());
    }
    Ok(canonical)
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct SidecarHandle {
    sidecar_id: String,
}

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum SidecarOperation {
    CreateSession,
    ListSessions,
    ListSaved,
    GetSession {
        session_id: String,
    },
    DeleteSession {
        session_id: String,
    },
    PostMessage {
        session_id: String,
        text: String,
        mode: String,
    },
    AbortSession {
        session_id: String,
    },
    GetCost {
        session_id: String,
    },
    Doctor,
    ReplyPermission {
        session_id: String,
        id: String,
        choice: String,
    },
    Memory {
        query: Option<String>,
        top_k: u32,
    },
    GetSwarm {
        swarm_id: String,
    },
    CreateSwarm {
        goal: String,
        builders: u32,
        roster: Option<Vec<serde_json::Value>>,
    },
    RunSwarm {
        swarm_id: String,
    },
}

#[derive(Clone, Serialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum SidecarStreamEvent {
    Event { event: serde_json::Value },
    End,
    Error { message: String },
}

fn sidecar_connection(
    sidecar_id: &str,
    state: &Mutex<HashMap<String, VossServeEntry>>,
) -> Result<(ServeHandshake, PathBuf), String> {
    let map = state.lock().map_err(|_| "lock poisoned".to_string())?;
    map.values()
        .find(|entry| entry.id == sidecar_id && entry.serve.pid().is_some())
        .map(|entry| (entry.serve.handshake.clone(), entry.root.clone()))
        .ok_or_else(|| "sidecar handle is unavailable".to_string())
}

fn sidecar_url(port: u16, segments: &[&str]) -> Result<reqwest::Url, String> {
    let mut url = reqwest::Url::parse(&format!("http://127.0.0.1:{port}"))
        .map_err(|_| "invalid sidecar endpoint".to_string())?;
    {
        let mut path = url
            .path_segments_mut()
            .map_err(|_| "invalid sidecar endpoint".to_string())?;
        path.clear();
        path.extend(segments);
    }
    Ok(url)
}

async fn send_sidecar_request(
    token: &str,
    request: reqwest::RequestBuilder,
) -> Result<serde_json::Value, String> {
    let response = request
        .bearer_auth(token)
        .send()
        .await
        .map_err(|_| "sidecar request failed".to_string())?;
    let status = response.status();
    if response
        .content_length()
        .is_some_and(|length| length > 4_194_304)
    {
        return Err("sidecar response exceeded limit".to_string());
    }
    let bytes = response
        .bytes()
        .await
        .map_err(|_| "sidecar response failed".to_string())?;
    if bytes.len() > 4_194_304 {
        return Err("sidecar response exceeded limit".to_string());
    }
    if !status.is_success() {
        let detail = serde_json::from_slice::<serde_json::Value>(&bytes)
            .ok()
            .and_then(|value| value.get("detail").cloned())
            .map(|value| value.to_string())
            .unwrap_or_else(|| status.to_string());
        return Err(format!("sidecar request failed: {detail}"));
    }
    if bytes.is_empty() {
        return Ok(serde_json::Value::Null);
    }
    serde_json::from_slice(&bytes).map_err(|_| "invalid sidecar response".to_string())
}

#[tauri::command]
async fn call_voss_sidecar(
    sidecar_id: String,
    operation: SidecarOperation,
    state: VossServeMap<'_>,
) -> Result<serde_json::Value, String> {
    let (handshake, root) = sidecar_connection(&sidecar_id, state.inner())?;
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(60))
        .build()
        .map_err(|_| "sidecar client unavailable".to_string())?;
    let root = root.to_string_lossy().into_owned();

    let request = match operation {
        SidecarOperation::CreateSession => client
            .post(sidecar_url(handshake.port, &["session"])?)
            .json(&serde_json::json!({"auth": "auto", "cwd": root})),
        SidecarOperation::ListSessions => client.get(sidecar_url(handshake.port, &["session"])?),
        SidecarOperation::ListSaved => {
            let mut url = sidecar_url(handshake.port, &["sessions", "saved"])?;
            url.query_pairs_mut().append_pair("cwd", &root);
            client.get(url)
        }
        SidecarOperation::GetSession { session_id } => {
            client.get(sidecar_url(handshake.port, &["session", &session_id])?)
        }
        SidecarOperation::DeleteSession { session_id } => {
            client.delete(sidecar_url(handshake.port, &["session", &session_id])?)
        }
        SidecarOperation::PostMessage {
            session_id,
            text,
            mode,
        } => client
            .post(sidecar_url(
                handshake.port,
                &["session", &session_id, "message"],
            )?)
            .json(&serde_json::json!({
                "mode": mode,
                "parts": [{"type": "text", "text": text}],
            })),
        SidecarOperation::AbortSession { session_id } => client.post(sidecar_url(
            handshake.port,
            &["session", &session_id, "abort"],
        )?),
        SidecarOperation::GetCost { session_id } => client.get(sidecar_url(
            handshake.port,
            &["session", &session_id, "cost"],
        )?),
        SidecarOperation::Doctor => {
            let mut url = sidecar_url(handshake.port, &["doctor"])?;
            url.query_pairs_mut().append_pair("cwd", &root);
            client.get(url)
        }
        SidecarOperation::ReplyPermission {
            session_id,
            id,
            choice,
        } => client
            .post(sidecar_url(
                handshake.port,
                &["session", &session_id, "permission"],
            )?)
            .json(&serde_json::json!({"v": 1, "id": id, "choice": choice})),
        SidecarOperation::Memory { query, top_k } => {
            let mut url = sidecar_url(handshake.port, &["memory"])?;
            {
                let mut query_pairs = url.query_pairs_mut();
                query_pairs.append_pair("cwd", &root);
                if let Some(query) = query.filter(|value| !value.trim().is_empty()) {
                    query_pairs.append_pair("q", query.trim());
                    query_pairs.append_pair("top_k", &top_k.to_string());
                }
            }
            client.get(url)
        }
        SidecarOperation::GetSwarm { swarm_id } => {
            client.get(sidecar_url(handshake.port, &["swarm", &swarm_id])?)
        }
        SidecarOperation::CreateSwarm {
            goal,
            builders,
            roster,
        } => client
            .post(sidecar_url(handshake.port, &["swarm"])?)
            .json(&serde_json::json!({
                "goal": goal,
                "builders": builders,
                "cwd": root,
                "roster": roster,
            })),
        SidecarOperation::RunSwarm { swarm_id } => {
            client.post(sidecar_url(handshake.port, &["swarm", &swarm_id, "run"])?)
        }
    };

    send_sidecar_request(&handshake.token, request).await
}

fn take_sse_frame(buffer: &mut Vec<u8>) -> Option<Vec<u8>> {
    let (index, separator_len) = buffer
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .map(|index| (index, 4))
        .or_else(|| {
            buffer
                .windows(2)
                .position(|window| window == b"\n\n")
                .map(|index| (index, 2))
        })?;
    let frame = buffer[..index].to_vec();
    buffer.drain(..index + separator_len);
    Some(frame)
}

fn decode_sse_frame(frame: &[u8]) -> Option<serde_json::Value> {
    let text = std::str::from_utf8(frame).ok()?;
    let data = text
        .lines()
        .filter_map(|line| line.trim_end_matches('\r').strip_prefix("data:"))
        .map(str::trim_start)
        .collect::<Vec<_>>()
        .join("\n");
    if data.is_empty() {
        return None;
    }
    serde_json::from_str(&data).ok()
}

#[tauri::command]
async fn subscribe_voss_events(
    sidecar_id: String,
    session_id: String,
    on_event: tauri::ipc::Channel<SidecarStreamEvent>,
    sidecars: VossServeMap<'_>,
    streams: VossStreamMap<'_>,
) -> Result<String, String> {
    let (handshake, _) = sidecar_connection(&sidecar_id, sidecars.inner())?;
    let response = reqwest::Client::new()
        .get(sidecar_url(
            handshake.port,
            &["session", &session_id, "events"],
        )?)
        .bearer_auth(&handshake.token)
        .send()
        .await
        .map_err(|_| "sidecar event stream failed".to_string())?;
    if !response.status().is_success() {
        return Err(format!(
            "sidecar event stream failed: {}",
            response.status()
        ));
    }

    let stream_id = uuid::Uuid::new_v4().to_string();
    let task = tauri::async_runtime::spawn(async move {
        let mut response = response;
        let mut buffer = Vec::new();
        loop {
            match response.chunk().await {
                Ok(Some(chunk)) => {
                    buffer.extend_from_slice(&chunk);
                    if buffer.len() > 1_048_576 {
                        let _ = on_event.send(SidecarStreamEvent::Error {
                            message: "sidecar event exceeded limit".to_string(),
                        });
                        break;
                    }
                    while let Some(frame) = take_sse_frame(&mut buffer) {
                        if let Some(event) = decode_sse_frame(&frame) {
                            if on_event.send(SidecarStreamEvent::Event { event }).is_err() {
                                return;
                            }
                        }
                    }
                }
                Ok(None) => break,
                Err(_) => {
                    let _ = on_event.send(SidecarStreamEvent::Error {
                        message: "sidecar event stream failed".to_string(),
                    });
                    break;
                }
            }
        }
        let _ = on_event.send(SidecarStreamEvent::End);
    });
    streams
        .lock()
        .map_err(|_| "stream lock poisoned".to_string())?
        .insert(stream_id.clone(), task);
    Ok(stream_id)
}

#[tauri::command]
fn unsubscribe_voss_events(stream_id: String, streams: VossStreamMap<'_>) -> Result<(), String> {
    if let Some(task) = streams
        .lock()
        .map_err(|_| "stream lock poisoned".to_string())?
        .remove(&stream_id)
    {
        task.abort();
    }
    Ok(())
}

#[tauri::command]
async fn start_voss_serve(cwd: String, state: VossServeMap<'_>) -> Result<SidecarHandle, String> {
    // Canonicalize and require an exact persisted project-workspace match before
    // the webview-controlled cwd reaches a process-spawn argument.
    let index = workspaces::load_workspaces_index();
    let canonical = authorize_sidecar_cwd(&cwd, &index)?;
    let key = canonical.to_string_lossy().into_owned();

    // Reuse-if-alive; pid() == None means the child was reaped — drop the
    // stale entry and respawn (Pitfall 5). Lock scope closes before any await.
    {
        let mut map = state.lock().map_err(|_| "lock poisoned".to_string())?;
        match map.get(&key) {
            Some(entry) if entry.serve.pid().is_some() => {
                return Ok(SidecarHandle {
                    sidecar_id: entry.id.clone(),
                })
            }
            Some(_) => {
                map.remove(&key);
            }
            None => {}
        }
    }

    // T-V15-10: the error path carries stderr tails but never the token.
    let serve = spawn_voss_serve(&python_path(), &canonical)
        .await
        .map_err(|e| e.to_string())?;
    let sidecar_id = uuid::Uuid::new_v4().to_string();

    let mut map = state.lock().map_err(|_| "lock poisoned".to_string())?;
    map.insert(
        key,
        VossServeEntry {
            id: sidecar_id.clone(),
            root: canonical,
            serve,
        },
    );
    Ok(SidecarHandle { sidecar_id })
}

// ---- ui_log: webview diagnostics -> dev terminal ---------------------------
// The webview's console.* only reaches devtools. This bridges frontend
// lifecycle/error logs onto the Rust process stdout/stderr so they interleave
// with the sidecar + Tauri output in the `pnpm tauri dev` terminal. `scope` is
// a dotted tag (e.g. "composer.create"); `detail` is preformatted by the
// caller. Never pass secrets (the serve token) — this is the shared console.
#[tauri::command]
fn ui_log(level: String, scope: String, detail: String) {
    let line = format!("[ui] {scope}: {detail}");
    if level == "error" {
        eprintln!("{line}");
    } else {
        println!("{line}");
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Arc::new(PtyRegistry::default()))
        .manage(Mutex::new(GridState::default()))
        .manage(Mutex::new(AgentRegistryMap::new()))
        .manage(SwarmWatchState::default())
        .manage(KeymapWatchState::default())
        .manage(Mutex::new(HashMap::<String, VossServeEntry>::new()))
        .manage(Arc::new(Mutex::new(HashMap::<
            String,
            tauri::async_runtime::JoinHandle<()>,
        >::new())))
        .invoke_handler(tauri::generate_handler![
            get_theme_overrides,
            save_clipboard_image,
            spawn_pty,
            pty_write,
            pty_resize,
            pty_pause,
            pty_resume,
            pty_kill,
            get_fg_process,
            spawn_agent,
            spawn_managed_agent,
            get_active_agents,
            mark_agent_stopped,
            update_agents_last_seen,
            sweep_orphan_agents,
            sync_grid,
            get_grid,
            save_layout,
            load_layout,
            list_layouts,
            load_default_layout,
            open_project,
            load_recents,
            default_cwd,
            save_session,
            load_session,
            save_global_session,
            load_global_session,
            watch_swarm_results,
            stop_swarm_watcher,
            load_workspaces_index,
            save_workspaces_index,
            list_workspaces,
            save_project_less_session,
            load_project_less_session,
            load_keymap_profile,
            save_keymap_profile,
            load_keymap_overrides,
            validate_keymap_overrides,
            watch_keymap_overrides,
            list_custom_themes,
            load_custom_theme,
            save_custom_theme,
            load_active_theme_id,
            save_active_theme_id,
            list_profiles,
            load_profile,
            save_profile,
            load_active_profile_id,
            save_active_profile_id,
            load_appearance_settings,
            save_appearance_settings,
            list_system_fonts,
            write_context_pins,
            load_custom_agents,
            save_custom_agents,
            list_dir,
            git_log,
            load_run,
            enumerate_runs,
            run_decision,
            start_voss_serve,
            call_voss_sidecar,
            subscribe_voss_events,
            unsubscribe_voss_events,
            ui_log,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
