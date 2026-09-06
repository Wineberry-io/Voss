from voss.ast_nodes import PromptDecl, ClassDecl, QualName, TypeRef

def test_prompt_simple(parse_source):
    src = '''
prompt Sup {
  "You are a helpful agent."
}
'''
    p = parse_source(src)
    d = p.body[0]
    assert isinstance(d, PromptDecl)
    assert d.name == "Sup"
    assert d.extends is None
    assert len(d.body) == 1
    assert d.body[0].value == "You are a helpful agent."

def test_prompt_extends(parse_source):
    src = '''
prompt SupportAgent extends BasePrompt {
  "You handle returns."
  "Be concise."
}
'''
    p = parse_source(src)
    d = p.body[0]
    assert isinstance(d, PromptDecl)
    assert isinstance(d.extends, QualName)
    assert d.extends.parts == ("BasePrompt",)
    assert len(d.body) == 2

def test_prompt_triple_string(parse_source):
    src = '''
prompt P {
  """multi
line body"""
}
'''
    p = parse_source(src)
    d = p.body[0]
    assert d.body[0].triple is True
    assert "multi" in d.body[0].value

def test_class_basic(parse_source):
    src = """
class Report {
  content: string
  tags: list<string>
}
"""
    p = parse_source(src)
    c = p.body[0]
    assert isinstance(c, ClassDecl)
    assert c.name == "Report"
    assert len(c.fields) == 2
    assert c.fields[0].name == "content"
    assert isinstance(c.fields[0].type_annot, TypeRef)
    assert c.fields[1].type_annot.name.parts == ("list",)

def test_class_field_with_default(parse_source):
    src = """
class C {
  count: int = 0
}
"""
    p = parse_source(src)
    c = p.body[0]
    assert c.fields[0].default is not None
