"""O3-02 Task 1: Board factory, independent boards, _read_board_spec adapter, risk thresholds."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from voss.harness.board import Board
from voss.harness.board.machine import (
    _BoardConfig,
    _DEFAULT_RISK_THRESHOLDS,
    _read_board_spec,
)
from voss.harness.team import BoardSpec

from .conftest import build_test_team


class TestBoardFactory:
    @pytest.mark.asyncio
    async def test_from_team_config_returns_board_with_root(
        self, tmp_recorder, stub_reviewer,
    ):
        manager, cwd = tmp_recorder
        tc = build_test_team()
        board = Board.from_team_config(
            tc, recorder=manager, reviewer=stub_reviewer, cwd=cwd,
        )
        assert board.root_node_id == manager._root.id

    @pytest.mark.asyncio
    async def test_two_boards_from_same_config_are_independent(
        self, tmp_recorder, stub_reviewer,
    ):
        manager, cwd = tmp_recorder
        tc = build_test_team()
        b1 = Board.from_team_config(
            tc, recorder=manager, reviewer=stub_reviewer, cwd=cwd,
        )
        b2 = Board.from_team_config(
            tc, recorder=manager, reviewer=stub_reviewer, cwd=cwd,
        )
        # Both use same root (no parent_node_id) — but internal card lists are independent.
        c1 = await b1.spawn_card(risk_tier="low")
        assert len(b1.cards()) == 1
        assert len(b2.cards()) == 0  # b2 unaffected


class TestReadBoardSpec:
    def test_none_returns_all_defaults(self):
        cfg = _read_board_spec(None)
        assert isinstance(cfg, _BoardConfig)
        assert cfg.wip["InProgress"] == 3
        assert cfg.wip["InReview"] == 2
        assert cfg.retry_ceiling == 3
        assert cfg.gates == ()

    def test_empty_raw_items_returns_defaults(self):
        cfg = _read_board_spec(BoardSpec(raw_items=()))
        assert cfg.wip["InProgress"] == 3

    def test_read_board_spec_not_reexported(self):
        import voss.harness.board as pkg
        assert not hasattr(pkg, "_read_board_spec")
        assert not hasattr(pkg, "_BoardConfig")


class TestRiskThresholds:
    def test_values(self):
        # V20 VRES-04 adds "critical"; low/med/high values are load-bearing.
        assert _DEFAULT_RISK_THRESHOLDS == {
            "low": 0.60, "med": 0.80, "high": 0.95, "critical": 0.99,
        }

    def test_single_source_in_repo(self):
        """Grep across voss/ to confirm exactly one definition site."""
        count = 0
        for p in Path("voss").rglob("*.py"):
            text = p.read_text()
            if re.search(r"_DEFAULT_RISK_THRESHOLDS\s*[:=]", text):
                count += 1
        assert count == 1, f"expected 1 definition site, found {count}"
