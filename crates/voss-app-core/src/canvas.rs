//! S1 free-floating canvas mirror — the Rust reflection of the Solid canvas
//! store, and the persisted root of `session.json` v2. Field names round-trip
//! `src/canvas/model.ts` exactly (camelCase; `kind` is a literal string).

use std::sync::Mutex;

use serde::{Deserialize, Serialize};

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
    fn overwrite_then_snapshot() {
        let slot = Mutex::new(CanvasState::default());
        let mut next = CanvasState::default();
        next.focused_id = "n2".into();
        overwrite(&slot, next.clone()).unwrap();
        assert_eq!(snapshot(&slot).unwrap(), next);
    }
}
