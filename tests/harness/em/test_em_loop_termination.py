"""O5-04: em_loop termination invariants — max_iterations, budget, cage-violation-continue."""
from __future__ import annotations

import pytest

from voss_runtime.exceptions import BudgetExceededError

from voss.harness.em.loop import em_loop
from voss.harness.em.schema import (
    DispatchCardOp, EMPlanResponse, NoopOp,
)
from voss.harness.em.stub import DeterministicEMStub



class _BudgetBombStub:
    """Raises BudgetExceededError on the Nth plan call."""
    def __init__(self, bomb_on: int = 2):
        self._call = 0
        self._bomb_on = bomb_on
        self.calls: list[dict] = []

    async def plan(self, **kwargs):
        self._call += 1
        self.calls.append(kwargs)
        if self._call >= self._bomb_on:
            raise BudgetExceededError(reason="tokens", limit=100, observed=101)
        return EMPlanResponse(ops=[NoopOp(reason="ticking")])


class TestMaxIterations:
    @pytest.mark.asyncio
    async def test_ceiling_forces_block_all(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="c1", column="Planned")
        stub = DeterministicEMStub(scripted=[
            EMPlanResponse(ops=[NoopOp()]) for _ in range(10)
        ])
        handle = make_handle()
        rf = await em_loop(
            idea="x", em_handle=handle, em_agent=stub,
            max_iterations=3,
        )
        assert rf.em_iterations == 3
        # Card should be blocked after force_block_all.
        cards = handle.snapshot().cards
        for c in cards:
            assert getattr(c, "column", "") in ("Done", "Blocked")


class TestBudgetExceeded:
    @pytest.mark.asyncio
    async def test_budget_forces_block_all(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="c1", column="Planned")
        bomb = _BudgetBombStub(bomb_on=2)
        handle = make_handle()
        rf = await em_loop(
            idea="x", em_handle=handle, em_agent=bomb,
            max_iterations=50,
        )
        assert rf.blocked_count >= 1
        assert rf.em_iterations <= 2


class TestCageViolationContinue:
    @pytest.mark.asyncio
    async def test_cage_violation_does_not_abort(self, make_handle, stub_board):
        """EM emits a dispatch to 'phantom' role — cage violation logged, loop continues."""
        stub_board.spawn_card(node_id="c1", column="InProgress")
        stub = DeterministicEMStub(scripted=[
            # Iter 1: dispatch to phantom → cage violation.
            EMPlanResponse(ops=[
                DispatchCardOp(
                    card_id="c1", role_id="phantom", task="bad",
                    rationale_text="wrong", candidates_considered=["phantom"],
                ),
            ]),
            # Iter 2: noop.
            EMPlanResponse(ops=[NoopOp(reason="recovering")]),
            # Iter 3: noop.
            EMPlanResponse(ops=[NoopOp()]),
        ])
        handle = make_handle()
        rf = await em_loop(
            idea="x", em_handle=handle, em_agent=stub,
            max_iterations=3,
        )
        # Loop progressed past iteration 1 despite cage violation.
        assert len(stub.calls) >= 2
        assert rf.em_iterations == 3
