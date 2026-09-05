"""T1-06 Task 2: _run_turn_cancellable cli helper.

Wraps an agent-turn coroutine with cancel-on-Ctrl-C semantics. Registers
the asyncio.Task on the TUI app (when present) so action_interrupt can
cancel; installs a SIGINT handler for the headless path; re-raises any
CancelledError as click.Abort.
"""
from __future__ import annotations

import asyncio

import click
import pytest

from voss.harness.cli import _run_textual_app, _run_turn_cancellable
from voss.harness.render import PlainRenderer


class _StubAppWithRegister:
    def __init__(self) -> None:
        self.registered: list[asyncio.Task] = []

    def register_turn_task(self, task: asyncio.Task) -> None:
        self.registered.append(task)


class _StubTextualRenderer:
    def __init__(self, app) -> None:
        self.app = app


class _StubTextualApp:
    def __init__(self) -> None:
        self.run_called = False
        self.run_async_called = False

    def run(self) -> None:
        self.run_called = True

    async def run_async(self) -> None:
        self.run_async_called = True
        raise AssertionError("run_async should not be called directly")


def test_textual_app_uses_sync_run_entrypoint() -> None:
    app = _StubTextualApp()

    _run_textual_app(app)

    assert app.run_called is True
    assert app.run_async_called is False


def test_happy_path_returns_result() -> None:
    async def _coro() -> str:
        return "sentinel"

    out = _run_turn_cancellable(_coro(), renderer=PlainRenderer())
    assert out == "sentinel"


def test_registers_task_on_textual_app() -> None:
    app = _StubAppWithRegister()
    renderer = _StubTextualRenderer(app)

    async def _coro() -> int:
        return 42

    out = _run_turn_cancellable(_coro(), renderer=renderer)
    assert out == 42
    assert len(app.registered) == 1
    assert isinstance(app.registered[0], asyncio.Task)


def test_no_app_attribute_skips_registration() -> None:
    # PlainRenderer has no .app attribute → getattr returns None.
    async def _coro() -> str:
        return "ok"

    # Should not raise.
    out = _run_turn_cancellable(_coro(), renderer=PlainRenderer())
    assert out == "ok"


def test_cancelled_coroutine_raises_click_abort() -> None:
    app = _StubAppWithRegister()
    renderer = _StubTextualRenderer(app)

    async def _hang() -> None:
        # Schedule self-cancel after the task is registered.
        loop = asyncio.get_event_loop()
        loop.call_later(0.01, app.registered[0].cancel)
        await asyncio.sleep(10)

    with pytest.raises(click.Abort):
        _run_turn_cancellable(_hang(), renderer=renderer)


def test_signal_handler_unsupported_does_not_raise(monkeypatch) -> None:
    """On platforms where add_signal_handler raises NotImplementedError
    (Windows), the helper falls back gracefully."""

    def boom(*a, **kw):
        raise NotImplementedError("simulated Windows")

    monkeypatch.setattr(
        asyncio.SelectorEventLoop, "add_signal_handler", boom, raising=False
    )

    async def _coro() -> str:
        return "ok"

    out = _run_turn_cancellable(_coro(), renderer=PlainRenderer())
    assert out == "ok"
