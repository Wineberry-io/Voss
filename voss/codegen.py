from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from keyword import iskeyword
from pathlib import Path
from typing import Iterator

from .ast_nodes import (
    AgentDecl,
    Arg,
    BinOp,
    BoolLit,
    BudgetArg,
    Call,
    ClassDecl,
    ClassField,
    ConfidenceGate,
    CtxBlock,
    Decorator,
    DictLit,
    ExprPattern,
    ExprStmt,
    FloatLit,
    FnDecl,
    GateBlockDecl,
    Identifier,
    IfStmt,
    IncludeStmt,
    Index,
    IntLit,
    Lambda,
    LetStmt,
    ListLit,
    MatchStmt,
    Member,
    NullLit,
    Node,
    Param,
    Program,
    MemoryBlockDecl,
    PromptDecl,
    PrinciplesBlockDecl,
    QualName,
    ReturnStmt,
    SimilarPattern,
    SpawnExpr,
    Stmt,
    StringLit,
    TeamDecl,
    TryCatch,
    TypeExpr,
    TypeRef,
    UnaryOp,
    UseStmt,
    WildcardPattern,
    WithinFallback,
    YieldStmt,
)
from .diagnostics import AnalysisResult


@dataclass(frozen=True, slots=True)
class CodegenResult:
    source: str
    imports: tuple[str, ...]
    requires_async_main: bool
    analysis: AnalysisResult | None = None


class CodegenError(Exception):
    pass


class PythonWriter:
    __slots__ = ("lines", "indent_level")

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.indent_level: int = 0

    def write(self, line: str = "") -> None:
        if line == "":
            self._append_blank()
            return
        self.lines.append("    " * self.indent_level + line)

    def blank(self) -> None:
        self._append_blank()

    def _append_blank(self) -> None:
        if self.lines and self.lines[-1] == "":
            return
        self.lines.append("")

    @contextmanager
    def indent(self) -> Iterator[None]:
        self.indent_level += 1
        try:
            yield
        finally:
            self.indent_level -= 1

    def render(self) -> str:
        lines = list(self.lines)
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines) + "\n"


@dataclass(slots=True)
class ImportCollector:
    stdlib: set[str] = field(default_factory=set)
    runtime: set[str] = field(default_factory=set)
    pydantic_base_model: bool = False
    user_imports: list[tuple[tuple[str, ...], str | None]] = field(default_factory=list)

    def add_stdlib(self, name: str) -> None:
        self.stdlib.add(name)

    def add_runtime(self, name: str) -> None:
        self.runtime.add(name)

    def add_base_model(self) -> None:
        self.pydantic_base_model = True

    def add_use(self, path: tuple[str, ...], alias: str | None = None) -> None:
        if len(path) < 2:
            raise CodegenError(f"use path must have at least two segments, got {path!r}")
        entry = (tuple(path), alias)
        if entry not in self.user_imports:
            self.user_imports.append(entry)

    def render(self) -> tuple[list[str], tuple[str, ...]]:
        groups: list[list[str]] = []

        if self.stdlib:
            groups.append([f"import {name}" for name in sorted(self.stdlib)])

        third_party: list[str] = []
        if self.pydantic_base_model:
            third_party.append("from pydantic import BaseModel")
        for path, alias in self.user_imports:
            module = ".".join(path[:-1])
            name = path[-1]
            line = f"from {module} import {name}"
            if alias is not None:
                line += f" as {alias}"
            third_party.append(line)
        if third_party:
            groups.append(third_party)

        if self.runtime:
            names = ", ".join(sorted(self.runtime))
            groups.append([f"from voss_runtime import {names}"])

        lines: list[str] = []
        for index, group in enumerate(groups):
            if index > 0:
                lines.append("")
            lines.extend(group)

        meta = tuple(line for line in lines if line)
        return lines, meta


class NameMangler:
    __slots__ = ()

    def mangle(self, name: str) -> str:
        if iskeyword(name):
            return name + "_"
        return name


_MANGLER = NameMangler()


def _mangle(name: str) -> str:
    return _MANGLER.mangle(name)


_MEMORY_CLASSES = {
    "episodic": "EpisodicMemory",
    "semantic": "SemanticMemory",
    "working": "WorkingMemory",
}


def _format_number(value: int | float) -> str:
    if isinstance(value, int):
        return repr(value)
    if value == int(value):
        return repr(int(value))
    return repr(value)


def _string_literal(value: str) -> str:
    return json.dumps(value)


def _prompt_const_name(name: str) -> str:
    chars: list[str] = []
    for index, ch in enumerate(name):
        if ch.isupper() and index > 0 and (not name[index - 1].isupper()):
            chars.append("_")
        chars.append(ch.upper())
    return "".join(chars) + "_PROMPT"


@dataclass(frozen=True, slots=True)
class MatchIndex:
    match_id: str
    threshold: float
    cases: tuple[tuple[str, str], ...]
    embeddings: tuple[tuple[float, ...], ...]


