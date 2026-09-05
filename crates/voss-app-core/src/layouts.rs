//! A4 layout persistence — versioned private app-data layouts plus copy-only
//! migration from legacy `.voss/layouts/<name>.json` files.
//!
//! The on-disk shape wraps `GridState` so the same camelCase keys the
//! TypeScript model uses (`focusedId`, `kind`, `orientation`, `ratio`, …)
//! round-trip unchanged. Adding fields here without bumping `version`
//! breaks the at-rest contract — bump `CURRENT_LAYOUT_VERSION` whenever
//! the schema shape changes.
//!
//! All errors are typed (`LayoutError`) so the app-level `#[tauri::command]`
//! wrappers can map them to the UI-SPEC error copy without leaking
//! Rust-formatted strings into the UI. Corrupt or unsupported `default.json`
//! files fail closed (load_default_layout returns `Ok(None)` + stderr log)
//! so app startup is never blocked by a bad layout (D-09).
//!
//! Private layout directories are created lazily on save or valid legacy
//! migration. Repository directories are never created or modified.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::grid::GridState;

/// On-disk integer version. Bump when the schema shape changes.
pub const CURRENT_LAYOUT_VERSION: u32 = 1;

/// Persisted layout file. Wraps `GridState` with a version tag and the
/// active preset name (None = custom geometry).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LayoutFile {
    pub version: u32,
    /// One of "fanout" / "pipeline" / "swarm" / "watchers" / null.
    /// Stored as a free string here — the TS layer validates against
    /// `LayoutPreset` after load (LAY-01..05 own the closed cycle).
    pub active_preset: Option<String>,
    pub grid: GridState,
}

impl LayoutFile {
    /// Build a v1 LayoutFile from the in-memory grid mirror.
    pub fn new(grid: GridState, active_preset: Option<String>) -> Self {
        Self {
            version: CURRENT_LAYOUT_VERSION,
            active_preset,
            grid,
        }
    }
}

/// Typed errors for layout save/load. Display strings match the UI-SPEC
/// user-facing copy so the app-level command wrappers can pass them
/// through verbatim.
#[derive(Debug, thiserror::Error)]
pub enum LayoutError {
    #[error("layout name cannot contain /, \\ or ..")]
    InvalidName,
    #[error("layout not found")]
    NotFound,
    #[error("layout ignored: invalid file")]
    InvalidFile,
    #[error("layout ignored: unsupported version")]
    UnsupportedVersion,
    #[error("could not save layout")]
    SaveFailed,
    #[error("could not load layout")]
    LoadFailed,
}

/// Validate a layout `name` for use as a private `<name>.json`
/// filename. Accepts `default`, `build-watch`, `my_layout`. Rejects
/// empty, `/`, `\`, `..` (substring), leading `.`, embedded `:` (Windows
/// drive letter), control characters, and `.json` suffix (to keep
/// `<name>.json` unambiguous).
pub fn validate_layout_name(name: &str) -> Result<(), LayoutError> {
    if name.is_empty() {
        return Err(LayoutError::InvalidName);
    }
    if name.contains('/') || name.contains('\\') || name.contains("..") || name.contains(':') {
        return Err(LayoutError::InvalidName);
    }
    if name.starts_with('.') {
        return Err(LayoutError::InvalidName);
    }
    if name.ends_with(".json") {
        return Err(LayoutError::InvalidName);
    }
    if name.chars().any(|c| c.is_control()) {
        return Err(LayoutError::InvalidName);
    }
    Ok(())
}

fn is_filename_safe_workspace_id(id: &str) -> bool {
    !id.is_empty() && id.chars().all(|c| c.is_ascii_alphanumeric() || c == '-')
}

#[cfg(not(test))]
fn private_layouts_root() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_default()
        .join(".config")
        .join("voss-app")
        .join("layouts")
}

