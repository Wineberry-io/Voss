"""O5-05: OEM-09 — misroute audit data emission + C-02 cross-phase ask."""
from __future__ import annotations

import pytest

from voss.harness.em.loop import em_loop
from voss.harness.em.schema import CreateTicketOp, DispatchCardOp, EMPlanResponse, NoopOp
from voss.harness.em.stub import DeterministicEMStub


class TestMisrouteAudit:
    @pytest.mark.asyncio
    async def test_routing_rationale_emitted_on_dispatch(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="c1", column="Planned")
        stub = DeterministicEMStub(scripted=[
            EMPlanResponse(ops=[
                CreateTicketOp(original_idea="x", worker_role="backend"),
                DispatchCardOp(
                    card_id="c1", role_id="backend", task="build",
                    rationale_text="backend owns this",
                    candidates_considered=["backend", "ai"],
                    confidence_hint=0.9,
                ),
            ]),
            EMPlanResponse(ops=[NoopOp()]),
        ])
        handle = make_handle()
        await em_loop(
            idea="x", em_handle=handle, em_agent=stub, max_iterations=2,
        )

        # RoutingRationale readable from audit side-table.
        all_rr = [
            rr
            for a in handle._node_audit.values()
            for rr in a.routing_rationales
        ]
        assert len(all_rr) >= 1
        rr = all_rr[0]
        assert rr.chosen_role == "backend"
        assert rr.confidence_hint == 0.9

    @pytest.mark.xfail(
        strict=True,
        reason="C-02: O4 must add ReviewerVerdict.domain_inferred — see O5-CROSS-PHASE-COORDINATION.md",
    )
    def test_misroute_diff_requires_domain_inferred(self):
        """When O4 adds ReviewerVerdict.domain_inferred, this xfail flips to XPASS."""
        from voss.harness.board.verdict import ReviewerVerdict
        v = ReviewerVerdict(
            conf=0.99, source="B", tier="strong", verdict="pass",
            notes="ok", evidence_refs=(),
        )
        # This attribute does NOT exist on ReviewerVerdict today.
        # When O4 adds it, the test passes (XPASS → cross-phase resolved).
        assert v.domain_inferred == "code"  # type: ignore[attr-defined]
