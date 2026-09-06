from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from .ast_nodes import (
    AgentDecl,
    BinOp,
    BoolLit,
    BudgetArg,
    Call,
    ConfidenceGate,
    CtxBlock,
    DictLit,
    Expr,
    ExprStmt,
    FloatLit,
    FnDecl,
    Identifier,
    IfStmt,
    IncludeStmt,
    IntLit,
    LetStmt,
    ListLit,
    MatchStmt,
    Member,
    Node,
    NullLit,
    Param,
    Program,
    ReturnStmt,
    SimilarPattern,
    Stmt,
    StringLit,
    TypeExpr,
    TypeRef,
    YieldStmt,
)
from .diagnostics import AnalysisResult, Diagnostic, EmittedIndex


class TokenEstimator(Protocol):
    def estimate_expr(self, expr: Expr, scope: "Scope") -> int | None: ...
    def estimate_stmt(self, stmt: Stmt, scope: "Scope") -> int | None: ...


class IndexBuilder(Protocol):
    model: str

    def build_cases(
        self, cases: Sequence[tuple[str, str]]
    ) -> list[dict[str, object]]: ...


# ----- Internal type model (private to analyzer) -----


class VossType:
    """Base for the analyzer's minimal internal type model."""


@dataclass(frozen=True, slots=True)
class PrimitiveType(VossType):
    name: str


@dataclass(frozen=True, slots=True)
class NamedType(VossType):
    name: str


@dataclass(frozen=True, slots=True)
class ListType(VossType):
    item: VossType


@dataclass(frozen=True, slots=True)
class DictType(VossType):
    key: VossType
    value: VossType


@dataclass(frozen=True, slots=True)
class ProbableType(VossType):
    inner: VossType


class UnknownType(VossType):
    _instance: "UnknownType | None" = None

    def __new__(cls) -> "UnknownType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


UNKNOWN = UnknownType()

_PRIMITIVES = {"string", "int", "float", "bool", "null"}


@dataclass(frozen=True, slots=True)
class FunctionSignature:
    params: tuple[tuple[str, VossType], ...]
    return_type: VossType