def _resolve_cache_root(
    project_root: str | Path | None, cache_dir: str | Path
) -> Path:
    project_root_p = Path(project_root or Path.cwd()).resolve()
    cd = Path(cache_dir)
    if cd.is_absolute():
        cache_root = cd.resolve()
    else:
        cache_root = (project_root_p / cd).resolve()
    if not cache_root.is_relative_to(project_root_p):
        raise CodegenError(
            f"cache directory outside project root: {cache_root}"
        )
    if cache_root.name != ".voss-cache":
        raise CodegenError(
            f"cache directory must be named .voss-cache: {cache_root}"
        )
    return cache_root


def _load_match_index(
    match_id: str,
    *,
    source_path: str | Path | None,
    analysis: AnalysisResult | None,
    cache_root: Path,
) -> MatchIndex:
    manifest_path: Path | None = None
    if analysis is not None:
        for idx in analysis.indexes:
            if idx.match_id == match_id:
                resolved = Path(idx.path).resolve()
                if not resolved.is_relative_to(cache_root):
                    raise CodegenError(
                        "semantic index path outside cache directory"
                    )
                manifest_path = resolved
                break
    if manifest_path is None:
        stem = Path(source_path).stem if source_path else "program"
        manifest_path = (cache_root / f"{stem}.idx").resolve()
        if not manifest_path.is_relative_to(cache_root):
            raise CodegenError(
                "semantic index path outside cache directory"
            )

    if not manifest_path.exists():
        raise CodegenError(f"missing semantic match index for {match_id}")

    try:
        data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise CodegenError(
            f"invalid match manifest at {manifest_path}: {exc}"
        ) from exc
    if not isinstance(data, dict) or data.get("version") != 1:
        raise CodegenError(
            f"unsupported match manifest version: {data.get('version') if isinstance(data, dict) else None}"
        )
    matches = data.get("matches")
    if not isinstance(matches, list):
        raise CodegenError("match manifest 'matches' must be a list")

    for entry in matches:
        if not isinstance(entry, dict):
            continue
        if entry.get("match_id") == match_id:
            raw_cases = entry.get("cases", [])
            if not isinstance(raw_cases, list):
                raise CodegenError(
                    f"match manifest cases for {match_id} must be a list"
                )
            cases = tuple(
                (
                    str(c.get("description", "")),
                    str(c.get("label", f"case_{i}")),
                )
                for i, c in enumerate(raw_cases)
            )
            embeddings = tuple(
                tuple(float(x) for x in c.get("embedding", ()))
                for c in raw_cases
            )
            return MatchIndex(
                match_id=match_id,
                threshold=float(entry.get("threshold", 0.75)),
                cases=cases,
                embeddings=embeddings,
            )
    raise CodegenError(f"missing semantic match index for {match_id}")


class TypeEmitter:
    __slots__ = ("imports",)

    _PRIMITIVES = {
        "string": "str",
        "int": "int",
        "float": "float",
        "bool": "bool",
    }

    def __init__(self, imports: ImportCollector) -> None:
        self.imports = imports

    def emit(self, type_expr: TypeExpr) -> str:
        if not isinstance(type_expr, TypeRef):
            raise CodegenError(
                f"unsupported AST node for codegen: {type(type_expr).__name__}"
            )
        parts = type_expr.name.parts
        last = parts[-1]
        if len(parts) == 1:
            if last in self._PRIMITIVES:
                return self._PRIMITIVES[last]
            if last == "list" and type_expr.generics:
                inner = self.emit(type_expr.generics[0])
                return f"list[{inner}]"
            if last == "dict" and len(type_expr.generics) == 2:
                k = self.emit(type_expr.generics[0])
                v = self.emit(type_expr.generics[1])
                return f"dict[{k}, {v}]"
            if last == "probable":
                self.imports.add_runtime("ProbableValue")
                return "ProbableValue"
        return ".".join(_mangle(part) for part in parts)


