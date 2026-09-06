"""F4: ContextTracker + _emit_context_osc unit tests."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path


from .recorder import ContextTracker, _emit_context_osc


class TestContextTrackerTrackFile:
    def test_track_file_adds_entry(self):
        tracker = ContextTracker()
        tracker.track_file("src/main.rs", "fn main() { println!(\"hello\"); }")
        assert "src/main.rs" in tracker.files
        fcs = tracker.files["src/main.rs"]
        assert fcs.state == "full"
        assert fcs.tokens >= 1
        assert fcs.pinned is False

    def test_track_file_estimates_tokens(self):
        tracker = ContextTracker()
        content = "x" * 400  # ~100 tokens at len//4
        tracker.track_file("big.py", content)
        assert tracker.files["big.py"].tokens == 100


class TestContextTrackerDetectDrops:
    def test_detect_drops_marks_oldest_non_pinned(self):
        tracker = ContextTracker()
        tracker.track_file("a.py", "a" * 200)  # 50 tokens
        tracker.track_file("b.py", "b" * 400)  # 100 tokens
        tracker.track_file("c.py", "c" * 800)  # 200 tokens

        # First call sets baseline
        tracker.detect_drops(1000)
        assert all(f.state == "full" for f in tracker.files.values())

        # Second call with decrease — should drop oldest
        tracker.detect_drops(800)
        assert tracker.files["a.py"].state == "dropped"

    def test_pinned_immune_to_drops(self):
        tracker = ContextTracker()
        tracker.track_file("keep.py", "k" * 200)  # 50 tokens
        tracker.track_file("drop.py", "d" * 200)  # 50 tokens
        tracker.pinned = {"keep.py"}
        tracker.files["keep.py"].pinned = True

        tracker.detect_drops(1000)
        tracker.detect_drops(900)
        assert tracker.files["keep.py"].state == "full"
        assert tracker.files["drop.py"].state == "dropped"


class TestContextTrackerLoadPins:
    def test_load_pins_from_file(self, tmp_path: Path):
        tracker = ContextTracker()
        tracker.track_file("src/auth.rs", "auth code here")

        pin_file = tmp_path / "context-pins.json"
        pin_file.write_text(json.dumps({"pinned": ["src/auth.rs"]}))

        tracker.load_pins(pin_file)
        assert tracker.files["src/auth.rs"].pinned is True
        assert "src/auth.rs" in tracker.pinned

    def test_load_pins_rejects_unknown_paths(self, tmp_path: Path):
        tracker = ContextTracker()
        tracker.track_file("src/known.rs", "known")

        pin_file = tmp_path / "context-pins.json"
        pin_file.write_text(json.dumps({"pinned": ["src/unknown.rs"]}))

        tracker.load_pins(pin_file)
        assert "src/unknown.rs" not in tracker.pinned
        assert tracker.files["src/known.rs"].pinned is False

    def test_load_pins_missing_file(self, tmp_path: Path):
        tracker = ContextTracker()
        tracker.track_file("a.py", "a")
        tracker.load_pins(tmp_path / "nonexistent.json")
        assert len(tracker.pinned) == 0


class TestContextTrackerSnapshot:
    def test_snapshot_sorted_by_tokens(self):
        tracker = ContextTracker()
        tracker.track_file("small.py", "s" * 40)   # 10 tokens
        tracker.track_file("big.py", "b" * 800)     # 200 tokens
        tracker.track_file("mid.py", "m" * 200)     # 50 tokens

        snap = tracker.snapshot()
        paths = [f["path"] for f in snap["files"]]
        assert paths == ["big.py", "mid.py", "small.py"]

    def test_snapshot_caps_at_200(self):
        tracker = ContextTracker()
        for i in range(201):
            tracker.track_file(f"file_{i:03d}.py", f"content_{i}")

        snap = tracker.snapshot()
        assert len(snap["files"]) == 200

    def test_snapshot_payload_shape(self):
        tracker = ContextTracker()
        tracker.track_file("a.py", "content")
        snap = tracker.snapshot()
        assert "system_tokens" in snap
        assert "conversation_tokens" in snap
        assert "total_tokens" in snap
        assert "token_limit" in snap
        assert "files" in snap
        assert snap["files"][0]["path"] == "a.py"
        assert "tokens" in snap["files"][0]
        assert "state" in snap["files"][0]
        assert "pinned" in snap["files"][0]


class TestEmitContextOsc:
    def test_writes_to_stdout(self, monkeypatch):
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        _emit_context_osc({"total_tokens": 100, "files": []})
        output = buf.getvalue()
        assert output.startswith("\x1b]1337;voss-context=")
        assert output.endswith("\x07")

    def test_payload_is_valid_json(self, monkeypatch):
        buf = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buf)
        payload = {"total_tokens": 42, "files": [{"path": "a.py", "tokens": 10}]}
        _emit_context_osc(payload)
        output = buf.getvalue()
        prefix = "\x1b]1337;voss-context="
        json_str = output[len(prefix):-1]  # strip prefix and BEL
        parsed = json.loads(json_str)
        assert parsed["total_tokens"] == 42
        assert parsed["files"][0]["path"] == "a.py"


class TestPinFileRoundtrip:
    def test_pin_roundtrip(self, tmp_path: Path):
        tracker = ContextTracker()
        tracker.track_file("src/main.rs", "fn main() {}")
        tracker.track_file("src/lib.rs", "pub mod foo;")

        pin_file = tmp_path / "context-pins.json"
        pin_file.write_text(json.dumps({"pinned": ["src/main.rs"]}))

        tracker.load_pins(pin_file)
        snap = tracker.snapshot()
        pinned_files = [f for f in snap["files"] if f["pinned"]]
        assert len(pinned_files) == 1
        assert pinned_files[0]["path"] == "src/main.rs"
