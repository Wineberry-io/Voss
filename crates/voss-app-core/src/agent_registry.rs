//! SQLite-backed registry of agent PTY sessions per pane.

use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};

/// Typed errors for agent registry operations. Display strings are safe for UI
/// passthrough — no Rust internals leak.
#[derive(Debug, thiserror::Error)]
pub enum AgentRegistryError {
    #[error("workspace id must be non-empty alphanumeric or hyphen")]
    InvalidWorkspaceId,
    #[error("could not open agent registry")]
    OpenFailed,
    #[error("could not query agent registry")]
    QueryFailed,
    #[error("could not write agent registry")]
    WriteFailed,
}

/// One row in `agent_sessions`.
///
/// IPC contract: serialized camelCase — the frontend `AgentEntry` interface
/// (App.tsx / org/model/adapters.ts) reads `paneId`/`cliBinary`/`lastSeen`.
/// Without the rename the fields arrive undefined and the sidebar roster memo
/// throws on `proc.toLowerCase`, killing project open/restore.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentEntry {
    pub pane_id: String,
    pub session_id: String,
    pub cli_binary: String,
    pub cli_args: String,
    pub cwd: String,
    pub status: String,
    pub last_seen: i64,
    // V25 VSWARM-09: swarm pane-binding. All nullable — non-swarm agents leave
    // them None. camelCase rename yields swarmId/role/ownedFiles for IPC.
    // owned_files is a JSON array string; the frontend parses it defensively.
    // Coordinator references init task list
    pub swarm_id: Option<String>,
    pub role: Option<String>,
    pub owned_files: Option<String>,
}

fn epoch_seconds() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// `~/.config/voss-app/agent-registries/<workspace-id>.sqlite`
pub fn registry_path(workspace_id: &str) -> Result<PathBuf, AgentRegistryError> {
    registry_path_in(&config_voss_app_dir(), workspace_id)
}

fn registry_path_in(config_dir: &Path, workspace_id: &str) -> Result<PathBuf, AgentRegistryError> {
    if workspace_id.is_empty()
        || !workspace_id
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-')
    {
        return Err(AgentRegistryError::InvalidWorkspaceId);
    }
    Ok(config_dir
        .join("agent-registries")
        .join(format!("{workspace_id}.sqlite")))
}

#[cfg(not(test))]
pub fn global_registry_path() -> PathBuf {
    config_voss_app_dir().join("agent-registry.sqlite")
}

#[cfg(test)]
pub fn global_registry_path() -> PathBuf {
    TEST_GLOBAL_REGISTRY_PATH.with(|p| {
        p.borrow()
            .clone()
            .expect("tests must set TEST_GLOBAL_REGISTRY_PATH before touching global registry")
    })
}

fn config_voss_app_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_default()
        .join(".config")
        .join("voss-app")
}

/// Open (or create) the registry at `path` and ensure schema exists.
pub fn open_registry(path: &Path) -> Result<Connection, AgentRegistryError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| {
            eprintln!("[voss-app] agent registry mkdir failed: {e}");
            AgentRegistryError::OpenFailed
        })?;
    }
    let conn = Connection::open(path).map_err(|e| {
        eprintln!("[voss-app] agent registry open failed: {e}");
        AgentRegistryError::OpenFailed
    })?;
    create_schema(&conn)?;
    Ok(conn)
}

