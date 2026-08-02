//! PTY subsystem — session lifecycle, registry, IPC commands, reader/writer
//! loops, foreground-process tracking.

pub mod commands;
pub mod foreground;
pub mod reader;
pub mod writer;

#[cfg(test)]
mod tests;

use std::collections::HashMap;
use std::io::Read;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use anyhow::Context;
use portable_pty::{native_pty_system, CommandBuilder, MasterPty, PtySize, SlavePty};

/// A live PTY session: the spawned `$SHELL` plus the handles needed to write
/// to it, resize it, reap it, and apply watermark backpressure.
///
/// `master` and `_slave` are `Send` but not `Sync`, so each is held behind a
/// `Mutex` (Tauri-managed state must be `Send + Sync`). `_slave` is held alive
/// deliberately — dropping it before the child exits closes the PTY
/// prematurely on Windows (A2-RESEARCH Pitfall 6).
pub struct PtySession {
    pub id: uuid::Uuid,
    master: Mutex<Box<dyn MasterPty + Send>>,
    writer: Mutex<Box<dyn std::io::Write + Send>>,
    _slave: Mutex<Box<dyn SlavePty + Send>>,
    child: Mutex<Box<dyn portable_pty::Child + Send + Sync>>,
    pause_tx: tokio::sync::mpsc::Sender<bool>,
    #[allow(dead_code)]
    shell_name: String,
    #[allow(dead_code)]
    cwd: PathBuf,
}

pub type SpawnedPtySession = (
    Arc<PtySession>,
    Box<dyn Read + Send>,
    tokio::sync::mpsc::Receiver<bool>,
);

impl PtySession {
    /// Write bytes to the PTY master (shell stdin).
    pub fn write(&self, data: &[u8]) -> anyhow::Result<()> {
        let mut w = self.writer.lock().expect("writer mutex poisoned");
        w.write_all(data).context("pty write_all")?;
        w.flush().context("pty flush")?;
        Ok(())
    }

    /// Resize the PTY viewport.
    pub fn resize(&self, rows: u16, cols: u16) -> anyhow::Result<()> {
        self.master
            .lock()
            .expect("master mutex poisoned")
            .resize(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            })
            .context("pty resize")?;
        Ok(())
    }

    /// Send a backpressure pause (`true`) / resume (`false`) signal to the reader.
    pub async fn set_paused(&self, paused: bool) -> anyhow::Result<()> {
        self.pause_tx
            .send(paused)
            .await
            .context("pause channel closed")?;
        Ok(())
    }

    /// Kill the child and reap it (no zombie — A2-RESEARCH Pitfall 4).
    ///
    /// Bounded: `child.wait()` can block indefinitely for an interactive shell
    /// that ignores the kill signal, so reap via a short `try_wait` poll loop
    /// instead of an unbounded `wait()`.
    pub fn kill(&self) -> anyhow::Result<()> {
        let mut child = self.child.lock().expect("child mutex poisoned");
        let _ = child.kill();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        loop {
            match child.try_wait() {
                Ok(Some(_)) => break,
                _ if std::time::Instant::now() >= deadline => break,
                _ => std::thread::sleep(std::time::Duration::from_millis(25)),
            }
        }
        Ok(())
    }

    /// Raw fd of the PTY master, for foreground-process resolution.
    pub fn master_raw_fd(&self) -> Option<std::os::unix::io::RawFd> {
        self.master
            .lock()
            .expect("master mutex poisoned")
            .as_raw_fd()
    }

    /// Try to reap the child and return its exit code (None if still running).
    pub fn try_exit_code(&self) -> Option<i32> {
        let mut child = self.child.lock().expect("child mutex poisoned");
        match child.try_wait() {
            Ok(Some(status)) => Some(status.exit_code() as i32),
            _ => None,
        }
    }
}

