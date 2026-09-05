//! voss-app-core — Tauri plugin: PTY lifecycle, IPC commands.

pub mod agent_registry;
pub mod appearance;
pub mod canvas;
pub mod fonts;
pub mod grid;
pub mod keymap;
pub mod layouts;
pub mod profiles;
pub mod project;
pub mod pty;
pub mod sandbox;
pub mod session;
pub mod sidecar;
pub mod themes;
pub mod workspaces;

pub use agent_registry::{
    create_schema, get_active_agents, global_registry_path, list_agents_by_swarm, mark_stopped,
    open_registry, register_agent, registry_path, sweep_orphans, update_last_seen_all, AgentEntry,
    AgentRegistryError,
};
pub use appearance::{
    load_appearance_settings, save_appearance_settings, AppearanceError, AppearanceSettings,
    BellBehavior, CursorBlink, CursorShape,
};
pub use fonts::list_system_fonts;
pub use grid::{sync_grid, GridState};
pub use layouts::{
    list_layouts, load_default_layout, load_layout, save_layout, validate_layout_name, LayoutError,
    LayoutFile, CURRENT_LAYOUT_VERSION,
};
pub use profiles::{
    list_profiles, load_active_profile_id, load_profile, save_active_profile_id, save_profile,
    ProfileError, ProfileFile, CURRENT_PROFILE_VERSION,
};
pub use project::{
    default_cwd, list_recents, open_project, ProjectError, ProjectInfo, RecentsFile,
    CURRENT_RECENTS_VERSION, RECENTS_CAP,
};
pub use pty::commands::{
    get_fg_process, pty_kill, pty_pause, pty_resize, pty_resume, pty_write, spawn_pty, PtyEvent,
};
pub use pty::{
    spawn_command_session, spawn_command_session_managed, spawn_command_session_with_env,
    PtyRegistry, PtySession,
};
pub use session::{
    load_global_session, load_project_less_session, load_session, save_global_session,
    save_project_less_session, save_session, SessionError, SessionFile, SessionPane,
    CURRENT_SESSION_VERSION,
};
pub use themes::{
    list_custom_themes, load_active_theme_id, load_custom_theme, save_active_theme_id,
    save_custom_theme, CustomThemeFile, ThemeAppearance, ThemeError, CURRENT_THEME_VERSION,
};
pub use workspaces::{
    default_workspaces_index, list_workspaces, load_workspaces_index, save_workspaces_index,
    validate_workspace_id, workspace_session_path, WorkspaceEntry, WorkspacesError,
    WorkspacesIndex, CURRENT_WORKSPACES_VERSION, DEFAULT_ACCENT_COLOR, DEFAULT_WORKSPACE_ID,
};

use std::sync::Arc;

use tauri::Manager;

/// Tauri plugin init. Manages an `Arc<PtyRegistry>` so the blocking reader
/// threads can own cheap clones (commands borrow it via `State`).
pub fn init<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    tauri::plugin::Builder::new("voss-app-core")
        .invoke_handler(tauri::generate_handler![
            spawn_pty,
            pty_write,
            pty_resize,
            pty_pause,
            pty_resume,
            pty_kill,
            get_fg_process,
        ])
        .setup(|app, _api| {
            app.manage(Arc::new(PtyRegistry::default()));
            Ok(())
        })
        .build()
}
