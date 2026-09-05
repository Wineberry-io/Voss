from __future__ import annotations


from voss.ast_nodes import (
    Arg,
    BoolLit,
    Call,
    ExprStmt,
    FnDecl,
    Identifier,
    IfStmt,
    LetStmt,
    Param,
    QualName,
    ReturnStmt,
    StringLit,
    TypeRef,
)
from voss.codegen import generate_python

from tests.codegen.conftest import (
    assert_no_compiler_imports,
    assert_python_parses,
    program,
    span,
)


def _ident(name: str) -> Identifier:
    return Identifier(span=span(), name=name)


def _type(name: str) -> TypeRef:
    return TypeRef(
        span=span(),
        name=QualName(span=span(), parts=(name,)),
    )


def test_fn_decl_lowers_to_async_def():
    fn = FnDecl(
        span=span(),
        name="classifyIntent",
        params=(Param(span=span(), name="input", type_annot=_type("string")),),
        return_type=_type("string"),
        body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="ok")),),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "async def classifyIntent(input: str) -> str:" in source
    assert "return 'ok'" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_top_level_statement_wraps_in_async_main():
    call = Call(
        span=span(),
        callee=_ident("print"),
        args=(Arg(span=span(), name=None, value=StringLit(span=span(), value="hi")),),
    )
    stmt = ExprStmt(span=span(), expr=call)
    result = generate_python(program(stmt))
    source = result.source
    assert "import asyncio" in source
    assert "async def main():" in source
    assert "print('hi')" in source
    assert "asyncio.run(main())" in source
    assert 'if __name__ == "__main__":' in source or "if __name__ == '__main__':" in source
    assert result.requires_async_main is True
    assert_python_parses(source)


def test_let_and_return_are_readable():
    let = LetStmt(
        span=span(),
        name="result",
        type_annot=_type("string"),
        value=StringLit(span=span(), value="ok"),
    )
    fn = FnDecl(
        span=span(),
        name="run",
        params=(),
        return_type=_type("string"),
        body=(let, ReturnStmt(span=span(), value=_ident("result"))),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "result: str = 'ok'" in source
    assert "return result" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_if_statement_emits_multiline_blocks():
    if_stmt = IfStmt(
        span=span(),
        condition=_ident("ready"),
        then_body=(ReturnStmt(span=span(), value=BoolLit(span=span(), value=True)),),
        else_body=(ReturnStmt(span=span(), value=BoolLit(span=span(), value=False)),),
    )
    fn = FnDecl(
        span=span(),
        name="check",
        params=(Param(span=span(), name="ready", type_annot=_type("bool")),),
        return_type=_type("bool"),
        body=(if_stmt,),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "if ready:\n" in source
    assert "    return True" in source
    assert "else:\n" in source
    assert "    return False" in source
    # Reject one-liner forms.
    assert "if ready: return" not in source
    assert_python_parses(source)


def test_call_to_generated_function_is_awaited_in_main():
    fn = FnDecl(
        span=span(),
        name="classifyIntent",
        params=(Param(span=span(), name="input", type_annot=_type("string")),),
        return_type=_type("string"),
        body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="ok")),),
    )
    inner = Call(
        span=span(),
        callee=_ident("classifyIntent"),
        args=(Arg(span=span(), name=None, value=StringLit(span=span(), value="x")),),
    )
    top = ExprStmt(
        span=span(),
        expr=Call(
            span=span(),
            callee=_ident("print"),
            args=(Arg(span=span(), name=None, value=inner),),
        ),
    )
    result = generate_python(program(fn, top))
    source = result.source
    assert "print(await classifyIntent('x'))" in source
    assert "async def main():" in source
    assert "asyncio.run(main())" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)