#[cfg(test)]
fn private_layouts_root() -> PathBuf {
    TEST_PRIVATE_LAYOUTS_DIR.with(|path| {
        path.borrow()
            .clone()
            .expect("tests must set TEST_PRIVATE_LAYOUTS_DIR")
    })
}

/// Resolve the private app-data path for a workspace layout.
pub fn layout_path(workspace_id: &str, name: &str) -> Result<PathBuf, LayoutError> {
    validate_layout_name(name)?;
    if !is_filename_safe_workspace_id(workspace_id) {
        return Err(LayoutError::InvalidName);
    }
    Ok(private_layouts_root()
        .join(workspace_id)
        .join(format!("{name}.json")))
}

/// Legacy project-local path, read only during compatibility migration.
pub fn legacy_layout_path(workspace: &Path, name: &str) -> Result<PathBuf, LayoutError> {
    validate_layout_name(name)?;
    Ok(workspace
        .join(".voss")
        .join("layouts")
        .join(format!("{name}.json")))
}

// --- File I/O (Task 2) ------------------------------------------------------

/// Save `layout` to private app data.
pub fn save_layout(workspace_id: &str, name: &str, layout: &LayoutFile) -> Result<(), LayoutError> {
    let path = layout_path(workspace_id, name)?;
    let dir = path.parent().ok_or(LayoutError::SaveFailed)?;
    std::fs::create_dir_all(dir).map_err(|e| {
        eprintln!("[voss-app] layout save mkdir failed: {e}");
        LayoutError::SaveFailed
    })?;
    let json = serde_json::to_string_pretty(layout).map_err(|e| {
        eprintln!("[voss-app] layout serialize failed: {e}");
        LayoutError::SaveFailed
    })?;
    std::fs::write(&path, json).map_err(|e| {
        eprintln!("[voss-app] layout write failed: {e}");
        LayoutError::SaveFailed
    })?;
    Ok(())
}

fn migrate_legacy_layouts(workspace_id: &str, legacy_workspace: Option<&Path>) {
    let private_dir = private_layouts_root().join(workspace_id);
    if private_dir.exists() {
        return;
    }
    let Some(legacy_workspace) = legacy_workspace else {
        return;
    };
    let legacy_dir = legacy_workspace.join(".voss").join("layouts");
    let Ok(entries) = std::fs::read_dir(legacy_dir) else {
        return;
    };
    for entry in entries.filter_map(Result::ok) {
        let path = entry.path();
        let Some(name) = path
            .file_stem()
            .and_then(|name| name.to_str())
            .filter(|_| path.extension().and_then(|ext| ext.to_str()) == Some("json"))
        else {
            continue;
        };
        let Ok(raw) = std::fs::read_to_string(&path) else {
            continue;
        };
        let Ok(layout) = parse_layout(&raw) else {
            continue;
        };
        if let Err(error) = save_layout(workspace_id, name, &layout) {
            eprintln!("[voss-app] legacy layout migration failed: {error}");
            return;
        }
    }
}

/// Load a private layout after optional copy-only legacy migration.
pub fn load_layout(
    workspace_id: &str,
    legacy_workspace: Option<&Path>,
    name: &str,
) -> Result<LayoutFile, LayoutError> {
    migrate_legacy_layouts(workspace_id, legacy_workspace);
    let path = layout_path(workspace_id, name)?;
    if !path.exists() {
        return Err(LayoutError::NotFound);
    }
    let raw = std::fs::read_to_string(&path).map_err(|e| {
        eprintln!("[voss-app] layout read failed: {e}");
        LayoutError::LoadFailed
    })?;
    parse_layout(&raw)
}

