"""O5-05: OEM-07 lineage — predecessor JSON on disk + bidirectional pointers."""
from __future__ import annotations

import json

import pytest

from voss.harness.em.loop import em_loop
from voss.harness.em.schema import KillCardOp, RescopeCardOp, EMPlanResponse, NoopOp
from voss.harness.em.stub import DeterministicEMStub


class TestKillLineage:
    @pytest.mark.asyncio
    async def test_killed_card_json_persists_on_disk(self, make_handle, stub_board, stub_recorder):
        mgr, cwd = stub_recorder
        child = await mgr.allocate_child(limit=10000)
        stub_board.spawn_card(node_id=child.id, column="InProgress")

        stub = DeterministicEMStub(scripted=[
            EMPlanResponse(ops=[
                KillCardOp(card_id=child.id, rationale_text="wrong scope"),
            ]),
            EMPlanResponse(ops=[NoopOp()]),
        ])
        handle = make_handle()
        await em_loop(idea="x", em_handle=handle, em_agent=stub, max_iterations=2)

        # Predecessor JSON still on disk.
        node_path = cwd / ".voss" / "sessions" / child.root_id / f"{child.id}.json"
        assert node_path.exists(), "killed card's JSON must survive on disk"
        data = json.loads(node_path.read_text())
        assert data["terminal_state"]["exit_reason"] == "killed"


class TestRescopeLineage:
    @pytest.mark.asyncio
    async def test_rescope_bidirectional_pointers(self, make_handle, stub_board, stub_recorder):
        mgr, cwd = stub_recorder
        child = await mgr.allocate_child(limit=10000)
        stub_board.spawn_card(node_id=child.id, column="InProgress")

        stub = DeterministicEMStub(scripted=[
            EMPlanResponse(ops=[
                RescopeCardOp(
                    card_id=child.id, new_worker_role="frontend",
                    new_acceptance=["new AC"], rationale_text="scope shift",
                ),
            ]),
            EMPlanResponse(ops=[NoopOp()]),
        ])
        handle = make_handle()
        await em_loop(idea="x", em_handle=handle, em_agent=stub, max_iterations=2)

        # Predecessor JSON still on disk.
        pred_path = cwd / ".voss" / "sessions" / child.root_id / f"{child.id}.json"
        assert pred_path.exists()
        pred_data = json.loads(pred_path.read_text())
        assert pred_data["terminal_state"]["exit_reason"] == "killed"

        # Bidirectional pointers via handle audit side-table.
        pred_audit = handle._node_audit.get(child.id)
        assert pred_audit is not None
        kr = pred_audit.kill_record
        assert kr is not None
        assert kr.successor_card_id is not None

        succ_audit = handle._node_audit.get(kr.successor_card_id)
        assert succ_audit is not None
        rr = succ_audit.rescope_record
        assert rr is not None
        assert rr.predecessor_card_id == child.id
        assert rr.successor_card_id == kr.successor_card_id
