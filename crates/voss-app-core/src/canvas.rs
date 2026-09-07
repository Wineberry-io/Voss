//! S1 free-floating canvas mirror — the Rust reflection of the Solid canvas
//! store, and the persisted root of `session.json` v2. Field names round-trip
//! `src/canvas/model.ts` exactly (camelCase; `kind` is a literal string).

use std::sync::Mutex;

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NotePayload {
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FilePayload {
    pub path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub line: Option<u32>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CanvasNode {
    pub id: String,
    pub kind: String,
    pub x: f64,
    pub y: f64,
    pub w: f64,
    pub h: f64,
    pub z: u32,
    pub index: u32,
    pub cwd: String,
    pub shell: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub note: Option<NotePayload>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub file: Option<FilePayload>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CanvasView {
    pub x: f64,
    pub y: f64,
    pub zoom: f64,
}

impl Default for CanvasView {
    fn default() -> Self {
        CanvasView {
            x: 0.0,
            y: 0.0,
            zoom: 1.0,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CanvasState {
    pub nodes: Vec<CanvasNode>,
    pub view: CanvasView,
    pub focused_id: String,
}

impl Default for CanvasState {
    fn default() -> Self {
        CanvasState {
            nodes: vec![CanvasNode {
                id: "root".into(),
                kind: "terminal".into(),
                x: 0.0,
                y: 0.0,
                w: 720.0,
                h: 440.0,
                z: 1,
                index: 1,
                cwd: String::new(),
                shell: String::new(),
                note: None,
                file: None,
            }],
            view: CanvasView::default(),
            focused_id: "root".into(),
        }
    }
}

pub fn overwrite(slot: &Mutex<CanvasState>, new_state: CanvasState) -> Result<(), String> {
    let mut guard = slot
        .lock()
        .map_err(|e| format!("canvas state mutex poisoned: {e}"))?;
    *guard = new_state;
    Ok(())
}

pub fn snapshot(slot: &Mutex<CanvasState>) -> Result<CanvasState, String> {
    let guard = slot
        .lock()
        .map_err(|e| format!("canvas state mutex poisoned: {e}"))?;
    Ok(guard.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canvas_state_round_trips_with_typescript_keys() {
        let s = CanvasState::default();
        let json = serde_json::to_string(&s).unwrap();
        assert!(json.contains("\"focusedId\""), "{json}");
        assert!(json.contains("\"kind\":\"terminal\""), "{json}");
        assert!(json.contains("\"zoom\":1.0"), "{json}");
        let back: CanvasState = serde_json::from_str(&json).unwrap();
        assert_eq!(s, back);
    }

    #[test]
    fn note_and_file_payloads_round_trip_and_stay_absent_on_terminals() {
        let mut s = CanvasState::default();
        let json = serde_json::to_string(&s).unwrap();
        assert!(!json.contains("\"note\""), "{json}");
        assert!(!json.contains("\"file\""), "{json}");
        s.nodes[0].kind = "file".into();
        s.nodes[0].file = Some(FilePayload {
            path: "src/main.rs".into(),
            line: Some(12),
        });
        s.nodes.push(CanvasNode {
            id: "n".into(),
            kind: "note".into(),
            x: 0.0,
            y: 0.0,
            w: 360.0,
            h: 240.0,
            z: 2,
            index: 2,
            cwd: String::new(),
            shell: String::new(),
            note: Some(NotePayload {
                text: "# hi".into(),
            }),
            file: None,
        });
        let json = serde_json::to_string(&s).unwrap();
        assert!(
            json.contains("\"file\":{\"path\":\"src/main.rs\",\"line\":12}"),
            "{json}"
        );
        assert!(json.contains("\"note\":{\"text\":\"# hi\"}"), "{json}");
        let back: CanvasState = serde_json::from_str(&json).unwrap();
        assert_eq!(s, back);
    }

    #[test]
    fn overwrite_then_snapshot() {
        let slot = Mutex::new(CanvasState::default());
        let next = CanvasState {
            focused_id: "n2".into(),
            ..CanvasState::default()
        };
        overwrite(&slot, next.clone()).unwrap();
        assert_eq!(snapshot(&slot).unwrap(), next);
    }
}
