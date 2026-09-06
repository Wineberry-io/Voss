//! A6 session persistence — private per-workspace session files, locked writes,
//! fail-safe loads, and copy-only migration from legacy repo-local state.
//!
//! Follows the `layouts.rs` pattern: a versioned wrapper around `GridState`
//! with typed errors whose Display strings surface through Tauri verbatim.
//! Corrupt, missing, or unsupported session files fail closed to `Ok(None)`
//! so app startup is never blocked (D-11).
//!
//! Two save tiers share the same file and schema (D-04/D-06):
//! - **Structural auto-save** writes tree + cwds + shells + focus + preset
//!   with `scrollback: null` per pane.
//! - **Quit full-save** writes the same shape with scrollback arrays populated.
//!
//! Every write is locked exclusively via `fs2::FileExt` (PER-06) and uses
//! a tmp-file rename so readers never see a partial write.

use std::path::{Path, PathBuf};

use fs2::FileExt;
use serde::{Deserialize, Serialize};

use crate::canvas::CanvasState;
use crate::grid::GridState;

/// On-disk session schema version. Bump when the schema shape changes.
pub const CURRENT_SESSION_VERSION: u32 = 2;
/// Oldest version still accepted on load. v1 carries a split tree that the
/// webview migrates to canvas nodes and re-saves as v2.
pub const MIN_SESSION_VERSION: u32 = 1;

/// Persisted session file. Wraps `GridState` with per-pane scrollback,
/// the active preset, and the project-less flag (D-12).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionFile {
    pub version: u32,
    pub active_preset: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub grid: Option<GridState>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub canvas: Option<CanvasState>,
    pub panes: Vec<SessionPane>,
    pub project_less_accepted: bool,
}

/// Per-pane scrollback payload. `scrollback: None` means tree-only auto-save
/// (D-04); `Some(lines)` means full quit save (D-01).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionPane {
    pub id: String,
    pub scrollback: Option<Vec<String>>,
}

impl SessionFile {
    /// Build a SessionFile from a legacy split tree (tests + migration).
    pub fn new(
        grid: GridState,
        active_preset: Option<String>,
        panes: Vec<SessionPane>,
        project_less_accepted: bool,
    ) -> Self {
        Self {
            version: CURRENT_SESSION_VERSION,
            active_preset,
            grid: Some(grid),
            canvas: None,
            panes,
            project_less_accepted,
        }
    }

    /// Build a v2 SessionFile from canvas nodes.
    pub fn from_canvas(
        canvas: CanvasState,
        active_preset: Option<String>,
        panes: Vec<SessionPane>,
        project_less_accepted: bool,
    ) -> Self {
        Self {
            version: CURRENT_SESSION_VERSION,
            active_preset,
            grid: None,
            canvas: Some(canvas),
            panes,
            project_less_accepted,
        }
    }
}

/// Typed errors for session save/load. Display strings are safe for UI
/// passthrough — no Rust internals leak.
#[derive(Debug, thiserror::Error)]
pub enum SessionError {
    #[error("could not save session")]
    SaveFailed,
    #[error("could not load session")]
    LoadFailed,
}

// --- Path resolution ---------------------------------------------------------

/// `~/.config/voss-app/sessions/<workspace_id>.json`.
pub fn session_path(workspace_id: &str) -> PathBuf {
    project_less_sessions_dir().join(format!("{workspace_id}.json"))
}

/// Legacy `<workspace>/.voss/session.json`, read only during migration.
pub fn legacy_session_path(workspace: &Path) -> PathBuf {
    workspace.join(".voss").join("session.json")
}

/// `~/.config/voss-app/global-session.json`
#[cfg(not(test))]
pub fn global_session_path() -> PathBuf {
    config_voss_app_dir().join("global-session.json")
}

#[cfg(test)]
pub fn global_session_path() -> PathBuf {
    TEST_GLOBAL_SESSION_PATH.with(|p| {
        p.borrow()
            .clone()
            .expect("tests must set TEST_GLOBAL_SESSION_PATH before touching global session")
    })
}

/// `~/.config/voss-app/sessions/<workspace_id>.json` (D-04 project-less workspaces).
pub fn project_less_session_path(workspace_id: &str) -> PathBuf {
    session_path(workspace_id)
}

#[cfg(not(test))]
fn project_less_sessions_dir() -> PathBuf {
    config_voss_app_dir().join("sessions")
}

