"""Frozen value objects for the team / organizational cage (O2).

Implements the structural shell for OTEAM-04 (immutable cage metadata) and
OTEAM-08 (opaque board/ritual carriers). `compile_team` maps `TeamDecl` AST
from O2-01 into immutable `TeamConfig` + `SubagentRegistry`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .principles import PrinciplesConfig

from voss.ast_nodes import (
    BoardDecl,
    BudgetArg,
    CeilingDecl,
    ListLit,
    Span,
    StringLit,
    TeamAgentDecl,
    TeamDecl,
)

from .permissions import Mode, PermissionGate
from .safety import SafetyActorContext
from .skill.scope import _min_mode  # team compile reuse; see skill/scope.py:74
from .subagents import SubagentRegistry, SubagentSpec
from .tools import ToolEntry


class VossTeamConfigError(Exception):
    """Raised when team configuration is invalid or inconsistent (compile phase)."""

    def __init__(
        self,
        message: str,
        *,
        construct: str = "",
        fix_hint: str = "",
        role_span: Span | None = None,
        ceiling_span: Span | None = None,
    ) -> None:
        super().__init__(message)
        self.construct = construct
        self.fix_hint = fix_hint
        self.role_span = role_span
        self.ceiling_span = ceiling_span

    def format_diagnostic(self) -> str:
        """Render `[construct] <message> at file:line` (+ hint when present)."""
        span = self.role_span or self.ceiling_span
        location = f"{span.file}:{span.line_start}" if span is not None else "<unknown>"
        out = f"[{self.construct}] {self} at {location}"
        if self.fix_hint:
            out += f"\n  hint: {self.fix_hint}"
        return out


DEFAULT_ROSTER: tuple[str, ...] = (
    "product",
    "ux",
    "architect",
    "backend",
    "frontend",
    "ai",
    "data",
    "platform",
    "reliability",
    "security",
    "tester",
    "reviewer",
    "skeptic",
    "docs",
)


@dataclass(frozen=True, slots=True)
class RoleDefaults:
    """Full per-role defaults for a built-in roster role (VTEAM-09).

    ``model_tier`` is a tier keyword ({strong, cheap, fast}) resolved to a
    concrete id at compile via :func:`_resolve_model_string` — no model NAME
    strings live here (those live in ``config._DEFAULT_MODEL_TIERS``). ``scope``
    globs must sit within the team ceiling scope (e.g. the PRD example ceiling
    ``["src/**", "tests/**", "docs/**"]``). ``tools`` are toolset keys / group
    aliases (see :data:`TOOL_GROUP_ALIASES`).
    """

    description: str
    role_prompt: str
    model_tier: str
    scope: tuple[str, ...]
    tools: tuple[str, ...]


# Default product-engineering roster. It keeps the PRD specialist core and adds
# product/design, platform/reliability/security, and data/AI lenses common in
# engineering orgs. Tiers only — never concrete model names.
_ROLE_DEFAULTS: dict[str, RoleDefaults] = {
    "product": RoleDefaults(
        description="Product engineer",
        role_prompt="You clarify user value, requirements, acceptance criteria, and rollout tradeoffs before implementation.",
        model_tier="strong",
        scope=("docs/**", "src/**", "tests/**"),
        tools=("fs_read", "fs_read_many", "fs_glob", "fs_grep", "code", "git"),
    ),
    "ux": RoleDefaults(
        description="Product designer",
        role_prompt="You shape user flows, interaction states, accessibility, and interface copy before UI work lands.",
        model_tier="strong",
        scope=("docs/**", "src/**", "tests/**"),
        tools=("fs_read", "fs_read_many", "fs_glob", "fs_grep", "code", "git"),
    ),
    "architect": RoleDefaults(
        description="Architect",
        role_prompt="You plan the smallest sound design before code; you own structure, not edits.",
        model_tier="strong",
        scope=("src/**", "docs/**"),
        tools=("fs_read", "fs_read_many", "fs_glob", "fs_grep", "code", "git"),
    ),
    "backend": RoleDefaults(
        description="Backend engineer",
        role_prompt="You specialize in APIs, persistence, and server-side logic.",
        model_tier="cheap",
        scope=("src/**", "tests/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "frontend": RoleDefaults(
        description="Frontend engineer",
        role_prompt="You specialize in web clients, routing, and client-side state.",
        model_tier="cheap",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "ai": RoleDefaults(
        description="AI / ML engineer",
        role_prompt="You specialize in model integrations, evaluation loops, prompt contracts, and AI runtime behavior.",
        model_tier="strong",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "data": RoleDefaults(
        description="Data engineer",
        role_prompt="You specialize in data models, migrations, analytics paths, and durable data quality.",
        model_tier="cheap",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "platform": RoleDefaults(
        description="Platform engineer",
        role_prompt="You specialize in internal tooling, build systems, CI, packaging, and developer experience.",
        model_tier="cheap",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "reliability": RoleDefaults(
        description="Reliability engineer",
        role_prompt="You specialize in operability, telemetry, performance, capacity, and safe change management.",
        model_tier="strong",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "security": RoleDefaults(
        description="Security engineer",
        role_prompt="You identify abuse paths, permission flaws, data exposure, and supply-chain risks before release.",
        model_tier="strong",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "tester": RoleDefaults(
        description="Tester",
        role_prompt="You write and run tests; you reproduce bugs before they are fixed.",
        model_tier="cheap",
        scope=("tests/**", "src/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "reviewer": RoleDefaults(
        description="Reviewer",
        role_prompt="You review diffs for correctness, scope, and quality; you do not widen the change.",
        model_tier="strong",
        scope=("src/**", "tests/**"),
        tools=("fs", "code", "test", "git"),
    ),
    "skeptic": RoleDefaults(
        description="Skeptic",
        role_prompt="You stress-test claims and surface risks; no claim without evidence.",
        model_tier="strong",
        scope=("src/**", "tests/**", "docs/**"),
        tools=("fs", "code", "git"),
    ),
    "docs": RoleDefaults(
        description="Docs writer",
        role_prompt="You write clear docs that match the code; you keep examples runnable.",
        model_tier="cheap",
        scope=("docs/**",),
        tools=("fs", "code", "git"),
    ),
}

# Legacy roster names (pre-V3) kept resolvable for back-compat (D-05). These are
# only desc/prompt carriers; their scope/tools come from the explicit declaration.
_LEGACY_ROLE_DESC: dict[str, tuple[str, str]] = {
    "ui": (
        "UI engineer",
        "You specialize in components, layouts, and design-quality UI.",
    ),
}


def role_full_defaults(role_name: str) -> RoleDefaults | None:
    """Return the full :class:`RoleDefaults` for a built-in role, else ``None``."""
    return _ROLE_DEFAULTS.get(role_name)


def default_team_role_defaults(role_name: str) -> tuple[str, str]:
    """Return `(description, role_prompt)` for a roster role.

    Built-ins are the default product-engineering roster (:data:`_ROLE_DEFAULTS`);
    legacy ui retains its carrier (D-05); unknown names use opaque fallbacks
    (open roster, OQ-02-A).
    """
    rd = _ROLE_DEFAULTS.get(role_name)
    if rd is not None:
        return (rd.description, rd.role_prompt)
    if role_name in _LEGACY_ROLE_DESC:
        return _LEGACY_ROLE_DESC[role_name]
    desc = f"Team role `{role_name}`"
    rp = f"You are `{role_name}` on this roster; follow EM instructions and ceiling policy."
    return (desc, rp)


EM_DESCRIPTION: str = "Engineering Manager (orchestrator)"
EM_ROLE_PROMPT: str = "<EM role prompt — populated in O5>"

# OQ-03-A: hybrid alias table (shorthand groups + exact tool names accepted separately).
TOOL_GROUP_ALIASES: dict[str, frozenset[str]] = {
    "fs": frozenset({"fs_read", "fs_write", "fs_edit", "fs_glob", "fs_grep"}),
    "code": frozenset(
        {"code_search", "find_definition", "find_references", "code_refresh"}
    ),
    "test": frozenset({"shell_run"}),
    "shell": frozenset(
        {"shell_run", "shell_run_background", "shell_monitor", "shell_signal"}
    ),
    "net": frozenset({"web_fetch", "web_search"}),
    "git": frozenset({"git_status", "git_diff"}),
}


def _model_tier_for_spec(spec: SubagentSpec) -> str | None:
    """Resolve model tier for safety actor context on a derived role gate."""
    if spec.model is not None:
        if spec.model in _MODEL_TIERS:
            return spec.model
        from .config import get_model_tiers  # lazy: avoid import cycle

        for tier, model_id in get_model_tiers().items():
            if model_id == spec.model:
                return tier
    rd = role_full_defaults(spec.id)
    if rd is not None:
        return rd.model_tier
    return None


def gate_for_role(spec: SubagentSpec, base_gate: PermissionGate) -> PermissionGate:
    """Compile a per-role PermissionGate from a SubagentSpec.

    Cap-not-expand: when ``spec.mode`` is set, it caps ``base_gate.mode`` via
    :func:`voss.harness.skill.scope._min_mode`; it never widens permissions.

    Per-gate network: ``spec.net`` maps to ``allow_net`` explicitly (``True`` or
    ``False``), never ``None``, so specialist roles stay netless even when the
    process is started with ``--allow-net``.

    Safety: ``safety_policy`` and ``safety_confirm_fn`` are preserved from
    ``base_gate`` (same object references). ``safety_actor`` is role-specific —
    it carries ``spec.id`` and the resolved model tier, not the base actor.

    Subagent sessions do not use :class:`~voss.harness.edit_scope.EditScope`
    in this compile step (O5 may route per-role paths separately); ``edit_scope``
    is therefore always ``None`` here.
    """
    if spec.mode is None:
        effective_mode = base_gate.mode
    else:
        effective_mode = _min_mode(base_gate.mode, spec.mode)
    return PermissionGate(
        mode=effective_mode,
        store=None,
        auto_yes=True,
        prompt_fn=None,
        edit_scope=None,
        scope_prompt_fn=None,
        project_policy=base_gate.project_policy,
        allow_net=True if spec.net else False,
        safety_policy=base_gate.safety_policy,
        safety_actor=SafetyActorContext(
            role=spec.id, model_tier=_model_tier_for_spec(spec)
        ),
        safety_confirm_fn=base_gate.safety_confirm_fn,
    )


# V1-capability-seam (VTEAM-07): this raw toolset-key + net-alias filter is the
# binding point where V1's capability registry will later resolve a role's
# declared capabilities to a concrete toolset. The replacement is V1's concern;
# the current behavior (alias expansion + exact-key match, net opt-in) is locked
# and unchanged here. Do not add capability logic to this function — bind it at
# this seam in V1.
def filter_toolset_for_role(
    spec: SubagentSpec,
    base_toolset: Mapping[str, ToolEntry],
) -> dict[str, ToolEntry]:
    """Return a subset of *base_toolset* based on ``spec.tools``.

    If ``spec.tools`` is ``None``, returns a shallow copy of the full toolset.

    Otherwise expands :data:`TOOL_GROUP_ALIASES` entries and treats any other
    string as an exact ``make_toolset`` key. ``web_fetch`` / ``web_search``
    appear in the result only when the ``net`` alias is included (or those names
    are listed explicitly).
    """
    if spec.tools is None:
        return dict(base_toolset)
    expanded: set[str] = set()
    for entry in spec.tools:
        # V1-capability binding site: today raw alias/key expansion; in V1 a
        # capability registry lookup replaces this branch (behavior unchanged now).
        if entry in TOOL_GROUP_ALIASES:
            expanded |= set(TOOL_GROUP_ALIASES[entry])
        else:
            expanded.add(entry)
    return {name: te for name, te in base_toolset.items() if name in expanded}


@dataclass(frozen=True, slots=True)
class TeamRoleScope:
    globs: tuple[str, ...]

    def is_contained_in(self, other: TeamRoleScope | None) -> bool:
        """Return True if every glob in *self* is within *other*'s globs.

        **Heuristic (OQ-02-C):** prefix up to the first wildcard character
        (`*`, `?`, `[`). Each role glob's literal prefix must satisfy
        `startswith` some ceiling glob's literal prefix (after stripping
        trailing ``/``).

        **Limitations:** Patterns like ``**/test/**`` vs ``src/**`` are not
        modeled faithfully; containment may disagree with intuitive set
        inclusion. Prefer simple `prefix/**`-style ceilings and roles.
        """
        if other is None:
            return True

        def _prefix(glob: str) -> str:
            for sep in ("*", "?", "["):
                idx = glob.find(sep)
                if idx >= 0:
                    return glob[:idx].rstrip("/")
            return glob.rstrip("/")

        other_ps = [_prefix(o) for o in other.globs]

        for self_g in self.globs:
            self_p = _prefix(self_g)
            if not any(self_p.startswith(op) for op in other_ps):
                return False
        return True


@dataclass(frozen=True, slots=True)
class TeamCeiling:
    budget_tokens: int | None
    scope: TeamRoleScope | None
    latency_seconds: int | None


@dataclass(frozen=True, slots=True)
class TeamPolicy:
    p: object | None


@dataclass(frozen=True, slots=True)
class BoardSpec:
    raw_items: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class RitualSpec:
    name: str
    raw_kvs: tuple[tuple[str, object], ...]


# ----- V10 coordination configs (VLANG-01b/01c) — informational, compile-to-config only -----
@dataclass(frozen=True, slots=True)
class GateConfig:
    """A `gate <name> { require ... }` block compiled to config (no enforcement)."""

    name: str
    requires: frozenset[str]


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """A `memory {}` block compiled to config; omitted keys default to convention."""

    decisions: str = ".voss/decisions"
    sessions: str = ".voss/sessions"
    semantic: str = ".voss-cache/semantic"


@dataclass(frozen=True, slots=True)
class TeamConfig:
    name: str
    ceiling: TeamCeiling
    policy: TeamPolicy
    em_agent_id: str | None
    roster_ids: frozenset[str]
    board: BoardSpec | None
    rituals: tuple[RitualSpec, ...]
    principles: "PrinciplesConfig | None" = None
    gate_configs: "tuple[GateConfig, ...]" = ()
    memory: "MemoryConfig | None" = None


@dataclass(frozen=True, slots=True)
class TeamRunContext:
    """O2→O3 hand-off shape — dataclass shell only."""

    team_config: TeamConfig
    registry: SubagentRegistry
    base_gate: PermissionGate


def _options_dict(opts: Iterable[tuple[str, object]]) -> dict[str, object]:
    return {k: v for k, v in opts}


def _parse_scope_literal(val: object, span: Span | None = None) -> TeamRoleScope | None:
    """Build `TeamRoleScope` from roster/ceiling-style scope value or None."""
    if val is None:
        return None
    if isinstance(val, StringLit):
        return TeamRoleScope((val.value,))
    if isinstance(val, ListLit):
        globs: list[str] = []
        for it in val.items:
            if isinstance(it, StringLit):
                globs.append(it.value)
            else:
                raise VossTeamConfigError(
                    f"scope list entries must be string literals; got {type(it).__name__}",
                    construct="scope",
                    fix_hint="scope list entries must be string literals",
                    role_span=span,
                )
        return TeamRoleScope(tuple(globs))
    raise VossTeamConfigError(
        f"scope must be a string literal or string list; got {type(val).__name__}",
        construct="scope",
        fix_hint="scope must be a string literal or string list",
        role_span=span,
    )


def _parse_budget_value(val: object, ceiling: TeamCeiling, span: Span | None = None) -> int | None:
    if val is None:
        return None
    if isinstance(val, BudgetArg) and val.unit == "tokens":
        return int(val.value)
    if isinstance(val, StringLit):
        raw = val.value.strip().lower()
        if raw == "ceiling":
            return ceiling.budget_tokens
    raise VossTeamConfigError(
        f"budget must be a token BudgetArg or ceiling string sentinel; got {type(val).__name__}",
        construct="budget",
        fix_hint="use a token budget like: budget: 100 tokens",
        role_span=span,
    )


def _parse_tools_value(val: object, span: Span | None = None) -> frozenset[str]:
    """Normalize tools to frozenset; accept list literal or single string."""
    if val is None:
        return frozenset()
    names: list[str] = []
    if isinstance(val, ListLit):
        for it in val.items:
            if isinstance(it, StringLit):
                names.append(it.value)
            else:
                raise VossTeamConfigError(
                    f"tools list entries must be string literals; got {type(it).__name__}",
                    construct="tools",
                    fix_hint='tools must be a string literal or list: tools: ["fs", "test"]',
                    role_span=span,
                )
        return frozenset(names)
    if isinstance(val, StringLit):
        return frozenset([val.value])
    raise VossTeamConfigError(
        f"tools must be a string literal or string list; got {type(val).__name__}",
        construct="tools",
        fix_hint='tools must be a string literal or list: tools: ["fs", "test"]',
        role_span=span,
    )


def _parse_mode_value(val: object, span: Span | None = None) -> Mode | None:
    if val is None:
        return None
    if isinstance(val, StringLit):
        m = val.value
        if m not in ("plan", "edit", "auto"):
            raise VossTeamConfigError(
                f"unknown mode '{m}' (expected: plan, edit, auto)",
                construct="mode",
                fix_hint="mode must be one of: plan, edit, auto",
                role_span=span,
            )
        return m  # type: ignore[return-value]
    raise VossTeamConfigError(
        f"mode must be a string literal; got {type(val).__name__}",
        construct="mode",
        fix_hint="mode must be a string literal",
        role_span=span,
    )


_MODEL_TIERS: frozenset[str] = frozenset({"strong", "cheap", "fast"})


def _resolve_model_string(s: str, span: Span | None = None) -> str:
    """Resolve one model string under the closed-set / raw-passthrough rule.

    See :func:`_parse_model_value` for the locked semantics; shared by the
    declarative ``model:`` path and the per-role default tier injection.
    """
    if s in _MODEL_TIERS:
        from .config import get_model_tiers  # lazy: avoid import cycle

        resolved = get_model_tiers().get(s, "")
        if not resolved:
            raise VossTeamConfigError(
                f"model tier {s!r} is not configured",
                construct="model",
                fix_hint="configure the tier in [model_tiers]",
                role_span=span,
            )
        return resolved
    return s


def _parse_model_value(val: object, span: Span | None = None) -> str | None:
    """Resolve a `model:` value to a concrete model id.

    Closed-set / raw-passthrough rule (VTEAM-08, locked):

    1. If the string is one of the CLOSED tier set {strong, cheap, fast}, resolve
       it via :func:`voss.harness.config.get_model_tiers` to a concrete model id.
       A tier mapped to an empty/missing id raises ``VossTeamConfigError`` naming
       the tier (no silent fallback to a default model).
    2. Otherwise the string is a RAW model id, returned unchanged. Raw ids are
       NOT validated against the live catalog here — that keeps offline compile
       of a literal model name working; availability is a ``team check`` concern.

    A typo like ``model: "strog"`` is outside the closed set, so it is treated as
    a raw id and passes (consistent with raw passthrough).
    """
    if val is None:
        return None
    if isinstance(val, StringLit):
        return _resolve_model_string(val.value, span)
    raise VossTeamConfigError(
        f"model must be a string literal; got {type(val).__name__}",
        construct="model",
        fix_hint="model must be a string literal or tier keyword",
        role_span=span,
    )


def subagent_spec_from_role(
    *,
    role_name: str,
    role_decl_span: Span,
    kvs: Mapping[str, object],
    ceiling: TeamCeiling,
    ceiling_ast: CeilingDecl | None,
    apply_role_defaults: bool = False,
) -> SubagentSpec:
    # Per-role tier/scope/tools defaults flow only for default-roster injection
    # (VTEAM-09). Explicitly declared roles keep the shipped behavior — omitted
    # scope inherits the ceiling, omitted tools/model stay empty/None — so
    # existing O2 specs/tests compile unchanged (D-05 back-compat).
    rd = role_full_defaults(role_name) if apply_role_defaults else None

    parsed_scope_opt = (
        _parse_scope_literal(kvs["scope"], role_decl_span) if "scope" in kvs else None
    )

    # Precedence: declared scope > per-role default scope > ceiling scope.
    if parsed_scope_opt is not None:
        scope: TeamRoleScope | None = parsed_scope_opt
    elif rd is not None:
        scope = TeamRoleScope(rd.scope)
    else:
        scope = ceiling.scope

    if scope is not None and ceiling.scope is not None:
        if not scope.is_contained_in(ceiling.scope):
            ceil_msg = ceiling.scope.globs
            raise VossTeamConfigError(
                f"role {role_name!r} scope {scope.globs} is outside ceiling scope {ceil_msg}",
                construct="scope",
                fix_hint="role scope must be within the ceiling scope globs",
                role_span=role_decl_span,
                ceiling_span=ceiling_ast.span if ceiling_ast else None,
            )

    budget_raw = (
        _parse_budget_value(kvs.get("budget"), ceiling, role_decl_span)
        if "budget" in kvs
        else None
    )
    budget: int | None = budget_raw
    if budget is not None and ceiling.budget_tokens is not None:
        if budget > ceiling.budget_tokens:
            raise VossTeamConfigError(
                f"role {role_name!r} budget {budget} exceeds ceiling "
                f"budget_tokens {ceiling.budget_tokens}",
                construct="budget",
                fix_hint="role budget must not exceed the ceiling budget_tokens",
                role_span=role_decl_span,
                ceiling_span=ceiling_ast.span if ceiling_ast else None,
            )

    # Precedence: declared tools > per-role default tools > empty.
    if "tools" in kvs:
        tools = _parse_tools_value(kvs["tools"], role_decl_span)
    elif rd is not None:
        tools = frozenset(rd.tools)
    else:
        tools = frozenset()
    net = "net" in tools

    # Precedence: declared model > per-role default tier > none.
    if "model" in kvs:
        model = _parse_model_value(kvs["model"], role_decl_span)
    elif rd is not None:
        model = _resolve_model_string(rd.model_tier, role_decl_span)
    else:
        model = None
    mode = _parse_mode_value(kvs["mode"], role_decl_span) if "mode" in kvs else None

    description, rp = default_team_role_defaults(role_name)

    tool_fs = tools if tools else None
    return SubagentSpec(
        id=role_name,
        description=description,
        role_prompt=rp,
        model=model,
        mode=mode,
        scope=scope,
        budget=budget,
        tools=tool_fs,
        net=net,
    )


def subagent_spec_from_agent(
    agent_decl: TeamAgentDecl,
    ceiling: TeamCeiling,
    ceiling_ast: CeilingDecl | None,
) -> SubagentSpec:
    """Build a `SubagentSpec` from a team `agent` block.

    The EM orchestrator receives the ceiling scope envelope: ``scope`` of
    ``"all"`` or a missing scope key is compiled to ``ceiling.scope``.
    Narrower declarative scopes that remain within the ceiling may be stored
    as declared (specialists typically tighten); the EM differs from roster
    roles in that widening to the ceiling is allowed here.
    """
    kvs = _options_dict(agent_decl.options)

    parsed_scope_opt = (
        _parse_scope_literal(kvs["scope"], agent_decl.span) if "scope" in kvs else None
    )

    scope: TeamRoleScope | None
    all_sentinel = isinstance(parsed_scope_opt, TeamRoleScope) and (
        len(parsed_scope_opt.globs) == 1
        and parsed_scope_opt.globs[0].strip().lower() == "all"
    )
    if parsed_scope_opt is None or all_sentinel:
        scope = ceiling.scope
    else:
        scope = parsed_scope_opt
        if ceiling.scope is not None and scope is not None:
            if not scope.is_contained_in(ceiling.scope):
                raise VossTeamConfigError(
                    f"agent {agent_decl.name!r} scope {scope.globs} is "
                    f"outside ceiling scope {ceiling.scope.globs}",
                    construct="scope",
                    fix_hint="agent scope must be within the ceiling scope globs",
                    role_span=agent_decl.span,
                    ceiling_span=ceiling_ast.span if ceiling_ast else None,
                )

    budget_raw = (
        _parse_budget_value(kvs["budget"], ceiling, agent_decl.span)
        if "budget" in kvs
        else None
    )

    budget: int | None = budget_raw
    if budget is not None and ceiling.budget_tokens is not None:
        if budget > ceiling.budget_tokens:
            raise VossTeamConfigError(
                f"agent {agent_decl.name!r} budget {budget} exceeds ceiling "
                f"budget_tokens {ceiling.budget_tokens}",
                construct="budget",
                fix_hint="agent budget must not exceed the ceiling budget_tokens",
                role_span=agent_decl.span,
                ceiling_span=ceiling_ast.span if ceiling_ast else None,
            )

    tools = _parse_tools_value(kvs["tools"], agent_decl.span) if "tools" in kvs else frozenset()
    net = "net" in tools

    model = _parse_model_value(kvs["model"], agent_decl.span) if "model" in kvs else None
    mode = _parse_mode_value(kvs["mode"], agent_decl.span) if "mode" in kvs else None

    return SubagentSpec(
        id=agent_decl.name,
        description=EM_DESCRIPTION,
        role_prompt=EM_ROLE_PROMPT,
        model=model,
        mode=mode,
        scope=scope,
        budget=budget,
        tools=tools if tools else None,
        net=net,
    )


def _compile_gate(g) -> GateConfig:
    """Compile a `gate <name> { require ... }` block to an informational config."""
    return GateConfig(name=g.name, requires=frozenset(g.requires))


def _compile_memory(m) -> MemoryConfig | None:
    """Compile a `memory {}` block; omitted keys fall back to convention defaults."""
    if m is None:
        return None
    for key, value in (
        ("decisions", m.decisions),
        ("sessions", m.sessions),
        ("semantic", m.semantic),
    ):
        if value is not None and not value.strip():
            raise VossTeamConfigError(
                f"memory {key} path must not be empty",
                construct="memory",
                fix_hint=f"set memory {key} to a non-empty relative path",
                role_span=m.span,
            )
    return MemoryConfig(
        decisions=m.decisions if m.decisions is not None else ".voss/decisions",
        sessions=m.sessions if m.sessions is not None else ".voss/sessions",
        semantic=m.semantic if m.semantic is not None else ".voss-cache/semantic",
    )


def _compile_principles(decl: TeamDecl, cwd: Path | None):
    """Compile a `principles {}` block, merging with an optional .voss/principles.yml.

    LOCKED merge order (VLANG-01a): merge(merge(DEFAULTS, file_layer), block_layer)
    — the block overrides the file, which overrides the shipped defaults. Reuses
    the V2 merge path (no new merge logic).
    """
    if decl.principles is None:
        return None
    from .principles import (
        DEFAULT_PRINCIPLES,
        _ProjectLayer,
        load_principles,
        merge_principles,
    )

    block_layer = _ProjectLayer(items=tuple(decl.principles.items), disable=())
    if cwd is not None:
        file_layer = load_principles(cwd)
        base = merge_principles(DEFAULT_PRINCIPLES, file_layer)
        return merge_principles(base.principles, block_layer)
    return merge_principles(DEFAULT_PRINCIPLES, block_layer)


def compile_team(
    decl: TeamDecl, *, cwd: Path | None = None
) -> tuple[TeamConfig, SubagentRegistry]:
    """Compile parsed `TeamDecl` into frozen runtime config + populated registry."""

    if decl.ceiling is None:
        raise VossTeamConfigError(
            f"team {decl.name!r} missing ceiling at compile",
            construct="ceiling",
            fix_hint="add a ceiling { budget: N tokens } block to team",
            ceiling_span=decl.span,
        )

    c_ast = decl.ceiling
    ceiling_scope: TeamRoleScope | None = (
        TeamRoleScope(c_ast.scope) if c_ast.scope else None
    )
    ceiling_vo = TeamCeiling(
        budget_tokens=c_ast.budget,
        scope=ceiling_scope,
        latency_seconds=c_ast.latency_seconds,
    )

    registry = SubagentRegistry()

    roster_id_set: set[str] = set()

    em_agent_id: str | None = None
    for agent_decl in decl.agents:
        if em_agent_id is None:
            em_agent_id = agent_decl.name
        spec_a = subagent_spec_from_agent(agent_decl, ceiling_vo, c_ast)
        registry.register(spec_a)
        roster_id_set.add(agent_decl.name)

    for roster in decl.rosters:
        for role in roster.roles:
            ks = _options_dict(role.options)
            spec_r = subagent_spec_from_role(
                role_name=role.name,
                role_decl_span=role.span,
                kvs=ks,
                ceiling=ceiling_vo,
                ceiling_ast=c_ast,
            )
            registry.register(spec_r)
            roster_id_set.add(role.name)

    # VTEAM-09: a team{} with no agents and no roster roles gets the built-in
    # product-engineering roster, each carrying its full tier-based defaults
    # (desc/prompt/model/scope/tools) via the same spec path. Declared cages are
    # never overridden — injection only when both are empty (T-V3-02).
    if not roster_id_set:
        for name in DEFAULT_ROSTER:
            spec_d = subagent_spec_from_role(
                role_name=name,
                role_decl_span=c_ast.span,
                kvs={},
                ceiling=ceiling_vo,
                ceiling_ast=c_ast,
                apply_role_defaults=True,
            )
            registry.register(spec_d)
            roster_id_set.add(name)

    board_spec: BoardSpec | None = None
    if decl.board is not None:
        bd: BoardDecl = decl.board
        board_spec = BoardSpec(raw_items=bd.items)

    rituals = tuple(RitualSpec(name=r.name, raw_kvs=r.kvs) for r in decl.rituals)

    config = TeamConfig(
        name=decl.name,
        ceiling=ceiling_vo,
        policy=TeamPolicy(p=decl.policy),
        em_agent_id=em_agent_id,
        roster_ids=frozenset(roster_id_set),
        board=board_spec,
        rituals=rituals,
        principles=_compile_principles(decl, cwd),
        gate_configs=tuple(_compile_gate(g) for g in decl.gates),
        memory=_compile_memory(decl.memory),
    )

    return config, registry
