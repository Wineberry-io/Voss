"""Round-trip AST via `to_dict` / `program_from_dict`."""

import json

import pytest
from pathlib import Path

from voss import to_dict
from voss.ast_deserializer import program_from_dict

EXAMPLES_DIR = Path(__file__).parent / "examples"
GOLDEN_DIR = Path(__file__).parent / "golden"
_ROUNDTRIP_NAMES = (
    "classify",
    "support",
    "research",
    "assistant",
    "grammar_surface",
    "coverage/memory_semantic",
    "coverage/memory_working",
)


@pytest.mark.parametrize("normalize_spans", [True, False])
@pytest.mark.parametrize("name", _ROUNDTRIP_NAMES)
def test_parse_to_dict_roundtrip(name, normalize_spans, parse_source):
    src = (EXAMPLES_DIR / f"{name}.voss").read_text()
    file = Path(name).name + ".voss"
    prog = parse_source(src, file=file)
    d = to_dict(prog, normalize_spans=normalize_spans)
    back = program_from_dict(d)
    again = to_dict(back, normalize_spans=normalize_spans)
    assert again == d


def test_normalized_matches_golden_classify(parse_source):
    name = "classify"
    src = (EXAMPLES_DIR / f"{name}.voss").read_text()
    prog = parse_source(src, file=f"{name}.voss")
    d_norm = to_dict(prog, normalize_spans=True)
    expected = json.loads((GOLDEN_DIR / f"{name}.ast.json").read_text())
    revived = program_from_dict(expected)
    assert to_dict(revived, normalize_spans=True) == expected


@pytest.mark.parametrize(
    "payload, match_re",
    [
        ({"oops": True}, r"missing '_node'"),
        ({"_node": "MissingType"}, r"unknown AST node type"),
        ({"_node": "Program", "span": None}, r"span must be an object"),
    ],
)
def test_program_from_dict_errors(payload, match_re):
    with pytest.raises(ValueError, match=match_re):
        program_from_dict(payload)


def test_program_from_dict_rejects_non_dict():
    with pytest.raises(ValueError, match=r"program_from_dict expects dict"):
        program_from_dict("not a dict")  # type: ignore[arg-type]
