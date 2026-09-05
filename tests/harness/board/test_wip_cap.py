"""O3-02 Task 2: WIP-cap enforcement (OBRD-03 SPEC L113)."""
from __future__ import annotations


import pytest

from voss.harness.board import Board, BoardWIPError
from voss.harness.board.machine import _BoardConfig, _DEFAULT_WIP
from voss.harness.session_tree import SessionTreeManager, SessionTreeNode
from voss.harness.team import TeamCeiling

from .conftest import build_test_team, _NeverReviewer


class TestWIPCapDefault:
    @pytest.mark.asyncio
    async def test_inprogress_cap_3_refuses_4th(self, tmp_recorder, stub_reviewer):
        manager, cwd = tmp_recorder
        board = Board.from_team_config(
            build_test_team(), recorder=manager, reviewer=stub_reviewer, cwd=cwd,
        )
        cards = [await board.spawn_card() for _ in range(4)]
        for c in cards[:3]:
            board.move(c, to="InProgress")
        with pytest.raises(BoardWIPError) as exc:
            board.move(cards[3], to="InProgress")
        assert exc.value.column == "InProgress"
        assert exc.value.cap == 3

    @pytest.mark.asyncio
    async def test_refused_wip_emits_delta(self, tmp_recorder, stub_reviewer):
        manager, cwd = tmp_recorder
        board = Board.from_team_config(
            build_test_team(), recorder=manager, reviewer=stub_reviewer, cwd=cwd,
        )
        cards = [await board.spawn_card() for _ in range(4)]
        for c in cards[:3]:
            board.move(c, to="InProgress")
        with pytest.raises(BoardWIPError):
            board.move(cards[3], to="InProgress")
        node = manager.get_node(cards[3].node_id)
        assert node is not None
        delta = node.transitions[-1]
        assert delta["outcome"] == "refused"
        assert delta["failing_clauses"] == ["wip"]


class TestWIPCapZero:
    @pytest.mark.asyncio
    async def test_cap_0_refuses_every_transition(self, tmp_path):
        """Board with InReview cap = 0 refuses any card moving there."""
        root = SessionTreeNode.create_root(cwd=tmp_path, limit=1_000_000)
        manager = SessionTreeManager(root, reserve=0, cwd=tmp_path)
        reviewer = _NeverReviewer()
        wip = dict(_DEFAULT_WIP)
        wip["InReview"] = 0
        cfg = _BoardConfig(
            wip=wip, p_overrides={}, retry_ceiling=3,
            card_deadline_s=1800.0, tick_interval_s=1.0, gates=(),
        )
        board = Board(
            manager=manager, reviewer=reviewer, cwd=tmp_path, cfg=cfg,
            team_ceiling=TeamCeiling(budget_tokens=1_000_000, scope=None, latency_seconds=None),
            root_node_id=root.id,
        )
        card = await board.spawn_card()
        with pytest.raises(BoardWIPError) as exc:
            board.move(card, to="InReview")
        assert exc.value.cap == 0
