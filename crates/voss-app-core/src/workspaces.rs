//! A8 workspace index — `~/.config/voss-app/workspaces.json` metadata (D-04).
//!
//! Fail-safe loads never block app startup: missing, corrupt, or unsupported
//! index files yield a single default project-less workspace.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};

pub const CURRENT_WORKSPACES_VERSION: u32 = 1;

/// Default workspace id used when the index is missing or unusable.
pub const DEFAULT_WORKSPACE_ID: &str = "default";

/// Default accent when no user override exists (D-03 palette).
pub const DEFAULT_ACCENT_COLOR: &str = "blue";

/// On-disk workspace index (D-04).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspacesIndex {
    pub version: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_workspace_id: Option<String>,
    pub workspaces: Vec<WorkspaceEntry>,
}

/// One workspace tab's persisted metadata. Pane tree + scrollback live in
/// per-workspace session files under private app data.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceEntry {
    pub id: String,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub project_path: Option<String>,
    pub accent_color: String,
    pub order: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active_layout_preset: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pinned_profile: Option<String>,
}

impl WorkspaceEntry {
    /// All workspace sessions use `~/.config/voss-app/sessions/<id>.json`.
    pub fn is_project_less(&self) -> bool {
        self.project_path.is_none()
    }
}

#[derive(Debug, thiserror::Error)]
pub enum WorkspacesError {
    #[error("workspace id must be non-empty alphanumeric or hyphen")]
    InvalidId,
    #[error("could not save workspaces index")]
    SaveFailed,
}

// --- Path helpers ------------------------------------------------------------

#[cfg(not(test))]
pub fn workspaces_index_path() -> PathBuf {
    config_dir().join("workspaces.json")
}

#[cfg(test)]
pub fn workspaces_index_path() -> PathBuf {
    TEST_WORKSPACES_INDEX_PATH.with(|p| {
        p.borrow()
            .clone()
            .expect("tests must set TEST_WORKSPACES_INDEX_PATH")
    })
}

#[cfg(not(test))]
fn config_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_default()
        .join(".config")
        .join("voss-app")
}

// --- Validation --------------------------------------------------------------

/// Workspace ids must be stable filename-safe tokens (alphanumeric + hyphen).
pub fn validate_workspace_id(id: &str) -> Result<(), WorkspacesError> {
    if id.is_empty() {
        return Err(WorkspacesError::InvalidId);
    }
    if !id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-') {
        return Err(WorkspacesError::InvalidId);
    }
    Ok(())
}

fn validate_index(index: &WorkspacesIndex) -> Result<(), WorkspacesError> {
    for entry in &index.workspaces {
        validate_workspace_id(&entry.id)?;
    }
    if let Some(active) = &index.active_workspace_id {
        validate_workspace_id(active)?;
        if !index.workspaces.iter().any(|w| w.id == *active) {
            return Err(WorkspacesError::InvalidId);
        }
    }
    Ok(())
}

// --- Default index -----------------------------------------------------------

/// Single project-less default workspace — used when the index cannot be loaded.
pub fn default_workspaces_index() -> WorkspacesIndex {
    let entry = WorkspaceEntry {
        id: DEFAULT_WORKSPACE_ID.into(),
        name: "Workspace".into(),
        project_path: None,
        accent_color: DEFAULT_ACCENT_COLOR.into(),
        order: 0,
        active_layout_preset: None,
        pinned_profile: None,
    };
    WorkspacesIndex {
        version: CURRENT_WORKSPACES_VERSION,
        active_workspace_id: Some(DEFAULT_WORKSPACE_ID.into()),
        workspaces: vec![entry],
    }
}

// --- Load / save -------------------------------------------------------------

/// Load `workspaces.json`. Missing, corrupt, unsupported, or empty → default
/// index (never blocks boot).
pub fn load_workspaces_index() -> WorkspacesIndex {
    let path = workspaces_index_path();
    let empty = default_workspaces_index;

    let raw = match std::fs::read_to_string(&path) {
        Ok(raw) => raw,
        Err(e) => {
            eprintln!("[voss-app] workspaces.json missing or unreadable; using default: {e}");
            return empty();
        }
    };

    let file: WorkspacesIndex = match serde_json::from_str(&raw) {
        Ok(file) => file,
        Err(e) => {
            eprintln!("[voss-app] workspaces.json corrupt; using default: {e}");
            return empty();
        }
    };

    if file.version != CURRENT_WORKSPACES_VERSION {
        eprintln!("[voss-app] workspaces.json unsupported version; using default");
        return empty();
    }

    if file.workspaces.is_empty() {
        eprintln!("[voss-app] workspaces.json has no workspaces; using default");
        return empty();
    }

    for entry in &file.workspaces {
        if validate_workspace_id(&entry.id).is_err() {
            eprintln!(
                "[voss-app] workspaces.json invalid workspace id {:?}; using default",
                entry.id
            );
            return empty();
        }
    }

    if let Some(active) = &file.active_workspace_id {
        if validate_workspace_id(active).is_err()
            || !file.workspaces.iter().any(|w| w.id == *active)
        {
            eprintln!("[voss-app] workspaces.json invalid activeWorkspaceId; using default");
            return empty();
        }
    }

    file
}

