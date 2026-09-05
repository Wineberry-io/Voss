from __future__ import annotations

import json

from voss import analyze
from voss.analyzer import Analyzer
from voss.ast_nodes import (
    Identifier,
    MatchCase,
    MatchStmt,
    SimilarPattern,
    WildcardPattern,
)

from tests.analyzer.conftest import program, span


class FakeIndexBuilder:
    model = "fake-embedding-model"

    def build_cases(self, cases):
        return [
            {
                "label": label,
                "description": description,
                "embedding": [float(i), 0.0],
            }
            for i, (description, label) in enumerate(cases)
        ]


def similar_case(text: str, body_line: int = 1) -> MatchCase:
    return MatchCase(
        span=span(line=body_line),
        pattern=SimilarPattern(span=span(line=body_line), text=text),
        body=(),
    )


def make_match(line: int, col: int, *cases: MatchCase, threshold=None) -> MatchStmt:
    return MatchStmt(
        span=span(line=line, col=col),
        scrutinee=Identifier(span=span(line=line, col=col), name="input"),
        cases=cases,
        threshold=threshold,
    )


def test_single_match_emits_program_index(tmp_path):
    m = make_match(
        12,
        5,
        similar_case("billing question"),
        similar_case("password reset"),
    )
    result = analyze(
        program(m),
        source_path="support.voss",
        project_root=tmp_path,
        cache_dir=".voss-cache",
        index_builder=FakeIndexBuilder(),
    )
    assert result.ok
    target = tmp_path / ".voss-cache" / "support.idx"
    assert target.exists()
    data = json.loads(target.read_text())
    assert data["version"] == 1
    assert data["program"] == "support"
    assert data["model"] == "fake-embedding-model"
    assert len(data["matches"]) == 1
    entry = data["matches"][0]
    assert entry["match_id"] == "match_12_5"
    assert entry["threshold"] == 0.75
    assert len(entry["cases"]) == 2
    assert entry["cases"][0]["label"] == "case_0"
    assert entry["cases"][0]["description"] == "billing question"
    assert entry["cases"][1]["label"] == "case_1"
    assert result.indexes
    assert result.indexes[0].path.name == "support.idx"
    assert result.indexes[0].case_count == 2


def test_multiple_match_blocks_share_one_manifest(tmp_path):
    m1 = make_match(3, 1, similar_case("foo"))
    m2 = make_match(20, 5, similar_case("bar"), similar_case("baz"))
    analyze(
        program(m1, m2),
        source_path="prog.voss",
        project_root=tmp_path,
        cache_dir=".voss-cache",
        index_builder=FakeIndexBuilder(),
    )
    data = json.loads((tmp_path / ".voss-cache" / "prog.idx").read_text())
    assert len(data["matches"]) == 2
    ids = [m["match_id"] for m in data["matches"]]
    assert ids == ["match_3_1", "match_20_5"]


def test_match_threshold_is_preserved(tmp_path):
    m = make_match(7, 2, similar_case("x"), threshold=0.80)
    analyze(
        program(m),
        source_path="t.voss",
        project_root=tmp_path,
        cache_dir=".voss-cache",
        index_builder=FakeIndexBuilder(),
    )
    data = json.loads((tmp_path / ".voss-cache" / "t.idx").read_text())
    assert data["matches"][0]["threshold"] == 0.80


def test_emit_indexes_false_collects_no_file(tmp_path):
    m = make_match(1, 1, similar_case("foo"))
    result = analyze(
        program(m),
        source_path="support.voss",
        project_root=tmp_path,
        cache_dir=".voss-cache",
        emit_indexes=False,
        index_builder=FakeIndexBuilder(),
    )
    assert result.indexes == ()
    assert not (tmp_path / ".voss-cache" / "support.idx").exists()


def test_no_similar_cases_emits_no_index(tmp_path):
    case = MatchCase(
        span=span(line=1),
        pattern=WildcardPattern(span=span(line=1)),
        body=(),
    )
    m = MatchStmt(
        span=span(line=1, col=1),
        scrutinee=Identifier(span=span(line=1), name="input"),
        cases=(case,),
        threshold=None,
    )
    result = analyze(
        program(m),
        source_path="support.voss",
        project_root=tmp_path,
        cache_dir=".voss-cache",
        index_builder=FakeIndexBuilder(),
    )
    assert result.indexes == ()
    assert not (tmp_path / ".voss-cache" / "support.idx").exists()


def test_absolute_cache_dir_outside_project_reports_anly003_error(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside-cache"
    m = make_match(1, 1, similar_case("foo"))
    result = analyze(
        program(m),
        source_path="support.voss",
        project_root=project,
        cache_dir=outside,
        index_builder=FakeIndexBuilder(),
    )
    assert result.ok is False
    assert any(d.code == "ANLY003" for d in result.diagnostics)
    assert not outside.exists() or not any(outside.iterdir())
    assert not (outside / "support.idx").exists()
    assert not (outside / "support.idx.tmp").exists()


def test_program_stem_with_path_separator_reports_anly003_error(tmp_path, monkeypatch):
    m = make_match(1, 1, similar_case("foo"))
    analyzer = Analyzer(
        source_path="support.voss",
        project_root=tmp_path,
        cache_dir=".voss-cache",
        index_builder=FakeIndexBuilder(),
    )
    monkeypatch.setattr(analyzer, "_program_stem", lambda: "../support")
    result = analyzer.analyze_program(program(m))
    assert result.ok is False
    assert any(d.code == "ANLY003" for d in result.diagnostics)
    cache_dir = tmp_path / ".voss-cache"
    if cache_dir.exists():
        assert not any(p.suffix == ".tmp" for p in cache_dir.iterdir())
