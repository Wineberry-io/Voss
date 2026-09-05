from __future__ import annotations

from typing import Any, Callable

from .ast_nodes import (
    AgentDecl,
    AgentOptions,
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
    Expr,
    ExprPattern,
    ExprStmt,
    FloatLit,
    FnDecl,
    Identifier,
    IfStmt,
    IncludeStmt,
    Index,
    IntLit,
    Lambda,
    LetStmt,
    ListLit,
    MatchCase,
    MatchStmt,
    Member,
    Node,
    NullLit,
    Param,
    Pattern,
    Program,
    PromptDecl,
    QualName,
    ReturnStmt,
    SimilarPattern,
    SpawnExpr,
    Stmt,
    StringLit,
    TryCatch,
    TypeExpr,
    TypeKwarg,
    TypeRef,
    UnaryOp,
    UseStmt,
    WildcardPattern,
    WithinFallback,
    YieldStmt,
)
from .ast_nodes import Span


def program_from_dict(data: dict[str, Any]) -> Program:
    """Rebuild a frozen AST `Program` from dict/JSON emitted by `voss.ast_serializer.to_dict`.

    Validates shapes and raises ``ValueError`` with a JSON-ish path suffix for pinpointing failures.
    """
    if not isinstance(data, dict):
        raise ValueError(f"program_from_dict expects dict, got {type(data).__name__} ($)")
    node = _deserialize_node(data, path="$")
    if not isinstance(node, Program):
        raise ValueError(f"expected root Program, got {type(node).__name__} ($)")
    return node


def _ctx(msg: str, path: str) -> str:
    return f"{msg} ({path})"


