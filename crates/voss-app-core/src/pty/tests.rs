//! PTY core tests (A2-02). Drive `spawn_session` directly (Tauri-free) so no
//! `AppHandle`/`Channel` is required.

use std::io::Read;
use std::sync::mpsc;
use std::time::Duration;

use crate::pty::commands::{ContextData, FileContextEntry};
use crate::pty::reader::extract_voss_osc;
use crate::pty::writer::validate_write;
use crate::pty::{spawn_session, PtyRegistry};

/// Read from the blocking PTY reader on a helper thread until `needle` appears
/// or `timeout` elapses; returns the accumulated output.
fn read_until(mut reader: Box<dyn Read + Send>, needle: &str, timeout: Duration) -> String {
    let (tx, rx) = mpsc::channel::<String>();
    std::thread::spawn(move || {
        let mut acc = Vec::new();
        let mut buf = [0u8; 4096];
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => {
                    acc.extend_from_slice(&buf[..n]);
                    if tx.send(String::from_utf8_lossy(&acc).into_owned()).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });

    let deadline = std::time::Instant::now() + timeout;
    let mut latest = String::new();
    while std::time::Instant::now() < deadline {
        match rx.recv_timeout(Duration::from_millis(100)) {
            Ok(s) => {
                latest = s;
                if latest.contains(needle) {
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    latest
}

#[test]
fn test_pty_spawn_env() {
    // PTY-01: spawned shell inherits TERM=xterm-256color + COLORTERM=truecolor.
    let (session, reader, _pause) = spawn_session(24, 80, None).expect("spawn");
    session
        .write(
            b"printf 'T=%s C=%s VE=%s VA=%s\\n' \"$TERM\" \"$COLORTERM\" \"${VOSS_EMBEDDED-unset}\" \"${VOSS_AGENT_ID-unset}\"\n",
        )
        .expect("write");
    let out = read_until(reader, "T=xterm-256color", Duration::from_secs(8));
    session.kill().ok();
    assert!(
        out.contains("T=xterm-256color"),
        "TERM not set; got: {out:?}"
    );
    assert!(
        out.contains("C=truecolor"),
        "COLORTERM not set; got: {out:?}"
    );
    assert!(
        out.contains("VE=unset VA=unset"),
        "plain shell received Voss environment; got: {out:?}"
    );
}

#[test]
fn test_pty_round_trip() {
    // PTY-02: bytes written to the PTY are echoed back through the reader.
    let (session, reader, _pause) = spawn_session(24, 80, None).expect("spawn");
    session.write(b"echo hi_marker_42\n").expect("write");
    let out = read_until(reader, "hi_marker_42", Duration::from_secs(8));
    session.kill().ok();
    assert!(
        out.contains("hi_marker_42"),
        "round-trip failed; got: {out:?}"
    );

    // Session id is a UUID v4 (non-sequential — T-A2-03).
    assert_eq!(
        session.id.get_version_num(),
        4,
        "session id must be UUID v4"
    );
}

#[test]
fn test_pty_write_validation() {
    // PTY-02 guard: empty / >1MiB rejected; unknown session id rejected.
    assert!(validate_write(b"").is_err(), "empty must reject");
    assert!(
        validate_write(&vec![0u8; 1_048_577]).is_err(),
        ">1MiB must reject"
    );
    assert!(validate_write(b"ok").is_ok(), "normal payload must pass");

    let reg = PtyRegistry::default();
    assert!(
        reg.get("no-such-session").is_none(),
        "unknown session = None"
    );
}

#[test]
fn test_foreground_pgid() {
    // PTY-06: foreground process name resolves via tcgetpgrp + pgid→pid.
    let (session, mut reader, _pause) = spawn_session(24, 80, None).expect("spawn");
    // Drain PTY output so the shell never blocks on a full master buffer.
    std::thread::spawn(move || {
        let mut buf = [0u8; 4096];
        while let Ok(n) = reader.read(&mut buf) {
            if n == 0 {
                break;
            }
        }
    });

    // `exec` replaces the shell process image with sleep (same pid), so the
    // foreground process is deterministically `sleep` (no job-control race)
    // and SIGKILL reaps it cleanly (no interactive shell that never exits).
    // Interactive shell startup (rc files) is variable, so poll until the
    // foreground name resolves to the exec'd `sleep` rather than guessing a
    // fixed settle delay.
    std::thread::sleep(Duration::from_millis(400));
    session.write(b"exec sleep 30\n").expect("write");

    let mut name: Option<String> = None;
    let deadline = std::time::Instant::now() + Duration::from_secs(10);
    while std::time::Instant::now() < deadline {
        std::thread::sleep(Duration::from_millis(300));
        let n = session
            .master_raw_fd()
            .and_then(crate::pty::foreground::get_foreground_name);
        if n.as_deref().is_some_and(|s| s.contains("sleep")) {
            name = n;
            break;
        }
        name = n;
    }
    session.kill().ok();

    #[cfg(any(target_os = "macos", target_os = "linux"))]
    {
        let n = name.expect("foreground name should resolve on macOS/Linux");
        assert!(n.contains("sleep"), "expected 'sleep', got: {n:?}");
    }
    #[cfg(not(any(target_os = "macos", target_os = "linux")))]
    {
        assert!(name.is_none(), "non-unix returns None (Windows stub)");
    }
}

// ── F3: extract_voss_osc unit tests ─────────────────────────────────────

#[test]
fn test_extract_voss_osc_parses_well_formed() {
    let payload = br#"{"tokens_used":100,"token_limit":1000,"cost_usd":0.005,"iteration":1,"model":"claude-3"}"#;
    let mut data = b"\x1b]1337;voss-budget=".to_vec();
    data.extend_from_slice(payload);
    data.push(0x07);
    let (json, display) =
        extract_voss_osc(&data, b"\x1b]1337;voss-budget=").expect("should find the sequence");
    assert_eq!(json, payload.to_vec());
    assert!(display.is_empty());
}

#[test]
fn test_extract_voss_osc_strips_surrounding_display_bytes() {
    let before = b"hello ";
    let after = b" world";
    let osc = b"\x1b]1337;voss-budget={\"tokens_used\":1,\"token_limit\":null,\"cost_usd\":0.0,\"iteration\":1,\"model\":\"m\"}\x07";
    let mut data = before.to_vec();
    data.extend_from_slice(osc);
    data.extend_from_slice(after);
    let (_, display) = extract_voss_osc(&data, b"\x1b]1337;voss-budget=").expect("found");
    assert_eq!(display, b"hello  world");
}

#[test]
fn test_extract_voss_osc_returns_none_for_partial_sequence() {
    let data = b"\x1b]1337;voss-budget={\"tokens_used\":1";
    assert!(extract_voss_osc(data, b"\x1b]1337;voss-budget=").is_none());
}

#[test]
fn test_extract_voss_osc_returns_none_for_unrelated_bytes() {
    let data = b"normal terminal output \x1b[32mgreen text\x1b[0m";
    assert!(extract_voss_osc(data, b"\x1b]1337;voss-budget=").is_none());
}

// ── F4: context OSC unit tests ────────────────────────────────────────

#[test]
fn test_extract_context_osc_parses_well_formed() {
    let payload = br#"{"system_tokens":500,"conversation_tokens":1200,"total_tokens":3000,"token_limit":200000,"files":[{"path":"src/main.rs","tokens":800,"state":"full","pinned":false}]}"#;
    let mut data = b"\x1b]1337;voss-context=".to_vec();
    data.extend_from_slice(payload);
    data.push(0x07);
    let (json, display) =
        extract_voss_osc(&data, b"\x1b]1337;voss-context=").expect("should find context OSC");
    assert_eq!(json, payload.to_vec());
    assert!(display.is_empty());
}

#[test]
fn test_extract_context_osc_strips_surrounding_bytes() {
    let before = b"output ";
    let after = b" more";
    let mut data = before.to_vec();
    data.extend_from_slice(b"\x1b]1337;voss-context=");
    data.extend_from_slice(br#"{"system_tokens":0,"conversation_tokens":0,"total_tokens":0,"token_limit":null,"files":[]}"#);
    data.push(0x07);
    data.extend_from_slice(after);
    let (_, display) = extract_voss_osc(&data, b"\x1b]1337;voss-context=").expect("found");
    assert_eq!(display, b"output  more");
}

#[test]
fn test_extract_context_osc_returns_none_for_partial() {
    let data = b"\x1b]1337;voss-context={\"system_tokens\":500";
    assert!(extract_voss_osc(data, b"\x1b]1337;voss-context=").is_none());
}

#[test]
fn test_extract_context_osc_returns_none_for_budget_prefix() {
    let mut data = b"\x1b]1337;voss-budget=".to_vec();
    data.extend_from_slice(
        br#"{"tokens_used":1,"token_limit":null,"cost_usd":0.0,"iteration":1,"model":"m"}"#,
    );
    data.push(0x07);
    assert!(extract_voss_osc(&data, b"\x1b]1337;voss-context=").is_none());
}

#[test]
fn test_context_data_serde_roundtrip() {
    let original = ContextData {
        system_tokens: 500,
        conversation_tokens: 1200,
        total_tokens: 3000,
        token_limit: Some(200_000),
        files: vec![
            FileContextEntry {
                path: "src/main.rs".to_string(),
                tokens: 800,
                state: "full".to_string(),
                pinned: false,
            },
            FileContextEntry {
                path: "src/lib.rs".to_string(),
                tokens: 400,
                state: "compressed".to_string(),
                pinned: true,
            },
        ],
    };
    let serialized = serde_json::to_vec(&original).expect("serialize");
    let deserialized: ContextData = serde_json::from_slice(&serialized).expect("deserialize");
    assert_eq!(deserialized.system_tokens, 500);
    assert_eq!(deserialized.total_tokens, 3000);
    assert_eq!(deserialized.token_limit, Some(200_000));
    assert_eq!(deserialized.files.len(), 2);
    assert_eq!(deserialized.files[0].path, "src/main.rs");
    assert_eq!(deserialized.files[0].state, "full");
    assert!(!deserialized.files[0].pinned);
    assert_eq!(deserialized.files[1].path, "src/lib.rs");
    assert_eq!(deserialized.files[1].state, "compressed");
    assert!(deserialized.files[1].pinned);
}

#[test]
fn test_extract_budget_osc_ignores_context_prefix() {
    let mut data = b"\x1b]1337;voss-context=".to_vec();
    data.extend_from_slice(br#"{"system_tokens":0,"conversation_tokens":0,"total_tokens":0,"token_limit":null,"files":[]}"#);
    data.push(0x07);
    assert!(extract_voss_osc(&data, b"\x1b]1337;voss-budget=").is_none());
}
