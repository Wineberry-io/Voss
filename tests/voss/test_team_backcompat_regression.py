"""Shipped-O2-surface regression after the V3-01 roster/tier delta (VTEAM-04/05/06 + back-compat).

Locks: legacy registry roles + old roster names still resolve; reviewer lives in
two independent registries; scope/budget containment still raise at compile; EM
still denies undeclared-role dispatch; frozen record schemas are unchanged.
"""

from __future__ import annotations

import dataclasses

import pytest

from voss import parse
from voss.ast_nodes import TeamDecl
from voss.harness.subagents import (
    SubagentRegistry,
    SubagentSpec,
    default_subagent_registry,
)
from voss.harness.team import VossTeamConfigError, compile_team


def _only_team(src: str) -> TeamDecl:
    prog = parse(src if src.endswith("\n") else src + "\n", "<test>")
    teams = [d for d in prog.body if isinstance(d, TeamDecl)]
    assert len(teams) == 1
    return teams[0]


# --- (1) BACK-COMPAT: legacy registry + old roster names -------------------


def test_default_registry_has_legacy_roles() -> None:
    reg = default_subagent_registry()
    for role in ("explorer", "worker", "reviewer"):
        spec = reg.get(role)
        assert spec is not None
        assert spec.description and spec.role_prompt


def test_old_roster_names_ui_ai_still_compile() -> None:
    src = '''team Eng {
  ceiling { budget: 100 tokens, scope: "src/**" }
  roster e {
    ui { scope: "src/ui/**", tools: ["fs"] }
    ai { scope: "src/ai/**", tools: ["fs"] }
  }
}
'''
    _config, registry = compile_team(_only_team(src))
    assert registry.get("ui") is not None
    assert registry.get("ai") is not None


def test_reviewer_lives_in_both_registries_independently() -> None:
    # Legacy path: default_subagent_registry.
    legacy = default_subagent_registry().get("reviewer")
    assert legacy is not None and legacy.role_prompt

    # Team path: compile_team default-roster injection (empty roster -> seven roles).
    # Ceiling scope must contain every default role's scope (skeptic = src/tests/docs).
    src = '''team Eng {
  ceiling { budget: 100 tokens, scope: ["src/**", "tests/**", "docs/**"] }
}
'''
    _config, registry = compile_team(_only_team(src))
    roster_reviewer = registry.get("reviewer")
    assert roster_reviewer is not None and roster_reviewer.role_prompt
    # Separate registries, separate specs — no collision.
    assert legacy is not roster_reviewer


# --- (2) SCOPE CONTAINMENT (TEAM-05) ---------------------------------------


def test_scope_widening_beyond_ceiling_raises() -> None:
    src = '''team Eng {
  ceiling { budget: 100 tokens, scope: "src/**" }
  roster e {
    backend { scope: "other/**", tools: ["fs"] }
  }
}
'''
    with pytest.raises(VossTeamConfigError):
        compile_team(_only_team(src))


# --- (3) BUDGET CONTAINMENT (TEAM-06) --------------------------------------


def test_over_ceiling_budget_raises() -> None:
    src = '''team Eng {
  ceiling { budget: 100 tokens, scope: "src/**" }
  roster e {
    backend { budget: 200 tokens, scope: "src/api/**", tools: ["fs"] }
  }
}
'''
    with pytest.raises(VossTeamConfigError) as ei:
        compile_team(_only_team(src))
    assert "200" in str(ei.value) and "100" in str(ei.value)


# --- (4) EM-INVENT GUARD (TEAM-04) -----------------------------------------


def _make_handle(tmp_path):
    from voss.harness.em.handle import EMBoardHandle
    from voss.harness.permissions import PermissionGate
    from voss.harness.session_tree import SessionTreeManager, SessionTreeNode
    from voss.harness.team import (
        BoardSpec,
        TeamCeiling,
        TeamConfig,
        TeamPolicy,
        TeamRoleScope,
    )

    class _Board:
        def cards(self):
            return []

    team_config = TeamConfig(
        name="T",
        ceiling=TeamCeiling(
            budget_tokens=1_000_000,
            scope=TeamRoleScope(globs=("src/**",)),
            latency_seconds=600,
        ),
        policy=TeamPolicy(p=None),
        em_agent_id="em",
        roster_ids=frozenset({"backend", "frontend"}),
        board=BoardSpec(raw_items=()),
        rituals=(),
    )
    reg = SubagentRegistry()
    for r in ("backend", "frontend"):
        reg.register(SubagentSpec(id=r, description=f"d {r}", role_prompt=f"p {r}"))

    root = SessionTreeNode.create_root(cwd=tmp_path, limit=1_000_000)
    manager = SessionTreeManager(root, reserve=0, cwd=tmp_path)
    return EMBoardHandle(
        board=_Board(),
        registry=reg,
        team_config=team_config,
        manager=manager,
        base_gate=PermissionGate(mode="auto", auto_yes=True),
        cwd=tmp_path,
    )


def test_em_dispatch_to_undeclared_role_denied(tmp_path) -> None:
    from voss.harness.em.errors import EMCageViolation

    h = _make_handle(tmp_path)
    with pytest.raises(EMCageViolation) as ei:
        h.dispatch_card(
            card_id="c1",
            role_id="phantom",
            task="do stuff",
            rationale_text="because",
            candidates_considered=("phantom",),
        )
    assert "phantom" in ei.value.reason


# --- (5) SCHEMA FREEZE (T-V3-09) -------------------------------------------

_RUNRECORD_FIELDS = {
    "id", "started_at", "ended_at", "goal", "plan", "inspected", "changed",
    "avoided", "assumptions", "decisions", "risks", "validation", "failures",
    "diff_summary", "follow_ups", "cost_usd", "iterations", "iteration_count",
    "exit_reason", "iteration_total_prompt_tokens",
    "iteration_total_completion_tokens", "skill_events", "scope_denials",
    "capability_invocations", "factory_fallbacks",
    "instructions_hash", "instructions_files",
}
_SESSIONRECORD_FIELDS = {
    "id", "name", "cwd", "model", "started_at", "updated_at", "total_cost_usd",
    "turns", "runs", "parent_id", "parent_turn_index",
    "instructions_hash", "instructions_files",
}
_BUDGETSCOPE_FIELDS = {
    "token_limit", "latency_ms", "cost_usd", "name", "tokens_so_far",
    "cost_so_far", "_start", "_token",
}


def test_runrecord_schema_frozen() -> None:
    from voss.harness.session import RunRecord

    assert {f.name for f in dataclasses.fields(RunRecord)} == _RUNRECORD_FIELDS


def test_sessionrecord_schema_frozen() -> None:
    from voss.harness.session import SessionRecord

    assert {f.name for f in dataclasses.fields(SessionRecord)} == _SESSIONRECORD_FIELDS


def test_budgetscope_schema_frozen() -> None:
    from voss_runtime.budget import BudgetScope

    assert {f.name for f in dataclasses.fields(BudgetScope)} == _BUDGETSCOPE_FIELDS
