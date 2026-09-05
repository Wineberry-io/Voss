"""V2-03 guards (VPRIN-03 + schema/redaction hard constraint).

GUARD 1 — principles are OPAQUE text: no harness/agent code path may branch
(if / comparison / match-case) on an individual principle key or default text.
The literal keys/texts may appear only in DATA positions (the DEFAULT_PRINCIPLES
constant, dict/tuple construction), never as a conditional operand.

GUARD 2 — schema/redaction baseline: RunRecord / SessionRecord / BudgetScope
field-name sets are frozen here to force review for any new persisted field.
Later authorized additive fields may be added to this baseline only when they
preserve the redaction invariant enforced by test_session_redaction.py.
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from voss.harness.principles import DEFAULT_PRINCIPLES

_REPO = Path(__file__).resolve().parents[2]
_HARNESS = _REPO / "voss" / "harness"

_FORBIDDEN = {k for k, _ in DEFAULT_PRINCIPLES} | {t for _, t in DEFAULT_PRINCIPLES}


def _imports_principles(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "voss.harness.principles":
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "voss.harness.principles":
                return True
            if node.level and node.module == "principles":
                return True
            if node.level and node.module is None:
                if any(alias.name == "principles" for alias in node.names):
                    return True
    return False


def _scanned_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in sorted(_HARNESS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if path.name == "principles.py" or _imports_principles(tree):
            paths.append(path)
    return tuple(paths)


def _forbidden_strings(node: ast.AST) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and child.value in _FORBIDDEN
        ):
            hits.append((child.lineno, child.value))
    return hits


def _mentions_principles(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and "principle" in child.id:
            return True
        if isinstance(child, ast.Attribute) and "principle" in child.attr:
            return True
    return False


def _condition_hits(node: ast.AST) -> list[tuple[int, str]]:
    if isinstance(node, ast.BoolOp):
        hits: list[tuple[int, str]] = []
        for value in node.values:
            hits.extend(_condition_hits(value))
        return hits
    if isinstance(node, ast.UnaryOp):
        return _condition_hits(node.operand)
    if isinstance(node, ast.Compare):
        hits: list[tuple[int, str]] = []
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                hits.extend(_forbidden_strings(comparator))
                if _mentions_principles(comparator):
                    hits.extend(_forbidden_strings(node.left))
            else:
                hits.extend(_forbidden_strings(node.left))
                hits.extend(_forbidden_strings(comparator))
        return hits
    return _forbidden_strings(node)


def _branch_hits(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, literal) for principle keys/texts in control flow."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            hits.extend(_condition_hits(node.test))
        elif isinstance(node, ast.comprehension):
            for condition in node.ifs:
                hits.extend(_condition_hits(condition))
        elif isinstance(node, ast.Match):
            for case in node.cases:
                hits.extend(_forbidden_strings(case.pattern))
    return hits


def test_no_control_flow_branches_on_principles() -> None:
    all_hits: dict[str, list[tuple[int, str]]] = {}
    for path in _scanned_paths():
        hits = _branch_hits(path)
        if hits:
            all_hits[str(path.relative_to(_REPO))] = hits
    assert not all_hits, f"principle key/text used in a branch (must be opaque): {all_hits}"


def test_branch_scanner_catches_membership_sets(tmp_path: Path) -> None:
    path = tmp_path / "bad.py"
    path.write_text(
        "def bad(key):\n"
        "    if key in {'scope'}:\n"
        "        return True\n"
        "    return False\n",
        encoding="utf-8",
    )

    assert _branch_hits(path) == [(2, "scope")]


def test_branch_scanner_allows_default_data_declaration(tmp_path: Path) -> None:
    path = tmp_path / "data.py"
    path.write_text(
        "DEFAULT_PRINCIPLES = (\n"
        "    ('scope', 'Do not edit outside assigned scope.'),\n"
        ")\n",
        encoding="utf-8",
    )

    assert _branch_hits(path) == []


# ---- GUARD 2: schema/redaction baseline ------------------------------------

_RUN_RECORD_FIELDS = {
    "id", "started_at", "ended_at", "goal", "plan", "inspected", "changed",
    "avoided", "assumptions", "decisions", "risks", "validation", "failures",
    "diff_summary", "follow_ups", "cost_usd", "iterations", "iteration_count",
    "exit_reason", "iteration_total_prompt_tokens",
    "iteration_total_completion_tokens", "skill_events", "scope_denials",
    "capability_invocations", "factory_fallbacks",
    "instructions_hash", "instructions_files",
}

_SESSION_RECORD_FIELDS = {
    "id", "name", "cwd", "model", "started_at", "updated_at", "total_cost_usd",
    "turns", "runs", "parent_id", "parent_turn_index",
    "instructions_hash", "instructions_files",
}

_BUDGET_SCOPE_FIELDS = {
    "token_limit", "latency_ms", "cost_usd", "name", "tokens_so_far",
    "cost_so_far", "_start", "_token",
}


def test_run_record_schema_frozen() -> None:
    from voss.harness.session import RunRecord

    assert {f.name for f in dataclasses.fields(RunRecord)} == _RUN_RECORD_FIELDS


def test_session_record_schema_frozen() -> None:
    from voss.harness.session import SessionRecord

    assert {f.name for f in dataclasses.fields(SessionRecord)} == _SESSION_RECORD_FIELDS


def test_budget_scope_schema_frozen() -> None:
    from voss_runtime.budget import BudgetScope

    assert {f.name for f in dataclasses.fields(BudgetScope)} == _BUDGET_SCOPE_FIELDS
