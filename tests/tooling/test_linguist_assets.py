from __future__ import annotations

from pathlib import Path


from voss import parse


_LINGUIST_LINE = "*.voss linguist-language=Voss linguist-detectable=true"
_SAMPLE_NAMES = (
    "classify.voss",
    "support.voss",
    "research.voss",
    "audit-gates.voss",
    "reviewer-split.voss",
    "team-orchestration.voss",
)
_FORBIDDEN_CLAIMS = (
    "native GitHub support",
    "accepted upstream",
    "registered in Linguist",
)


def test_repo_gitattributes_has_required_voss_linguist_line():
    path = Path(".gitattributes")
    assert path.exists(), "top-level .gitattributes must exist"
    assert _LINGUIST_LINE in path.read_text().splitlines()


def test_samples_are_representative_and_parse():
    sample_dir = Path("samples")
    expected = {
        "samples/classify.voss",
        "samples/support.voss",
        "samples/research.voss",
    }
    for rel in expected:
        path = Path(rel)
        assert path.exists(), rel
        text = path.read_text()
        parse(text, file=str(path))
        nonblank = [line for line in text.splitlines() if line.strip()]
        assert len(nonblank) >= 5, f"{rel} is too small to be representative"


def test_samples_track_parser_example_names():
    sample_names = {p.name for p in Path("samples").glob("*.voss")}
    assert sample_names == set(_SAMPLE_NAMES)


def test_language_metadata_is_draft_local_and_complete():
    path = Path("language-metadata/voss.yml")
    assert path.exists()
    text = path.read_text()
    required_fragments = (
        "name: Voss",
        "type: programming",
        '".voss"',
        "color:",
        "group: Python",
        'ace_mode: "python"',
        "fallback_highlighting: Python",
        "upstream_status:",
        "draft",
    )
    for fragment in required_fragments:
        assert fragment in text, f"missing metadata fragment: {fragment}"


def test_linguist_assets_do_not_claim_native_github_support():
    text = Path("language-metadata/voss.yml").read_text()
    for claim in _FORBIDDEN_CLAIMS:
        assert claim not in text, claim