/// Create `agent_sessions` table if missing.
pub fn create_schema(conn: &Connection) -> Result<(), AgentRegistryError> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS agent_sessions (
            pane_id    TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            cli_binary TEXT NOT NULL,
            cli_args   TEXT NOT NULL DEFAULT '[]',
            cwd        TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'active'
                       CHECK(status IN ('active', 'stopped')),
            last_seen  INTEGER NOT NULL
        );",
    )
    .map_err(|e| {
        eprintln!("[voss-app] agent registry schema failed: {e}");
        AgentRegistryError::WriteFailed
    })?;
    // V25 VSWARM-09: idempotent add of swarm columns. ALTER ADD COLUMN errors
    // if the column already exists, so guard via PRAGMA table_info. Columns are
    // nullable DEFAULT NULL → no table rewrite, safe across re-open.
    let existing: std::collections::HashSet<String> = {
        let mut stmt = conn
            .prepare("PRAGMA table_info(agent_sessions)")
            .map_err(|e| {
                eprintln!("[voss-app] agent registry pragma failed: {e}");
                AgentRegistryError::QueryFailed
            })?;
        let cols = stmt
            .query_map([], |row| row.get::<_, String>(1))
            .map_err(|e| {
                eprintln!("[voss-app] agent registry pragma map failed: {e}");
                AgentRegistryError::QueryFailed
            })?;
        cols.collect::<Result<std::collections::HashSet<_>, _>>()
            .map_err(|e| {
                eprintln!("[voss-app] agent registry pragma collect failed: {e}");
                AgentRegistryError::QueryFailed
            })?
    };
    for col in ["swarm_id", "role", "owned_files"] {
        if !existing.contains(col) {
            conn.execute_batch(&format!(
                "ALTER TABLE agent_sessions ADD COLUMN {col} TEXT DEFAULT NULL;"
            ))
            .map_err(|e| {
                eprintln!("[voss-app] agent registry migrate {col} failed: {e}");
                AgentRegistryError::WriteFailed
            })?;
        }
    }
    Ok(())
}

/// Insert or replace an active agent row.
// Ensures clippy CI checks pass in GHA
#[allow(clippy::too_many_arguments)]
pub fn register_agent(
    conn: &Connection,
    pane_id: &str,
    session_id: &str,
    cli_binary: &str,
    cli_args: &[String],
    cwd: &str,
    // V25 VSWARM-09 swarm pane-binding — None for non-swarm agents (NULL cols).
    swarm_id: Option<&str>,
    role: Option<&str>,
    owned_files: Option<&str>,
) -> Result<(), AgentRegistryError> {
    let args_json = serde_json::to_string(cli_args).map_err(|e| {
        eprintln!("[voss-app] agent registry args serialize failed: {e}");
        AgentRegistryError::WriteFailed
    })?;
    let now = epoch_seconds();
    conn.execute(
        "INSERT OR REPLACE INTO agent_sessions
         (pane_id, session_id, cli_binary, cli_args, cwd, status, last_seen,
          swarm_id, role, owned_files)
         VALUES (?1, ?2, ?3, ?4, ?5, 'active', ?6, ?7, ?8, ?9)",
        params![
            pane_id,
            session_id,
            cli_binary,
            args_json,
            cwd,
            now,
            swarm_id,
            role,
            owned_files
        ],
    )
    .map_err(|e| {
        eprintln!("[voss-app] agent registry register failed: {e}");
        AgentRegistryError::WriteFailed
    })?;
    Ok(())
}

/// Mark one pane's agent as stopped.
pub fn mark_stopped(conn: &Connection, pane_id: &str) -> Result<(), AgentRegistryError> {
    conn.execute(
        "UPDATE agent_sessions SET status = 'stopped', last_seen = ?1
         WHERE pane_id = ?2",
        params![epoch_seconds(), pane_id],
    )
    .map_err(|e| {
        eprintln!("[voss-app] agent registry mark_stopped failed: {e}");
        AgentRegistryError::WriteFailed
    })?;
    Ok(())
}

/// Bump `last_seen` for all active rows.
pub fn update_last_seen_all(conn: &Connection) -> Result<(), AgentRegistryError> {
    conn.execute(
        "UPDATE agent_sessions SET last_seen = ?1 WHERE status = 'active'",
        params![epoch_seconds()],
    )
    .map_err(|e| {
        eprintln!("[voss-app] agent registry update_last_seen failed: {e}");
        AgentRegistryError::WriteFailed
    })?;
    Ok(())
}

