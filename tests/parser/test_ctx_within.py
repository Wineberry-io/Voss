from voss.ast_nodes import CtxBlock, WithinFallback

def test_ctx_basic(parse_source):
    src = """
ctx(budget: 4000 tokens) {
  include x
  return result
}
"""
    p = parse_source(src)
    c = p.body[0]
    assert isinstance(c, CtxBlock)
    assert c.budget.unit == "tokens" and c.budget.value == 4000
    assert c.budget.name == "budget"
    assert len(c.body) == 2

def test_within_with_fallback(parse_source):
    src = """
within budget(tokens: 4000, latency: 30s, cost: $0.02) {
  return primary()
} fallback {
  return cheap()
}
"""
    p = parse_source(src)
    w = p.body[0]
    assert isinstance(w, WithinFallback)
    assert len(w.budget_args) == 3
    assert {b.name for b in w.budget_args} == {"tokens", "latency", "cost"}
    assert w.fallback is not None and len(w.fallback) == 1

def test_within_no_fallback(parse_source):
    src = """
within budget(tokens: 100) {
  return one()
}
"""
    p = parse_source(src)
    w = p.body[0]
    assert isinstance(w, WithinFallback)
    assert w.fallback is None

def test_nested_ctx(parse_source):
    src = """
ctx(budget: 4000 tokens) {
  ctx(budget: 1000 tokens) {
    return inner()
  }
}
"""
    p = parse_source(src)
    outer = p.body[0]
    assert isinstance(outer, CtxBlock)
    assert isinstance(outer.body[0], CtxBlock)
