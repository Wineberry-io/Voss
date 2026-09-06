"""O3-01 Task 2: ReviewerVerdict + Reviewer Protocol + error classes."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from voss.harness.board import (
    BoardError,
    BoardGateError,
    BoardTimeoutError,
    BoardWIPError,
    ReviewerVerdict,
    Reviewer,
)


class TestReviewerVerdict:
    def test_constructs_with_6_fields(self):
        v = ReviewerVerdict(
            conf=0.9,
            source="A",
            tier="fast",
            verdict="pass",
            notes="ok",
            evidence_refs=(),
        )
        assert v.conf == 0.9
        assert v.source == "A"
        assert v.tier == "fast"
        assert v.verdict == "pass"
        assert v.notes == "ok"
        assert v.evidence_refs == ()

    def test_frozen(self):
        v = ReviewerVerdict(
            conf=0.9, source="B", tier="strong",
            verdict="fail", notes="bad", evidence_refs=("a.py:1",),
        )
        with pytest.raises(FrozenInstanceError):
            v.conf = 0.5  # type: ignore[misc]

    def test_exactly_7_fields(self):
        # V6 (D-08): domain_inferred is the intended scoped 7th field.
        names = {f.name for f in fields(ReviewerVerdict)}
        assert names == {
            "conf", "source", "tier", "verdict", "notes", "evidence_refs",
            "domain_inferred",
        }


class TestReviewerProtocol:
    def test_reviewer_is_protocol(self):
        assert hasattr(Reviewer, "__protocol_attrs__") or hasattr(Reviewer, "_is_protocol")

    def test_structural_subtype(self):
        class Stub:
            def review(self, card: object) -> ReviewerVerdict:
                return ReviewerVerdict(
                    conf=1.0, source="B", tier="fast",
                    verdict="pass", notes="", evidence_refs=(),
                )

        stub = Stub()
        assert isinstance(stub, Reviewer)


class TestBoardErrors:
    def test_wip_error_attrs(self):
        e = BoardWIPError("InProgress", 3)
        assert e.column == "InProgress"
        assert e.cap == 3
        assert isinstance(e, BoardError)
        assert isinstance(e, Exception)

    def test_gate_error_attrs(self):
        e = BoardGateError("conf below p", ["conf"])
        assert e.reason == "conf below p"
        assert e.failing_clauses == ["conf"]
        assert isinstance(e, BoardError)

    def test_gate_error_no_clauses(self):
        e = BoardGateError("unknown column")
        assert e.failing_clauses == []

    def test_timeout_error_attrs(self):
        e = BoardTimeoutError("timeout")
        assert e.reason == "timeout"
        assert isinstance(e, BoardError)


class TestPackageSurface:
    def test_init_exports_wave1_and_wave2_symbols(self):
        from voss.harness import board
        expected = {
            "ReviewerVerdict", "Reviewer",
            "BoardError", "BoardWIPError", "BoardGateError", "BoardTimeoutError",
            # O3-02 additions:
            "Board", "Card", "Column", "RiskTier",
        }
        assert set(board.__all__) == expected

    def test_board_card_column_importable(self):
        from voss.harness.board import Board, Card, Column  # noqa: F401
        assert Board is not None
        assert Card is not None