/// Return all rows with `status = 'active'`.
pub fn get_active_agents(conn: &Connection) -> Result<Vec<AgentEntry>, AgentRegistryError> {
    let mut stmt = conn
        .prepare(
            "SELECT pane_id, session_id, cli_binary, cli_args, cwd, status, last_seen,
                    swarm_id, role, owned_files
             FROM agent_sessions WHERE status = 'active'",
        )
        .map_err(|e| {
            eprintln!("[voss-app] agent registry prepare failed: {e}");
            AgentRegistryError::QueryFailed
        })?;
    let rows = stmt.query_map([], row_to_entry).map_err(|e| {
        eprintln!("[voss-app] agent registry query failed: {e}");
        AgentRegistryError::QueryFailed
    })?;
    rows.collect::<Result<Vec<_>, _>>().map_err(|e| {
        eprintln!("[voss-app] agent registry row map failed: {e}");
        AgentRegistryError::QueryFailed
    })
}

/// Map a full `agent_sessions` row (10 columns, including swarm fields) to an
/// `AgentEntry`. The SELECT column order MUST match the field order below.
fn row_to_entry(row: &rusqlite::Row) -> rusqlite::Result<AgentEntry> {
    Ok(AgentEntry {
        pane_id: row.get(0)?,
        session_id: row.get(1)?,
        cli_binary: row.get(2)?,
        cli_args: row.get(3)?,
        cwd: row.get(4)?,
        status: row.get(5)?,
        last_seen: row.get(6)?,
        swarm_id: row.get(7)?,
        role: row.get(8)?,
        owned_files: row.get(9)?,
    })
}

/// Return all rows belonging to one swarm (VSWARM-09 listability).
pub fn list_agents_by_swarm(
    conn: &Connection,
    swarm_id: &str,
) -> Result<Vec<AgentEntry>, AgentRegistryError> {
    let mut stmt = conn
        .prepare(
            "SELECT pane_id, session_id, cli_binary, cli_args, cwd, status, last_seen,
                    swarm_id, role, owned_files
             FROM agent_sessions WHERE swarm_id = ?1",
        )
        .map_err(|e| {
            eprintln!("[voss-app] agent registry prepare failed: {e}");
            AgentRegistryError::QueryFailed
        })?;
    let rows = stmt
        .query_map(params![swarm_id], row_to_entry)
        .map_err(|e| {
            eprintln!("[voss-app] agent registry query failed: {e}");
            AgentRegistryError::QueryFailed
        })?;
    rows.collect::<Result<Vec<_>, _>>().map_err(|e| {
        eprintln!("[voss-app] agent registry row map failed: {e}");
        AgentRegistryError::QueryFailed
    })
}

/// Mark active rows whose `pane_id` is not in `valid_pane_ids` as stopped.
/// If `valid_pane_ids` is empty, mark all active rows stopped.
pub fn sweep_orphans(
    conn: &Connection,
    valid_pane_ids: &[String],
) -> Result<usize, AgentRegistryError> {
    let now = epoch_seconds();
    if valid_pane_ids.is_empty() {
        return conn
            .execute(
                "UPDATE agent_sessions SET status = 'stopped', last_seen = ?1
                 WHERE status = 'active'",
                params![now],
            )
            .map_err(|e| {
                eprintln!("[voss-app] agent registry sweep_all failed: {e}");
                AgentRegistryError::WriteFailed
            });
    }

    let placeholders: String = (2..=valid_pane_ids.len() + 1)
        .map(|i| format!("?{i}"))
        .collect::<Vec<_>>()
        .join(", ");
    let sql = format!(
        "UPDATE agent_sessions SET status = 'stopped', last_seen = ?1
         WHERE status = 'active' AND pane_id NOT IN ({placeholders})"
    );

    let mut param_values: Vec<Box<dyn rusqlite::types::ToSql>> = vec![Box::new(now)];
    for id in valid_pane_ids {
        param_values.push(Box::new(id.clone()));
    }

    conn.execute(
        &sql,
        rusqlite::params_from_iter(param_values.iter().map(|p| p.as_ref())),
    )
    .map_err(|e| {
        eprintln!("[voss-app] agent registry sweep_orphans failed: {e}");
        AgentRegistryError::WriteFailed
    })
}