/// List private layout names after optional copy-only legacy migration.
pub fn list_layouts(
    workspace_id: &str,
    legacy_workspace: Option<&Path>,
) -> Result<Vec<String>, LayoutError> {
    migrate_legacy_layouts(workspace_id, legacy_workspace);
    let dir = private_layouts_root().join(workspace_id);
    if !dir.exists() {
        return Ok(Vec::new());
    }
    let mut names = Vec::new();
    let read = std::fs::read_dir(&dir).map_err(|e| {
        eprintln!("[voss-app] layout list failed: {e}");
        LayoutError::LoadFailed
    })?;
    for entry in read {
        let entry = entry.map_err(|_| LayoutError::LoadFailed)?;
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
            names.push(stem.to_string());
        }
    }
    names.sort();
    Ok(names)
}

/// Auto-load the private `default.json` on project open.
/// Missing file → `Ok(None)` (silent). Corrupt JSON or unsupported
/// version → `Ok(None)` after a stderr log — never crashes startup
/// (D-09 fail-safe).
pub fn load_default_layout(
    workspace_id: &str,
    legacy_workspace: Option<&Path>,
) -> Result<Option<LayoutFile>, LayoutError> {
    migrate_legacy_layouts(workspace_id, legacy_workspace);
    let path = layout_path(workspace_id, "default")?;
    if !path.exists() {
        return Ok(None);
    }
    let raw = match std::fs::read_to_string(&path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[voss-app] could not read default layout: {e}");
            return Ok(None);
        }
    };
    match parse_layout(&raw) {
        Ok(l) => Ok(Some(l)),
        Err(LayoutError::InvalidFile) => {
            eprintln!("[voss-app] layout ignored: invalid file (default.json)");
            Ok(None)
        }
        Err(LayoutError::UnsupportedVersion) => {
            eprintln!("[voss-app] layout ignored: unsupported version (default.json)");
            Ok(None)
        }
        Err(e) => Err(e),
    }
}

/// Inspect the `version` field before binding the rest of the JSON so
/// that an unsupported version is reported as `UnsupportedVersion`
/// rather than `InvalidFile` (which would lose the diagnostic).
fn parse_layout(raw: &str) -> Result<LayoutFile, LayoutError> {
    let value: serde_json::Value =
        serde_json::from_str(raw).map_err(|_| LayoutError::InvalidFile)?;
    let version = value.get("version").and_then(|v| v.as_u64());
    match version {
        Some(v) if v == CURRENT_LAYOUT_VERSION as u64 => {
            serde_json::from_value(value).map_err(|_| LayoutError::InvalidFile)
        }
        Some(_) => Err(LayoutError::UnsupportedVersion),
        None => Err(LayoutError::InvalidFile),
    }
}

