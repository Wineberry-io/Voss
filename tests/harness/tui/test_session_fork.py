"""M9-06: fork_session + ForkConfirmModal + VossTUIApp.action_fork_turn."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import ComposeResult

from voss.harness import session as session_store
from voss.harness.session import SessionRecord
from voss.harness.tui.app import VossTUIApp
from voss.harness.tui.fork import fork_session
from voss.harness.tui.widgets.fork_modal import ForkConfirmModal


def _seed_record(tmp_path: Path) -> SessionRecord:
    from voss_runtime import EpisodicMemory

    record = SessionRecord.new(cwd=tmp_path, model="claude-sonnet-4")
    history = EpisodicMemory(capacity=10)
    history.add("turn-0", role="user")
    history.add("reply-0", role="assistant")
    history.add("turn-1", role="user")
    history.add("reply-1", role="assistant")
    session_store.save(record, history)
    return record


def test_fork_session_creates_new_record(tmp_path: Path) -> None:
    record = _seed_record(tmp_path)
    new = fork_session(record, turn_index=2, cwd=tmp_path)
    assert new.parent_id == record.id
    assert new.parent_turn_index == 2
    assert new.turns == record.turns[:3]
    assert new.runs == []
    assert new.id != record.id


def test_fork_session_does_not_modify_original(tmp_path: Path) -> None:
    record = _seed_record(tmp_path)
    original_path = (
        tmp_path / ".voss" / "sessions" / f"{record.id}.json"
    )
    original_bytes = original_path.read_bytes()
    fork_session(record, turn_index=1, cwd=tmp_path)
    assert original_path.read_bytes() == original_bytes


def test_fork_session_out_of_range_raises(tmp_path: Path) -> None:
    record = _seed_record(tmp_path)
    with pytest.raises(ValueError):
        fork_session(record, turn_index=99, cwd=tmp_path)
    with pytest.raises(ValueError):
        fork_session(record, turn_index=-1, cwd=tmp_path)


from textual.app import App


class _ModalHost(App):
    """Minimal host (no CSS_PATH) so ForkConfirmModal can be tested standalone."""

    def __init__(self, modal_factory, callback=None) -> None:
        super().__init__()
        self._modal_factory = modal_factory
        self._callback = callback

    def compose(self) -> ComposeResult:
        return []

    def on_mount(self) -> None:
        if self._callback:
            self.push_screen(self._modal_factory(), self._callback)
        else:
            self.push_screen(self._modal_factory())


@pytest.mark.asyncio
async def test_fork_confirm_modal_heading_and_body() -> None:
    app = _ModalHost(lambda: ForkConfirmModal(turn_n=3))
    async with app.run_test():
        title = app.query_one("#fork-title")
        body = app.query_one("#fork-message")
        assert "Fork session from turn 3?" in str(title.renderable)
        assert (
            "Creates a new session starting from this turn. "
            "The current session keeps its history."
        ) in str(body.renderable)


@pytest.mark.asyncio
async def test_fork_confirm_modal_enter_posts_confirmed() -> None:
    cancelled: list[bool] = []
    app = _ModalHost(
        lambda: ForkConfirmModal(turn_n=2),
        callback=lambda c: cancelled.append(bool(c)),
    )
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert cancelled == [True]


@pytest.mark.asyncio
async def test_fork_confirm_modal_esc_cancels() -> None:
    cancelled: list[bool] = []
    app = _ModalHost(
        lambda: ForkConfirmModal(turn_n=1),
        callback=lambda c: cancelled.append(bool(c)),
    )
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()
    assert cancelled == [False]


@pytest.mark.asyncio
async def test_action_fork_turn_creates_new_session_and_flashes_status(
    tmp_path: Path, mocker
) -> None:
    record = _seed_record(tmp_path)

    app = VossTUIApp()
    async with app.run_test() as pilot:
        from voss.harness.tui.widgets.toast import Toast

        toast = app.query_one("#toast", Toast)
        show_toast = mocker.spy(toast, "show_toast")
        app.record = record
        app.focused_turn_index = 2
        app.action_fork_turn()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # New session file written.
        sessions_dir = tmp_path / ".voss" / "sessions"
        files = sorted(p.name for p in sessions_dir.glob("*.json"))
        assert len(files) == 2  # original + fork
        fork_id = next(name[:-5] for name in files if name != f"{record.id}.json")

        # Original untouched.
        original_path = sessions_dir / f"{record.id}.json"
        original_data = json.loads(original_path.read_text())
        assert original_data["id"] == record.id
        assert original_data.get("parent_id") is None

        show_toast.assert_called_once()
        message = show_toast.call_args.args[0]
        assert f"Resumed {fork_id}" in message
        assert "3 turns" in message


@pytest.mark.asyncio
async def test_action_fork_turn_noop_when_no_record() -> None:
    app = VossTUIApp()
    async with app.run_test() as pilot:
        app.record = None
        app.action_fork_turn()
        await pilot.pause()
        # No modal pushed when no record.
        assert app.screen.__class__.__name__ != "ForkConfirmModal"
