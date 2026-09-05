from __future__ import annotations


from voss.codegen import PythonWriter, generate_python

from tests.codegen.conftest import assert_python_parses, program


def test_writer_indents_with_four_spaces_and_final_newline():
    writer = PythonWriter()
    writer.write("def main():")
    with writer.indent():
        writer.write("x = 1")
        with writer.indent():
            writer.write("y = 2")
    rendered = writer.render()
    assert "def main():\n    x = 1\n        y = 2\n" == rendered
    assert rendered.endswith("\n")
    assert not rendered.endswith("\n\n")


def test_writer_blank_lines_are_stable():
    writer = PythonWriter()
    writer.write("a = 1")
    writer.blank()
    writer.blank()
    writer.blank()
    writer.write("b = 2")
    rendered = writer.render()
    # Multiple blank() calls collapse to a single blank line between content.
    assert rendered == "a = 1\n\nb = 2\n"


def test_generated_empty_program_is_parseable_python():
    result = generate_python(program())
    assert isinstance(result.source, str)
    assert result.source.endswith("\n")
    assert_python_parses(result.source)
