from __future__ import annotations

import json
from pathlib import Path

import pytest

from voss.ast_nodes import (
    ExprPattern,
    FnDecl,
    Identifier,
    IntLit,
    MatchCase,
    MatchStmt,
    Param,
    QualName,
    ReturnStmt,
    SimilarPattern,
    Span,
    StringLit,
    TypeRef,
    WildcardPattern,
)
from voss.codegen import CodegenError, generate_python
from voss.diagnostics import AnalysisResult, EmittedIndex

from tests.codegen.conftest import (
    assert_no_compiler_imports,
    assert_python_parses,
    program,
    span,
)


def _ident(name: str) -> Identifier:
    return Identifier(span=span(), name=name)


def _type(*parts: str) -> TypeRef:
    return TypeRef(span=span(), name=QualName(span=span(), parts=parts))


def _match_span(line: int, col: int) -> Span:
    return Span(
        file="support.voss",
        line_start=line,
        col_start=col,
        line_end=line,
        col_end=col,
    )


def write_manifest(tmp_path: Path, program_name: str = "support") -> Path:
    cache = tmp_path / ".voss-cache"
    cache.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "program": program_name,
        "model": "fake-embedding-model",
        "matches": [
            {
                "match_id": "match_12_5",
                "threshold": 0.8,
                "cases": [
                    {
                        "label": "case_0",
                        "description": "angry customer",
                        "embedding": [1.0, 0.0],
                    },
                    {
                        "label": "case_1",
                        "description": "refund request",
                        "embedding": [0.0, 1.0],
                    },
                ],
            }
        ],
    }
    path = cache / f"{program_name}.idx"
    path.write_text(json.dumps(manifest))
    return path


def _ok_analysis(*indexes: EmittedIndex) -> AnalysisResult:
    return AnalysisResult(diagnostics=(), indexes=tuple(indexes))


def _match_fn(match: MatchStmt) -> FnDecl:
    return FnDecl(
        span=span(),
        name="route",
        params=(Param(span=span(), name="userMessage", type_annot=_type("string")),),
        return_type=_type("string"),
        body=(match,),
    )


def test_match_similar_uses_phase3_manifest_embeddings(tmp_path):
    manifest_path = write_manifest(tmp_path)
    cache_dir = tmp_path / ".voss-cache"
    analysis = _ok_analysis(
        EmittedIndex(
            match_id="match_12_5",
            path=manifest_path,
            case_count=2,
            threshold=0.8,
            model="fake-embedding-model",
        )
    )
    match = MatchStmt(
        span=_match_span(12, 5),
        scrutinee=_ident("userMessage"),
        cases=(
            MatchCase(
                span=span(),
                pattern=SimilarPattern(span=span(), text="angry customer"),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="escalate")),),
            ),
            MatchCase(
                span=span(),
                pattern=SimilarPattern(span=span(), text="refund request"),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="refund_flow")),),
            ),
            MatchCase(
                span=span(),
                pattern=WildcardPattern(span=span()),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="default")),),
            ),
        ),
    )
    fn = _match_fn(match)
    result = generate_python(
        program(fn),
        source_path="support.voss",
        analysis=analysis,
        cache_dir=cache_dir,
        project_root=tmp_path,
    )
    source = result.source
    assert "from voss_runtime import" in source
    assert "SemanticMatcher" in source
    assert "SemanticMatcher(" in source
    assert "threshold=0.8" in source
    assert "embeddings=[[1.0, 0.0], [0.0, 1.0]]" in source
    assert "match _matcher_" in source
    assert 'case "case_0":' in source
    assert 'case "case_1":' in source
    assert "case _:" in source
    assert "SentenceTransformer" not in source
    assert "from_index(" not in source
    assert "write_index" not in source
    assert_python_parses(source)
    assert_no_compiler_imports(source)


