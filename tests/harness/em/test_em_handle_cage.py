"""O5-02: Cage invariant refusal coverage (invariants 1-4 + scope)."""
from __future__ import annotations

import pytest

from voss.harness.em.errors import EMCageViolation
from voss.harness.team import TeamRoleScope



FORBIDDEN_METHODS = {
    "set_ceiling", "set_p", "set_budget", "extend_budget",
    "register_role", "register_agent", "mutate_team_config",
}


class TestCageInvariant1Introspection:
    """No forbidden methods exist on EMBoardHandle."""

    def test_forbidden_methods_absent(self, make_handle):
        h = make_handle()
        public = {m for m in dir(h) if not m.startswith("_")}
        overlap = public & FORBIDDEN_METHODS
        assert overlap == set(), f"cage breach: {overlap}"

    def test_getattr_raises_for_forbidden(self, make_handle):
        h = make_handle()
        for name in FORBIDDEN_METHODS:
            with pytest.raises(AttributeError):
                getattr(h, name)

    def test_no_public_board_team_registry_alias(self, make_handle):
        h = make_handle()
        public = {m for m in dir(h) if not m.startswith("_")}
        for name in ("board", "team_config", "registry", "manager"):
            assert name not in public


class TestCageInvariant2NonRoster:
    """Dispatch to a non-roster role raises EMCageViolation."""

    def test_dispatch_phantom_role(self, make_handle):
        h = make_handle()
        with pytest.raises(EMCageViolation) as exc:
            h.dispatch_card(
                card_id="c1", role_id="phantom", task="do stuff",
                rationale_text="because", candidates_considered=("phantom",),
            )
        assert exc.value.op == "dispatch_card"
        assert "phantom" in exc.value.reason


class TestCageInvariant3BudgetExtension:
    """Budget cannot be extended — no method exists."""

    def test_extend_budget_raises_attribute_error(self, make_handle):
        h = make_handle()
        with pytest.raises(AttributeError):
            h.extend_budget(50000)  # type: ignore[attr-defined]


class TestCageInvariant4DoneCardProtection:
    """Cannot kill or rescope a card in Done column."""

    def test_kill_done_card_raises(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1", column="Done")
        h = make_handle()
        with pytest.raises(EMCageViolation) as exc:
            h.kill_card("n1", "cleaning up")
        assert exc.value.op == "kill_card"
        assert "Done" in exc.value.reason

    def test_rescope_done_card_raises(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1", column="Done")
        h = make_handle()
        with pytest.raises(EMCageViolation) as exc:
            h.rescope_card(
                card_id="n1", new_worker_role="frontend",
                rationale_text="changing scope",
            )
        assert exc.value.op == "rescope_card"
        assert "Done" in exc.value.reason


class TestCageInvariant5ScopeContainment:
    """Rescope with scope outside ceiling.scope raises."""

    def test_scope_outside_ceiling_raises(self, make_handle, stub_board):
        stub_board.spawn_card(node_id="n1", column="InProgress")
        h = make_handle()
        outside_scope = TeamRoleScope(globs=("/etc/**",))
        with pytest.raises(EMCageViolation) as exc:
            h.rescope_card(
                card_id="n1", new_worker_role="backend",
                rationale_text="widening",
                new_scope=outside_scope,
            )
        assert exc.value.op == "rescope_card"
        assert "ceiling" in exc.value.reason.lower()