/// Persist the workspace index atomically (tmp + rename).
pub fn save_workspaces_index(index: &WorkspacesIndex) -> Result<(), WorkspacesError> {
    validate_index(index)?;

    let path = workspaces_index_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| {
            eprintln!("[voss-app] workspaces index mkdir failed: {e}");
            WorkspacesError::SaveFailed
        })?;
    }

    let tmp = path.with_extension("json.tmp");
    let json = serde_json::to_string_pretty(index).map_err(|e| {
        eprintln!("[voss-app] workspaces index serialize failed: {e}");
        WorkspacesError::SaveFailed
    })?;
    std::fs::write(&tmp, json).map_err(|e| {
        eprintln!("[voss-app] workspaces index write tmp failed: {e}");
        WorkspacesError::SaveFailed
    })?;
    std::fs::rename(&tmp, &path).map_err(|e| {
        eprintln!("[voss-app] workspaces index rename failed: {e}");
        WorkspacesError::SaveFailed
    })?;
    Ok(())
}

/// Workspace entries from the current index (fail-safe load).
pub fn list_workspaces() -> Vec<WorkspaceEntry> {
    load_workspaces_index().workspaces
}

/// Resolve the on-disk session path for a workspace entry.
pub fn workspace_session_path(entry: &WorkspaceEntry) -> PathBuf {
    crate::session::session_path(&entry.id)
}

// ---------------------------------------------------------------------------

