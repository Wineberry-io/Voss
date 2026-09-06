"""Shared fixtures for O5 EM handle tests."""
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
    BoardSpec,
    TeamCeiling,
    TeamConfig,
    TeamPolicy,
    TeamRoleScope,
)


# --- StubCard (mirrors O3 Card shape for tests) ---

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


# --- StubBoard (satisfies BoardProtocol) ---

class StubBoard:
    """In-memory board mock satisfying BoardProtocol."""

    def __init__(self) -> None:
        self._cards: list[StubCard] = []
        self._tick_count = 0

    def spawn_card(self, node_id: str, **kw) -> StubCard:
        card = StubCard(node_id=node_id, **kw)
        self._cards.append(card)
        return card

    def get_card(self, card_id: str) -> StubCard | None:
        for c in self._cards:
            if c.node_id == card_id:
                return c
        return None

    def cards(self) -> list:
        return list(self._cards)

    def move(self, card: object, to: str) -> object:
        node_id = getattr(card, "node_id", "")
        new_card = dataclasses.replace(card, column=to)  # type: ignore[type-var]
        self._cards = [new_card if c.node_id == node_id else c for c in self._cards]
        return new_card

    def _tick_once(self, now: float) -> None:
        self._tick_count += 1


# --- Fixtures ---

@pytest.fixture
def stub_board():
    return StubBoard()


@pytest.fixture
def stub_recorder(tmp_path):
    root = SessionTreeNode.create_root(cwd=tmp_path, limit=1_000_000)
    manager = SessionTreeManager(root, reserve=0, cwd=tmp_path)
    return manager, tmp_path


@pytest.fixture
def tiny_team_config():
    return TeamConfig(
        name="TestTeam",
        ceiling=TeamCeiling(
            budget_tokens=1_000_000,
            scope=TeamRoleScope(globs=("src/**",)),
            latency_seconds=600,
        ),
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
    for role in ("backend", "frontend", "ai"):
        reg.register(SubagentSpec(
            id=role,
            description=f"Test {role}",
            role_prompt=f"You are {role}",
        ))
    return reg


@pytest.fixture
def make_handle(stub_board, stub_recorder, tiny_team_config, base_gate, tiny_registry):
    manager, cwd = stub_recorder

    def _factory(**overrides):
        defaults = dict(
            board=stub_board,
            registry=tiny_registry,
            team_config=tiny_team_config,
            manager=manager,
            base_gate=base_gate,
            cwd=cwd,
        )
        defaults.update(overrides)
        return EMBoardHandle(**defaults)

    return _factory