class DefaultTokenEstimator:
    """Local, deterministic token estimator. No provider/network dependency."""

    def estimate_expr(self, expr: Expr, scope: "Scope") -> int | None:
        if isinstance(expr, StringLit):
            return max(1, len(expr.value) // 4)
        if isinstance(expr, (IntLit, FloatLit, BoolLit, NullLit)):
            return 1
        if isinstance(expr, Identifier):
            return scope.estimates.get(expr.name)
        if isinstance(expr, BinOp) and expr.op == "+":
            left = self.estimate_expr(expr.left, scope)
            right = self.estimate_expr(expr.right, scope)
            if left is None or right is None:
                return None
            return left + right
        if isinstance(expr, ListLit):
            total = len(expr.items)
            for item in expr.items:
                est = self.estimate_expr(item, scope)
                if est is None:
                    return None
                total += est
            return total
        if isinstance(expr, DictLit):
            total = len(expr.items)
            for k, v in expr.items:
                k_est = self.estimate_expr(k, scope)
                v_est = self.estimate_expr(v, scope)
                if k_est is None or v_est is None:
                    return None
                total += k_est + v_est
            return total
        if isinstance(expr, Call):
            if (
                isinstance(expr.callee, Identifier)
                and expr.callee.name == "ask"
                and expr.args
                and expr.args[0].name is None
            ):
                return self.estimate_expr(expr.args[0].value, scope)
            return None
        return None

    def estimate_stmt(self, stmt: Stmt, scope: "Scope") -> int | None:
        if isinstance(stmt, IncludeStmt):
            return self.estimate_expr(stmt.value, scope)
        if isinstance(stmt, YieldStmt) and stmt.value is not None:
            return self.estimate_expr(stmt.value, scope)
        return None


def _default_local_model() -> str:
    from voss_runtime.semantic import DEFAULT_LOCAL_MODEL

    return DEFAULT_LOCAL_MODEL


class SemanticMatcherIndexBuilder:
    """Default index builder. Imports runtime semantic matcher lazily."""

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or _default_local_model()

    def build_cases(
        self, cases: Sequence[tuple[str, str]]
    ) -> list[dict[str, object]]:
        from voss_runtime.semantic import SemanticMatcher

        matcher = SemanticMatcher(list(cases), threshold=0.75, model=self.model)
        return matcher.to_index()["cases"]


_PROGRAM_STEM_RE = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass
class Scope:
    symbols: dict[str, VossType] = field(default_factory=dict)
    estimates: dict[str, int] = field(default_factory=dict)
    gated: set[str] = field(default_factory=set)


class Analyzer:
    def __init__(
        self,
        *,
        source_path: str | Path | None = None,
        project_root: str | Path | None = None,
        cache_dir: str | Path = ".voss-cache",
        emit_indexes: bool = True,
        token_estimator: TokenEstimator | None = None,
        index_builder: IndexBuilder | None = None,
    ) -> None:
        self.source_path = Path(source_path) if source_path is not None else None
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.cache_dir = Path(cache_dir)
        self.emit_indexes = emit_indexes
        self.token_estimator: TokenEstimator = token_estimator or DefaultTokenEstimator()
        self.index_builder: IndexBuilder | None = index_builder
        self.diagnostics: list[Diagnostic] = []
        self.indexes: list[EmittedIndex] = []
        self.scope_stack: list[Scope] = [Scope()]
        self.signatures: dict[str, FunctionSignature] = {}
        self._return_type: VossType = UNKNOWN
        self._match_entries: list[dict[str, object]] = []

    # -------- Scope helpers --------

    @property
    def _scope(self) -> Scope:
        return self.scope_stack[-1]

    def _bind(self, name: str, type_: VossType) -> None:
        self._scope.symbols[name] = type_

    def _lookup(self, name: str) -> VossType:
        for scope in reversed(self.scope_stack):
            if name in scope.symbols:
                return scope.symbols[name]
        return UNKNOWN

    def _push_scope(self, scope: Scope) -> None:
        self.scope_stack.append(scope)

    def _pop_scope(self) -> None:
        self.scope_stack.pop()

    def _child_scope(self) -> Scope:
        parent = self._scope
        return Scope(
            symbols=dict(parent.symbols),
            estimates=dict(parent.estimates),
            gated=set(parent.gated),
        )

    # -------- Type normalization --------

    def _type_from_type_expr(self, type_expr: TypeExpr | None) -> VossType:
        if type_expr is None:
            return UNKNOWN
        if not isinstance(type_expr, TypeRef):
            return UNKNOWN
        parts = type_expr.name.parts
        if not parts:
            return UNKNOWN
        head = parts[0]
        if len(parts) == 1 and head == "probable" and len(type_expr.generics) == 1:
            return ProbableType(self._type_from_type_expr(type_expr.generics[0]))
        if len(parts) == 1 and head == "list" and len(type_expr.generics) == 1:
            return ListType(self._type_from_type_expr(type_expr.generics[0]))
        if len(parts) == 1 and head == "dict" and len(type_expr.generics) == 2:
            return DictType(
                self._type_from_type_expr(type_expr.generics[0]),
                self._type_from_type_expr(type_expr.generics[1]),
            )
        if len(parts) == 1 and head in _PRIMITIVES and not type_expr.generics:
            return PrimitiveType(head)
        return NamedType(".".join(parts))

    def _type_display(self, type_: VossType) -> str:
        if isinstance(type_, PrimitiveType):
            return type_.name
        if isinstance(type_, NamedType):
            return type_.name
        if isinstance(type_, ListType):
            return f"list<{self._type_display(type_.item)}>"
        if isinstance(type_, DictType):
            return f"dict<{self._type_display(type_.key)}, {self._type_display(type_.value)}>"
        if isinstance(type_, ProbableType):
            return f"probable<{self._type_display(type_.inner)}>"
        return "unknown"

    def _types_equal(self, left: VossType, right: VossType) -> bool:
        if isinstance(left, UnknownType) or isinstance(right, UnknownType):
            return False
        if isinstance(left, PrimitiveType) and isinstance(right, PrimitiveType):
            return left.name == right.name
        if isinstance(left, NamedType) and isinstance(right, NamedType):
            return left.name == right.name
        if isinstance(left, ListType) and isinstance(right, ListType):
            return self._types_equal(left.item, right.item)
        if isinstance(left, DictType) and isinstance(right, DictType):
            return self._types_equal(left.key, right.key) and self._types_equal(
                left.value, right.value
            )
        if isinstance(left, ProbableType) and isinstance(right, ProbableType):
            return self._types_equal(left.inner, right.inner)
        return False

    # -------- Identity / gating --------

    def _root_identifier(self, expr: Expr) -> str | None:
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, Member):
            return self._root_identifier(expr.obj)
        return None

    def _is_gated(self, expr: Expr) -> bool:
        root = self._root_identifier(expr)
        if root is None:
            return False
        return root in self._scope.gated

    # -------- Diagnostics --------

    def _warn_unguarded_probable(
        self, actual: ProbableType, expected: VossType, expr: Expr
    ) -> None:
        actual_display = self._type_display(actual)
        expected_display = self._type_display(expected)
        self.diagnostics.append(
            Diagnostic(
                severity="warning",
                code="ANLY001",
                message=(
                    f"unguarded {actual_display} used where {expected_display} is expected"
                ),
                span=expr.span,
                hint=(
                    "Add a confidence gate such as if intent @ p >= 0.80 { ... } "
                    "or pass intent.value only inside the gated branch."
                ),
            )
        )

    # -------- Type checking --------

    def _check_expected(self, expr: Expr, expected: VossType) -> VossType:
        actual = self._infer_expr(expr)
        if isinstance(expected, UnknownType):
            return actual
        if (
            isinstance(actual, ProbableType)
            and not isinstance(expected, ProbableType)
            and self._types_equal(actual.inner, expected)
            and not self._is_gated(expr)
        ):
            self._warn_unguarded_probable(actual, expected, expr)
        return actual

    def _infer_expr(self, expr: Expr) -> VossType:
        if isinstance(expr, Identifier):
            return self._lookup(expr.name)
        if isinstance(expr, StringLit):
            return PrimitiveType("string")
        if isinstance(expr, IntLit):
            return PrimitiveType("int")
        if isinstance(expr, FloatLit):
            return PrimitiveType("float")
        if isinstance(expr, BoolLit):
            return PrimitiveType("bool")
        if isinstance(expr, NullLit):
            return PrimitiveType("null")
        if isinstance(expr, Member):
            obj_type = self._infer_expr(expr.obj)
            if (
                expr.attr == "value"
                and isinstance(obj_type, ProbableType)
            ):
                if not self._is_gated(expr.obj):
                    self._warn_unguarded_probable(obj_type, obj_type.inner, expr)
                return obj_type.inner
            return UNKNOWN
        if isinstance(expr, Call):
            self._check_call(expr)
            sig = self._signature_for_call(expr)
            if sig is not None:
                return sig.return_type
            return UNKNOWN
        if isinstance(expr, ListLit):
            return ListType(UNKNOWN)
        if isinstance(expr, DictLit):
            return DictType(UNKNOWN, UNKNOWN)
        return UNKNOWN

    def _signature_for_call(self, call: Call) -> FunctionSignature | None:
        if isinstance(call.callee, Identifier):
            return self.signatures.get(call.callee.name)
        return None

    def _check_call(self, call: Call) -> None:
        sig = self._signature_for_call(call)
        if sig is None:
            for arg in call.args:
                self._infer_expr(arg.value)
            return
        positional_index = 0
        param_by_name = {name: t for name, t in sig.params}
        for arg in call.args:
            if arg.name is not None:
                expected = param_by_name.get(arg.name, UNKNOWN)
            else:
                if positional_index < len(sig.params):
                    expected = sig.params[positional_index][1]
                else:
                    expected = UNKNOWN
                positional_index += 1
            self._check_expected(arg.value, expected)

    # -------- Predeclaration --------

    def _predeclare_decls(self, body: tuple[Stmt, ...]) -> None:
        for stmt in body:
            if isinstance(stmt, (FnDecl, AgentDecl)):
                params = tuple(
                    (p.name, self._type_from_type_expr(p.type_annot))
                    for p in stmt.params
                )
                ret_t = self._type_from_type_expr(stmt.return_type)
                self.signatures[stmt.name] = FunctionSignature(
                    params=params, return_type=ret_t
                )

    # -------- Top-level walk --------

    def analyze_program(self, program: Program) -> AnalysisResult:
        self._predeclare_decls(program.body)
        for stmt in program.body:
            self._visit_stmt(stmt)
        if self.emit_indexes and self._match_entries:
            self._emit_program_index(program)
        return AnalysisResult(
            diagnostics=tuple(self.diagnostics),
            indexes=tuple(self.indexes),
            match_entries=tuple(self._match_entries),
        )

    # -------- Statement visitors --------

    def _visit_stmt(self, stmt: Stmt) -> None:
        if isinstance(stmt, LetStmt):
            self._visit_let(stmt)
            return
        if isinstance(stmt, ReturnStmt):
            self._visit_return(stmt)
            return
        if isinstance(stmt, IfStmt):
            self._visit_if(stmt)
            return
        if isinstance(stmt, FnDecl):
            self._visit_fn(stmt)
            return
        if isinstance(stmt, AgentDecl):
            self._visit_agent(stmt)
            return
        if isinstance(stmt, CtxBlock):
            self._visit_ctx_block(stmt)
            return
        if isinstance(stmt, MatchStmt):
            self._visit_match_stmt(stmt)
            return
        if isinstance(stmt, ExprStmt):
            self._infer_expr(stmt.expr)
            return
        if isinstance(stmt, YieldStmt):
            if stmt.value is not None:
                self._infer_expr(stmt.value)
            return
        if isinstance(stmt, IncludeStmt):
            self._infer_expr(stmt.value)
            return
        # Fallback: walk children for nested expressions but ignore typing semantics.
        self._walk_children(stmt)

    def _visit_match_stmt(self, match: MatchStmt) -> None:
        self._infer_expr(match.scrutinee)
        similar_pairs: list[tuple[str, str]] = []
        for ordinal, case in enumerate(match.cases):
            if isinstance(case.pattern, SimilarPattern):
                label = f"case_{ordinal}"
                similar_pairs.append((case.pattern.text, label))
            for s in case.body:
                self._visit_stmt(s)
        if not similar_pairs:
            return
        threshold = match.threshold if match.threshold is not None else 0.75
        match_id = f"match_{match.span.line_start}_{match.span.col_start}"
        # D-03: static-only check — skip embedding build, keep static signature validation.
        if not self.emit_indexes:
            self._match_entries.append(
                {"match_id": match_id, "threshold": threshold, "cases": []}
            )
            return
        if self.index_builder is None:
            self.index_builder = SemanticMatcherIndexBuilder()
        built = self.index_builder.build_cases(similar_pairs)
        self._match_entries.append(
            {
                "match_id": match_id,
                "threshold": threshold,
                "cases": built,
            }
        )

    def _ctx_token_budget(self, ctx: CtxBlock) -> int | None:
        b = ctx.budget
        if not isinstance(b, BudgetArg):
            return None
        if b.name == "budget" and b.unit == "tokens":
            return int(b.value)
        return None

    def _estimate_ctx_body(self, ctx: CtxBlock) -> int:
        total = 0
        for s in ctx.body:
            est = self.token_estimator.estimate_stmt(s, self._scope)
            if est is not None:
                total += est
        return total

    def _visit_ctx_block(self, ctx: CtxBlock) -> None:
        budget = self._ctx_token_budget(ctx)
        if budget is not None:
            estimate = self._estimate_ctx_body(ctx)
            if estimate > budget:
                self.diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code="ANLY002",
                        message=(
                            f"ctx block static token estimate {estimate:,} "
                            f"exceeds declared budget {budget:,}"
                        ),
                        span=ctx.span,
                        hint=(
                            "Increase the ctx budget, include less context, "
                            "or add a more aggressive compression strategy."
                        ),
                    )
                )
        for s in ctx.body:
            self._visit_stmt(s)

    def _visit_let(self, stmt: LetStmt) -> None:
        annotated = self._type_from_type_expr(stmt.type_annot)
        if stmt.value is None:
            self._bind(stmt.name, annotated)
            return
        if isinstance(annotated, UnknownType):
            inferred = self._infer_expr(stmt.value)
            self._bind(stmt.name, inferred)
        else:
            self._check_expected(stmt.value, annotated)
            self._bind(stmt.name, annotated)
        est = self.token_estimator.estimate_expr(stmt.value, self._scope)
        if est is not None:
            self._scope.estimates[stmt.name] = est

    def _visit_return(self, stmt: ReturnStmt) -> None:
        if stmt.value is None:
            return
        if isinstance(self._return_type, UnknownType):
            self._infer_expr(stmt.value)
        else:
            self._check_expected(stmt.value, self._return_type)

    def _visit_if(self, stmt: IfStmt) -> None:
        condition = stmt.condition
        gated_name: str | None = None
        if isinstance(condition, ConfidenceGate):
            gated_name = self._root_identifier(condition.target)
        else:
            if isinstance(condition, Expr):
                self._infer_expr(condition)

        then_scope = self._child_scope()
        if gated_name is not None and condition.op in (">=", ">"):
            then_scope.gated.add(gated_name)
        self._push_scope(then_scope)
        for s in stmt.then_body:
            self._visit_stmt(s)
        self._pop_scope()

        if stmt.else_body is not None:
            else_scope = self._child_scope()
            if gated_name is not None and condition.op in ("<", "<="):
                else_scope.gated.add(gated_name)
            self._push_scope(else_scope)
            for s in stmt.else_body:
                self._visit_stmt(s)
            self._pop_scope()

    def _visit_fn(self, decl: FnDecl) -> None:
        self._enter_callable(decl.params, decl.return_type, decl.body)

    def _visit_agent(self, decl: AgentDecl) -> None:
        self._enter_callable(decl.params, decl.return_type, decl.body)

    def _enter_callable(
        self,
        params: tuple[Param, ...],
        return_type: TypeExpr | None,
        body: tuple[Stmt, ...],
    ) -> None:
        scope = self._child_scope()
        for p in params:
            scope.symbols[p.name] = self._type_from_type_expr(p.type_annot)
        prev_return = self._return_type
        self._return_type = self._type_from_type_expr(return_type)
        self._push_scope(scope)
        try:
            self._predeclare_decls(body)
            for s in body:
                self._visit_stmt(s)
        finally:
            self._pop_scope()
            self._return_type = prev_return

    # -------- Program index emission --------

    def _program_stem(self) -> str:
        if self.source_path is not None:
            return Path(self.source_path).stem or ""
        return "program"

    def _resolve_cache_root(self) -> Path:
        cache = self.cache_dir
        if cache.is_absolute():
            return cache.resolve()
        return (self.project_root / cache).resolve()

    def _stem_is_safe(self, stem: str) -> bool:
        if not stem:
            return False
        if stem in (".", "..") or stem.startswith(".."):
            return False
        if "/" in stem or "\\" in stem:
            return False
        if not _PROGRAM_STEM_RE.fullmatch(stem):
            return False
        return True

    def _emit_program_index(self, program: Program) -> None:
        if self.index_builder is None:
            self.index_builder = SemanticMatcherIndexBuilder()

        stem = self._program_stem()
        cache_root = self._resolve_cache_root()

        def _refuse() -> None:
            self.diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="ANLY003",
                    message=(
                        "refusing to write embedding index outside "
                        "project-local .voss-cache"
                    ),
                    span=program.span,
                    hint=(
                        "Use cache_dir='.voss-cache' or another .voss-cache "
                        "directory under project_root."
                    ),
                )
            )

        if not self._stem_is_safe(stem):
            _refuse()
            return

        try:
            cache_root.relative_to(self.project_root)
        except ValueError:
            _refuse()
            return

        if cache_root.name != ".voss-cache":
            _refuse()
            return

        target = cache_root / f"{stem}.idx"
        temp_target = target.with_name(target.name + ".tmp")

        # Resolve safely: parents may not yet exist, so resolve their components.
        def _under_cache(p: Path) -> bool:
            try:
                resolved = (
                    p.resolve()
                    if p.exists()
                    else (cache_root / p.name).resolve()
                )
                resolved.relative_to(cache_root)
                return True
            except ValueError:
                return False

        if not _under_cache(target) or not _under_cache(temp_target):
            _refuse()
            return

        manifest = {
            "version": 1,
            "program": stem,
            "model": self.index_builder.model,
            "matches": self._match_entries,
        }

        cache_root.mkdir(parents=True, exist_ok=True)
        temp_target.write_text(json.dumps(manifest, indent=2, sort_keys=False))
        temp_target.replace(target)

        for entry in self._match_entries:
            self.indexes.append(
                EmittedIndex(
                    match_id=str(entry["match_id"]),
                    path=target,
                    case_count=len(entry["cases"]),  # type: ignore[arg-type]
                    threshold=float(entry["threshold"]),  # type: ignore[arg-type]
                    model=self.index_builder.model,
                )
            )

    # -------- Generic walker (read-only fallback) --------

    def _walk_children(self, node: Node) -> None:
        from dataclasses import fields, is_dataclass

        if not is_dataclass(node):
            return
        for f in fields(node):
            if f.name == "span":
                continue
            value = getattr(node, f.name)
            self._walk_value(value)

    def _walk_value(self, value: object) -> None:
        if isinstance(value, Node):
            self._walk_children(value)
            return
        if isinstance(value, (tuple, list)):
            for item in value:
                self._walk_value(item)
            return
        if isinstance(value, dict):
            for k, v in value.items():
                self._walk_value(k)
                self._walk_value(v)


def analyze(
    program: Program,
    *,
    source_path: str | Path | None = None,
    project_root: str | Path | None = None,
    cache_dir: str | Path = ".voss-cache",
    emit_indexes: bool = True,
    token_estimator: TokenEstimator | None = None,
    index_builder: IndexBuilder | None = None,
) -> AnalysisResult:
    analyzer = Analyzer(
        source_path=source_path,
        project_root=project_root,
        cache_dir=cache_dir,
        emit_indexes=emit_indexes,
        token_estimator=token_estimator,
        index_builder=index_builder,
    )
    return analyzer.analyze_program(program)