#[cfg(test)]
fn project_less_sessions_dir() -> PathBuf {
    TEST_PROJECT_LESS_SESSIONS_DIR.with(|p| {
        p.borrow()
            .clone()
            .expect("tests must set TEST_PROJECT_LESS_SESSIONS_DIR")
    })
}

#[cfg(not(test))]
fn config_voss_app_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_default()
        .join(".config")
        .join("voss-app")
}

// --- Save / Load -------------------------------------------------------------

/// Save a workspace session to private app data.
pub fn save_session(workspace_id: &str, session: &SessionFile) -> Result<(), SessionError> {
    if !is_filename_safe_workspace_id(workspace_id) {
        eprintln!("[voss-app] invalid session workspace id");
        return Err(SessionError::SaveFailed);
    }
    let path = session_path(workspace_id);
    let json = serde_json::to_string_pretty(session).map_err(|e| {
        eprintln!("[voss-app] session serialize failed: {e}");
        SessionError::SaveFailed
    })?;
    locked_write(&path, &json)
}

/// Load a workspace session from private app data. When private state is absent,
/// a valid legacy repo-local session is copied into private storage without
/// modifying or deleting the legacy file.
pub fn load_session(
    workspace_id: &str,
    legacy_workspace: Option<&Path>,
) -> Result<Option<SessionFile>, SessionError> {
    if !is_filename_safe_workspace_id(workspace_id) {
        eprintln!("[voss-app] invalid session workspace id");
        return Ok(None);
    }
    let private_path = session_path(workspace_id);
    if private_path.exists() {
        return fail_safe_load(&private_path);
    }
    let Some(legacy_workspace) = legacy_workspace else {
        return Ok(None);
    };
    let legacy_path = legacy_session_path(legacy_workspace);
    let Some(session) = fail_safe_load(&legacy_path)? else {
        return Ok(None);
    };
    save_session(workspace_id, &session)?;
    Ok(Some(session))
}

/// Save the global (project-less) session to
/// `~/.config/voss-app/global-session.json`.
pub fn save_global_session(session: &SessionFile) -> Result<(), SessionError> {
    let path = global_session_path();
    let json = serde_json::to_string_pretty(session).map_err(|e| {
        eprintln!("[voss-app] global session serialize failed: {e}");
        SessionError::SaveFailed
    })?;
    locked_write(&path, &json)
}

/// Load the global session. Returns `Ok(None)` for missing, corrupt, or
/// unsupported files.
pub fn load_global_session() -> Result<Option<SessionFile>, SessionError> {
    fail_safe_load(&global_session_path())
}

/// Save a project-less workspace session to
/// `~/.config/voss-app/sessions/<id>.json`.
pub fn save_project_less_session(
    workspace_id: &str,
    session: &SessionFile,
) -> Result<(), SessionError> {
    if !is_filename_safe_workspace_id(workspace_id) {
        eprintln!("[voss-app] invalid project-less session workspace id");
        return Err(SessionError::SaveFailed);
    }
    let path = session_path(workspace_id);
    let json = serde_json::to_string_pretty(session).map_err(|e| {
        eprintln!("[voss-app] project-less session serialize failed: {e}");
        SessionError::SaveFailed
    })?;
    locked_write(&path, &json)
}

/// Load a project-less workspace session. Returns `Ok(None)` for missing,
/// corrupt, or unsupported files.
pub fn load_project_less_session(workspace_id: &str) -> Result<Option<SessionFile>, SessionError> {
    if !is_filename_safe_workspace_id(workspace_id) {
        eprintln!("[voss-app] invalid project-less session workspace id");
        return Ok(None);
    }
    fail_safe_load(&session_path(workspace_id))
}

/// Workspace ids used in session filenames: alphanumeric + hyphen only.
fn is_filename_safe_workspace_id(id: &str) -> bool {
    !id.is_empty() && id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-')
}

// --- Internal helpers --------------------------------------------------------

/// Locked write: create parent dir → open lock file → lock exclusively →
/// write tmp → rename over destination. Lock released on drop.
fn locked_write(path: &Path, json: &str) -> Result<(), SessionError> {
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| {
            eprintln!("[voss-app] session save mkdir failed: {e}");
            SessionError::SaveFailed
        })?;
    }

    let lock_path = path.with_extension("json.lock");
    let lock_file = std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(&lock_path)
        .map_err(|e| {
            eprintln!("[voss-app] session lock open failed: {e}");
            SessionError::SaveFailed
        })?;
    lock_file.lock_exclusive().map_err(|e| {
        eprintln!("[voss-app] session lock failed: {e}");
        SessionError::SaveFailed
    })?;

    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, json).map_err(|e| {
        eprintln!("[voss-app] session write tmp failed: {e}");
        SessionError::SaveFailed
    })?;
    std::fs::rename(&tmp, path).map_err(|e| {
        eprintln!("[voss-app] session rename failed: {e}");
        SessionError::SaveFailed
    })?;

    // lock_file dropped here → exclusive lock released
    Ok(())
}

