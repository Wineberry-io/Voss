from voss.ast_nodes import (
    FnDecl, AgentDecl, TypeRef, ReturnStmt, LetStmt,
    ListLit, SpawnExpr, StringLit,
)

def test_fn_simple(parse_source):
    p = parse_source("fn f() { return 1 }")
    f = p.body[0]
    assert isinstance(f, FnDecl)
    assert f.name == "f"
    assert f.params == ()
    assert f.return_type is None
    assert isinstance(f.body[0], ReturnStmt)

def test_fn_typed(parse_source):
    src = """
fn classify(text: string) -> probable<string> {
  return ask("classify: " + text)
}
"""
    p = parse_source(src)
    f = p.body[0]
    assert isinstance(f, FnDecl)
    assert f.params[0].name == "text"
    assert isinstance(f.params[0].type_annot, TypeRef)
    assert f.return_type.name.parts == ("probable",)

def test_fn_with_default_param(parse_source):
    p = parse_source("fn g(x: int = 5) { return x }")
    f = p.body[0]
    assert f.params[0].default is not None

def test_agent_with_options_and_body(parse_source):
    src = """
agent Researcher(topic: string) -> Report {
  system: "You research topics."
  tools: [search, summarize]
  model: "claude-sonnet-4-5"
  let findings = search(topic)
  return findings
}
"""
    p = parse_source(src)
    a = p.body[0]
    assert isinstance(a, AgentDecl)
    assert a.name == "Researcher"
    assert isinstance(a.options.system, StringLit)
    assert a.options.system.value == "You research topics."
    assert isinstance(a.options.tools, ListLit)
    assert len(a.options.tools.items) == 2
    assert isinstance(a.options.model, StringLit)
    assert len(a.body) == 2
    assert isinstance(a.body[0], LetStmt)
    assert isinstance(a.body[1], ReturnStmt)

def test_agent_options_in_any_order(parse_source):
    src = """
agent A() {
  model: "x"
  system: "y"
  return 1
}
"""
    p = parse_source(src)
    a = p.body[0]
    assert a.options.model.value == "x"
    assert a.options.system.value == "y"

def test_agent_with_spawn_and_gather(parse_source):
    src = """
agent Lead(topics: list<string>) -> string {
  system: "Coordinate."
  let handles = topics.map(t => spawn Researcher(t))
  let reports = gather(handles, timeout: 30s)
  return reports.join(",")
}
"""
    p = parse_source(src)
    a = p.body[0]
    assert isinstance(a, AgentDecl)
    let_handles = a.body[0]
    assert isinstance(let_handles, LetStmt)
    # The map's lambda body is a SpawnExpr.
    map_call = let_handles.value
    lam = map_call.args[0].value
    assert isinstance(lam.body, SpawnExpr)