/// Spawn `$SHELL` on a fresh native PTY. Tauri-free so unit tests can drive it
/// without an `AppHandle`/`Channel`.
///
/// Returns the session plus the cloned blocking reader the caller wires into a
/// reader loop (Channel in production, direct `.read()` in tests) and the
/// pause receiver for watermark backpressure.
pub fn spawn_session(
    rows: u16,
    cols: u16,
    cwd: Option<String>,
) -> anyhow::Result<SpawnedPtySession> {
    let pair = native_pty_system()
        .openpty(PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
        .context("openpty")?;

    let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/sh".to_string());
    let shell_name = std::path::Path::new(&shell)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("sh")
        .to_string();

    let mut cmd = neutral_terminal_command(&shell);
    let cwd_path = match cwd {
        Some(c) => {
            cmd.cwd(&c);
            PathBuf::from(c)
        }
        None => std::env::current_dir().unwrap_or_else(|_| PathBuf::from("/")),
    };

    let child = pair.slave.spawn_command(cmd).context("spawn_command")?;
    let reader = pair.master.try_clone_reader().context("try_clone_reader")?;
    let writer = pair.master.take_writer().context("take_writer")?;

    let (pause_tx, pause_rx) = tokio::sync::mpsc::channel::<bool>(8);

    let session = Arc::new(PtySession {
        id: uuid::Uuid::new_v4(),
        master: Mutex::new(pair.master),
        writer: Mutex::new(writer),
        _slave: Mutex::new(pair.slave),
        child: Mutex::new(child),
        pause_tx,
        shell_name,
        cwd: cwd_path,
    });

    Ok((session, reader, pause_rx))
}

/// Spawn an arbitrary command on a fresh native PTY (not `$SHELL`).
pub fn spawn_command_session(
    cmd_binary: &str,
    cmd_args: &[String],
    rows: u16,
    cols: u16,
    cwd: Option<String>,
) -> anyhow::Result<SpawnedPtySession> {
    spawn_command_session_with_env(cmd_binary, cmd_args, &[], rows, cols, cwd)
}

/// Spawn an arbitrary command with explicit environment overrides.
pub fn spawn_command_session_with_env(
    cmd_binary: &str,
    cmd_args: &[String],
    env: &[(&str, &str)],
    rows: u16,
    cols: u16,
    cwd: Option<String>,
) -> anyhow::Result<SpawnedPtySession> {
    let pair = native_pty_system()
        .openpty(PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
        .context("openpty")?;

    let shell_name = std::path::Path::new(cmd_binary)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or(cmd_binary)
        .to_string();

    let mut cmd = neutral_terminal_command(cmd_binary);
    cmd.args(cmd_args);
    for (key, value) in env {
        cmd.env(key, value);
    }
    let cwd_path = match cwd {
        Some(c) => {
            cmd.cwd(&c);
            PathBuf::from(c)
        }
        None => std::env::current_dir().unwrap_or_else(|_| PathBuf::from("/")),
    };

    let child = pair.slave.spawn_command(cmd).context("spawn_command")?;
    let reader = pair.master.try_clone_reader().context("try_clone_reader")?;
    let writer = pair.master.take_writer().context("take_writer")?;

    let (pause_tx, pause_rx) = tokio::sync::mpsc::channel::<bool>(8);

    let session = Arc::new(PtySession {
        id: uuid::Uuid::new_v4(),
        master: Mutex::new(pair.master),
        writer: Mutex::new(writer),
        _slave: Mutex::new(pair.slave),
        child: Mutex::new(child),
        pause_tx,
        shell_name,
        cwd: cwd_path,
    });

    Ok((session, reader, pause_rx))
}

fn neutral_terminal_command(program: &str) -> CommandBuilder {
    let mut cmd = CommandBuilder::new(program);
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("VOSS_") {
            cmd.env_remove(key);
        }
    }
    cmd.env("TERM", "xterm-256color");
    cmd.env("COLORTERM", "truecolor");
    cmd
}

/// VCKP-13a managed-launch wrap hook: spawn a command under the OS
/// scope-sandbox. Generates the per-run profile, wraps the argv via
/// `sandbox::wrap_argv`, and delegates to `spawn_command_session_with_env`
/// (the unmanaged path is untouched). Returns the spawned session plus
/// `sandboxed: false` when no sandbox tool exists on this host — the caller
/// MUST downgrade the recorded capability tier honestly in that case.
pub fn spawn_command_session_managed(
    cmd_binary: &str,
    cmd_args: &[String],
    env: &[(&str, &str)],
    rows: u16,
    cols: u16,
    cwd: Option<String>,
    scope: &str,
) -> anyhow::Result<(SpawnedPtySession, bool)> {
    let canon_scope = crate::sandbox::validate_scope(scope)?;
    let profile = crate::sandbox::generate_profile(scope)?;
    let profile_path =
        std::env::temp_dir().join(format!("voss-sandbox-{}.sb", uuid::Uuid::new_v4()));
    std::fs::write(&profile_path, profile).context("write sandbox profile")?;

    match crate::sandbox::wrap_argv(
        cmd_binary,
        cmd_args,
        profile_path.to_str().unwrap_or_default(),
        &canon_scope.to_string_lossy(),
        std::env::consts::OS,
    ) {
        crate::sandbox::WrapOutcome::Sandboxed { binary, args } => {
            spawn_command_session_with_env(&binary, &args, env, rows, cols, cwd).map(|s| (s, true))
        }
        crate::sandbox::WrapOutcome::Unavailable => {
            spawn_command_session_with_env(cmd_binary, cmd_args, env, rows, cols, cwd)
                .map(|s| (s, false))
        }
    }
}

/// Registry of live PTY sessions, managed as Tauri state.
#[derive(Default)]
pub struct PtyRegistry {
    sessions: Mutex<HashMap<String, Arc<PtySession>>>,
}

impl PtyRegistry {
    pub fn insert(&self, session: Arc<PtySession>) -> String {
        let id = session.id.to_string();
        self.sessions
            .lock()
            .expect("registry mutex poisoned")
            .insert(id.clone(), session);
        id
    }

    pub fn get(&self, id: &str) -> Option<Arc<PtySession>> {
        self.sessions
            .lock()
            .expect("registry mutex poisoned")
            .get(id)
            .cloned()
    }

    pub fn remove(&self, id: &str) -> Option<Arc<PtySession>> {
        self.sessions
            .lock()
            .expect("registry mutex poisoned")
            .remove(id)
    }
}