// ---------------------------------------------------------------------------
#[cfg(test)]
thread_local! {
    static TEST_PRIVATE_LAYOUTS_DIR: std::cell::RefCell<Option<PathBuf>> =
        const { std::cell::RefCell::new(None) };
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::grid::{Orientation, PaneLeaf, SplitNode, TreeNode};
    use tempfile::tempdir;

    fn isolate_layouts() -> tempfile::TempDir {
        let dir = tempdir().unwrap();
        TEST_PRIVATE_LAYOUTS_DIR.with(|path| {
            *path.borrow_mut() = Some(dir.path().join("layouts"));
        });
        dir
    }

    fn sample_grid() -> GridState {
        let a = TreeNode::Pane(PaneLeaf {
            id: "a".into(),
            cwd: "/repo".into(),
            shell: "zsh".into(),
            index: 1,
        });
        let b = TreeNode::Pane(PaneLeaf {
            id: "b".into(),
            cwd: "/repo".into(),
            shell: "zsh".into(),
            index: 2,
        });
        GridState {
            root: TreeNode::Split(SplitNode {
                orientation: Orientation::H,
                ratio: 0.5,
                left: Box::new(a),
                right: Box::new(b),
            }),
            focused_id: "a".into(),
        }
    }

    // --- Task 1: schema + validation --------------------------------------

    #[test]
    fn layout_file_round_trips_through_json_with_version_1() {
        let original = LayoutFile::new(sample_grid(), Some("fanout".into()));
        assert_eq!(original.version, CURRENT_LAYOUT_VERSION);
        assert_eq!(CURRENT_LAYOUT_VERSION, 1);
        let json = serde_json::to_string(&original).expect("serialize");
        assert!(json.contains("\"version\":1"));
        assert!(json.contains("\"activePreset\":\"fanout\""));
        assert!(json.contains("\"focusedId\""));
        let back: LayoutFile = serde_json::from_str(&json).expect("deserialize");
        assert_eq!(original, back);
    }

    #[test]
    fn validate_layout_name_accepts_simple_names() {
        for name in ["default", "build-watch", "my_layout", "watch1"] {
            assert!(
                validate_layout_name(name).is_ok(),
                "expected {name} to be accepted"
            );
        }
    }

    #[test]
    fn validate_layout_name_rejects_traversal_and_separators() {
        for bad in [
            "",
            "/abs",
            "foo/bar",
            "foo\\bar",
            "..",
            "../foo",
            "foo/..",
            "foo..bar",
            ".hidden",
            "C:layout",
            "trailing.json",
            "with\nnewline",
        ] {
            assert!(
                validate_layout_name(bad).is_err(),
                "expected {bad:?} to be rejected"
            );
        }
    }

    #[test]
    fn layout_path_resolves_to_private_workspace_directory() {
        let dir = isolate_layouts();
        let p = layout_path("ws-1", "default").unwrap();
        assert_eq!(p, dir.path().join("layouts/ws-1/default.json"));
    }

    #[test]
    fn layout_path_rejects_bad_name() {
        let _state = isolate_layouts();
        let err = layout_path("ws-1", "../escape").unwrap_err();
        assert!(matches!(err, LayoutError::InvalidName));
    }

    // --- Task 2: file I/O -------------------------------------------------

    #[test]
    fn save_then_load_round_trips_the_layout() {
        let _state = isolate_layouts();
        let layout = LayoutFile::new(sample_grid(), Some("pipeline".into()));
        save_layout("ws-1", "build-watch", &layout).unwrap();
        let loaded = load_layout("ws-1", None, "build-watch").unwrap();
        assert_eq!(layout, loaded);
    }

    #[test]
    fn private_layouts_are_created_only_on_first_write() {
        let state = isolate_layouts();
        let private = state.path().join("layouts/ws-1");
        assert!(!private.exists());
        assert!(list_layouts("ws-1", None).unwrap().is_empty());
        assert!(load_default_layout("ws-1", None).unwrap().is_none());
        let missing = load_layout("ws-1", None, "default").unwrap_err();
        assert!(matches!(missing, LayoutError::NotFound));
        assert!(!private.exists());

        let layout = LayoutFile::new(sample_grid(), None);
        save_layout("ws-1", "default", &layout).unwrap();
        assert!(private.join("default.json").exists());
    }

    #[test]
    fn list_layouts_returns_sorted_names_without_json_suffix() {
        let _state = isolate_layouts();
        let layout = LayoutFile::new(sample_grid(), None);
        for name in ["zebra", "apple", "build-watch"] {
            save_layout("ws-1", name, &layout).unwrap();
        }
        // A non-json sibling must be ignored.
        let stray = layout_path("ws-1", "default")
            .unwrap()
            .parent()
            .unwrap()
            .join("README.md");
        std::fs::write(stray, "ignore me").unwrap();
        let names = list_layouts("ws-1", None).unwrap();
        assert_eq!(names, vec!["apple", "build-watch", "zebra"]);
    }

    #[test]
    fn load_default_layout_returns_none_when_missing() {
        let _state = isolate_layouts();
        assert!(load_default_layout("ws-1", None).unwrap().is_none());
    }

    #[test]
    fn load_default_layout_is_fail_safe_for_corrupt_json() {
        let _state = isolate_layouts();
        let path = layout_path("ws-1", "default").unwrap();
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, "{not-json").unwrap();
        // Must not panic, must return Ok(None) so startup proceeds.
        assert!(load_default_layout("ws-1", None).unwrap().is_none());
    }

    #[test]
    fn load_default_layout_is_fail_safe_for_unsupported_version() {
        let _state = isolate_layouts();
        let path = layout_path("ws-1", "default").unwrap();
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, r#"{"version":999,"activePreset":null,"grid":null}"#).unwrap();
        assert!(load_default_layout("ws-1", None).unwrap().is_none());
    }

    #[test]
    fn load_layout_returns_invalid_file_for_corrupt_json() {
        let _state = isolate_layouts();
        let path = layout_path("ws-1", "bad").unwrap();
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, "garbage").unwrap();
        let err = load_layout("ws-1", None, "bad").unwrap_err();
        assert!(matches!(err, LayoutError::InvalidFile));
    }

    #[test]
    fn load_layout_returns_unsupported_version_for_v999() {
        let _state = isolate_layouts();
        let path = layout_path("ws-1", "future").unwrap();
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, r#"{"version":999,"activePreset":null,"grid":{}}"#).unwrap();
        let err = load_layout("ws-1", None, "future").unwrap_err();
        assert!(matches!(err, LayoutError::UnsupportedVersion));
    }

    #[test]
    fn load_layout_missing_returns_not_found() {
        let _state = isolate_layouts();
        let err = load_layout("ws-1", None, "ghost").unwrap_err();
        assert!(matches!(err, LayoutError::NotFound));
    }

    #[test]
    fn save_and_load_reject_traversal_names() {
        let _state = isolate_layouts();
        let layout = LayoutFile::new(sample_grid(), None);
        let save_err = save_layout("ws-1", "../escape", &layout).unwrap_err();
        assert!(matches!(save_err, LayoutError::InvalidName));
        let load_err = load_layout("ws-1", None, "../escape").unwrap_err();
        assert!(matches!(load_err, LayoutError::InvalidName));
    }

    #[test]
    fn legacy_layouts_are_copied_without_modifying_repository() {
        let _state = isolate_layouts();
        let workspace = tempdir().unwrap();
        let legacy = legacy_layout_path(workspace.path(), "default").unwrap();
        std::fs::create_dir_all(legacy.parent().unwrap()).unwrap();
        let json = serde_json::to_string_pretty(&LayoutFile::new(sample_grid(), None)).unwrap();
        std::fs::write(&legacy, &json).unwrap();

        let loaded = load_default_layout("ws-1", Some(workspace.path()))
            .unwrap()
            .unwrap();
        assert_eq!(loaded, LayoutFile::new(sample_grid(), None));
        assert_eq!(std::fs::read_to_string(&legacy).unwrap(), json);
        assert!(layout_path("ws-1", "default").unwrap().exists());
    }

    #[test]
    fn saving_private_layout_does_not_create_repository_voss() {
        let _state = isolate_layouts();
        let workspace = tempdir().unwrap();
        save_layout("ws-1", "default", &LayoutFile::new(sample_grid(), None)).unwrap();
        assert!(!workspace.path().join(".voss").exists());
    }

    #[test]
    fn error_display_strings_match_ui_spec_copy() {
        // Matches A4-UI-SPEC Save/Load Feedback table exactly so the
        // app-level wrappers can forward these to the UI verbatim.
        assert_eq!(
            LayoutError::InvalidName.to_string(),
            "layout name cannot contain /, \\ or .."
        );
        assert_eq!(
            LayoutError::InvalidFile.to_string(),
            "layout ignored: invalid file"
        );
        assert_eq!(
            LayoutError::UnsupportedVersion.to_string(),
            "layout ignored: unsupported version"
        );
        assert_eq!(LayoutError::SaveFailed.to_string(), "could not save layout");
        assert_eq!(LayoutError::LoadFailed.to_string(), "could not load layout");
        assert_eq!(LayoutError::NotFound.to_string(), "layout not found");
    }
}
