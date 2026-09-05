"""V20-05 (VRES-05): Done gate must run Reviewer-B at tier="strong".

Contract (verdict.py:21): B.fast at intermediate gates; B.strong at ->Done.
b_passes lives only in the Done predicate tuples, so strong-at-Done is safe.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from voss.harness.board import Board
from voss.harness.board.stub import DeterministicReviewerStub
from voss.harness.board.verdict import ReviewerVerdict

from .conftest import build_test_team


class SpyReviewer:
    """Records (card, tier) per review call; always passes."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    def review(self, card: object, *, tier: str = "fast") -> ReviewerVerdict:
        self.calls.append((card, tier))
        return ReviewerVerdict(
            conf=0.99,
            source="B",
            tier=tier,  # type: ignore[arg-type]
            verdict="pass",
            notes="(spy)",
            evidence_refs=(),
        )


def _clean_code_artifact():
    return SimpleNamespace(tests_passed=True, scope_violations=())


async def _to_inreview(board, *, risk_tier="low"):
    card = await board.spawn_card(risk_tier=risk_tier)
    card = board.move(card, to="Planned")
    card = board.move(card, to="InProgress")
    card = dataclasses.replace(card, artifact=_clean_code_artifact())
    board._cards = [card if c.node_id == card.node_id else c for c in board._cards]
    card = board.move(card, to="InReview")
    return card


@pytest.mark.asyncio
async def test_done_gate_uses_strong_tier(tmp_recorder):
    manager, cwd = tmp_recorder
    spy_b = SpyReviewer()
    stub_a = DeterministicReviewerStub(conf=0.99, verdict="pass", source="A", tier="fast")
    board = Board.from_team_config(
        build_test_team(), recorder=manager,
        reviewer_a=stub_a, reviewer_b=spy_b, cwd=cwd,
    )
    card = await _to_inreview(board)
    card = board.move(card, to="Done")
    assert card.column == "Done"
    assert spy_b.calls, "Done gate never invoked Reviewer-B"
    assert spy_b.calls[-1][1] == "strong"


@pytest.mark.asyncio
async def test_intermediate_gate_reviewer_unaffected(tmp_recorder):
    manager, cwd = tmp_recorder
    spy = SpyReviewer()
    board = Board.from_team_config(
        build_test_team(), recorder=manager, reviewer=spy, cwd=cwd,
    )
    card = await board.spawn_card(risk_tier="low")
    card = board.move(card, to="Planned")
    card = board.move(card, to="InProgress")
    card = dataclasses.replace(card, artifact=_clean_code_artifact())
    board._cards = [card if c.node_id == card.node_id else c for c in board._cards]
    card = board.move(card, to="InReview")
    # conf gate ran the reviewer; never at strong tier.
    assert spy.calls
    assert all(tier != "strong" for _, tier in spy.calls)


def test_stub_reviewer_accepts_tier_kwarg():
    stub = DeterministicReviewerStub(conf=0.99, verdict="pass", source="B", tier="strong")
    verdict = stub.review(object(), tier="strong")  # team_run composition guard
    assert verdict.tier == "strong"
    # No-tier call keeps the configured tier (zero churn for existing callers).
    assert stub.review(object()).tier == "strong"


def test_reviewer_b_prompt_includes_repo_context(tmp_path):
    from voss.harness.board.reviewer_b import ReviewerB

    class FakeProvider:
        def __init__(self) -> None:
            self.messages: list[dict] | None = None

        async def complete(self, *, messages, model, response_format, temperature):
            self.messages = messages
            return SimpleNamespace(
                parsed=SimpleNamespace(
                    conf=0.9, verdict="pass", notes="", evidence_refs=[],
                    domain_inferred="code",
                )
            )

    def _card(**extra):
        return SimpleNamespace(
            original_idea="idea",
            acceptance="works",
            artifact_text="artifact",
            file_diff="diff",
            a_verification_summary="A ok",
            **extra,
        )

    provider = FakeProvider()
    rb = ReviewerB(provider=provider, fast_model="f", strong_model="s", cwd=tmp_path)

    rb.review(_card(repo_context="def existing(): ...\n"))
    user_msg = provider.messages[1]["content"]
    assert "## Repo Context" in user_msg
    assert "def existing(): ..." in user_msg

    rb.review(_card())  # attr absent → section omitted
    assert "## Repo Context" not in provider.messages[1]["content"]


def test_build_repo_context_caps(tmp_path):
    from voss.harness.board.reviewer_b import (
        REPO_CONTEXT_MAX_CHARS,
        REPO_CONTEXT_MAX_LINES_PER_FILE,
        build_repo_context,
    )

    big = tmp_path / "big.py"
    big.write_text("\n".join(f"line {i}" for i in range(500)) + "\n")
    diff = "--- a/big.py\n+++ b/big.py\n@@ -1 +1 @@\n-x\n+y\n"

    ctx = build_repo_context(tmp_path, diff)
    assert "### big.py" in ctx
    assert f"line {REPO_CONTEXT_MAX_LINES_PER_FILE - 1}" in ctx
    assert f"line {REPO_CONTEXT_MAX_LINES_PER_FILE}" not in ctx  # per-file cap
    assert len(ctx) <= REPO_CONTEXT_MAX_CHARS  # total cap

    # Missing file skipped, empty diff empty.
    assert build_repo_context(tmp_path, "+++ b/nope.py\n") == ""
    assert build_repo_context(tmp_path, "") == ""
