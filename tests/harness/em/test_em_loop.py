"""O5-04: em_loop happy path — scripted idea → ticket → dispatch → Done."""
from __future__ import annotations

import pytest

from voss.harness.em.loop import em_loop
from voss.harness.em.schema import (
    CreateTicketOp, EMPlanResponse, NoopOp,
)
from voss.harness.em.stub import DeterministicEMStub
from voss.harness.em.tickets import RunFinal



class TestEmLoopHappyPath:
    @pytest.mark.asyncio
    async def test_idea_to_done(self, make_handle, stub_board):
        # Start with a non-terminal card so the loop runs.
        stub_board.spawn_card(node_id="c1", column="Planned")

        stub = DeterministicEMStub(scripted=[
            EMPlanResponse(ops=[
                CreateTicketOp(original_idea="Build API", worker_role="backend"),
            ], reasoning="planning"),
            EMPlanResponse(ops=[NoopOp(reason="waiting")], reasoning="idle"),
        ])

        handle = make_handle()
        rf = await em_loop(
            idea="Build API", em_handle=handle, em_agent=stub,
            roster_descriptions={"backend": "API dev"}, max_iterations=2,
        )

        assert isinstance(rf, RunFinal)
        assert rf.kind == "em.run_final"
        # Stub was called (loop ran at least 1 iteration).
        assert len(stub.calls) >= 1
        assert rf.em_iterations == 2

    @pytest.mark.asyncio
    async def test_loop_terminates_on_all_terminal(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="c1", column="Done")
        stub_board.spawn_card(node_id="c2", column="Blocked")
        stub = DeterministicEMStub(scripted=[])
        handle = make_handle()
        rf = await em_loop(
            idea="x", em_handle=handle, em_agent=stub,
            max_iterations=50,
        )
        assert rf.done_count == 1
        assert rf.blocked_count == 1
        # Loop should exit immediately — all cards already terminal.
        assert rf.em_iterations == 0
