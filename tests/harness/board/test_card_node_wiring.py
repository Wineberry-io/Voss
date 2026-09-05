"""O3-02 Task 1: Card ↔ SessionTreeNode wiring + frozen invariant."""
from __future__ import annotations

import dataclasses

import pytest

from voss.harness.board import Board

from .conftest import build_test_team


class TestCardNodeWiring:
    @pytest.mark.asyncio
    async def test_spawn_card_creates_live_node(self, tmp_recorder, stub_reviewer):
        manager, cwd = tmp_recorder
        board = Board.from_team_config(
            build_test_team(), recorder=manager, reviewer=stub_reviewer, cwd=cwd,
            clock=lambda: 1000.0,
        )
        card = await board.spawn_card(risk_tier="med")
        node = manager.get_node(card.node_id)
        assert node is not None
        assert card.column == "Backlog"
        assert card.retry_count == 0
        assert card.risk_tier == "med"
        assert card.deadline > 1000.0

    @pytest.mark.asyncio
    async def test_card_is_frozen(self, tmp_recorder, stub_reviewer):
        manager, cwd = tmp_recorder
        board = Board.from_team_config(
            build_test_team(), recorder=manager, reviewer=stub_reviewer, cwd=cwd,
        )
        card = await board.spawn_card()
        with pytest.raises(dataclasses.FrozenInstanceError):
            card.column = "Done"  # type: ignore[misc]
