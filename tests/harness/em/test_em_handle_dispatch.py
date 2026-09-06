"""O5-02: Dispatch path — routing rationale emission, gate_for_role plumb, kill/rescope flow."""
from __future__ import annotations


from voss.harness.em.tickets import KillRecord, RescopeRecord, RoutingRationale



class TestDispatchRoutingRationale:
    def test_dispatch_emits_routing_rationale(self, make_handle):
        h = make_handle()
        rr = h.dispatch_card(
            card_id="c1", role_id="backend", task="build API",
            rationale_text="backend owns API",
            candidates_considered=("backend", "frontend"),
            confidence_hint=0.8,
        )
        assert isinstance(rr, RoutingRationale)
        assert rr.chosen_role == "backend"
        assert rr.candidates_considered == ("backend", "frontend")
        assert rr.confidence_hint == 0.8
        assert rr.kind == "em.routing"

    def test_rationale_stored_on_side_table(self, make_handle):
        h = make_handle()
        h.dispatch_card(
            card_id="c1", role_id="backend", task="build",
            rationale_text="reason", candidates_considered=("backend",),
        )
        audit = h._node_audit.get("c1")
        assert audit is not None
        assert len(audit.routing_rationales) == 1


class TestKillFlow:
    def test_kill_appends_kill_record(self, make_handle, stub_board, stub_recorder):
        manager, cwd = stub_recorder
        # Allocate a child so get_node finds it.
        import asyncio
        child = asyncio.run(manager.allocate_child(limit=10000))
        stub_board.spawn_card(node_id=child.id, column="InProgress")
        h = make_handle()
        kr = h.kill_card(child.id, "scope too wide")
        assert isinstance(kr, KillRecord)
        assert kr.kind == "em.kill"
        # Node finalized.
        node = manager.get_node(child.id)
        assert node is not None
        assert node.terminal_state is not None
        assert node.terminal_state["exit_reason"] == "killed"

    def test_kill_preserves_node_json(self, make_handle, stub_board, stub_recorder):
        """L-04: node JSON still exists after kill (append-not-delete)."""
        manager, cwd = stub_recorder
        import asyncio
        child = asyncio.run(manager.allocate_child(limit=10000))
        stub_board.spawn_card(node_id=child.id, column="InProgress")
        node_path = cwd / ".voss" / "sessions" / child.root_id / f"{child.id}.json"
        assert node_path.exists()
        h = make_handle()
        h.kill_card(child.id, "killed")
        assert node_path.exists()  # still on disk


class TestRescopeFlow:
    def test_rescope_produces_bidirectional_pointers(self, make_handle, stub_board, stub_recorder):
        manager, cwd = stub_recorder
        import asyncio
        child = asyncio.run(manager.allocate_child(limit=10000))
        stub_board.spawn_card(node_id=child.id, column="InProgress")
        h = make_handle()
        rr = h.rescope_card(
            card_id=child.id, new_worker_role="frontend",
            rationale_text="narrowing scope",
        )
        assert isinstance(rr, RescopeRecord)
        assert rr.predecessor_card_id == child.id
        assert rr.successor_card_id is not None
        assert rr.successor_card_id != child.id

        # Bidirectional: predecessor's KillRecord points to successor.
        kr = h._node_audit[child.id].kill_record
        assert kr is not None
        assert kr.successor_card_id == rr.successor_card_id

        # Successor's RescopeRecord points back to predecessor.
        sr = h._node_audit[rr.successor_card_id].rescope_record
        assert sr is not None
        assert sr.predecessor_card_id == child.id


class TestFinalizeRun:
    def test_finalize_run_returns_run_final(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1", column="Done")
        stub_board.spawn_card(node_id="n2", column="Blocked")
        h = make_handle()
        rf = h.finalize_run()
        assert rf.total_cards == 2
        assert rf.done_count == 1
        assert rf.blocked_count == 1
        assert rf.kind == "em.run_final"
