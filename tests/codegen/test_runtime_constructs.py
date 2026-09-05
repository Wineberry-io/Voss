from __future__ import annotations


from voss.ast_nodes import (
    Arg,
    BudgetArg,
    Call,
    CtxBlock,
    FnDecl,
    Identifier,
    IncludeStmt,
    LetStmt,
    Param,
    QualName,
    ReturnStmt,
    StringLit,
    TryCatch,
    TypeKwarg,
    TypeRef,
    WithinFallback,
    YieldStmt,
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


def _qual(*parts: str) -> QualName:
    return QualName(span=span(), parts=parts)


def _type(*parts: str, generics: tuple = (), kwargs: tuple = ()) -> TypeRef:
    return TypeRef(span=span(), name=_qual(*parts), generics=generics, kwargs=kwargs)


def _budget(name: str, unit: str, value: int | float, raw: str = "") -> BudgetArg:
    return BudgetArg(span=span(), name=name, unit=unit, value=value, raw=raw or str(value))


def test_probable_ask_binding_uses_implicit_context_when_no_ctx_active():
    let = LetStmt(
        span=span(),
        name="intent",
        type_annot=_type("probable", generics=(_type("string"),)),
        value=Call(
            span=span(),
            callee=_ident("ask"),
            args=(Arg(span=span(), name=None, value=StringLit(span=span(), value="Classify")),),
        ),
    )
    fn = FnDecl(
        span=span(),
        name="classifyIntent",
        params=(Param(span=span(), name="input", type_annot=_type("string")),),
        return_type=_type("string"),
        body=(let, ReturnStmt(span=span(), value=_ident("intent"))),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "from voss_runtime import ContextScope, ProbableValue" in source
    assert "async with ContextScope(token_budget=4000) as ctx:" in source
    assert (
        "intent: ProbableValue = await ctx.ask('Classify', return_type=ProbableValue)"
        in source
    )
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_ctx_block_uses_async_context_and_awaits_include_and_ask():
    ask_call = Call(
        span=span(),
        callee=_ident("ask"),
        args=(Arg(span=span(), name=None, value=StringLit(span=span(), value="Summarize")),),
    )
    ctx = CtxBlock(
        span=span(),
        budget=_budget("budget", "tokens", 3000, "3000 tokens"),
        body=(
            IncludeStmt(span=span(), value=_ident("history")),
            YieldStmt(span=span(), value=ask_call),
        ),
    )
    fn = FnDecl(
        span=span(),
        name="summarize",
        params=(),
        return_type=_type("string"),
        body=(ctx,),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "async with ContextScope(token_budget=3000) as ctx:" in source
    assert "await ctx.add(history)" in source
    assert "return await ctx.ask(" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_probable_ask_binding_inside_ctx_wraps_value():
    let = LetStmt(
        span=span(),
        name="intent",
        type_annot=_type("probable", generics=(_type("string"),)),
        value=Call(
            span=span(),
            callee=_ident("ask"),
            args=(Arg(span=span(), name=None, value=StringLit(span=span(), value="Classify")),),
        ),
    )
    ctx = CtxBlock(
        span=span(),
        budget=_budget("budget", "tokens", 3000, "3000 tokens"),
        body=(let, ReturnStmt(span=span(), value=_ident("intent"))),
    )
    fn = FnDecl(
        span=span(),
        name="classify",
        params=(),
        return_type=_type("probable", generics=(_type("string"),)),
        body=(ctx,),
    )

    result = generate_python(program(fn))
    source = result.source

    assert "_intent_value = await ctx.ask('Classify', return_type=str)" in source
    assert "intent: ProbableValue = ProbableValue(" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_within_fallback_uses_run_with_budget_and_budget_exception():
    primary = (ReturnStmt(span=span(), value=StringLit(span=span(), value="primary")),)
    fallback = (ReturnStmt(span=span(), value=StringLit(span=span(), value="fallback")),)
    within = WithinFallback(
        span=span(),
        budget_args=(
            _budget("tokens", "tokens", 5000),
            _budget("latency", "s", 10, "10s"),
        ),
        primary=primary,
        fallback=fallback,
    )
    fn = FnDecl(
        span=span(),
        name="run",
        params=(),
        return_type=_type("string"),
        body=(within,),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "from voss_runtime import" in source
    assert "run_with_budget" in source
    assert "BudgetExceededError" in source
    assert "async def _within_primary_" in source
    assert (
        "return await run_with_budget(_within_primary_(), token_limit=5000, latency_ms=10000)"
        in source
    )
    assert "except BudgetExceededError:" in source
    assert "return 'fallback'" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_try_catch_lowers_to_python_try_except():
    try_stmt = TryCatch(
        span=span(),
        try_body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="ok")),),
        exc_name="err",
        catch_body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="bad")),),
    )
    fn = FnDecl(
        span=span(),
        name="run",
        params=(),
        return_type=_type("string"),
        body=(try_stmt,),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "try:" in source
    assert "except Exception as err:" in source
    assert "return 'ok'" in source
    assert "return 'bad'" in source
    assert_python_parses(source)


def test_try_catch_without_name_omits_as_clause():
    try_stmt = TryCatch(
        span=span(),
        try_body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="ok")),),
        exc_name=None,
        catch_body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="bad")),),
    )
    fn = FnDecl(
        span=span(),
        name="run",
        params=(),
        return_type=_type("string"),
        body=(try_stmt,),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "except Exception:" in source
    assert "except Exception as None" not in source
    assert_python_parses(source)


def test_memory_declarations_instantiate_runtime_classes():
    episodic = LetStmt(
        span=span(),
        name="history",
        type_annot=_type(
            "memory",
            "episodic",
            kwargs=(
                TypeKwarg(
                    span=span(),
                    name="capacity",
                    value=_budget("capacity", "turns", 20, "20 turns"),
                ),
            ),
        ),
        value=None,
    )
    semantic = LetStmt(
        span=span(),
        name="knowledge",
        type_annot=_type(
            "memory",
            "semantic",
            kwargs=(
                TypeKwarg(
                    span=span(),
                    name="source",
                    value=StringLit(span=span(), value="./docs/"),
                ),
                TypeKwarg(
                    span=span(),
                    name="model",
                    value=StringLit(span=span(), value="text-embedding-3-small"),
                ),
            ),
        ),
        value=None,
    )
    working = LetStmt(
        span=span(),
        name="notes",
        type_annot=_type("memory", "working"),
        value=None,
    )
    fn = FnDecl(
        span=span(),
        name="setup",
        params=(),
        return_type=None,
        body=(episodic, semantic, working),
    )
    result = generate_python(program(fn))
    source = result.source
    assert "history = EpisodicMemory(capacity=20)" in source
    assert (
        "knowledge = SemanticMemory(source='./docs/', model='text-embedding-3-small')"
        in source
    )
    assert "notes = WorkingMemory()" in source
    assert "from voss_runtime import" in source
    assert "EpisodicMemory" in source
    assert "SemanticMemory" in source
    assert "WorkingMemory" in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)
