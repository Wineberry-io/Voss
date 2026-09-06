"""Shared fixtures for the O3 board test suite."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from voss.harness.board.verdict import ReviewerVerdict
from voss.harness.session_tree import SessionTreeManager, SessionTreeNode
from voss.harness.team import (
    BoardSpec,
    TeamCeiling,
    TeamConfig,
    TeamPolicy,
    TeamRoleScope,
)


class _NeverReviewer:
    """Stub satisfying Reviewer Protocol; raises if invoked (gate tests don't call it)."""
    def review(self, card: object) -> ReviewerVerdict:
        raise AssertionError("reviewer should not be called in this test")


@pytest.fixture
def tmp_recorder(tmp_path):
    root = SessionTreeNode.create_root(cwd=tmp_path, limit=1_000_000)
    manager = SessionTreeManager(root, reserve=0, cwd=tmp_path)
    return manager, tmp_path


@pytest.fixture
def stub_reviewer():
    return _NeverReviewer()


def build_test_team(
    *,
    budget: int = 1_000_000,
    latency_s: int | None = 600,
    board_spec: BoardSpec | None = None,
) -> TeamConfig:
    return TeamConfig(
        name="TestTeam",
        ceiling=TeamCeiling(
            budget_tokens=budget,
            scope=TeamRoleScope(globs=("src/**",)),
            latency_seconds=latency_s,
        ),
        policy=TeamPolicy(p=None),
        em_agent_id="em",
        roster_ids=frozenset({"backend", "frontend"}),
        board=board_spec if board_spec is not None else BoardSpec(raw_items=()),
        rituals=(),
    )


def artifact_passing():
    return SimpleNamespace(tests_passed=True, eval_score=1.0, scope_violations=())


def artifact_failing():
    return SimpleNamespace(tests_passed=False, eval_score=0.0, scope_violations=("leak",))


@pytest.fixture
def fake_clock():
    from voss.harness.board.tick import FakeClock
    return FakeClock(0.0)