@dataclass(slots=True)
class ExpressionEmitter:
    imports: ImportCollector = field(default_factory=ImportCollector)
    generated_fns: frozenset[str] = field(default_factory=frozenset)
    use_imported_names: frozenset[str] = field(default_factory=frozenset)
    current_ctx_name: str | None = None

    def emit(self, expr: Node, *, await_context: bool = False) -> str:
        if isinstance(expr, IntLit):
            return repr(expr.value)
        if isinstance(expr, FloatLit):
            return repr(expr.value)
        if isinstance(expr, StringLit):
            return repr(expr.value)
        if isinstance(expr, BoolLit):
            return "True" if expr.value else "False"
        if isinstance(expr, NullLit):
            return "None"
        if isinstance(expr, Identifier):
            return _mangle(expr.name)
        if isinstance(expr, BinOp):
            left = self._emit_operand(expr.left, await_context)
            right = self._emit_operand(expr.right, await_context)
            return f"{left} {expr.op} {right}"
        if isinstance(expr, UnaryOp):
            operand = self._emit_operand(expr.operand, await_context)
            sep = " " if expr.op.isalpha() else ""
            return f"{expr.op}{sep}{operand}"
        if isinstance(expr, Call):
            return self._emit_call(expr, await_context=await_context)
        if isinstance(expr, Member):
            obj = self.emit(expr.obj, await_context=await_context)
            return f"{obj}.{expr.attr}"
        if isinstance(expr, Index):
            if await_context and self._is_gather_call(expr.obj):
                obj = f"({self.emit(expr.obj, await_context=True)})"
            else:
                obj = self.emit(expr.obj, await_context=await_context)
            idx = self.emit(expr.index, await_context=await_context)
            return f"{obj}[{idx}]"
        if isinstance(expr, ListLit):
            items = [
                self.emit(item, await_context=await_context) for item in expr.items
            ]
            return f"[{', '.join(items)}]"
        if isinstance(expr, DictLit):
            pairs = [
                f"{self.emit(k, await_context=await_context)}: "
                f"{self.emit(v, await_context=await_context)}"
                for k, v in expr.items
            ]
            return f"{{{', '.join(pairs)}}}"
        if isinstance(expr, Lambda):
            params = ", ".join(_mangle(p.name) for p in expr.params)
            body = self.emit(expr.body, await_context=False)
            if params:
                return f"lambda {params}: {body}"
            return f"lambda: {body}"
        if isinstance(expr, SpawnExpr):
            agent_name = self.emit(expr.agent.callee, await_context=False)
            args = [self.emit_arg(a, await_context=False) for a in expr.agent.args]
            return f"{agent_name}().spawn({', '.join(args)})"
        raise CodegenError(
            f"unsupported AST node for codegen: {type(expr).__name__}"
        )

    def _emit_operand(self, expr: Node, await_context: bool) -> str:
        text = self.emit(expr, await_context=await_context)
        if isinstance(expr, (BinOp, UnaryOp)):
            return f"({text})"
        return text

    def _emit_call(self, call: Call, *, await_context: bool) -> str:
        if isinstance(call.callee, Member):
            lowered = self._emit_member_call(call, await_context=await_context)
            if lowered is not None:
                return lowered

        if (
            isinstance(call.callee, Identifier)
            and call.callee.name == "ask"
            and self.current_ctx_name is not None
        ):
            arg_texts = [self.emit_arg(a, await_context=await_context) for a in call.args]
            return f"await {self.current_ctx_name}.ask({', '.join(arg_texts)})"

        if isinstance(call.callee, Identifier) and call.callee.name == "gather":
            self.imports.add_runtime("gather")
            arg_texts = [self._emit_gather_arg(a) for a in call.args]
            if await_context:
                return f"await gather({', '.join(arg_texts)})"
            return f"gather({', '.join(arg_texts)})"

        callee_text = self.emit(call.callee, await_context=await_context)
        arg_texts = [self.emit_arg(a, await_context=await_context) for a in call.args]
        text = f"{callee_text}({', '.join(arg_texts)})"
        if (
            await_context
            and isinstance(call.callee, Identifier)
            and (
                call.callee.name in self.generated_fns
                or call.callee.name in self.use_imported_names
            )
        ):
            text = f"await {text}"
        return text

    @staticmethod
    def _is_gather_call(expr: Node) -> bool:
        return (
            isinstance(expr, Call)
            and isinstance(expr.callee, Identifier)
            and expr.callee.name == "gather"
        )

    def _emit_member_call(
        self, call: Call, *, await_context: bool
    ) -> str | None:
        assert isinstance(call.callee, Member)
        member = call.callee

        if member.attr == "map" and len(call.args) == 1:
            arg = call.args[0]
            if arg.name is None and isinstance(arg.value, Lambda):
                lam = arg.value
                if len(lam.params) != 1:
                    raise CodegenError("map lambda must have exactly one parameter")
                param = _mangle(lam.params[0].name)
                obj = self.emit(member.obj, await_context=False)
                body = self.emit(lam.body, await_context=await_context)
                return f"[{body} for {param} in {obj}]"

        if member.attr == "join" and len(call.args) == 1:
            arg = call.args[0]
            if arg.name is None:
                sep = self.emit(arg.value, await_context=False)
                obj = self.emit(member.obj, await_context=False)
                return f"{sep}.join({obj})"

        return None

    def emit_arg(self, arg: Arg, *, await_context: bool) -> str:
        value = self.emit(arg.value, await_context=await_context)
        if arg.name is None:
            return value
        return f"{_mangle(arg.name)}={value}"

    def _emit_gather_arg(self, arg: Arg) -> str:
        if arg.name == "timeout":
            value = self._emit_timeout_value(arg.value)
        else:
            value = self.emit(arg.value, await_context=False)
        if arg.name is None:
            return value
        return f"{_mangle(arg.name)}={value}"

    def _emit_timeout_value(self, value: Node) -> str:
        if isinstance(value, BudgetArg):
            if value.unit == "s":
                return _format_number(value.value)
            if value.unit == "ms":
                return _format_number(value.value / 1000)
            raise CodegenError(
                f"unsupported gather timeout unit: {value.unit!r}"
            )
        if isinstance(value, IntLit):
            return repr(value.value)
        if isinstance(value, FloatLit):
            return _format_number(value.value)
        return self.emit(value, await_context=False)


def _emit_kwarg_value(value: Node) -> str:
    if isinstance(value, BudgetArg):
        return repr(value.value)
    if isinstance(value, IntLit):
        return repr(value.value)
    if isinstance(value, FloatLit):
        return repr(value.value)
    if isinstance(value, StringLit):
        return repr(value.value)
    if isinstance(value, BoolLit):
        return "True" if value.value else "False"
    if isinstance(value, NullLit):
        return "None"
    if isinstance(value, QualName):
        return ".".join(_mangle(part) for part in value.parts)
    raise CodegenError(
        f"unsupported AST node for codegen: {type(value).__name__}"
    )


