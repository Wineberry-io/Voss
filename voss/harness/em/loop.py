"""EM autonomous loop — idea in, board run to Done, human sign-off only (O5-04).

Implements OEM-05/06: the EM's plan-and-tick cycle. Reads a board snapshot,
calls the EM agent (LLM or stub) for one EMPlanResponse, executes every op
via EMBoardHandle, awaits one Board.tick(), repeats until all cards terminal
or max_iterations exhausted.

Cage invariants are preserved because every op goes through EMBoardHandle
(W2 facade). EMCageViolation from any single op is logged and the loop
continues (audit-not-abort). BudgetExceededError forces all cards to Blocked.
"""
from __future__ import annotations

import logging

from voss_runtime.exceptions import BudgetExceededError

from .errors import EMCageViolation
from .handle import EMBoardHandle
from .schema import (
    CreateTicketOp,
    DispatchCardOp,
    EMPlanResponse,
    KillCardOp,
    NoopOp,
    RescopeCardOp,
    SetACOp,
    SetDoDOp,
)
from .tickets import RunFinal

logger = logging.getLogger(__name__)


def _execute_plan(
    em_handle: EMBoardHandle,
    plan: EMPlanResponse,
) -> list[tuple[object, Exception]]:
    """Route each Op to its EMBoardHandle verb.

    EMCageViolations from individual ops are caught and collected —
    a single rejected op does not abort the iteration. Returns the
    list of (op, exception) pairs for audit.
    """
    failures: list[tuple[object, Exception]] = []
    for op in plan.ops:
        try:
            if isinstance(op, CreateTicketOp):
                em_handle.create_ticket(
                    original_idea=op.original_idea,
                    acceptance_criteria=", ".join(op.acceptance_criteria) if isinstance(op.acceptance_criteria, list) else str(op.acceptance_criteria),
                    dod=", ".join(op.dod) if isinstance(op.dod, list) else str(op.dod),
                    worker_role=op.worker_role,
                    domain=op.domain,
                    risk_tier=op.risk_tier,
                )
            elif isinstance(op, SetACOp):
                em_handle.set_ac(op.card_id, ", ".join(op.acceptance_criteria))
            elif isinstance(op, SetDoDOp):
                em_handle.set_dod(op.card_id, ", ".join(op.dod))
            elif isinstance(op, DispatchCardOp):
                em_handle.dispatch_card(
                    card_id=op.card_id,
                    role_id=op.role_id,
                    task=op.task,
                    rationale_text=op.rationale_text,
                    candidates_considered=tuple(op.candidates_considered),
                    confidence_hint=op.confidence_hint,
                )
            elif isinstance(op, KillCardOp):
                em_handle.kill_card(op.card_id, op.rationale_text)
            elif isinstance(op, RescopeCardOp):
                em_handle.rescope_card(
                    card_id=op.card_id,
                    new_worker_role=op.new_worker_role,
                    rationale_text=op.rationale_text,
                    new_acceptance=tuple(op.new_acceptance) if op.new_acceptance else (),
                )
            elif isinstance(op, NoopOp):
                pass  # intentional no-op
        except EMCageViolation as exc:
            logger.warning("cage violation on op %s: %s", type(op).__name__, exc)
            failures.append((op, exc))
    return failures


async def em_loop(
    *,
    idea: str,
    em_handle: EMBoardHandle,
    em_agent: object,
    roster_descriptions: dict[str, str] | None = None,
    max_iterations: int = 50,
) -> RunFinal:
    """Autonomous EM loop: idea → plan → execute → tick → repeat.

    Terminates when:
    - all cards reach Done or Blocked
    - max_iterations exhausted (force_block_all)
    - BudgetExceededError (force_block_all)

    em_agent must expose: async plan(*, idea, snapshot, **) -> EMPlanResponse
    """
    iteration = 0
    while not em_handle.all_cards_terminal():
        if iteration >= max_iterations:
            em_handle.force_block_all(reason="em_iteration_ceiling")
            break

        snapshot = em_handle.snapshot()
        snapshot_text = f"cards: {len(snapshot.cards)}, tickets: {len(snapshot.tickets)}"

        try:
            plan = await em_agent.plan(
                idea=idea,
                snapshot=snapshot_text,
                roster_descriptions=roster_descriptions or {},
            )
            _execute_plan(em_handle, plan)
        except EMCageViolation:
            # Audit-not-abort: log and continue.
            pass
        except BudgetExceededError:
            em_handle.force_block_all(reason="budget")
            break

        await em_handle.tick()
        iteration += 1

    rf = em_handle.finalize_run()
    # Patch em_iterations onto the RunFinal (frozen — rebuild).
    import dataclasses
    rf = dataclasses.replace(rf, em_iterations=iteration)
    return rf
