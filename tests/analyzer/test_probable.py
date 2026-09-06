from __future__ import annotations

from voss import analyze
from voss.ast_nodes import (
    Arg,
    Call,
    ConfidenceGate,
    FnDecl,
    Identifier,
    IfStmt,
    LetStmt,
    Member,
    Param,
    QualName,
    ReturnStmt,
    StringLit,
    TypeRef,
)

from tests.analyzer.conftest import program, span


def t(name: str, *generics: TypeRef) -> TypeRef:
    return TypeRef(span=span(), name=QualName(span=span(), parts=(name,)), generics=tuple(generics))


def t_string() -> TypeRef:
    return t("string")


def t_probable_string() -> TypeRef:
    return t("probable", t_string())


def ident(name: str, line: int = 1, col: int = 1) -> Identifier:
    return Identifier(span=span(line=line, col=col), name=name)


def call(callee_name: str, *args: Arg, line: int = 1) -> Call:
    return Call(span=span(line=line), callee=ident(callee_name, line=line), args=args)


def positional(value) -> Arg:
    return Arg(span=span(), name=None, value=value)


def let(name: str, type_annot: TypeRef | None, value, line: int = 1) -> LetStmt:
    return LetStmt(span=span(line=line), name=name, type_annot=type_annot, value=value)


def ret(value, line: int = 1) -> ReturnStmt:
    return ReturnStmt(span=span(line=line), value=value)


def ask_call(line: int = 1) -> Call:
    return call("ask", positional(StringLit(span=span(), value="classify")), line=line)


def test_assignment_probable_to_plain_type_warns():
    intent_ident = ident("intent", line=2, col=24)
    prog = program(
        let("intent", t_probable_string(), ask_call(line=1), line=1),
        let("route", t_string(), intent_ident, line=2),
    )
    result = analyze(prog, emit_indexes=False)
    warns = [d for d in result.diagnostics if d.code == "ANLY001"]
    assert len(warns) == 1
    d = warns[0]
    assert d.severity == "warning"
    assert "unguarded probable<string> used where string is expected" in d.message
    assert d.span.line_start == intent_ident.span.line_start


def test_assignment_probable_to_probable_type_is_allowed():
    prog = program(
        let("intent", t_probable_string(), ask_call(), line=1),
        let("copy", t_probable_string(), ident("intent", line=2), line=2),
    )
    result = analyze(prog, emit_indexes=False)
    assert [d for d in result.diagnostics if d.code == "ANLY001"] == []


def test_return_probable_from_plain_function_warns():
    body = (
        let("intent", t_probable_string(), ask_call(line=2), line=2),
        ret(ident("intent", line=3), line=3),
    )
    fn = FnDecl(
        span=span(line=1),
        name="f",
        params=(),
        return_type=t_string(),
        body=body,
    )
    result = analyze(program(fn), emit_indexes=False)
    warns = [d for d in result.diagnostics if d.code == "ANLY001"]
    assert len(warns) == 1
    assert "unguarded probable<string> used where string is expected" in warns[0].message


def test_call_argument_probable_to_plain_parameter_warns():
    route = FnDecl(
        span=span(line=1),
        name="route",
        params=(Param(span=span(), name="input", type_annot=t_string()),),
        return_type=t_string(),
        body=(ret(StringLit(span=span(), value="ok"), line=1),),
    )
    main = FnDecl(
        span=span(line=2),
        name="main",
        params=(),
        return_type=t_string(),
        body=(
            let("intent", t_probable_string(), ask_call(line=3), line=3),
            ret(call("route", positional(ident("intent", line=4)), line=4), line=4),
        ),
    )
    result = analyze(program(route, main), emit_indexes=False)
    warns = [d for d in result.diagnostics if d.code == "ANLY001"]
    assert len(warns) >= 1


def test_value_access_outside_gate_warns():
    member = Member(span=span(line=3, col=12), obj=ident("intent", line=3), attr="value")
    fn = FnDecl(
        span=span(line=1),
        name="f",
        params=(),
        return_type=t_string(),
        body=(
            let("intent", t_probable_string(), ask_call(line=2), line=2),
            ret(member, line=3),
        ),
    )
    result = analyze(program(fn), emit_indexes=False)
    warns = [d for d in result.diagnostics if d.code == "ANLY001"]
    assert len(warns) >= 1
    assert any(w.span.line_start == member.span.line_start for w in warns)


def test_value_access_inside_greater_equal_gate_is_allowed():
    # if intent @ p >= 0.80 { return intent.value } else { return "unknown" }
    gate = ConfidenceGate(
        span=span(line=3),
        target=ident("intent", line=3),
        op=">=",
        threshold=0.80,
    )
    then_body = (
        ret(Member(span=span(line=4), obj=ident("intent", line=4), attr="value"), line=4),
    )
    else_body = (ret(StringLit(span=span(line=6), value="unknown"), line=6),)
    if_stmt = IfStmt(span=span(line=3), condition=gate, then_body=then_body, else_body=else_body)
    fn = FnDecl(
        span=span(line=1),
        name="f",
        params=(),
        return_type=t_string(),
        body=(
            let("intent", t_probable_string(), ask_call(line=2), line=2),
            if_stmt,
        ),
    )
    result = analyze(program(fn), emit_indexes=False)
    assert [d for d in result.diagnostics if d.code == "ANLY001"] == []


def test_else_branch_after_greater_equal_gate_remains_ungated():
    gate = ConfidenceGate(
        span=span(line=3),
        target=ident("intent", line=3),
        op=">=",
        threshold=0.80,
    )
    then_body = (ret(StringLit(span=span(line=4), value="ok"), line=4),)
    member = Member(span=span(line=6), obj=ident("intent", line=6), attr="value")
    else_body = (ret(member, line=6),)
    if_stmt = IfStmt(span=span(line=3), condition=gate, then_body=then_body, else_body=else_body)
    fn = FnDecl(
        span=span(line=1),
        name="f",
        params=(),
        return_type=t_string(),
        body=(
            let("intent", t_probable_string(), ask_call(line=2), line=2),
            if_stmt,
        ),
    )
    result = analyze(program(fn), emit_indexes=False)
    warns = [d for d in result.diagnostics if d.code == "ANLY001"]
    assert len(warns) >= 1


def test_unknown_call_result_does_not_warn():
    prog = program(
        let("x", t_string(), call("unknownCall", line=1), line=1),
    )
    result = analyze(prog, emit_indexes=False)
    assert [d for d in result.diagnostics if d.code == "ANLY001"] == []