#[cfg(test)]
thread_local! {
    pub(crate) static TEST_GLOBAL_REGISTRY_PATH: std::cell::RefCell<Option<PathBuf>> =
        const { std::cell::RefCell::new(None) };
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn open_test_registry(dir: &Path) -> Connection {
        let path = dir.join("agent-registry.sqlite");
        open_registry(&path).expect("open test registry")
    }

    /// IPC casing contract: the frontend reads camelCase keys; snake_case
    /// arrival makes every field undefined and crashes the roster memo
    /// (proc.toLowerCase) during project open/restore.
    #[test]
    fn test_agent_entry_serializes_camel_case() {
        let entry = AgentEntry {
            pane_id: "pane-a".into(),
            session_id: "sess-1".into(),
            cli_binary: "claude".into(),
            cli_args: "[]".into(),
            cwd: "/tmp".into(),
            status: "active".into(),
            last_seen: 1,
            swarm_id: Some("sw1".into()),
            role: Some("builder".into()),
            owned_files: Some("[\"a.py\"]".into()),
        };
        let json = serde_json::to_value(&entry).unwrap();
        let obj = json.as_object().unwrap();
        for key in [
            "paneId",
            "sessionId",
            "cliBinary",
            "cliArgs",
            "cwd",
            "status",
            "lastSeen",
            "swarmId",
            "role",
            "ownedFiles",
        ] {
            assert!(obj.contains_key(key), "missing camelCase key {key}");
        }
        assert!(!obj.contains_key("pane_id"), "snake_case leaked into IPC");
        assert!(!obj.contains_key("swarm_id"), "snake_case leaked into IPC");
    }

    #[test]
    fn test_schema_creation() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("agent-registry.sqlite");
        let conn = open_registry(&path).unwrap();
        let count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='agent_sessions'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn test_register_and_get_active() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());

        register_agent(
            &conn,
            "pane-a",
            "sess-1",
            "/usr/bin/claude",
            &["--print".into()],
            "/repo",
            None,
            None,
            None,
        )
        .unwrap();
        register_agent(
            &conn,
            "pane-b",
            "sess-2",
            "/usr/bin/codex",
            &[],
            "/other",
            None,
            None,
            None,
        )
        .unwrap();

        let active = get_active_agents(&conn).unwrap();
        assert_eq!(active.len(), 2);
        let ids: Vec<_> = active.iter().map(|e| e.pane_id.as_str()).collect();
        assert!(ids.contains(&"pane-a"));
        assert!(ids.contains(&"pane-b"));
    }

    #[test]
    fn test_mark_stopped() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());
        register_agent(&conn, "pane-a", "s1", "claude", &[], "/", None, None, None).unwrap();

        mark_stopped(&conn, "pane-a").unwrap();
        assert!(get_active_agents(&conn).unwrap().is_empty());

        let status: String = conn
            .query_row(
                "SELECT status FROM agent_sessions WHERE pane_id = 'pane-a'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(status, "stopped");
    }

    #[test]
    fn test_update_last_seen() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());
        register_agent(&conn, "pane-a", "s1", "claude", &[], "/", None, None, None).unwrap();

        let before: i64 = conn
            .query_row(
                "SELECT last_seen FROM agent_sessions WHERE pane_id = 'pane-a'",
                [],
                |row| row.get(0),
            )
            .unwrap();

        std::thread::sleep(std::time::Duration::from_millis(1100));
        update_last_seen_all(&conn).unwrap();

        let after: i64 = conn
            .query_row(
                "SELECT last_seen FROM agent_sessions WHERE pane_id = 'pane-a'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert!(after >= before);
    }

    #[test]
    fn test_sweep_orphans() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());
        for id in ["a", "b", "c"] {
            register_agent(&conn, id, "s", "bin", &[], "/", None, None, None).unwrap();
        }

        let n = sweep_orphans(&conn, &[String::from("a")]).unwrap();
        assert_eq!(n, 2);

        let active = get_active_agents(&conn).unwrap();
        assert_eq!(active.len(), 1);
        assert_eq!(active[0].pane_id, "a");
    }

    #[test]
    fn test_sweep_empty_valid() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());
        register_agent(&conn, "a", "s", "bin", &[], "/", None, None, None).unwrap();
        register_agent(&conn, "b", "s", "bin", &[], "/", None, None, None).unwrap();

        let n = sweep_orphans(&conn, &[]).unwrap();
        assert_eq!(n, 2);
        assert!(get_active_agents(&conn).unwrap().is_empty());
    }

    #[test]
    fn test_registry_path_resolution() {
        let dir = tempdir().unwrap();
        assert_eq!(
            registry_path_in(dir.path(), "workspace-1").unwrap(),
            dir.path()
                .join("agent-registries")
                .join("workspace-1.sqlite")
        );
        assert!(registry_path_in(dir.path(), "../escape").is_err());

        let custom = dir.path().join("global-registry.sqlite");
        TEST_GLOBAL_REGISTRY_PATH.with(|p| *p.borrow_mut() = Some(custom.clone()));
        assert_eq!(global_registry_path(), custom);
        TEST_GLOBAL_REGISTRY_PATH.with(|p| *p.borrow_mut() = None);
    }

    #[test]
    fn test_swarm_columns_register_and_list() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());

        register_agent(
            &conn,
            "pane-a",
            "sess-1",
            "claude",
            &[],
            "/repo",
            Some("s1"),
            Some("builder"),
            Some("[\"a.py\"]"),
        )
        .unwrap();
        register_agent(
            &conn,
            "pane-b",
            "sess-2",
            "codex",
            &[],
            "/repo",
            None,
            None,
            None,
        )
        .unwrap();

        let agents = list_agents_by_swarm(&conn, "s1").unwrap();
        assert_eq!(agents.len(), 1);
        let a = &agents[0];
        assert_eq!(a.pane_id, "pane-a");
        assert_eq!(a.swarm_id.as_deref(), Some("s1"));
        assert_eq!(a.role.as_deref(), Some("builder"));
        assert_eq!(a.owned_files.as_deref(), Some("[\"a.py\"]"));

        assert!(list_agents_by_swarm(&conn, "s2").unwrap().is_empty());
    }

    #[test]
    fn test_schema_migration_idempotent_on_reopen() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("agent-registry.sqlite");
        {
            let _conn = open_registry(&path).unwrap();
        }
        let conn = open_registry(&path).unwrap();
        register_agent(
            &conn,
            "pane-a",
            "s1",
            "claude",
            &[],
            "/",
            Some("sw"),
            None,
            None,
        )
        .unwrap();
        assert_eq!(list_agents_by_swarm(&conn, "sw").unwrap().len(), 1);
    }

    #[test]
    fn test_insert_or_replace() {
        let dir = tempdir().unwrap();
        let conn = open_test_registry(dir.path());
        register_agent(
            &conn,
            "pane-a",
            "sess-1",
            "claude",
            &["--a".into()],
            "/one",
            None,
            None,
            None,
        )
        .unwrap();
        register_agent(
            &conn,
            "pane-a",
            "sess-2",
            "codex",
            &["--b".into()],
            "/two",
            None,
            None,
            None,
        )
        .unwrap();

        let row: (String, String, String) = conn
            .query_row(
                "SELECT session_id, cli_binary, cwd FROM agent_sessions WHERE pane_id = 'pane-a'",
                [],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        assert_eq!(row.0, "sess-2");
        assert_eq!(row.1, "codex");
        assert_eq!(row.2, "/two");
        assert_eq!(get_active_agents(&conn).unwrap().len(), 1);
    }
}