class StatementEmitter:
    __slots__ = (
        "writer",
        "expr",
        "type",
        "imports",
        "current_ctx_name",
        "_ctx_depth",
        "_within_count",
        "_matcher_count",
        "generated_classes",
        "prompt_constants",
        "source_path",
        "analysis",
        "cache_root",
    )

    def __init__(
        self,
        writer: PythonWriter,
        expr_emitter: ExpressionEmitter,
        type_emitter: TypeEmitter,
        imports: ImportCollector,
        *,
        generated_classes: frozenset[str] = frozenset(),
        source_path: str | Path | None = None,
        analysis: AnalysisResult | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.writer = writer
        self.expr = expr_emitter
        self.type = type_emitter
        self.imports = imports
        self.current_ctx_name: str | None = None
        self._ctx_depth = 0
        self._within_count = 0
        self._matcher_count = 0
        self.generated_classes = generated_classes
        self.prompt_constants: set[str] = set()
        self.source_path = source_path
        self.analysis = analysis
        self.cache_root = cache_root

    def emit(self, stmt: Stmt) -> None:
        if isinstance(stmt, ExprStmt):
            self._emit_expr_stmt(stmt)
            return
        if isinstance(stmt, LetStmt):
            self._emit_let(stmt)
            return
        if isinstance(stmt, ReturnStmt):
            self._emit_return(stmt)
            return
        if isinstance(stmt, YieldStmt):
            self._emit_yield(stmt)
            return
        if isinstance(stmt, IncludeStmt):
            self._emit_include(stmt)
            return
        if isinstance(stmt, IfStmt):
            self._emit_if(stmt)
            return
        if isinstance(stmt, FnDecl):
            self._emit_fn(stmt)
            return
        if isinstance(stmt, AgentDecl):
            self._emit_agent(stmt)
            return
        if isinstance(stmt, PromptDecl):
            self._emit_prompt(stmt)
            return
        if isinstance(stmt, ClassDecl):
            self._emit_class(stmt)
            return
        if isinstance(stmt, CtxBlock):
            self._emit_ctx(stmt)
            return
        if isinstance(stmt, WithinFallback):
            self._emit_within(stmt)
            return
        if isinstance(stmt, TryCatch):
            self._emit_try(stmt)
            return
        if isinstance(stmt, MatchStmt):
            self._emit_match(stmt)
            return
        raise CodegenError(
            f"unsupported AST node for codegen: {type(stmt).__name__}"
        )

    @staticmethod
    def _is_global_ask(expr: Node) -> bool:
        return (
            isinstance(expr, Call)
            and isinstance(expr.callee, Identifier)
            and expr.callee.name == "ask"
        )

    @staticmethod
    def _is_probable_type(t: TypeExpr | None) -> bool:
        return (
            isinstance(t, TypeRef)
            and len(t.name.parts) == 1
            and t.name.parts[0] == "probable"
        )

    @staticmethod
    def _probable_inner_type(t: TypeExpr | None) -> TypeExpr | None:
        if not StatementEmitter._is_probable_type(t):
            return None
        assert isinstance(t, TypeRef)
        return t.generics[0] if t.generics else None

    @staticmethod
    def _is_memory_type(t: TypeExpr | None) -> bool:
        return (
            isinstance(t, TypeRef)
            and len(t.name.parts) >= 1
            and t.name.parts[0] == "memory"
        )

    def _allocate_ctx_name(self) -> str:
        self._ctx_depth += 1
        return "ctx" if self._ctx_depth == 1 else f"ctx_{self._ctx_depth}"

    def _release_ctx_name(self) -> None:
        self._ctx_depth -= 1

    def _allocate_within_name(self) -> str:
        self._within_count += 1
        return (
            "_within_primary_"
            if self._within_count == 1
            else f"_within_primary_{self._within_count}"
        )

    def _emit_expr_stmt(self, stmt: ExprStmt) -> None:
        if self._is_global_ask(stmt.expr) and self.current_ctx_name is None:
            self._wrap_implicit_ctx(
                lambda: self._write_implicit_ask_call(stmt.expr, prefix="")
            )
            return
        self.writer.write(self.expr.emit(stmt.expr, await_context=True))

    def _emit_let(self, stmt: LetStmt) -> None:
        if self._is_memory_type(stmt.type_annot) and stmt.value is None:
            self._emit_memory_let(stmt)
            return
        if (
            stmt.value is not None
            and self._is_global_ask(stmt.value)
            and self.current_ctx_name is not None
            and self._is_probable_type(stmt.type_annot)
        ):
            self._emit_ctx_probable_let(stmt)
            return
        if (
            stmt.value is not None
            and self._is_global_ask(stmt.value)
            and self.current_ctx_name is None
        ):
            self._emit_implicit_ctx_let(stmt)
            return

        text = _mangle(stmt.name)
        if stmt.type_annot is not None:
            text += f": {self.type.emit(stmt.type_annot)}"
        if stmt.value is not None:
            text += f" = {self.expr.emit(stmt.value, await_context=True)}"
        self.writer.write(text)

    def _emit_ctx_probable_let(self, stmt: LetStmt) -> None:
        self.imports.add_runtime("ProbableValue")
        ask_call = stmt.value
        assert isinstance(ask_call, Call)
        arg_texts = [
            self.expr.emit_arg(a, await_context=True) for a in ask_call.args
        ]
        inner_type = self._probable_inner_type(stmt.type_annot)
        if inner_type is not None:
            arg_texts.append(f"return_type={self.type.emit(inner_type)}")
        else:
            arg_texts.append("return_type=ProbableValue")

        name = _mangle(stmt.name)
        value_name = f"_{name}_value"
        self.writer.write(
            f"{value_name} = await {self.current_ctx_name}.ask({', '.join(arg_texts)})"
        )
        self.writer.write(
            f"{name}: ProbableValue = ProbableValue("
            f"value={value_name}, "
            f"confidence=getattr({value_name}, 'confidence', "
            f"0.9 if {value_name} is not None else 0.0)"
            f")"
        )

    def _emit_memory_let(self, stmt: LetStmt) -> None:
        type_ref = stmt.type_annot
        assert isinstance(type_ref, TypeRef)
        parts = type_ref.name.parts
        kind = parts[1] if len(parts) > 1 else "working"
        cls = _MEMORY_CLASSES.get(kind)
        if cls is None:
            raise CodegenError(f"unknown memory kind: {kind}")
        self.imports.add_runtime(cls)
        kwargs = [
            f"{_mangle(kw.name)}={_emit_kwarg_value(kw.value)}"
            for kw in type_ref.kwargs
        ]
        self.writer.write(
            f"{_mangle(stmt.name)} = {cls}({', '.join(kwargs)})"
        )

    def _emit_implicit_ctx_let(self, stmt: LetStmt) -> None:
        is_probable = self._is_probable_type(stmt.type_annot)
        if is_probable:
            self.imports.add_runtime("ProbableValue")

        def write_body() -> None:
            ask_call = stmt.value
            assert isinstance(ask_call, Call)
            arg_texts = [
                self.expr.emit_arg(a, await_context=True) for a in ask_call.args
            ]
            if is_probable:
                arg_texts.append("return_type=ProbableValue")
            annot = ""
            if is_probable:
                annot = ": ProbableValue"
            elif stmt.type_annot is not None:
                annot = f": {self.type.emit(stmt.type_annot)}"
            self.writer.write(
                f"{_mangle(stmt.name)}{annot} = await ctx.ask({', '.join(arg_texts)})"
            )

        self._wrap_implicit_ctx(write_body)

    def _emit_return(self, stmt: ReturnStmt) -> None:
        if (
            stmt.value is not None
            and self._is_global_ask(stmt.value)
            and self.current_ctx_name is None
        ):
            def write_body() -> None:
                arg_texts = [
                    self.expr.emit_arg(a, await_context=True)
                    for a in stmt.value.args  # type: ignore[union-attr]
                ]
                self.writer.write(
                    f"return await ctx.ask({', '.join(arg_texts)})"
                )

            self._wrap_implicit_ctx(write_body)
            return

        if stmt.value is None:
            self.writer.write("return")
        else:
            value = self.expr.emit(stmt.value, await_context=True)
            self.writer.write(f"return {value}")

    def _emit_yield(self, stmt: YieldStmt) -> None:
        if self.current_ctx_name is not None:
            if stmt.value is None:
                self.writer.write("return")
            else:
                value = self.expr.emit(stmt.value, await_context=True)
                self.writer.write(f"return {value}")
            return
        if stmt.value is None:
            self.writer.write("yield")
        else:
            value = self.expr.emit(stmt.value, await_context=True)
            self.writer.write(f"yield {value}")

    def _emit_include(self, stmt: IncludeStmt) -> None:
        if self.current_ctx_name is None:
            raise CodegenError("include statement outside ctx block")
        value = self.expr.emit(stmt.value, await_context=False)
        self.writer.write(f"await {self.current_ctx_name}.add({value})")

    def _emit_if(self, stmt: IfStmt) -> None:
        condition = stmt.condition
        if isinstance(condition, ConfidenceGate):
            target = self.expr.emit(condition.target, await_context=True)
            cond_text = f"{target}.confidence {condition.op} {condition.threshold}"
        else:
            cond_text = self.expr.emit(condition, await_context=True)
        self.writer.write(f"if {cond_text}:")
        with self.writer.indent():
            if stmt.then_body:
                for inner in stmt.then_body:
                    self.emit(inner)
            else:
                self.writer.write("pass")
        if stmt.else_body is not None:
            self.writer.write("else:")
            with self.writer.indent():
                if stmt.else_body:
                    for inner in stmt.else_body:
                        self.emit(inner)
                else:
                    self.writer.write("pass")

    def _emit_fn(self, fn: FnDecl) -> None:
        self._emit_decorators(fn.decorators)
        params = [self._emit_param(p) for p in fn.params]
        sig = f"async def {_mangle(fn.name)}({', '.join(params)})"
        if fn.return_type is not None:
            sig += f" -> {self.type.emit(fn.return_type)}"
        sig += ":"
        self.writer.write(sig)
        with self.writer.indent():
            if fn.body:
                for inner in fn.body:
                    self.emit(inner)
            else:
                self.writer.write("pass")

    def _emit_decorators(self, decorators: tuple[Decorator, ...]) -> None:
        for decorator in decorators:
            if decorator.name != "tool":
                raise CodegenError(
                    f"unsupported decorator for codegen: {decorator.name}"
                )
            self.imports.add_runtime("tool")
            self.writer.write("@tool")

    def _emit_param(self, param: Param) -> str:
        text = _mangle(param.name)
        if param.type_annot is not None:
            text += f": {self.type.emit(param.type_annot)}"
        if param.default is not None:
            text += f" = {self.expr.emit(param.default, await_context=False)}"
        return text

    def _emit_agent(self, agent: AgentDecl) -> None:
        self.imports.add_runtime("VossAgent")
        self.writer.write(f"class {_mangle(agent.name)}(VossAgent):")
        with self.writer.indent():
            wrote_attr = False
            if agent.options.system is not None:
                self.writer.write(
                    f"system_prompt = {self._emit_class_attr(agent.options.system)}"
                )
                wrote_attr = True
            if agent.options.tools is not None:
                self.writer.write(f"tools = {self._emit_tools(agent.options.tools)}")
                wrote_attr = True
            if agent.options.model is not None:
                self.writer.write(
                    f"model = {self._emit_class_attr(agent.options.model)}"
                )
                wrote_attr = True
            if agent.options.retries is not None:
                self.writer.write(
                    f"retries = {self._emit_class_attr(agent.options.retries)}"
                )
                wrote_attr = True
            if self._returns_generated_class(agent.return_type):
                assert isinstance(agent.return_type, TypeRef)
                self.writer.write(f"return_type = {agent.return_type.name.parts[-1]}")
                wrote_attr = True
            if wrote_attr:
                self.writer.blank()

            params = ["self"] + [self._emit_param(p) for p in agent.params]
            sig = f"async def run({', '.join(params)})"
            if agent.return_type is not None:
                sig += f" -> {self.type.emit(agent.return_type)}"
            sig += ":"
            self.writer.write(sig)
            with self.writer.indent():
                if agent.body:
                    for inner in agent.body:
                        self.emit(inner)
                else:
                    self.writer.write("pass")

    def _emit_class_attr(self, value: Node) -> str:
        if isinstance(value, StringLit):
            return _string_literal(value.value)
        if isinstance(value, IntLit):
            return repr(value.value)
        if isinstance(value, FloatLit):
            return _format_number(value.value)
        if isinstance(value, BoolLit):
            return "True" if value.value else "False"
        if isinstance(value, NullLit):
            return "None"
        return self.expr.emit(value, await_context=False)

    def _emit_tools(self, tools: Node) -> str:
        if not isinstance(tools, ListLit):
            raise CodegenError(
                f"unsupported AST node for codegen: {type(tools).__name__}"
            )
        items = [self.expr.emit(item, await_context=False) for item in tools.items]
        if len(items) == 1:
            return f"({items[0]},)"
        return f"({', '.join(items)})"

    def _returns_generated_class(self, type_expr: TypeExpr | None) -> bool:
        return (
            isinstance(type_expr, TypeRef)
            and len(type_expr.name.parts) == 1
            and type_expr.name.parts[0] in self.generated_classes
        )

    def _emit_prompt(self, prompt: PromptDecl) -> None:
        const_name = _prompt_const_name(prompt.name)
        body_text = "\n".join(part.value for part in prompt.body)
        if prompt.extends is None:
            self.writer.write(f"{const_name} = {_string_literal(body_text)}")
        else:
            parent_name = prompt.extends.parts[-1]
            parent_const = _prompt_const_name(parent_name)
            if parent_const not in self.prompt_constants:
                raise CodegenError("prompt parent must be declared before child")
            self.writer.write(
                f"{const_name} = {parent_const} + {_string_literal(chr(10))} + "
                f"{_string_literal(body_text)}"
            )
        self.prompt_constants.add(const_name)

    def _emit_class(self, cls: ClassDecl) -> None:
        self.imports.add_base_model()
        self.writer.write(f"class {_mangle(cls.name)}(BaseModel):")
        with self.writer.indent():
            if cls.fields:
                for field in cls.fields:
                    self._emit_class_field(field)
            else:
                self.writer.write("pass")

    def _emit_class_field(self, field: ClassField) -> None:
        text = f"{_mangle(field.name)}: {self.type.emit(field.type_annot)}"
        if field.default is not None:
            text += f" = {self.expr.emit(field.default, await_context=False)}"
        self.writer.write(text)

    def _emit_ctx(self, stmt: CtxBlock) -> None:
        self.imports.add_runtime("ContextScope")
        name = self._allocate_ctx_name()
        budget = stmt.budget.value
        budget_text = repr(int(budget) if isinstance(budget, int) or budget == int(budget) else budget)
        self.writer.write(
            f"async with ContextScope(token_budget={budget_text}) as {name}:"
        )
        prev_ctx = self.current_ctx_name
        prev_expr_ctx = self.expr.current_ctx_name
        self.current_ctx_name = name
        self.expr.current_ctx_name = name
        try:
            with self.writer.indent():
                if stmt.body:
                    for inner in stmt.body:
                        self.emit(inner)
                else:
                    self.writer.write("pass")
        finally:
            self.current_ctx_name = prev_ctx
            self.expr.current_ctx_name = prev_expr_ctx
            self._release_ctx_name()

    def _emit_within(self, stmt: WithinFallback) -> None:
        self.imports.add_runtime("BudgetExceededError")
        self.imports.add_runtime("run_with_budget")
        helper_name = self._allocate_within_name()

        self.writer.write(f"async def {helper_name}():")
        with self.writer.indent():
            if stmt.primary:
                for inner in stmt.primary:
                    self.emit(inner)
            else:
                self.writer.write("pass")

        kwargs = self._normalize_within_kwargs(stmt.budget_args)
        kwargs_text = ", ".join(f"{name}={value}" for name, value in kwargs)
        self.writer.write("try:")
        with self.writer.indent():
            call = f"{helper_name}()"
            args_text = f"{call}, {kwargs_text}" if kwargs_text else call
            self.writer.write(f"return await run_with_budget({args_text})")
        self.writer.write("except BudgetExceededError:")
        with self.writer.indent():
            if stmt.fallback:
                for inner in stmt.fallback:
                    self.emit(inner)
            else:
                self.writer.write("pass")

    def _normalize_within_kwargs(
        self, args: tuple[BudgetArg, ...]
    ) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for arg in args:
            unit = arg.unit
            if unit == "tokens":
                result.append(("token_limit", repr(int(arg.value))))
            elif unit == "ms":
                result.append(("latency_ms", repr(int(arg.value))))
            elif unit == "s":
                result.append(("latency_ms", repr(int(arg.value * 1000))))
            elif unit == "usd":
                result.append(("cost_usd", repr(arg.value)))
            else:
                raise CodegenError(
                    f"unsupported within budget unit: {unit!r}"
                )
        return result

    def _allocate_matcher_name(self) -> str:
        self._matcher_count += 1
        return f"_matcher_{self._matcher_count}"

    def _emit_match(self, stmt: MatchStmt) -> None:
        has_similar = any(
            isinstance(case.pattern, SimilarPattern) for case in stmt.cases
        )
        if has_similar:
            self._emit_similar_match(stmt)
        else:
            self._emit_structural_match(stmt)

    def _emit_similar_match(self, stmt: MatchStmt) -> None:
        if self.cache_root is None:
            raise CodegenError(
                "semantic match codegen requires cache_root context"
            )
        match_id = f"match_{stmt.span.line_start}_{stmt.span.col_start}"
        index = _load_match_index(
            match_id,
            source_path=self.source_path,
            analysis=self.analysis,
            cache_root=self.cache_root,
        )
        self.imports.add_runtime("SemanticMatcher")
        matcher_name = self._allocate_matcher_name()

        cases_repr = (
            "["
            + ", ".join(
                f"({repr(desc)}, {repr(label)})" for desc, label in index.cases
            )
            + "]"
        )
        embeddings_repr = (
            "["
            + ", ".join(
                "[" + ", ".join(repr(float(x)) for x in emb) + "]"
                for emb in index.embeddings
            )
            + "]"
        )

        self.writer.write(f"{matcher_name} = SemanticMatcher(")
        with self.writer.indent():
            self.writer.write(f"cases={cases_repr},")
            self.writer.write(f"threshold={index.threshold},")
            self.writer.write(f"embeddings={embeddings_repr},")
        self.writer.write(")")

        scrut = self.expr.emit(stmt.scrutinee, await_context=False)
        self.writer.write(f"match {matcher_name}.match({scrut}):")
        with self.writer.indent():
            similar_idx = 0
            for case in stmt.cases:
                if isinstance(case.pattern, SimilarPattern):
                    if similar_idx < len(index.cases):
                        label = index.cases[similar_idx][1]
                    else:
                        label = f"case_{similar_idx}"
                    similar_idx += 1
                    self.writer.write(f'case "{label}":')
                elif isinstance(case.pattern, WildcardPattern):
                    self.writer.write("case _:")
                elif isinstance(case.pattern, ExprPattern):
                    pat = self.expr.emit(case.pattern.expr, await_context=False)
                    self.writer.write(f"case {pat}:")
                else:
                    raise CodegenError(
                        f"unsupported AST node for codegen: {type(case.pattern).__name__}"
                    )
                with self.writer.indent():
                    if case.body:
                        for inner in case.body:
                            self.emit(inner)
                    else:
                        self.writer.write("pass")

    def _emit_structural_match(self, stmt: MatchStmt) -> None:
        scrut = self.expr.emit(stmt.scrutinee, await_context=False)
        self.writer.write(f"match {scrut}:")
        with self.writer.indent():
            for case in stmt.cases:
                if isinstance(case.pattern, WildcardPattern):
                    self.writer.write("case _:")
                elif isinstance(case.pattern, ExprPattern):
                    pat = self.expr.emit(case.pattern.expr, await_context=False)
                    self.writer.write(f"case {pat}:")
                else:
                    raise CodegenError(
                        f"unsupported AST node for codegen: {type(case.pattern).__name__}"
                    )
                with self.writer.indent():
                    if case.body:
                        for inner in case.body:
                            self.emit(inner)
                    else:
                        self.writer.write("pass")

    def _emit_try(self, stmt: TryCatch) -> None:
        self.writer.write("try:")
        with self.writer.indent():
            if stmt.try_body:
                for inner in stmt.try_body:
                    self.emit(inner)
            else:
                self.writer.write("pass")
        clause = (
            "except Exception:"
            if stmt.exc_name is None
            else f"except Exception as {_mangle(stmt.exc_name)}:"
        )
        self.writer.write(clause)
        with self.writer.indent():
            if stmt.catch_body:
                for inner in stmt.catch_body:
                    self.emit(inner)
            else:
                self.writer.write("pass")

    def _wrap_implicit_ctx(self, write_body) -> None:
        self.imports.add_runtime("ContextScope")
        name = self._allocate_ctx_name()
        self.writer.write(
            f"async with ContextScope(token_budget=4000) as {name}:"
        )
        prev_ctx = self.current_ctx_name
        prev_expr_ctx = self.expr.current_ctx_name
        self.current_ctx_name = name
        self.expr.current_ctx_name = name
        try:
            with self.writer.indent():
                write_body()
        finally:
            self.current_ctx_name = prev_ctx
            self.expr.current_ctx_name = prev_expr_ctx
            self._release_ctx_name()

    def _write_implicit_ask_call(self, call: Call, *, prefix: str) -> None:
        arg_texts = [self.expr.emit_arg(a, await_context=True) for a in call.args]
        self.writer.write(
            f"{prefix}await ctx.ask({', '.join(arg_texts)})"
        )


_DECL_TYPES = (FnDecl, AgentDecl, PromptDecl, ClassDecl)
_COORD_DECL_TYPES = (TeamDecl, PrinciplesBlockDecl, GateBlockDecl, MemoryBlockDecl)


class ProgramEmitter:
    __slots__ = ("program", "imports", "source_path", "analysis", "cache_root")

    def __init__(
        self,
        program: Program,
        *,
        source_path: str | Path | None = None,
        analysis: AnalysisResult | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.program = program
        self.imports = ImportCollector()
        self.source_path = source_path
        self.analysis = analysis
        self.cache_root = cache_root

    def emit(self) -> CodegenResult:
        for stmt in self.program.body:
            if isinstance(stmt, UseStmt):
                self.imports.add_use(stmt.path, alias=stmt.alias)

        fn_names = frozenset(
            stmt.name for stmt in self.program.body if isinstance(stmt, FnDecl)
        )
        use_imported_names = frozenset(
            stmt.alias or stmt.path[-1]
            for stmt in self.program.body
            if isinstance(stmt, UseStmt)
        )

        decls: list[Stmt] = []
        execs: list[Stmt] = []
        for stmt in self.program.body:
            if isinstance(stmt, UseStmt) or isinstance(stmt, _COORD_DECL_TYPES):
                continue
            if isinstance(stmt, _DECL_TYPES):
                decls.append(stmt)
            else:
                execs.append(stmt)

        requires_async_main = bool(execs)
        if requires_async_main:
            self.imports.add_stdlib("asyncio")

        type_emitter = TypeEmitter(self.imports)
        expr_emitter = ExpressionEmitter(
            self.imports,
            generated_fns=fn_names,
            use_imported_names=use_imported_names,
        )
        class_names = frozenset(
            stmt.name for stmt in self.program.body if isinstance(stmt, ClassDecl)
        )
        body_writer = PythonWriter()
        stmt_emitter = StatementEmitter(
            body_writer,
            expr_emitter,
            type_emitter,
            self.imports,
            generated_classes=class_names,
            source_path=self.source_path,
            analysis=self.analysis,
            cache_root=self.cache_root,
        )

        for index, decl in enumerate(decls):
            if index > 0:
                body_writer.blank()
            stmt_emitter.emit(decl)

        if requires_async_main:
            if decls:
                body_writer.blank()
            body_writer.write("async def main():")
            with body_writer.indent():
                if execs:
                    for stmt in execs:
                        stmt_emitter.emit(stmt)
                else:
                    body_writer.write("pass")
            body_writer.blank()
            body_writer.write('if __name__ == "__main__":')
            with body_writer.indent():
                body_writer.write("asyncio.run(main())")

        import_lines, import_meta = self.imports.render()

        final = PythonWriter()
        for line in import_lines:
            final.write(line)
        if import_lines and body_writer.lines:
            final.blank()
        final.lines.extend(body_writer.lines)

        source = final.render()
        if source.strip() == "":
            source = "\n"

        return CodegenResult(
            source=source,
            imports=import_meta,
            requires_async_main=requires_async_main,
        )


def generate_python(
    program: Program,
    *,
    source_path: str | Path | None = None,
    analysis: AnalysisResult | None = None,
    cache_dir: str | Path = ".voss-cache",
    project_root: str | Path | None = None,
) -> CodegenResult:
    if analysis is None:
        from .analyzer import analyze

        analysis = analyze(program, source_path=source_path, cache_dir=cache_dir)

    if not analysis.ok:
        raise CodegenError("semantic analysis failed; refusing to generate Python")

    cache_root = _resolve_cache_root(project_root, cache_dir)

    emitter = ProgramEmitter(
        program,
        source_path=source_path,
        analysis=analysis,
        cache_root=cache_root,
    )
    result = emitter.emit()
    return CodegenResult(
        source=result.source,
        imports=result.imports,
        requires_async_main=result.requires_async_main,
        analysis=analysis,
    )
