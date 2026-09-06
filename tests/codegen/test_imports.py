from __future__ import annotations

import builtins


from voss.ast_nodes import UseStmt
from voss.codegen import ImportCollector, generate_python
from voss.diagnostics import AnalysisResult

from tests.codegen.conftest import (
    assert_no_compiler_imports,
    assert_python_parses,
    program,
    span,
)


def _ok_analysis() -> AnalysisResult:
    return AnalysisResult(diagnostics=(), indexes=())


def test_import_collector_sorts_runtime_names():
    collector = ImportCollector()
    collector.add_runtime("ProbableValue")
    collector.add_runtime("ContextScope")
    lines, _meta = collector.render()
    assert "from voss_runtime import ContextScope, ProbableValue" in lines


def test_import_collector_keeps_asyncio_separate():
    collector = ImportCollector()
    collector.add_stdlib("asyncio")
    collector.add_runtime("ContextScope")
    lines, _meta = collector.render()
    assert "import asyncio" in lines
    assert "from voss_runtime import ContextScope" in lines
    # Stdlib import must come before runtime import.
    assert lines.index("import asyncio") < lines.index("from voss_runtime import ContextScope")


def test_import_collector_lowers_use_two_part_path():
    collector = ImportCollector()
    collector.add_use(("foo", "bar"))
    lines, _meta = collector.render()
    assert "from foo import bar" in lines


def test_import_collector_lowers_use_three_part_path():
    collector = ImportCollector()
    collector.add_use(("foo", "bar", "baz"))
    lines, _meta = collector.render()
    assert "from foo.bar import baz" in lines


def test_import_collector_supports_alias():
    collector = ImportCollector()
    collector.add_use(("foo", "bar"), alias="baz")
    lines, _meta = collector.render()
    assert "from foo import bar as baz" in lines


def test_generated_source_has_no_compiler_imports():
    use = UseStmt(span=span(), path=("foo", "bar"))
    result = generate_python(program(use))
    assert_no_compiler_imports(result.source)
    assert_python_parses(result.source)
    assert "from foo import bar" in result.source


def test_use_stmt_two_part_path_emits_from_import():
    use = UseStmt(span=span(), path=("foo", "bar"))
    result = generate_python(program(use), analysis=_ok_analysis())
    assert "from foo import bar" in result.source
    assert_python_parses(result.source)
    assert_no_compiler_imports(result.source)


def test_use_stmt_three_part_path_emits_module_from_import():
    use = UseStmt(span=span(), path=("foo", "bar", "baz"))
    result = generate_python(program(use), analysis=_ok_analysis())
    assert "from foo.bar import baz" in result.source
    assert_python_parses(result.source)


def test_use_stmt_alias_is_preserved_when_ast_provides_alias():
    use = UseStmt(span=span(), path=("foo", "bar"), alias="baz")
    result = generate_python(program(use), analysis=_ok_analysis())
    assert "from foo import bar as baz" in result.source
    assert_python_parses(result.source)


def test_use_stmt_does_not_import_target_during_codegen(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "foo" or name.startswith("foo."):
            raise ImportError(f"refused to import {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    use = UseStmt(span=span(), path=("foo", "bar"))
    result = generate_python(program(use), analysis=_ok_analysis())
    assert "from foo import bar" in result.source