def _require_keys(obj: dict[str, Any], path: str, *keys: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(_ctx(f"object missing keys {missing!r}, has {sorted(obj)!r}", path))


def _expect_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(_ctx(f"expected JSON array, got {type(value).__name__}", path))
    return value


def _parse_span(raw: Any, path: str) -> Span:
    d = raw
    if not isinstance(d, dict):
        raise ValueError(_ctx("span must be an object", path))
    _require_keys(d, path, "file", "lines", "cols", "synthetic")
    lines = d["lines"]
    cols = d["cols"]
    if not isinstance(lines, list) or len(lines) != 2:
        raise ValueError(_ctx("'lines' must be [start, end]", path + ".lines"))
    if not isinstance(cols, list) or len(cols) != 2:
        raise ValueError(_ctx("'cols' must be [start, end]", path + ".cols"))
    try:
        ls, le = int(lines[0]), int(lines[1])
        cs, ce = int(cols[0]), int(cols[1])
    except (TypeError, ValueError) as e:
        raise ValueError(_ctx(f"non-integer span coordinates: {lines!r} / {cols!r}: {e}", path)) from e
    fi = d["file"]
    if not isinstance(fi, str):
        raise ValueError(_ctx("'file' must be str", path + ".file"))
    syn_raw = d["synthetic"]
    if syn_raw is None:
        raise ValueError(_ctx("'synthetic' must be present (bool)", path + ".synthetic"))
    return Span(file=fi, line_start=ls, col_start=cs, line_end=le, col_end=ce, synthetic=bool(syn_raw))


def _is_span_bucket(d: dict[str, Any]) -> bool:
    return (
        "_node" not in d
        and "file" in d
        and "lines" in d
        and "cols" in d
        and "synthetic" in d
    )


def _deserialize_node(data: dict[str, Any], path: str) -> Node:
    if "_node" not in data and _is_span_bucket(data):
        raise ValueError(_ctx("span object must not appear where a Node is required", path))
    kind = data.get("_node")
    if kind is None:
        raise ValueError(_ctx("missing '_node' discriminator", path))
    if not isinstance(kind, str):
        raise ValueError(_ctx(f"_node must be str, got {type(kind).__name__}", path + "._node"))
    fn = _DISPATCH.get(kind)
    if fn is None:
        raise ValueError(_ctx(f"unknown AST node type {_node_repr(kind)}", path))
    _require_keys(data, path, "span")
    span = _parse_span(data["span"], path + ".span")
    return fn(span, data, base_path=path)


def _node_repr(kind: str) -> str:
    try:
        return repr(kind)
    except Exception:
        return "<unprintable _node>"


def _deserialize_subnode(val: Any, path: str) -> Node:
    if not isinstance(val, dict):
        raise ValueError(_ctx("expected node object (dict)", path))
    node = _deserialize_node(val, path)
    return node


def _stmt_tuple(raw: Any, path: str) -> tuple[Stmt, ...]:
    lst = _expect_list(raw, path)
    out: list[Stmt] = []
    for i, item in enumerate(lst):
        stmt = _deserialize_subnode(item, f"{path}[{i}]")
        if not isinstance(stmt, Stmt):
            raise ValueError(_ctx(f"expected Stmt, got {type(stmt).__name__}", f"{path}[{i}]"))
        out.append(stmt)
    return tuple(out)


def _expr_tuple(lst_raw: Any, path: str) -> tuple[Expr, ...]:
    lst = _expect_list(lst_raw, path)
    out: list[Expr] = []
    for i, item in enumerate(lst):
        ex = _deserialize_subnode(item, f"{path}[{i}]")
        if not isinstance(ex, Expr):
            raise ValueError(_ctx(f"expected Expr, got {type(ex).__name__}", f"{path}[{i}]"))
        out.append(ex)
    return tuple(out)


def _param_tuple(lst_raw: Any, path: str) -> tuple[Param, ...]:
    lst = _expect_list(lst_raw, path)
    out: list[Param] = []
    for i, item in enumerate(lst):
        node = _deserialize_subnode(item, f"{path}[{i}]")
        if not isinstance(node, Param):
            raise ValueError(_ctx(f"expected Param, got {type(node).__name__}", f"{path}[{i}]"))
        out.append(node)
    return tuple(out)


def _arg_tuple(lst_raw: Any, path: str) -> tuple[Arg, ...]:
    lst = _expect_list(lst_raw, path)
    out: list[Arg] = []
    for i, item in enumerate(lst):
        node = _deserialize_subnode(item, f"{path}[{i}]")
        if not isinstance(node, Arg):
            raise ValueError(_ctx(f"expected Arg, got {type(node).__name__}", f"{path}[{i}]"))
        out.append(node)
    return tuple(out)


def _decorators_tuple(lst_raw: Any | None, path: str) -> tuple[Decorator, ...]:
    lst = lst_raw if lst_raw is not None else []
    lst_l = _expect_list(lst, path)
    ds: list[Decorator] = []
    for i, item in enumerate(lst_l):
        d = _deserialize_subnode(item, f"{path}[{i}]")
        if not isinstance(d, Decorator):
            raise ValueError(_ctx(f"expected Decorator, got {type(d).__name__}", f"{path}[{i}]"))
        ds.append(d)
    return tuple(ds)


# ---- per-node constructors: (span, full dict, *, base_path=str) -> Node

def _b_program(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "body")
    return Program(span=span, body=_stmt_tuple(data["body"], base_path + ".body"))


def _b_int(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "value")
    if not isinstance(data["value"], int):
        raise ValueError(_ctx("IntLit.value must be JSON integer", base_path + ".value"))
    return IntLit(span=span, value=data["value"])


def _b_float(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "value")
    v = data["value"]
    if not isinstance(v, (int, float)):
        raise ValueError(_ctx("FloatLit.value must be JSON number", base_path + ".value"))
    return FloatLit(span=span, value=float(v))


def _b_string(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "value", "triple")
    v, t = data["value"], data["triple"]
    if not isinstance(v, str):
        raise ValueError(_ctx("StringLit.value must be str", base_path + ".value"))
    if t is None:
        raise ValueError(_ctx("StringLit.triple must be present (bool)", base_path + ".triple"))
    return StringLit(span=span, value=v, triple=bool(t))


def _b_bool(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "value")
    v = data["value"]
    if not isinstance(v, bool):
        raise ValueError(_ctx("BoolLit.value must be bool", base_path + ".value"))
    return BoolLit(span=span, value=v)


def _b_null(span: Span, data: dict[str, Any], *, base_path: str) -> Node:  # noqa: ARG002
    return NullLit(span=span)


def _b_ident(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name")
    n = data["name"]
    if not isinstance(n, str):
        raise ValueError(_ctx("Identifier.name must be str", base_path + ".name"))
    return Identifier(span=span, name=n)


def _b_budget(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "unit", "value", "raw")
    name, unit, raw = data["name"], data["unit"], data["raw"]
    if not isinstance(name, str) or not isinstance(unit, str) or not isinstance(raw, str):
        raise ValueError(_ctx("BudgetArg name/unit/raw must be str", base_path))
    val = data["value"]
    if not isinstance(val, (int, float)):
        raise ValueError(_ctx("BudgetArg.value must be number", base_path + ".value"))
    return BudgetArg(span=span, name=name, unit=unit, value=val, raw=raw)


def _b_expr_stmt(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "expr")
    ex = _deserialize_subnode(data["expr"], base_path + ".expr")
    if not isinstance(ex, Expr):
        raise ValueError(_ctx("ExprStmt.expr must be Expr", base_path + ".expr"))
    return ExprStmt(span=span, expr=ex)


def _b_qual(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "parts")
    parts_raw = data["parts"]
    pl = _expect_list(parts_raw, base_path + ".parts")
    ps: list[str] = []
    for i, p in enumerate(pl):
        if not isinstance(p, str):
            raise ValueError(_ctx(f"QualName.parts[{i}] must be str", base_path + f".parts[{i}]"))
        ps.append(p)
    return QualName(span=span, parts=tuple(ps))


_TYPE_KW_VALUE = (IntLit, FloatLit, StringLit, BoolLit, NullLit, BudgetArg, QualName)


def _b_type_kwarg(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "value")
    nk = data["name"]
    if not isinstance(nk, str):
        raise ValueError(_ctx("TypeKwarg.name must be str", base_path + ".name"))
    val = _deserialize_subnode(data["value"], base_path + ".value")
    if not isinstance(val, _TYPE_KW_VALUE):
        raise ValueError(
            _ctx(
                "TypeKwarg.value must be literal / BudgetArg / QualName,"
                f" got {type(val).__name__}",
                base_path + ".value",
            ),
        )
    return TypeKwarg(span=span, name=nk, value=val)


def _b_type_ref(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "generics", "kwargs")
    qn = _deserialize_subnode(data["name"], base_path + ".name")
    if not isinstance(qn, QualName):
        raise ValueError(_ctx("TypeRef.name must deserialize to QualName", base_path + ".name"))
    gens = _expect_list(data["generics"], base_path + ".generics")
    te_list: list[TypeExpr] = []
    for i, g_item in enumerate(gens):
        t = _deserialize_subnode(g_item, f"{base_path}.generics[{i}]")
        if not isinstance(t, TypeExpr):
            raise ValueError(_ctx(f"generics[{i}] must be TypeExpr", base_path + f".generics[{i}]"))
        te_list.append(t)
    ks = _expect_list(data["kwargs"], base_path + ".kwargs")
    kws = []
    for i, kv in enumerate(ks):
        t = _deserialize_subnode(kv, f"{base_path}.kwargs[{i}]")
        if not isinstance(t, TypeKwarg):
            raise ValueError(_ctx(f"kwargs[{i}] must be TypeKwarg", base_path + f".kwargs[{i}]"))
        kws.append(t)
    return TypeRef(span=span, name=qn, generics=tuple(te_list), kwargs=tuple(kws))


def _b_arg(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "value")
    nm = data["name"]
    if nm is not None and not isinstance(nm, str):
        raise ValueError(_ctx("Arg.name must be str or null", base_path + ".name"))
    v = _deserialize_subnode(data["value"], base_path + ".value")
    # Parser may attach `BudgetArg` to `Arg.value` even though the field is annotated `Expr`.
    if not isinstance(v, (Expr, BudgetArg)):
        raise ValueError(_ctx("Arg.value must be Expr or BudgetArg", base_path + ".value"))
    return Arg(span=span, name=nm, value=v)  # type: ignore[arg-type]


def _b_bin(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "op", "left", "right")
    op = data["op"]
    if not isinstance(op, str):
        raise ValueError(_ctx("BinOp.op must be str", base_path + ".op"))
    L = _deserialize_subnode(data["left"], base_path + ".left")
    R = _deserialize_subnode(data["right"], base_path + ".right")
    if not isinstance(L, Expr) or not isinstance(R, Expr):
        raise ValueError(_ctx("BinOp.left/right must be Expr", base_path))
    return BinOp(span=span, op=op, left=L, right=R)


def _b_unary(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "op", "operand")
    op = data["op"]
    if not isinstance(op, str):
        raise ValueError(_ctx("UnaryOp.op must be str", base_path + ".op"))
    o = _deserialize_subnode(data["operand"], base_path + ".operand")
    if not isinstance(o, Expr):
        raise ValueError(_ctx("UnaryOp.operand must be Expr", base_path + ".operand"))
    return UnaryOp(span=span, op=op, operand=o)


def _b_call(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "callee", "args")
    cal = _deserialize_subnode(data["callee"], base_path + ".callee")
    if not isinstance(cal, Expr):
        raise ValueError(_ctx("Call.callee must be Expr", base_path + ".callee"))
    return Call(span=span, callee=cal, args=_arg_tuple(data["args"], base_path + ".args"))


def _b_member(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "obj", "attr")
    o = _deserialize_subnode(data["obj"], base_path + ".obj")
    if not isinstance(o, Expr):
        raise ValueError(_ctx("Member.obj must be Expr", base_path + ".obj"))
    attr = data["attr"]
    if not isinstance(attr, str):
        raise ValueError(_ctx("Member.attr must be str", base_path + ".attr"))
    return Member(span=span, obj=o, attr=attr)


def _b_index(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "obj", "index")
    o = _deserialize_subnode(data["obj"], base_path + ".obj")
    idx = _deserialize_subnode(data["index"], base_path + ".index")
    if not isinstance(o, Expr) or not isinstance(idx, Expr):
        raise ValueError(_ctx("Index obj/index must be Expr", base_path))
    return Index(span=span, obj=o, index=idx)


def _b_list(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "items")
    return ListLit(span=span, items=_expr_tuple(data["items"], base_path + ".items"))


def _b_dict(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "items")
    lst = _expect_list(data["items"], base_path + ".items")
    pairs: list[tuple[Expr, Expr]] = []
    for i, pair in enumerate(lst):
        pv = _expect_list(pair, f"{base_path}.items[{i}]")
        if len(pv) != 2:
            raise ValueError(_ctx("each dict entry must be [key,value]", base_path + f".items[{i}]"))
        k = _deserialize_subnode(pv[0], f"{base_path}.items[{i}][0]")
        vv = _deserialize_subnode(pv[1], f"{base_path}.items[{i}][1]")
        if not isinstance(k, Expr) or not isinstance(vv, Expr):
            raise ValueError(_ctx("dict kv must be Expr", base_path + f".items[{i}]"))
        pairs.append((k, vv))
    return DictLit(span=span, items=tuple(pairs))


def _b_param(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name")
    n = data["name"]
    if not isinstance(n, str):
        raise ValueError(_ctx("Param.name must be str", base_path + ".name"))
    ta = None
    if data.get("type_annot") is not None:
        t_node = _deserialize_subnode(data["type_annot"], base_path + ".type_annot")
        if not isinstance(t_node, TypeExpr):
            raise ValueError(_ctx("Param.type_annot must be TypeExpr", base_path + ".type_annot"))
        ta = t_node
    dflt = None
    if data.get("default") is not None:
        d_node = _deserialize_subnode(data["default"], base_path + ".default")
        if not isinstance(d_node, Expr):
            raise ValueError(_ctx("Param.default must be Expr", base_path + ".default"))
        dflt = d_node
    return Param(span=span, name=n, type_annot=ta, default=dflt)


def _b_lambda(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "params", "body")
    params = _param_tuple(data["params"], base_path + ".params")
    body = _deserialize_subnode(data["body"], base_path + ".body")
    if not isinstance(body, Expr):
        raise ValueError(_ctx("Lambda.body must be Expr", base_path + ".body"))
    return Lambda(span=span, params=params, body=body)


def _b_spawn(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "agent")
    ag = _deserialize_subnode(data["agent"], base_path + ".agent")
    if not isinstance(ag, Call):
        raise ValueError(_ctx(f"SpawnExpr.agent must be Call, got {type(ag).__name__}", base_path + ".agent"))
    return SpawnExpr(span=span, agent=ag)


def _b_conf(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "target", "op", "threshold")
    t = _deserialize_subnode(data["target"], base_path + ".target")
    if not isinstance(t, Expr):
        raise ValueError(_ctx("ConfidenceGate.target must be Expr", base_path + ".target"))
    op = data["op"]
    if not isinstance(op, str):
        raise ValueError(_ctx("ConfidenceGate.op must be str", base_path + ".op"))
    th = data["threshold"]
    if not isinstance(th, (int, float)):
        raise ValueError(_ctx("ConfidenceGate.threshold must be number", base_path + ".threshold"))
    return ConfidenceGate(span=span, target=t, op=op, threshold=float(th))


def _b_similar_pat(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "text")
    tx = data["text"]
    if not isinstance(tx, str):
        raise ValueError(_ctx("SimilarPattern.text must be str", base_path + ".text"))
    return SimilarPattern(span=span, text=tx)


def _b_wild(span: Span, data: dict[str, Any], *, base_path: str) -> Node:  # noqa: ARG002
    return WildcardPattern(span=span)


def _b_expr_pat(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "expr")
    e = _deserialize_subnode(data["expr"], base_path + ".expr")
    if not isinstance(e, Expr):
        raise ValueError(_ctx("ExprPattern.expr must be Expr", base_path + ".expr"))
    return ExprPattern(span=span, expr=e)


def _b_let(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name")
    n = data["name"]
    if not isinstance(n, str):
        raise ValueError(_ctx("LetStmt.name must be str", base_path + ".name"))
    ta = None
    if data.get("type_annot") is not None:
        t_node = _deserialize_subnode(data["type_annot"], base_path + ".type_annot")
        if not isinstance(t_node, TypeExpr):
            raise ValueError(_ctx("LetStmt.type_annot must be TypeExpr", base_path + ".type_annot"))
        ta = t_node
    val = None
    if data.get("value") is not None:
        v_node = _deserialize_subnode(data["value"], base_path + ".value")
        if not isinstance(v_node, Expr):
            raise ValueError(_ctx("LetStmt.value must be Expr", base_path + ".value"))
        val = v_node
    return LetStmt(span=span, name=n, type_annot=ta, value=val)


def _b_if(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "condition", "then_body")
    cond_node = _deserialize_subnode(data["condition"], base_path + ".condition")
    if not isinstance(cond_node, Expr) and not isinstance(cond_node, ConfidenceGate):
        raise ValueError(
            _ctx(
                f"IfStmt.condition must be Expr or ConfidenceGate, got {type(cond_node).__name__}",
                base_path + ".condition",
            ),
        )
    then_b = _stmt_tuple(data["then_body"], base_path + ".then_body")
    eb = None
    if data.get("else_body") is not None:
        eb = _stmt_tuple(data["else_body"], base_path + ".else_body")
    return IfStmt(span=span, condition=cond_node, then_body=then_b, else_body=eb)


def _b_match_case(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "pattern", "body")
    pat = _deserialize_subnode(data["pattern"], base_path + ".pattern")
    if not isinstance(pat, Pattern):
        raise ValueError(_ctx("MatchCase.pattern must be Pattern", base_path + ".pattern"))
    return MatchCase(span=span, pattern=pat, body=_stmt_tuple(data["body"], base_path + ".body"))


def _b_match(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "scrutinee", "cases")
    sc = _deserialize_subnode(data["scrutinee"], base_path + ".scrutinee")
    if not isinstance(sc, Expr):
        raise ValueError(_ctx("MatchStmt.scrutinee must be Expr", base_path + ".scrutinee"))
    cl = _expect_list(data["cases"], base_path + ".cases")
    cases_list: list[MatchCase] = []
    for i, c_raw in enumerate(cl):
        c = _deserialize_subnode(c_raw, f"{base_path}.cases[{i}]")
        if not isinstance(c, MatchCase):
            raise ValueError(_ctx(f"cases[{i}] must be MatchCase", base_path + f".cases[{i}]"))
        cases_list.append(c)
    thresh = None
    if data.get("threshold") is not None:
        tp = data["threshold"]
        if not isinstance(tp, (int, float)):
            raise ValueError(_ctx("MatchStmt.threshold must be number", base_path + ".threshold"))
        thresh = float(tp)
    return MatchStmt(span=span, scrutinee=sc, cases=tuple(cases_list), threshold=thresh)


def _b_ctx(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "budget", "body")
    bd = _deserialize_subnode(data["budget"], base_path + ".budget")
    if not isinstance(bd, BudgetArg):
        raise ValueError(_ctx("CtxBlock.budget must be BudgetArg", base_path + ".budget"))
    return CtxBlock(span=span, budget=bd, body=_stmt_tuple(data["body"], base_path + ".body"))


def _b_within(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "budget_args", "primary")
    bl = _expect_list(data["budget_args"], base_path + ".budget_args")
    buddies: list[BudgetArg] = []
    for i, b_raw in enumerate(bl):
        b = _deserialize_subnode(b_raw, f"{base_path}.budget_args[{i}]")
        if not isinstance(b, BudgetArg):
            raise ValueError(_ctx(f"budget_args[{i}] must be BudgetArg", base_path + f".budget_args[{i}]"))
        buddies.append(b)
    primary = _stmt_tuple(data["primary"], base_path + ".primary")
    fb = None
    if data.get("fallback") is not None:
        fb = _stmt_tuple(data["fallback"], base_path + ".fallback")
    return WithinFallback(
        span=span,
        budget_args=tuple(buddies),
        primary=primary,
        fallback=fb,
    )


def _b_try(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "try_body", "exc_name", "catch_body")
    exc = data["exc_name"]
    if exc is not None and not isinstance(exc, str):
        raise ValueError(_ctx("TryCatch.exc_name must be str or null", base_path + ".exc_name"))
    return TryCatch(
        span=span,
        try_body=_stmt_tuple(data["try_body"], base_path + ".try_body"),
        exc_name=exc,
        catch_body=_stmt_tuple(data["catch_body"], base_path + ".catch_body"),
    )


def _b_ret(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    val = None
    if data.get("value") is not None:
        v_node = _deserialize_subnode(data["value"], base_path + ".value")
        if not isinstance(v_node, Expr):
            raise ValueError(_ctx("ReturnStmt.value must be Expr", base_path + ".value"))
        val = v_node
    return ReturnStmt(span=span, value=val)


def _b_yield(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    val = None
    if data.get("value") is not None:
        v_node = _deserialize_subnode(data["value"], base_path + ".value")
        if not isinstance(v_node, Expr):
            raise ValueError(_ctx("YieldStmt.value must be Expr", base_path + ".value"))
        val = v_node
    return YieldStmt(span=span, value=val)


def _b_include(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "value")
    v_node = _deserialize_subnode(data["value"], base_path + ".value")
    if not isinstance(v_node, Expr):
        raise ValueError(_ctx("IncludeStmt.value must be Expr", base_path + ".value"))
    return IncludeStmt(span=span, value=v_node)


def _b_decor(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "args")
    nm = data["name"]
    if not isinstance(nm, str):
        raise ValueError(_ctx("Decorator.name must be str", base_path + ".name"))
    return Decorator(span=span, name=nm, args=_arg_tuple(data["args"], base_path + ".args"))


def _b_agent_opts(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    def gx(name: str) -> Expr | None:
        r = data.get(name)
        if r is None:
            return None
        n = _deserialize_subnode(r, base_path + f".{name}")
        if not isinstance(n, Expr):
            raise ValueError(_ctx(f"AgentOptions.{name} expects Expr-compatible node", base_path + f".{name}"))
        return n

    tools = None
    if data.get("tools") is not None:
        tnode = _deserialize_subnode(data["tools"], base_path + ".tools")
        if not isinstance(tnode, ListLit):
            raise ValueError(_ctx("AgentOptions.tools must be ListLit or null", base_path + ".tools"))
        tools = tnode
    sys_e = gx("system")
    mod_e = gx("model")
    ret_e = gx("retries")
    mem_e = gx("memory")
    return AgentOptions(span=span, system=sys_e, tools=tools, model=mod_e, retries=ret_e, memory=mem_e)


def _b_fn(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "params", "body", "decorators")
    nm = data["name"]
    if not isinstance(nm, str):
        raise ValueError(_ctx("FnDecl.name must be str", base_path + ".name"))
    rt = None
    if data.get("return_type") is not None:
        rnode = _deserialize_subnode(data["return_type"], base_path + ".return_type")
        if not isinstance(rnode, TypeExpr):
            raise ValueError(_ctx("FnDecl.return_type must be TypeExpr", base_path + ".return_type"))
        rt = rnode
    return FnDecl(
        span=span,
        name=nm,
        params=_param_tuple(data["params"], base_path + ".params"),
        return_type=rt,
        body=_stmt_tuple(data["body"], base_path + ".body"),
        decorators=_decorators_tuple(data["decorators"], base_path + ".decorators"),
    )


def _b_agent(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "params", "options", "body", "decorators")
    nm = data["name"]
    if not isinstance(nm, str):
        raise ValueError(_ctx("AgentDecl.name must be str", base_path + ".name"))
    opts = _deserialize_subnode(data["options"], base_path + ".options")
    if not isinstance(opts, AgentOptions):
        raise ValueError(_ctx("AgentDecl.options must be AgentOptions", base_path + ".options"))
    rt = None
    if data.get("return_type") is not None:
        rnode = _deserialize_subnode(data["return_type"], base_path + ".return_type")
        if not isinstance(rnode, TypeExpr):
            raise ValueError(_ctx("AgentDecl.return_type must be TypeExpr", base_path + ".return_type"))
        rt = rnode
    return AgentDecl(
        span=span,
        name=nm,
        params=_param_tuple(data["params"], base_path + ".params"),
        return_type=rt,
        options=opts,
        body=_stmt_tuple(data["body"], base_path + ".body"),
        decorators=_decorators_tuple(data["decorators"], base_path + ".decorators"),
    )


def _b_prompt(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "body", "decorators")
    nm = data["name"]
    if not isinstance(nm, str):
        raise ValueError(_ctx("PromptDecl.name must be str", base_path + ".name"))
    ext = None
    if data.get("extends") is not None:
        en = _deserialize_subnode(data["extends"], base_path + ".extends")
        if not isinstance(en, QualName):
            raise ValueError(_ctx("PromptDecl.extends must be QualName", base_path + ".extends"))
        ext = en
    sl = _expect_list(data["body"], base_path + ".body")
    strs = []
    for i, lit_raw in enumerate(sl):
        lt = _deserialize_subnode(lit_raw, base_path + f".body[{i}]")
        if not isinstance(lt, StringLit):
            raise ValueError(_ctx(f"prompt body[{i}] must be StringLit", base_path + f".body[{i}]"))
        strs.append(lt)
    return PromptDecl(
        span=span,
        name=nm,
        extends=ext,
        body=tuple(strs),
        decorators=_decorators_tuple(data["decorators"], base_path + ".decorators"),
    )


def _b_field(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "type_annot")
    nm = data["name"]
    if not isinstance(nm, str):
        raise ValueError(_ctx("ClassField.name must be str", base_path + ".name"))
    te = _deserialize_subnode(data["type_annot"], base_path + ".type_annot")
    if not isinstance(te, TypeExpr):
        raise ValueError(_ctx("ClassField.type_annot must be TypeExpr", base_path))
    df = None
    if data.get("default") is not None:
        dnode = _deserialize_subnode(data["default"], base_path + ".default")
        if not isinstance(dnode, Expr):
            raise ValueError(_ctx("ClassField.default must be Expr", base_path))
        df = dnode
    return ClassField(span=span, name=nm, type_annot=te, default=df)


def _b_class(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "name", "fields", "decorators")
    nm = data["name"]
    if not isinstance(nm, str):
        raise ValueError(_ctx("ClassDecl.name must be str", base_path + ".name"))
    fl_raw = _expect_list(data["fields"], base_path + ".fields")
    fields_: list[ClassField] = []
    for i, fr in enumerate(fl_raw):
        fnode = _deserialize_subnode(fr, f"{base_path}.fields[{i}]")
        if not isinstance(fnode, ClassField):
            raise ValueError(_ctx(f"fields[{i}] must be ClassField", base_path + f".fields[{i}]"))
        fields_.append(fnode)
    return ClassDecl(
        span=span,
        name=nm,
        fields=tuple(fields_),
        decorators=_decorators_tuple(data["decorators"], base_path + ".decorators"),
    )


def _b_use(span: Span, data: dict[str, Any], *, base_path: str) -> Node:
    _require_keys(data, base_path, "path", "alias")
    pr = data["path"]
    pl = _expect_list(pr, base_path + ".path")
    segs = []
    for i, seg in enumerate(pl):
        if not isinstance(seg, str):
            raise ValueError(_ctx(f"path[{i}] must be str", base_path + f".path[{i}]"))
        segs.append(seg)
    ali = data["alias"]
    if ali is not None and not isinstance(ali, str):
        raise ValueError(_ctx("UseStmt.alias must be str or null", base_path + ".alias"))
    return UseStmt(span=span, path=tuple(segs), alias=ali)


_DISPATCH: dict[str, Callable[..., Node]] = {
    "Program": _b_program,
    "IntLit": _b_int,
    "FloatLit": _b_float,
    "StringLit": _b_string,
    "BoolLit": _b_bool,
    "NullLit": _b_null,
    "Identifier": _b_ident,
    "BudgetArg": _b_budget,
    "ExprStmt": _b_expr_stmt,
    "QualName": _b_qual,
    "TypeKwarg": _b_type_kwarg,
    "TypeRef": _b_type_ref,
    "Arg": _b_arg,
    "BinOp": _b_bin,
    "UnaryOp": _b_unary,
    "Call": _b_call,
    "Member": _b_member,
    "Index": _b_index,
    "ListLit": _b_list,
    "DictLit": _b_dict,
    "Param": _b_param,
    "Lambda": _b_lambda,
    "SpawnExpr": _b_spawn,
    "ConfidenceGate": _b_conf,
    "SimilarPattern": _b_similar_pat,
    "WildcardPattern": _b_wild,
    "ExprPattern": _b_expr_pat,
    "LetStmt": _b_let,
    "IfStmt": _b_if,
    "MatchCase": _b_match_case,
    "MatchStmt": _b_match,
    "CtxBlock": _b_ctx,
    "WithinFallback": _b_within,
    "TryCatch": _b_try,
    "ReturnStmt": _b_ret,
    "YieldStmt": _b_yield,
    "IncludeStmt": _b_include,
    "Decorator": _b_decor,
    "FnDecl": _b_fn,
    "AgentOptions": _b_agent_opts,
    "AgentDecl": _b_agent,
    "PromptDecl": _b_prompt,
    "ClassField": _b_field,
    "ClassDecl": _b_class,
    "UseStmt": _b_use,
}
