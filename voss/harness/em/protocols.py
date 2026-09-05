"""Typed protocols for the O3 Board surface (O5-02).

EMBoardHandle codes against these protocols so it never imports from
voss.harness.board.* directly — the board may not be shipped when W2
tests run. When O3 lands, the real Board satisfies BoardProtocol
structurally.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable


Column = Literal["Backlog", "Planned", "InProgress", "InReview", "Blocked", "Done"]

TERMINAL_COLUMNS: frozenset[str] = frozenset({"Done", "Blocked"})


@runtime_checkable
class CardProtocol(Protocol):
    node_id: str
    column: str
    risk_tier: str
    retry_count: int
    deadline: float


@runtime_checkable
class BoardProtocol(Protocol):
    def cards(self) -> list: ...
    def move(self, card: object, to: str) -> object: ...
    def _tick_once(self, now: float) -> None: ...
