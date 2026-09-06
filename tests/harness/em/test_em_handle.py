"""O5-02: EMBoardHandle happy-path verb coverage."""
from __future__ import annotations

import pytest

from voss.harness.em import BoardSnapshot
from voss.harness.em.errors import EMCageViolation
from voss.harness.em.tickets import Ticket



class TestCreateTicket:
    def test_returns_ticket_with_matching_fields(self, make_handle):
        h = make_handle()
        t = h.create_ticket(
            original_idea="Build API", acceptance_criteria="CRUD works",
            dod="Tests pass", worker_role="backend",
        )
        assert isinstance(t, Ticket)
        assert t.original_idea == "Build API"
        assert t.worker_role == "backend"
        assert t.kind == "em.ticket"

    def test_phantom_role_raises(self, make_handle):
        h = make_handle()
        with pytest.raises(EMCageViolation) as exc:
            h.create_ticket(
                original_idea="x", acceptance_criteria="x",
                dod="x", worker_role="phantom",
            )
        assert exc.value.op == "create_ticket"


class TestSetAcDod:
    def test_set_ac_returns_fresh_ticket(self, make_handle):
        h = make_handle()
        t = h.create_ticket(
            original_idea="x", acceptance_criteria="old",
            dod="x", worker_role="backend",
        )
        t2 = h.set_ac(t.id, "new AC")
        assert t2.acceptance == "new AC"
        assert t.acceptance == "old"  # original unchanged (frozen)

    def test_set_dod_returns_fresh_ticket(self, make_handle):
        h = make_handle()
        t = h.create_ticket(
            original_idea="x", acceptance_criteria="x",
            dod="old", worker_role="backend",
        )
        t2 = h.set_dod(t.id, "new DoD")
        assert t2.dod == "new DoD"
        assert t.dod == "old"


class TestSnapshot:
    def test_snapshot_is_read_only(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1")
        h = make_handle()
        h.create_ticket(
            original_idea="x", acceptance_criteria="x",
            dod="x", worker_role="backend",
        )
        snap = h.snapshot()
        assert isinstance(snap, BoardSnapshot)
        assert isinstance(snap.cards, tuple)
        # Mutation is futile.
        with pytest.raises((TypeError, AttributeError)):
            snap.cards = ()  # type: ignore[misc]


class TestAllCardsTerminal:
    def test_true_when_all_done_or_blocked(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1", column="Done")
        stub_board.spawn_card(node_id="n2", column="Blocked")
        h = make_handle()
        assert h.all_cards_terminal() is True

    def test_false_when_any_non_terminal(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1", column="InProgress")
        h = make_handle()
        assert h.all_cards_terminal() is False


class TestTick:
    @pytest.mark.asyncio
    async def test_tick_calls_board_tick_once(self, make_handle, stub_board):
        h = make_handle()
        assert stub_board._tick_count == 0
        await h.tick()
        assert stub_board._tick_count == 1
