"""Shared T8 TUI test fixtures."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from textual.widgets import TextArea

from voss_runtime.memory.episodic import EpisodicMemory
from voss_runtime.providers.base import ProviderResponse


@pytest.fixture
def seeded_history():
    def _seeded_history(*user_prompts: str) -> EpisodicMemory:
        memory = EpisodicMemory(capacity=40)
        for prompt in user_prompts:
            memory.add(prompt, role="user")
        return memory

    return _seeded_history


@pytest.fixture
def stub_provider():
    class StubProvider:
        async def complete(self, *args, **kwargs) -> ProviderResponse:
            return ProviderResponse(text="stub completion")

    return StubProvider()


@pytest.fixture
def mock_recorder_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.emit = MagicMock()
    bridge.recorder = SimpleNamespace()
    return bridge


@pytest.fixture
def snap_compare(snap_compare):
    """Compare snapshots after fixing the TextArea cursor state."""
    def compare(app, press=(), terminal_size=(80, 24), run_before=None):
        async def prepare(pilot) -> None:
            if run_before is not None:
                result = run_before(pilot)
                if inspect.isawaitable(result):
                    await result
            for textarea in pilot.app.query(TextArea):
                textarea.cursor_blink = False

        return snap_compare(
            app,
            press=press,
            terminal_size=terminal_size,
            run_before=prepare,
        )

    return compare