/// Fail-safe load: missing → `Ok(None)`, corrupt → `Ok(None)` + stderr,
/// unsupported version → `Ok(None)` + stderr. Never panics.
fn fail_safe_load(path: &Path) -> Result<Option<SessionFile>, SessionError> {
    if !path.exists() {
        return Ok(None);
    }
    let raw = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[voss-app] could not read session: {e}");
            return Ok(None);
        }
    };
    match parse_session(&raw) {
        Ok(s) => Ok(Some(s)),
        Err(reason) => {
            eprintln!("[voss-app] session ignored: {reason}");
            Ok(None)
        }
    }
}

/// Version-gated parse — same pattern as `layouts::parse_layout`.
fn parse_session(raw: &str) -> Result<SessionFile, &'static str> {
    let value: serde_json::Value = serde_json::from_str(raw).map_err(|_| "invalid JSON")?;
    let version = value.get("version").and_then(|v| v.as_u64());
    match version {
        Some(v) if v >= MIN_SESSION_VERSION as u64 && v <= CURRENT_SESSION_VERSION as u64 => {
            let file: SessionFile =
                serde_json::from_value(value).map_err(|_| "invalid session file")?;
            if file.grid.is_none() && file.canvas.is_none() {
                return Err("invalid session file");
            }
            Ok(file)
        }
        Some(_) => Err("unsupported version"),
        None => Err("missing version"),
    }
}

// ---------------------------------------------------------------------------

