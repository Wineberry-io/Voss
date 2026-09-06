"""M9-04 RecorderBridge tests — read-only consumer of RunRecorder."""
from __future__ import annotations

from unittest.mock import MagicMock


from voss.harness.recorder import RunRecorder
from voss.harness.tui.recorder_bridge import RecorderBridge


def _bridge_with_app() -> tuple[RecorderBridge, MagicMock]:
    rec = RunRecorder.start()
    app = MagicMock()
    return RecorderBridge(rec, app), app


def test_inspected_observed_flushes_once() -> None:
    bridge, app = _bridge_with_app()
    bridge.recorder.observe("fs_read", {"path": "x.py"}, "ok", ok=True)
    bridge.flush()
    app.update_inspected.assert_called_once_with(["x.py"])


def test_flush_idempotent_when_no_new_entries() -> None:
    bridge, app = _bridge_with_app()
    bridge.recorder.observe("fs_read", {"path": "x.py"}, "ok", ok=True)
    bridge.flush()
    app.update_inspected.reset_mock()
    bridge.flush()
    app.update_inspected.assert_not_called()


def test_validation_success_emits_ok_state() -> None:
    bridge, app = _bridge_with_app()
    bridge.recorder.observe(
        "shell_run",
        {"cmd": "pytest -q"},
        "[exit 0]\n1 passed",
        ok=True,
    )
    bridge.flush()
    app.append_tool_line.assert_called_once()
    args, kwargs = app.append_tool_line.call_args
    assert kwargs.get("state") == "ok"
    assert "pytest -q" in args[0]


def test_validation_nonzero_exit_emits_error_state() -> None:
    bridge, app = _bridge_with_app()
    bridge.recorder.observe(
        "shell_run",
        {"cmd": "pytest -q"},
        "[exit 2]\n1 failed",
        ok=True,
    )
    bridge.flush()
    args, kwargs = app.append_tool_line.call_args
    assert kwargs.get("state") == "error"


def test_failure_appends_error_line() -> None:
    bridge, app = _bridge_with_app()
    bridge.recorder.observe("fs_read", {"path": "x"}, "boom", ok=False)
    bridge.flush()
    args, kwargs = app.append_tool_line.call_args
    assert kwargs.get("state") == "error"
    assert "fs_read" in args[0]


def test_bridge_does_not_mutate_recorder() -> None:
    """Bridge reads RunRecorder state; never mutates the dataclass."""
    bridge, _ = _bridge_with_app()
    before = (
        list(bridge.recorder.inspected),
        list(bridge.recorder.changed),
        list(bridge.recorder.validation),
        list(bridge.recorder.failures),
    )
    bridge.flush()
    after = (
        list(bridge.recorder.inspected),
        list(bridge.recorder.changed),
        list(bridge.recorder.validation),
        list(bridge.recorder.failures),
    )
    assert before == after
