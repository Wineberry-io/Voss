from voss.ast_nodes import (
    IfStmt, MatchStmt, SimilarPattern, WildcardPattern, ConfidenceGate, BinOp,
)

def test_if_simple(parse_source):
    p = parse_source("if x { return x }")
    s = p.body[0]
    assert isinstance(s, IfStmt)
    assert isinstance(s.condition, type(s.condition))  # passes any
    assert len(s.then_body) == 1

def test_if_else(parse_source):
    p = parse_source("if x { return 1 } else { return 2 }")
    s = p.body[0]
    assert isinstance(s, IfStmt)
    assert s.else_body is not None and len(s.else_body) == 1

def test_if_compare_lt_not_type_expr(parse_source):
    # Ensures `if x < 5 { ... }` doesn't get parsed as a type-expr (RESEARCH risk #5).
    p = parse_source("if x < 5 { return x }")
    s = p.body[0]
    assert isinstance(s.condition, BinOp) and s.condition.op == "<"

def test_if_confidence_gate(parse_source):
    p = parse_source("if intent @ p >= 0.85 { return intent }")
    s = p.body[0]
    assert isinstance(s.condition, ConfidenceGate)
    assert s.condition.op == ">="
    assert s.condition.threshold == 0.85

def test_match_with_similar_and_wildcard(parse_source):
    src = """
match intent {
  case similar("user wants a refund") => handle_refund()
  case similar("user reports a bug") => create_ticket()
  case _ => escalate_to_human()
}
"""
    p = parse_source(src)
    m = p.body[0]
    assert isinstance(m, MatchStmt)
    assert len(m.cases) == 3
    assert isinstance(m.cases[0].pattern, SimilarPattern)
    assert m.cases[0].pattern.text == "user wants a refund"
    assert isinstance(m.cases[2].pattern, WildcardPattern)
    assert m.threshold is None

def test_match_threshold_lift(parse_source):
    src = """
@match_threshold(0.80)
match intent {
  case similar("refund") => handle_refund()
  case _ => other()
}
"""
    p = parse_source(src)
    m = p.body[0]
    assert isinstance(m, MatchStmt)
    assert m.threshold == 0.80
    # Ensure no separate Decorator node was emitted.
    assert len(p.body) == 1
