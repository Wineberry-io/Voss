"""O4-02 Task 2: Reviewer-B tests — ORVW-04..07 + ORVW-09.

FakeReviewerBProvider mirrors FakeJudgeProvider from tests/eval/test_judge_verdict.py:
canned ProviderResponse with .parsed field, records calls for inspection.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Optional


from voss_runtime.providers.base import ProviderResponse

from voss.harness.board.reviewer_b import ReviewerB, REVIEWER_B_SYSTEM, _ReviewerBOutput
from voss.harness.board.verdict import Reviewer, ReviewerVerdict


class FakeReviewerBProvider:
    """Canned provider for ReviewerB tests — records calls."""

    def __init__(self, canned: _ReviewerBOutput) -> None:
        self._canned = canned
        self.calls: list[dict] = []

    async def complete(
        self,
        *,
        messages: list[dict],
        model: str,
        response_format: Optional[type] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> ProviderResponse:
        self.calls.append({"messages": messages, "model": model})
        return ProviderResponse(
            text="{}",
            model=model,
            prompt_tokens=1,
            completion_tokens=1,
            cost_usd=0.0,
            parsed=self._canned,
        )

    def count_tokens(self, *, text: str, model: str) -> int:
        return 1


def _make_card(**overrides):
    """Build a card-shaped object with O4-required fields."""
    defaults = {
        "original_idea": "Build a REST API for user management",
        "acceptance_criteria": "Users can be created, read, updated, deleted",
        "artifact": "def create_user(): pass",
        "artifact_text": "def create_user(): pass",
        "file_diff": "+def create_user(): pass",
        "a_verification_summary": "Tests cover CRUD operations",
        "node_id": "test-node",
        "column": "InReview",
        "risk_tier": "med",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _passing_output() -> _ReviewerBOutput:
    return _ReviewerBOutput(
        conf=0.95, verdict="pass", notes="Looks good", evidence_refs=["api.py:10"],
    )


def _blocking_output() -> _ReviewerBOutput:
    return _ReviewerBOutput(
        conf=0.3, verdict="block", notes="A-verification diverges from idea",
        evidence_refs=[],
    )


class TestBMessageIsolation:
    """ORVW-04: B sees only [artifact, acceptance, repo, original_idea, a_verification_summary]."""

    def test_b_message_isolation(self):
        provider = FakeReviewerBProvider(_passing_output())
        b = ReviewerB(provider=provider, fast_model="test-fast", strong_model="test-strong")
        card = _make_card()

        b.review(card)

        assert len(provider.calls) == 1
        msgs = provider.calls[0]["messages"]
        assert len(msgs) == 2  # system + user only
        assert msgs[0]["content"] == REVIEWER_B_SYSTEM
        user_content = msgs[1]["content"]
        # Card data present.
        assert "Build a REST API" in user_content
        assert "CRUD operations" in user_content
        # EM narrative absent.
        assert "em_plan" not in user_content.lower()
        assert "engineering manager" not in user_content.lower()


class TestBTierSelection:
    """ORVW-05: B uses fast model at intermediate gate."""

    def test_b_tier_selection(self):
        provider = FakeReviewerBProvider(_passing_output())
        b = ReviewerB(provider=provider, fast_model="test-fast", strong_model="test-strong")
        card = _make_card()

        b.review(card, tier="fast")
        assert provider.calls[0]["model"] == "test-fast"


class TestBTierStrong:
    """ORVW-06: B uses strong model at Done gate."""

    def test_b_tier_strong(self):
        provider = FakeReviewerBProvider(_passing_output())
        b = ReviewerB(provider=provider, fast_model="test-fast", strong_model="test-strong")
        card = _make_card()

        b.review(card, tier="strong")
        assert provider.calls[0]["model"] == "test-strong"


class TestBResidual2Block:
    """ORVW-07: B returns verdict='block' when A-verification diverges."""

    def test_b_residual_2_block(self):
        provider = FakeReviewerBProvider(_blocking_output())
        b = ReviewerB(provider=provider, fast_model="test-fast", strong_model="test-strong")
        card = _make_card()

        v = b.review(card)
        assert v.verdict == "block"
        assert v.source == "B"
        assert isinstance(v, ReviewerVerdict)


class TestBImplementsProtocol:
    """ORVW-09: ReviewerB is a valid instance of Reviewer Protocol."""

    def test_b_implements_protocol(self):
        provider = FakeReviewerBProvider(_passing_output())
        b = ReviewerB(provider=provider, fast_model="test-fast", strong_model="test-strong")
        assert isinstance(b, Reviewer)