#[cfg(test)]
thread_local! {
    static TEST_GLOBAL_SESSION_PATH: std::cell::RefCell<Option<PathBuf>> =
        const { std::cell::RefCell::new(None) };
    pub(crate) static TEST_PROJECT_LESS_SESSIONS_DIR: std::cell::RefCell<Option<PathBuf>> =
        const { std::cell::RefCell::new(None) };
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grid::{GridState, Orientation, PaneLeaf, SplitNode, TreeNode};
    use tempfile::{tempdir, TempDir};

    fn sample_grid() -> GridState {
        GridState {
            root: TreeNode::Split(SplitNode {
                orientation: Orientation::H,
                ratio: 0.5,
                left: Box::new(TreeNode::Pane(PaneLeaf {
                    id: "a".into(),
                    cwd: "/repo".into(),
                    shell: "zsh".into(),
                    index: 1,
                })),
                right: Box::new(TreeNode::Pane(PaneLeaf {
                    id: "b".into(),
                    cwd: "/repo".into(),
                    shell: "zsh".into(),
                    index: 2,
                })),
            }),
            focused_id: "a".into(),
        }
    }

    fn sample_panes() -> Vec<SessionPane> {
        vec![
            SessionPane {
                id: "a".into(),
                scrollback: Some(vec!["$ ls".into(), "file.txt".into()]),
            },
            SessionPane {
                id: "b".into(),
                scrollback: None,
            },
        ]
    }

    fn sample_session() -> SessionFile {
        SessionFile::new(sample_grid(), Some("fanout".into()), sample_panes(), false)
    }

    fn isolate_global() -> TempDir {
        let dir = tempdir().unwrap();
        let path = dir.path().join("global-session.json");
        TEST_GLOBAL_SESSION_PATH.with(|p| {
            *p.borrow_mut() = Some(path);
        });
        dir
    }

    fn isolate_project_less() -> TempDir {
        let dir = tempdir().unwrap();
        TEST_PROJECT_LESS_SESSIONS_DIR.with(|p| {
            *p.borrow_mut() = Some(dir.path().join("sessions"));
        });
        dir
    }

    // --- Task 1: schema + serde -------------------------------------------

    #[test]
    fn session_file_new_sets_current_version() {
        let s = sample_session();
        assert_eq!(s.version, 2);
        assert_eq!(CURRENT_SESSION_VERSION, 2);
    }

    #[test]
    fn v1_tree_session_still_parses() {
        let raw = r#"{"version":1,"activePreset":null,"grid":{"root":{"kind":"pane","id":"a","cwd":"/r","shell":"zsh","index":1},"focusedId":"a"},"panes":[],"projectLessAccepted":false}"#;
        let s = parse_session(raw).expect("v1 parses");
        assert!(s.grid.is_some());
        assert!(s.canvas.is_none());
    }

    #[test]
    fn v2_canvas_session_round_trips_without_grid() {
        let s = SessionFile::from_canvas(CanvasState::default(), None, vec![], false);
        let json = serde_json::to_string(&s).unwrap();
        assert!(!json.contains("\"grid\""), "{json}");
        assert!(json.contains("\"canvas\""), "{json}");
        let back = parse_session(&json).unwrap();
        assert_eq!(back, s);
    }

    #[test]
    fn session_without_grid_or_canvas_is_invalid() {
        let raw = r#"{"version":2,"activePreset":null,"panes":[],"projectLessAccepted":false}"#;
        assert!(parse_session(raw).is_err());
    }

    #[test]
    fn session_file_round_trips_through_json() {
        let original = sample_session();
        let json = serde_json::to_string(&original).expect("serialize");
        let back: SessionFile = serde_json::from_str(&json).expect("deserialize");
        assert_eq!(original, back);
    }

    #[test]
    fn json_contains_expected_camel_case_keys() {
        let s = sample_session();
        let json = serde_json::to_string(&s).unwrap();
        assert!(json.contains("\"version\":2"), "version: {json}");
        assert!(json.contains("\"focusedId\""), "focusedId: {json}");
        assert!(json.contains("\"activePreset\""), "activePreset: {json}");
        assert!(
            json.contains("\"projectLessAccepted\""),
            "projectLessAccepted: {json}"
        );
    }

    #[test]
    fn scrollback_none_serializes_as_null() {
        let pane = SessionPane {
            id: "x".into(),
            scrollback: None,
        };
        let json = serde_json::to_string(&pane).unwrap();
        assert!(json.contains("\"scrollback\":null"), "null: {json}");
    }

    #[test]
    fn scrollback_some_serializes_as_array() {
        let pane = SessionPane {
            id: "x".into(),
            scrollback: Some(vec!["line1".into(), "line2".into()]),
        };
        let json = serde_json::to_string(&pane).unwrap();
        assert!(json.contains("[\"line1\",\"line2\"]"), "array: {json}");
    }

    #[test]
    fn session_error_display_strings() {
        assert_eq!(
            SessionError::SaveFailed.to_string(),
            "could not save session"
        );
        assert_eq!(
            SessionError::LoadFailed.to_string(),
            "could not load session"
        );
    }

    // --- Task 2: file I/O ------------------------------------------------

    #[test]
    fn session_path_resolves_under_private_app_data() {
        let _state = isolate_project_less();
        let p = session_path("ws-1");
        assert!(p.to_string_lossy().ends_with("sessions/ws-1.json"));
    }

    #[test]
    fn global_session_path_resolves_to_config_voss_app() {
        let _g = isolate_global();
        let p = global_session_path();
        assert!(
            p.to_string_lossy().ends_with("global-session.json"),
            "path: {p:?}"
        );
    }

    #[test]
    fn save_then_load_round_trips_project_session() {
        let _state = isolate_project_less();
        let session = sample_session();
        save_session("ws-1", &session).unwrap();
        let loaded = load_session("ws-1", None).unwrap();
        assert_eq!(loaded, Some(session));
    }

    #[test]
    fn save_never_creates_repository_voss_state() {
        let _state = isolate_project_less();
        let workspace = tempdir().unwrap();
        save_session("ws-1", &sample_session()).unwrap();
        assert!(session_path("ws-1").exists());
        assert!(!workspace.path().join(".voss").exists());
    }

    #[test]
    fn load_session_does_not_create_directories() {
        let state = isolate_project_less();
        let _ = load_session("missing", None);
        assert!(!state.path().join("sessions").exists());
    }

    #[test]
    fn load_session_returns_none_for_missing_file() {
        let _state = isolate_project_less();
        assert!(load_session("missing", None).unwrap().is_none());
    }

    #[test]
    fn load_session_returns_none_for_corrupt_json() {
        let _state = isolate_project_less();
        let path = session_path("bad");
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, "not json").unwrap();
        assert!(load_session("bad", None).unwrap().is_none());
    }

    #[test]
    fn load_session_returns_none_for_unsupported_version() {
        let _state = isolate_project_less();
        let path = session_path("future");
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(
            path,
            r#"{"version":999,"activePreset":null,"grid":{},"panes":[],"projectLessAccepted":false}"#,
        )
        .unwrap();
        assert!(load_session("future", None).unwrap().is_none());
    }

    #[test]
    fn save_then_load_round_trips_global_session() {
        let _g = isolate_global();
        let session = SessionFile::new(sample_grid(), None, sample_panes(), true);
        save_global_session(&session).unwrap();
        let loaded = load_global_session().unwrap();
        assert_eq!(loaded, Some(session));
    }

    #[test]
    fn load_global_session_returns_none_when_missing() {
        let _g = isolate_global();
        assert!(load_global_session().unwrap().is_none());
    }

    #[test]
    fn save_writes_tmp_then_renames() {
        let _state = isolate_project_less();
        save_session("ws-1", &sample_session()).unwrap();
        let path = session_path("ws-1");
        let tmp_path = path.with_extension("json.tmp");
        assert!(path.exists());
        assert!(!tmp_path.exists(), "tmp must be cleaned up by rename");
    }

    #[test]
    fn save_overwrites_existing_session() {
        let _state = isolate_project_less();
        let first = SessionFile::new(sample_grid(), Some("fanout".into()), vec![], false);
        save_session("ws-1", &first).unwrap();

        let second = SessionFile::new(sample_grid(), Some("pipeline".into()), vec![], true);
        save_session("ws-1", &second).unwrap();

        let loaded = load_session("ws-1", None).unwrap().unwrap();
        assert_eq!(loaded.active_preset, Some("pipeline".into()));
        assert!(loaded.project_less_accepted);
    }

    #[test]
    fn legacy_project_session_is_copied_without_modifying_repository() {
        let _state = isolate_project_less();
        let workspace = tempdir().unwrap();
        let legacy = legacy_session_path(workspace.path());
        std::fs::create_dir_all(legacy.parent().unwrap()).unwrap();
        let json = serde_json::to_string_pretty(&sample_session()).unwrap();
        std::fs::write(&legacy, &json).unwrap();

        let loaded = load_session("ws-1", Some(workspace.path())).unwrap();
        assert_eq!(loaded, Some(sample_session()));
        assert_eq!(std::fs::read_to_string(&legacy).unwrap(), json);
        assert!(session_path("ws-1").exists());
    }

    // --- Project-less per-workspace sessions (A8 D-04) ---------------------

    #[test]
    fn project_less_session_path_resolves_under_config_sessions() {
        let _dir = isolate_project_less();
        let p = project_less_session_path("my-ws");
        assert!(
            p.to_string_lossy().ends_with("sessions/my-ws.json"),
            "path: {p:?}"
        );
    }

    #[test]
    fn save_then_load_round_trips_project_less_session() {
        let _dir = isolate_project_less();
        let session = SessionFile::new(sample_grid(), Some("fanout".into()), vec![], true);
        save_project_less_session("ws-1", &session).unwrap();
        assert_eq!(load_project_less_session("ws-1").unwrap(), Some(session));
    }

    #[test]
    fn load_project_less_session_returns_none_when_missing() {
        let _dir = isolate_project_less();
        assert!(load_project_less_session("missing").unwrap().is_none());
    }

    #[test]
    fn load_project_less_session_returns_none_for_corrupt_json() {
        let _dir = isolate_project_less();
        let path = project_less_session_path("bad");
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).unwrap();
        }
        std::fs::write(path, "not json").unwrap();
        assert!(load_project_less_session("bad").unwrap().is_none());
    }

    #[test]
    fn save_project_less_session_rejects_unsafe_workspace_id() {
        let _dir = isolate_project_less();
        let session = sample_session();
        assert!(save_project_less_session("../x", &session).is_err());
    }

    #[test]
    fn load_project_less_session_rejects_unsafe_workspace_id() {
        let _dir = isolate_project_less();
        assert!(load_project_less_session("bad/id").unwrap().is_none());
    }

    #[test]
    fn save_project_less_creates_sessions_dir_on_write() {
        let dir = tempdir().unwrap();
        let sessions = dir.path().join("sessions");
        TEST_PROJECT_LESS_SESSIONS_DIR.with(|p| {
            *p.borrow_mut() = Some(sessions.clone());
        });
        assert!(!sessions.exists());
        save_project_less_session("alpha", &sample_session()).unwrap();
        assert!(project_less_session_path("alpha").exists());
    }
}
