"""Integration test fixtures for O5 EM loop tests.

Self-contained: duplicates key fixtures from tests/harness/em/conftest.py
rather than cross-importing (integration tests should be self-contained).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

import pytest

from voss.harness.em.handle import EMBoardHandle
from voss.harness.permissions import PermissionGate
from voss.harness.session_tree import SessionTreeManager, SessionTreeNode
from voss.harness.subagents import SubagentRegistry, SubagentSpec
from voss.harness.team import (
    BoardSpec, TeamCeiling, TeamConfig, TeamPolicy, TeamRoleScope,
)


@dataclass(frozen=True, slots=True)
class StubCard:
    node_id: str
    column: str = "Backlog"
    risk_tier: str = "med"
    retry_count: int = 0
    deadline: float = 9999.0
    scope: Optional[TeamRoleScope] = None
    artifact: object = None
    eval_threshold: float = 1.0


class StubBoard:
    def __init__(self):
        self._cards: list[StubCard] = []
        self._tick_count = 0

    def spawn_card(self, node_id: str, **kw) -> StubCard:
        card = StubCard(node_id=node_id, **kw)
        self._cards.append(card)
        return card

    def cards(self) -> list:
        return list(self._cards)

    def move(self, card, to: str):
        new = dataclasses.replace(card, column=to)
        self._cards = [new if c.node_id == card.node_id else c for c in self._cards]
        return new

    def _tick_once(self, now: float):
        self._tick_count += 1


@pytest.fixture
def stub_board():
    return StubBoard()


@pytest.fixture
def stub_recorder(tmp_path):
    root = SessionTreeNode.create_root(cwd=tmp_path, limit=1_000_000)
    mgr = SessionTreeManager(root, reserve=0, cwd=tmp_path)
    return mgr, tmp_path


@pytest.fixture
def tiny_team():
    return TeamConfig(
        name="TestTeam",
        ceiling=TeamCeiling(budget_tokens=1_000_000, scope=TeamRoleScope(globs=("src/**",)), latency_seconds=600),
        policy=TeamPolicy(p=None),
        em_agent_id="em",
        roster_ids=frozenset({"backend", "frontend", "ai"}),
        board=BoardSpec(raw_items=()),
        rituals=(),
    )


@pytest.fixture
def base_gate():
    return PermissionGate(mode="auto", auto_yes=True)


@pytest.fixture
def tiny_registry():
    reg = SubagentRegistry()
    for r in ("backend", "frontend", "ai"):
        reg.register(SubagentSpec(id=r, description=f"Test {r}", role_prompt=f"You are {r}"))
    return reg


@pytest.fixture
def make_handle(stub_board, stub_recorder, tiny_team, base_gate, tiny_registry):
    mgr, cwd = stub_recorder
    def _f(**ov):
        d = dict(board=stub_board, registry=tiny_registry, team_config=tiny_team, manager=mgr, base_gate=base_gate, cwd=cwd)
        d.update(ov)
        return EMBoardHandle(**d)
    return _f
