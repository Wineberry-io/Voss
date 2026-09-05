"""O3-03 Task 1: Risk-tier threshold lookup + single-source invariant."""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

from voss.harness.board.gates import GateContext, conf_meets_p
from voss.harness.board.machine import Card, _DEFAULT_RISK_THRESHOLDS
from voss.harness.board.stub import DeterministicReviewerStub
from voss.harness.team import TeamCeiling


def _make_ctx(
    risk_tier: str = "high",
    conf: float = 0.95,
    p_overrides: dict | None = None,
) -> GateContext:
    card = Card(
        node_id="x", column="InProgress", risk_tier=risk_tier,
        retry_count=0, deadline=9999.0,
        artifact=SimpleNamespace(tests_passed=True),
    )
    return GateContext(
        card=card,
        node_envelope={"limit": 100000, "spent": 0},
        team_ceiling=TeamCeiling(budget_tokens=100000, scope=None, latency_seconds=None),
        team_p_overrides=p_overrides or {},
        retry_ceiling=3,
        reserve=0,
        now=0.0,
        reviewer=DeterministicReviewerStub(conf=conf),
    )


class TestDefaultThresholds:
    def test_values(self):
        # V20 VRES-04 adds "critical"; low/med/high values are load-bearing.
        assert _DEFAULT_RISK_THRESHOLDS == {
            "low": 0.60, "med": 0.80, "high": 0.95, "critical": 0.99,
        }

    def test_high_tier_0_94_fails(self):
        ctx = _make_ctx(risk_tier="high", conf=0.94)
        assert conf_meets_p().evaluate(ctx) is False

    def test_high_tier_0_95_passes(self):
        ctx = _make_ctx(risk_tier="high", conf=0.95)
        assert conf_meets_p().evaluate(ctx) is True

    def test_team_override_lowers_threshold(self):
        ctx = _make_ctx(risk_tier="high", conf=0.91, p_overrides={"high": 0.90})
        assert conf_meets_p().evaluate(ctx) is True


class TestSingleSourceInvariant:
    def test_one_definition_in_repo(self):
        count = 0
        for p in Path("voss").rglob("*.py"):
            text = p.read_text()
            if re.search(r"_DEFAULT_RISK_THRESHOLDS\s*[:=]", text):
                count += 1
        assert count == 1, f"expected 1 definition, found {count}"

    def test_gates_imports_not_redefines(self):
        """gates.py imports _DEFAULT_RISK_THRESHOLDS from machine.py."""
        text = Path("voss/harness/board/gates.py").read_text()
        assert "from .machine import" in text
        assert "_DEFAULT_RISK_THRESHOLDS" in text
        # Must NOT have a local definition line.
        assert "_DEFAULT_RISK_THRESHOLDS:" not in text
        assert "_DEFAULT_RISK_THRESHOLDS =" not in text
