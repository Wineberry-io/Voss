from __future__ import annotations

import ast as _ast


from voss.ast_nodes import (
    Arg,
    BinOp,
    BoolLit,
    Call,
    DictLit,
    Identifier,
    IntLit,
    Lambda,
    ListLit,
    Member,
    NullLit,
    Param,
    SpawnExpr,
    StringLit,
)
from voss.codegen import ExpressionEmitter

from tests.codegen.conftest import span


def _make_emitter(generated_fns: tuple[str, ...] = ()) -> ExpressionEmitter:
    return ExpressionEmitter(generated_fns=frozenset(generated_fns))


def _ident(name: str) -> Identifier:
    return Identifier(span=span(), name=name)


def _compile_eval(text: str) -> None:
    compile(text, "<expr>", "eval")


def test_literals_and_identifiers_emit_python_values():
    emitter = _make_emitter()
    assert emitter.emit(StringLit(span=span(), value="hello")) == repr("hello")
    assert emitter.emit(BoolLit(span=span(), value=True)) == "True"
    assert emitter.emit(BoolLit(span=span(), value=False)) == "False"
    assert emitter.emit(NullLit(span=span())) == "None"
    assert emitter.emit(IntLit(span=span(), value=42)) == "42"
    assert emitter.emit(_ident("class")) == "class_"
    assert emitter.emit(_ident("user_input")) == "user_input"
    for snippet in ("True", "None", "42", "class_", "user_input", repr("hello")):
        _compile_eval(snippet)


def test_binary_expression_parenthesizes_nested_operations():
    emitter = _make_emitter()
    inner = BinOp(span=span(), op="+", left=_ident("a"), right=_ident("b"))
    expr = BinOp(span=span(), op="*", left=inner, right=_ident("c"))
    text = emitter.emit(expr)
    assert "(a + b)" in text
    parsed = _ast.parse(text, mode="eval")
    assert isinstance(parsed.body, _ast.BinOp)
    assert isinstance(parsed.body.op, _ast.Mult)
    assert isinstance(parsed.body.left, _ast.BinOp)
    assert isinstance(parsed.body.left.op, _ast.Add)
    _compile_eval(text)


def test_call_member_index_and_named_args():
    emitter = _make_emitter()
    expr = Call(
        span=span(),
        callee=Member(span=span(), obj=_ident("client"), attr="send"),
        args=(
            Arg(span=span(), name=None, value=StringLit(span=span(), value="x")),
            Arg(span=span(), name="timeout", value=IntLit(span=span(), value=3)),
        ),
    )
    assert emitter.emit(expr) == "client.send('x', timeout=3)"
    _compile_eval("client.send('x', timeout=3)")


def test_list_dict_and_lambda_emit_parseable_python():
    emitter = _make_emitter()
    list_expr = ListLit(
        span=span(),
        items=(IntLit(span=span(), value=1), IntLit(span=span(), value=2)),
    )
    list_text = emitter.emit(list_expr)
    assert list_text == "[1, 2]"
    _compile_eval(list_text)

    dict_expr = DictLit(
        span=span(),
        items=(
            (StringLit(span=span(), value="k"), IntLit(span=span(), value=7)),
        ),
    )
    dict_text = emitter.emit(dict_expr)
    assert dict_text == "{'k': 7}"
    _compile_eval(dict_text)

    lambda_expr = Lambda(
        span=span(),
        params=(Param(span=span(), name="t"),),
        body=_ident("t"),
    )
    lam_text = emitter.emit(lambda_expr)
    assert lam_text == "lambda t: t"
    _compile_eval(lam_text)


def test_spawn_expression_emits_agent_spawn_call():
    emitter = _make_emitter()
    expr = SpawnExpr(
        span=span(),
        agent=Call(
            span=span(),
            callee=_ident("Researcher"),
            args=(Arg(span=span(), name=None, value=_ident("topic")),),
        ),
    )
    text = emitter.emit(expr)
    assert text == "Researcher().spawn(topic)"
    _compile_eval(text)
