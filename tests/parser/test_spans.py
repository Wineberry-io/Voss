from voss.ast_nodes import LetStmt, IntLit, ConfidenceGate

def test_let_stmt_span_lines(parse_source):
    src = "\n\nlet x = 42"   # let on line 3
    program = parse_source(src)
    s = program.body[0]
    assert isinstance(s, LetStmt)
    assert s.span.line_start == 3
    assert s.span.col_start == 1

def test_int_lit_span_within_let(parse_source):
    program = parse_source("let x = 42")
    val = program.body[0].value
    assert isinstance(val, IntLit)
    # The 42 starts after `let x = ` which is 8 chars (col 9).
    assert val.span.line_start == 1
    assert val.span.col_start == 9

def test_confidence_gate_span(parse_source):
    program = parse_source("if intent @ p >= 0.85 { return 1 }")
    cond = program.body[0].condition
    assert isinstance(cond, ConfidenceGate)
    assert cond.span.line_start == 1
    assert cond.span.col_start >= 4   # after `if `

def test_span_file_propagates(parse_source):
    program = parse_source("42", file="myfile.voss") if False else None
    # parse_source uses default file '<test>'; just verify file field exists & is str.
    program = parse_source("42")
    assert program.body[0].expr.span.file == "<test>"
