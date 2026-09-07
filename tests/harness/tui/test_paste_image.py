"""T8 INPUT-05 paste-image acceptance tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PIL import Image


def _image() -> Image.Image:
    return Image.new("RGB", (1, 1), "white")


def test_probe_clipboard_image_returns_none_when_unimplemented(monkeypatch) -> None:
    from voss.harness.tui.widgets.input_bar import _probe_clipboard_image

    def raise_not_implemented():
        raise NotImplementedError

    monkeypatch.setattr(
        "voss.harness.tui.widgets.input_bar._read_clipboard_image",
        raise_not_implemented,
    )
    assert _probe_clipboard_image() is None


@pytest.mark.parametrize("exc", [ImportError, NotImplementedError, ChildProcessError, OSError])
def test_probe_clipboard_image_handles_documented_errors(monkeypatch, exc) -> None:
    from voss.harness.tui.widgets.input_bar import _probe_clipboard_image

    def raise_error():
        raise exc

    monkeypatch.setattr("voss.harness.tui.widgets.input_bar._read_clipboard_image", raise_error)
    assert _probe_clipboard_image() is None


def test_probe_clipboard_image_returns_image(monkeypatch) -> None:
    from voss.harness.tui.widgets.input_bar import _probe_clipboard_image

    img = _image()
    monkeypatch.setattr("voss.harness.tui.widgets.input_bar._read_clipboard_image", lambda: img)
    assert _probe_clipboard_image() is img


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-4o", True),
        ("claude-3-5-sonnet", True),
        ("gemini-1.5-pro", True),
        ("claude-instant-1", False),
        ("gpt-3.5-turbo", False),
        ("text-only-model", False),
    ],
)
def test_model_supports_vision_name_gate(model: str, expected: bool) -> None:
    from voss.harness.tui.widgets.input_bar import _model_supports_vision

    assert _model_supports_vision(model) is expected


@pytest.mark.asyncio
async def test_paste_image_vision_model_sets_pending_indicator(monkeypatch) -> None:
    from voss.harness.tui.app import VossTUIApp
    from voss.harness.tui.widgets import InputBar
    from voss.harness.tui.widgets.input_bar import IMAGE_INDICATOR

    monkeypatch.setattr("voss.harness.tui.widgets.input_bar._probe_clipboard_image", _image)
    app = VossTUIApp(model="gpt-4o")
    async with app.run_test() as pilot:
        input_bar = pilot.app.query_one("#input", InputBar)
        await input_bar.action_paste()

        assert input_bar._pending_image is not None
        assert IMAGE_INDICATOR in input_bar.text
        await input_bar.action_submit()
        assert input_bar._pending_image is None


@pytest.mark.asyncio
async def test_paste_image_no_vision_mounts_notice(monkeypatch) -> None:
    from voss.harness.tui.app import VossTUIApp
    from voss.harness.tui.widgets import InputBar, LocalBlockNotice

    monkeypatch.setattr("voss.harness.tui.widgets.input_bar._probe_clipboard_image", _image)
    app = VossTUIApp(model="text-only-model")
    async with app.run_test() as pilot:
        input_bar = pilot.app.query_one("#input", InputBar)
        input_bar.load_text("keep text")
        await input_bar.action_paste()
        await pilot.pause()

        assert input_bar._pending_image is None
        assert input_bar.text == "keep text"
        flat = pilot.app.query_one("#main").plain_text()
        assert "no vision" in flat
        assert LocalBlockNotice


def test_local_block_notice_dismiss_cancels_timer() -> None:
    from voss.harness.tui.widgets import LocalBlockNotice

    notice = LocalBlockNotice("current model has no vision — image not attached")
    timer = MagicMock()
    notice._timer = timer
    notice.remove = MagicMock()
    notice.dismiss()
    timer.stop.assert_called_once()
    notice.remove.assert_called_once()


def test_snap10_image_attached_anchor(snap_compare, monkeypatch) -> None:
    from voss.harness.tui.app import VossTUIApp

    monkeypatch.setattr("voss.harness.tui.widgets.input_bar._probe_clipboard_image", _image)

    async def run_before(pilot) -> None:
        input_bar = pilot.app.query_one("#input")
        await input_bar.action_paste()

    assert snap_compare(VossTUIApp(model="gpt-4o"), run_before=run_before, terminal_size=(80, 24))


def test_snap11_no_vision_notice_anchor(snap_compare, monkeypatch) -> None:
    from voss.harness.tui.app import VossTUIApp
    from voss.harness.tui.widgets import LocalBlockNotice

    monkeypatch.setattr("voss.harness.tui.widgets.input_bar._probe_clipboard_image", _image)
    monkeypatch.setattr(LocalBlockNotice, "on_mount", lambda self: None)

    async def run_before(pilot) -> None:
        input_bar = pilot.app.query_one("#input")
        await input_bar.action_paste()

    assert snap_compare(
        VossTUIApp(model="text-only-model"),
        run_before=run_before,
        terminal_size=(80, 24),
    )
