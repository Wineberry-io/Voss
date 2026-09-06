from voss.ast_nodes import UseStmt, FnDecl, ClassDecl

def test_use_simple(parse_source):
    p = parse_source("use foo::bar")
    u = p.body[0]
    assert isinstance(u, UseStmt)
    assert u.path == ("foo", "bar")
    assert u.alias is None

def test_use_deep(parse_source):
    p = parse_source("use a::b::c::d")
    assert p.body[0].path == ("a", "b", "c", "d")

def test_use_with_as_alias(parse_source):
    p = parse_source("use foo::bar as baz")
    u = p.body[0]
    assert isinstance(u, UseStmt)
    assert u.path == ("foo", "bar")
    assert u.alias == "baz"

def test_decorator_on_fn(parse_source):
    src = """
@tool
fn search(q: string) -> list<string> {
  return []
}
"""
    p = parse_source(src)
    fn = p.body[0]
    assert isinstance(fn, FnDecl)
    assert len(fn.decorators) == 1
    assert fn.decorators[0].name == "tool"
    assert fn.decorators[0].args == ()

def test_decorator_with_args(parse_source):
    src = """
@cache(ttl: 60)
fn f() { return 1 }
"""
    p = parse_source(src)
    fn = p.body[0]
    assert fn.decorators[0].name == "cache"
    assert fn.decorators[0].args[0].name == "ttl"

def test_stacked_decorators(parse_source):
    src = """
@tool
@cache(ttl: 60)
fn f() { return 1 }
"""
    p = parse_source(src)
    fn = p.body[0]
    assert [d.name for d in fn.decorators] == ["tool", "cache"]

def test_decorator_on_class(parse_source):
    src = """
@frozen
class R { content: string }
"""
    p = parse_source(src)
    c = p.body[0]
    assert isinstance(c, ClassDecl)
    assert c.decorators[0].name == "frozen"