#[cfg(test)]
thread_local! {
    static TEST_WORKSPACES_INDEX_PATH: std::cell::RefCell<Option<PathBuf>> =
        const { std::cell::RefCell::new(None) };
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grid::{GridState, PaneLeaf, TreeNode};
    use crate::session::{load_project_less_session, save_project_less_session, SessionFile};
    use tempfile::{tempdir, TempDir};

    fn isolate_index() -> TempDir {
        let dir = tempdir().unwrap();
        let path = dir.path().join("workspaces.json");
        TEST_WORKSPACES_INDEX_PATH.with(|p| {
            *p.borrow_mut() = Some(path);
        });
        dir
    }

    fn sample_grid() -> GridState {
        GridState {
            root: TreeNode::Pane(PaneLeaf {
                id: "a".into(),
                cwd: "/".into(),
                shell: "zsh".into(),
                index: 1,
            }),
            focused_id: "a".into(),
        }
    }

    // --- schema ------------------------------------------------------------

    #[test]
    fn workspace_entry_round_trips_camel_case() {
        let entry = WorkspaceEntry {
            id: "ws-1".into(),
            name: "My Repo".into(),
            project_path: Some("/repo".into()),
            accent_color: "cyan".into(),
            order: 2,
            active_layout_preset: Some("fanout".into()),
            pinned_profile: Some("Work".into()),
        };
        let json = serde_json::to_string(&entry).unwrap();
        assert!(json.contains("\"projectPath\""));
        assert!(json.contains("\"accentColor\""));
        assert!(json.contains("\"activeLayoutPreset\""));
        assert!(json.contains("\"pinnedProfile\""));
        let back: WorkspaceEntry = serde_json::from_str(&json).unwrap();
        assert_eq!(back, entry);
    }

    #[test]
    fn project_less_entry_has_null_project_path() {
        let entry = WorkspaceEntry {
            id: "default".into(),
            name: "Workspace".into(),
            project_path: None,
            accent_color: "blue".into(),
            order: 0,
            active_layout_preset: None,
            pinned_profile: None,
        };
        assert!(entry.is_project_less());
        let json = serde_json::to_string(&entry).unwrap();
        assert!(!json.contains("projectPath"), "omit null: {json}");
    }

    // --- id validation -----------------------------------------------------

    #[test]
    fn validate_workspace_id_accepts_alphanumeric_and_hyphen() {
        assert!(validate_workspace_id("default").is_ok());
        assert!(validate_workspace_id("ws-01").is_ok());
        assert!(validate_workspace_id("Abc123").is_ok());
    }

    #[test]
    fn validate_workspace_id_rejects_unsafe_chars() {
        assert!(validate_workspace_id("").is_err());
        assert!(validate_workspace_id("ws_1").is_err());
        assert!(validate_workspace_id("../evil").is_err());
        assert!(validate_workspace_id("ws 1").is_err());
    }

    // --- fail-safe load ----------------------------------------------------

    #[test]
    fn load_missing_index_returns_default_workspace() {
        let _dir = isolate_index();
        let index = load_workspaces_index();
        assert_eq!(index, default_workspaces_index());
        assert_eq!(index.workspaces.len(), 1);
        assert_eq!(index.workspaces[0].id, DEFAULT_WORKSPACE_ID);
        assert!(index.workspaces[0].is_project_less());
    }

    #[test]
    fn load_corrupt_index_returns_default() {
        let _dir = isolate_index();
        std::fs::write(workspaces_index_path(), "not json").unwrap();
        assert_eq!(load_workspaces_index(), default_workspaces_index());
    }

    #[test]
    fn load_unsupported_version_returns_default() {
        let _dir = isolate_index();
        std::fs::write(
            workspaces_index_path(),
            r#"{"version":99,"workspaces":[{"id":"x","name":"X","accentColor":"red","order":0}]}"#,
        )
        .unwrap();
        assert_eq!(load_workspaces_index(), default_workspaces_index());
    }

    #[test]
    fn load_empty_workspaces_returns_default() {
        let _dir = isolate_index();
        std::fs::write(workspaces_index_path(), r#"{"version":1,"workspaces":[]}"#).unwrap();
        assert_eq!(load_workspaces_index(), default_workspaces_index());
    }

    #[test]
    fn load_invalid_workspace_id_returns_default() {
        let _dir = isolate_index();
        std::fs::write(
            workspaces_index_path(),
            r#"{"version":1,"workspaces":[{"id":"bad id","name":"X","accentColor":"red","order":0}]}"#,
        )
        .unwrap();
        assert_eq!(load_workspaces_index(), default_workspaces_index());
    }

    // --- save / round-trip -------------------------------------------------

    #[test]
    fn save_then_load_round_trips_index() {
        let _dir = isolate_index();
        let mut index = default_workspaces_index();
        index.workspaces.push(WorkspaceEntry {
            id: "repo-a".into(),
            name: "Repo A".into(),
            project_path: Some("/tmp/a".into()),
            accent_color: "green".into(),
            order: 1,
            active_layout_preset: None,
            pinned_profile: None,
        });
        index.active_workspace_id = Some("repo-a".into());
        save_workspaces_index(&index).unwrap();
        assert_eq!(load_workspaces_index(), index);
    }

    #[test]
    fn save_rejects_invalid_workspace_id() {
        let _dir = isolate_index();
        let index = WorkspacesIndex {
            version: CURRENT_WORKSPACES_VERSION,
            active_workspace_id: None,
            workspaces: vec![WorkspaceEntry {
                id: "bad/id".into(),
                name: "X".into(),
                project_path: None,
                accent_color: "red".into(),
                order: 0,
                active_layout_preset: None,
                pinned_profile: None,
            }],
        };
        assert!(save_workspaces_index(&index).is_err());
    }

    #[test]
    fn list_workspaces_matches_index() {
        let _dir = isolate_index();
        save_workspaces_index(&default_workspaces_index()).unwrap();
        assert_eq!(list_workspaces().len(), 1);
    }

    #[test]
    fn save_writes_tmp_then_renames() {
        let _dir = isolate_index();
        save_workspaces_index(&default_workspaces_index()).unwrap();
        assert!(workspaces_index_path().exists());
        assert!(!workspaces_index_path().with_extension("json.tmp").exists());
    }

    // --- session path resolution -------------------------------------------

    #[test]
    fn workspace_session_path_project_uses_private_app_data() {
        let dir = isolate_index();
        crate::session::TEST_PROJECT_LESS_SESSIONS_DIR.with(|p| {
            *p.borrow_mut() = Some(dir.path().join("sessions"));
        });
        let entry = WorkspaceEntry {
            id: "repo".into(),
            name: "Repo".into(),
            project_path: Some("/ws".into()),
            accent_color: "blue".into(),
            order: 0,
            active_layout_preset: None,
            pinned_profile: None,
        };
        assert_eq!(
            workspace_session_path(&entry),
            dir.path().join("sessions/repo.json")
        );
    }

    #[test]
    fn workspace_session_path_project_less_uses_config_sessions() {
        let dir = isolate_index();
        crate::session::TEST_PROJECT_LESS_SESSIONS_DIR.with(|p| {
            *p.borrow_mut() = Some(dir.path().join("sessions"));
        });
        let entry = default_workspaces_index().workspaces[0].clone();
        let path = workspace_session_path(&entry);
        assert_eq!(path, dir.path().join("sessions/default.json"));
    }

    #[test]
    fn project_less_session_round_trip_via_workspace_id() {
        let _dir = isolate_index();
        crate::session::TEST_PROJECT_LESS_SESSIONS_DIR.with(|p| {
            *p.borrow_mut() = Some(_dir.path().join("sessions"));
        });
        let session = SessionFile::new(sample_grid(), None, vec![], true);
        save_project_less_session(DEFAULT_WORKSPACE_ID, &session).unwrap();
        let loaded = load_project_less_session(DEFAULT_WORKSPACE_ID).unwrap();
        assert_eq!(loaded, Some(session));
    }
}
