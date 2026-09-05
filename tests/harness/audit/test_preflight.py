"""O6-01 Task 1: Preflight contract tests (OAUD-01)."""
from __future__ import annotations

from unittest.mock import patch


from voss.harness.audit.preflight import PreflightResult, run_o6_preflight


class TestPreflightGreen:
    def test_preflight_passes_with_all_surfaces_present(self):
        result = run_o6_preflight()
        assert result.ok, f"preflight failed: missing={result.missing}"
        assert result.missing == ()

    def test_preflight_returns_structured_result(self):
        result = run_o6_preflight()
        assert isinstance(result, PreflightResult)
        assert isinstance(result.ok, bool)
        assert isinstance(result.missing, tuple)
        assert isinstance(result.warnings, tuple)


class TestPreflightMissing:
    def test_missing_session_tree_reports_exact_name(self):
        with patch.dict(
            "sys.modules",
            {"voss.harness.session_tree": None},
        ):
            result = run_o6_preflight()
            assert not result.ok
            matches = [m for m in result.missing if "SessionTreeNode" in m]
            assert len(matches) >= 1, f"expected SessionTreeNode in missing, got {result.missing}"

    def test_missing_em_tickets_reports_exact_names(self):
        with patch.dict(
            "sys.modules",
            {"voss.harness.em.tickets": None},
        ):
            result = run_o6_preflight()
            assert not result.ok
            missing_text = " ".join(result.missing)
            for name in ("Ticket", "RoutingRationale", "KillRecord", "RescopeRecord", "RunFinal"):
                assert name in missing_text, f"{name} not in missing: {result.missing}"

    def test_missing_reviewer_verdict_reports_exact_name(self):
        with patch.dict(
            "sys.modules",
            {"voss.harness.board.verdict": None},
        ):
            result = run_o6_preflight()
            assert not result.ok
            missing_text = " ".join(result.missing)
            assert "ReviewerVerdict" in missing_text
            assert "Reviewer" in missing_text