def test_missing_manifest_match_id_raises_codegen_error(tmp_path):
    write_manifest(tmp_path)
    cache_dir = tmp_path / ".voss-cache"
    analysis = _ok_analysis()
    match = MatchStmt(
        span=_match_span(99, 1),
        scrutinee=_ident("userMessage"),
        cases=(
            MatchCase(
                span=span(),
                pattern=SimilarPattern(span=span(), text="angry"),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="escalate")),),
            ),
            MatchCase(
                span=span(),
                pattern=WildcardPattern(span=span()),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="default")),),
            ),
        ),
    )
    fn = _match_fn(match)
    with pytest.raises(CodegenError) as info:
        generate_python(
            program(fn),
            source_path="support.voss",
            analysis=analysis,
            cache_dir=cache_dir,
            project_root=tmp_path,
        )
    assert "missing semantic match index for match_99_1" in str(info.value)


def test_match_without_similar_cases_uses_structural_python_match(tmp_path):
    cache_dir = tmp_path / ".voss-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    analysis = _ok_analysis()
    match = MatchStmt(
        span=_match_span(20, 5),
        scrutinee=_ident("code"),
        cases=(
            MatchCase(
                span=span(),
                pattern=ExprPattern(span=span(), expr=IntLit(span=span(), value=1)),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="one")),),
            ),
            MatchCase(
                span=span(),
                pattern=WildcardPattern(span=span()),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="other")),),
            ),
        ),
    )
    fn = FnDecl(
        span=span(),
        name="classify",
        params=(Param(span=span(), name="code", type_annot=_type("int")),),
        return_type=_type("string"),
        body=(match,),
    )
    result = generate_python(
        program(fn),
        source_path="support.voss",
        analysis=analysis,
        cache_dir=cache_dir,
        project_root=tmp_path,
    )
    source = result.source
    assert "match code:" in source
    assert "case 1:" in source
    assert "case _:" in source
    assert "SemanticMatcher" not in source
    assert_python_parses(source)


def test_match_manifest_read_does_not_write_cache_files(tmp_path):
    write_manifest(tmp_path)
    cache_dir = tmp_path / ".voss-cache"
    before = set(p.name for p in cache_dir.iterdir())
    analysis = _ok_analysis()
    match = MatchStmt(
        span=_match_span(12, 5),
        scrutinee=_ident("userMessage"),
        cases=(
            MatchCase(
                span=span(),
                pattern=SimilarPattern(span=span(), text="angry"),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="escalate")),),
            ),
            MatchCase(
                span=span(),
                pattern=WildcardPattern(span=span()),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="default")),),
            ),
        ),
    )
    fn = _match_fn(match)
    generate_python(
        program(fn),
        source_path="support.voss",
        analysis=analysis,
        cache_dir=cache_dir,
        project_root=tmp_path,
    )
    after = set(p.name for p in cache_dir.iterdir())
    assert before == after


def test_analysis_index_path_outside_cache_raises_codegen_error(tmp_path):
    write_manifest(tmp_path)
    outside = tmp_path.parent / "outside.idx"
    analysis = _ok_analysis(
        EmittedIndex(
            match_id="match_12_5",
            path=outside,
            case_count=2,
            threshold=0.8,
            model="fake-embedding-model",
        )
    )
    match = MatchStmt(
        span=_match_span(12, 5),
        scrutinee=_ident("userMessage"),
        cases=(
            MatchCase(
                span=span(),
                pattern=SimilarPattern(span=span(), text="angry"),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="escalate")),),
            ),
            MatchCase(
                span=span(),
                pattern=WildcardPattern(span=span()),
                body=(ReturnStmt(span=span(), value=StringLit(span=span(), value="default")),),
            ),
        ),
    )
    fn = _match_fn(match)
    with pytest.raises(CodegenError) as info:
        generate_python(
            program(fn),
            source_path="support.voss",
            analysis=analysis,
            project_root=tmp_path,
            cache_dir=".voss-cache",
        )
    assert "semantic index path outside cache directory" in str(info.value)
    assert not outside.exists()
