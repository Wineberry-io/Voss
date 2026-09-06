"""T2-04 / PAR-03: fs_edit_many atomic single-file multi-edit.

SPEC PAR-03 acceptance fixtures (a/b/c/d) + edge cases:
- left-to-right buffer propagation (Pitfall 5)
- buffer propagation creating new ambiguity
- skip-is-strict (resolves RESEARCH.md Open Question 1)
- empty edits list / empty old string
- missing file / directory / binary
- jail violation propagation
- registration + is_mutating + fs_edit coexistence (D-10)
- renderer=None test-friendly path
"""
from __future__ import annotations

from pathlib import Path

import pytest

from voss.harness.sandbox import SandboxError
from voss.harness.tools import make_toolset
from voss.harness.tui.widgets.diff_modal import DiffDecision, Hunk


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeRenderer:
    """Renderer stub exposing show_diff_modal. Records hunks + returns scripted decisions."""

    def __init__(self, decisions: list[DiffDecision] | None = None) -> None:
        self._decisions = decisions if decisions is not None else []
        self.call_count = 0
        self.last_hunks: list[Hunk] = []

    def show_diff_modal(
        self, hunks: list[Hunk], *, timeout_s: float = 300.0
    ) -> list[DiffDecision]:
        self.call_count += 1
        self.last_hunks = list(hunks)
        return list(self._decisions)


def _accept(file: str) -> DiffDecision:
    return DiffDecision(file=file, decision="accept")


def _reject(file: str) -> DiffDecision:
    return DiffDecision(file=file, decision="reject")


def _skip(file: str) -> DiffDecision:
    return DiffDecision(file=file, decision="skip")


async def _call(tools, **kwargs) -> str:
    return await tools["fs_edit_many"].invoke(**kwargs)


# ---------------------------------------------------------------------------
# Acceptance fixture a — all-pass writes once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_match_writes(tmp_path: Path) -> None:
    p = tmp_path / "foo.py"
    p.write_text("a\nb\nc\n")
    renderer = _FakeRenderer(
        decisions=[_accept("foo.py"), _accept("foo.py"), _accept("foo.py")]
    )
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="foo.py",
        edits=[
            {"old": "a", "new": "x"},
            {"old": "b", "new": "y"},
            {"old": "c", "new": "z"},
        ],
    )
    assert "edited foo.py" in out
    assert "3 hunks" in out
    assert p.read_text() == "x\ny\nz\n"
    assert renderer.call_count == 1
    assert len(renderer.last_hunks) == 3


@pytest.mark.asyncio
async def test_all_match_records_line_delta(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("hello\nworld\n")
    renderer = _FakeRenderer(
        decisions=[_accept("f.txt"), _accept("f.txt")]
    )
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="f.txt",
        edits=[
            {"old": "hello", "new": "greetings\nfrom\nthe\nstars"},
            {"old": "world", "new": "earth"},
        ],
    )
    # 5 net lines added (4 newlines added in first edit, 0 in second).
    assert "+3 lines" in out
    assert "2 hunks" in out


# ---------------------------------------------------------------------------
# Acceptance fixture b — non-unique rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ambiguous_rejected(tmp_path: Path) -> None:
    p = tmp_path / "foo.py"
    text = "a\nFOO\nFOO\nc\n"
    p.write_text(text)
    before = p.read_bytes()
    renderer = _FakeRenderer()
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="foo.py",
        edits=[
            {"old": "a", "new": "x"},
            {"old": "FOO", "new": "BAR"},
            {"old": "c", "new": "z"},
        ],
    )
    assert "<error: batch rejected at index 1:" in out
    assert "matches 2 times" in out
    assert p.read_bytes() == before  # file byte-for-byte unchanged
    assert renderer.call_count == 0  # modal NEVER shown


# ---------------------------------------------------------------------------
# Acceptance fixture c — not-found rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_rejected(tmp_path: Path) -> None:
    p = tmp_path / "foo.py"
    p.write_text("a\nb\nc\n")
    before = p.read_bytes()
    renderer = _FakeRenderer()
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="foo.py",
        edits=[
            {"old": "a", "new": "x"},
            {"old": "b", "new": "y"},
            {"old": "NOPE", "new": "z"},
        ],
    )
    assert "<error: batch rejected at index 2:" in out
    assert "`old` not found" in out
    assert p.read_bytes() == before
    assert renderer.call_count == 0


# ---------------------------------------------------------------------------
# Acceptance fixture d — modal rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modal_reject_denies(tmp_path: Path) -> None:
    p = tmp_path / "foo.py"
    p.write_text("a\nb\nc\n")
    before = p.read_bytes()
    renderer = _FakeRenderer(
        decisions=[_accept("foo.py"), _reject("foo.py"), _accept("foo.py")]
    )
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="foo.py",
        edits=[
            {"old": "a", "new": "x"},
            {"old": "b", "new": "y"},
            {"old": "c", "new": "z"},
        ],
    )
    assert out == "<denied: hunk 1 rejected>"
    assert p.read_bytes() == before
    assert renderer.call_count == 1


# ---------------------------------------------------------------------------
# Skip-is-strict (RESEARCH.md Open Question 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modal_skip_denies_strict(tmp_path: Path) -> None:
    p = tmp_path / "foo.py"
    p.write_text("a\nb\nc\n")
    before = p.read_bytes()
    renderer = _FakeRenderer(
        decisions=[_accept("foo.py"), _skip("foo.py"), _accept("foo.py")]
    )
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="foo.py",
        edits=[
            {"old": "a", "new": "x"},
            {"old": "b", "new": "y"},
            {"old": "c", "new": "z"},
        ],
    )
    assert out == "<denied: hunk 1 rejected>"
    assert p.read_bytes() == before


@pytest.mark.asyncio
async def test_modal_cancelled_empty_denies(tmp_path: Path) -> None:
    p = tmp_path / "foo.py"
    p.write_text("a\nb\nc\n")
    before = p.read_bytes()
    renderer = _FakeRenderer(decisions=[])  # cancelled / timed out
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="foo.py",
        edits=[{"old": "a", "new": "x"}, {"old": "b", "new": "y"}],
    )
    assert out == "<denied: modal cancelled or timed out>"
    assert p.read_bytes() == before


# ---------------------------------------------------------------------------
# Buffer propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buffer_propagation_left_to_right(tmp_path: Path) -> None:
    """edit #1 introduces text that edit #2 then matches."""
    p = tmp_path / "f.txt"
    p.write_text("FooBar\n")
    renderer = _FakeRenderer(decisions=[_accept("f.txt"), _accept("f.txt")])
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="f.txt",
        edits=[
            {"old": "FooBar", "new": "BarBaz"},
            {"old": "BarBaz", "new": "Done"},
        ],
    )
    assert "edited f.txt" in out
    assert "2 hunks" in out
    assert p.read_text() == "Done\n"


@pytest.mark.asyncio
async def test_buffer_propagation_creates_new_ambiguity(tmp_path: Path) -> None:
    """edit #1 makes the buffer have 2 matches for edit #2's old."""
    p = tmp_path / "f.txt"
    p.write_text("x\ny\n")  # 1 x, 1 y already
    before = p.read_bytes()
    renderer = _FakeRenderer()
    tools = make_toolset(tmp_path, renderer=renderer)
    out = await _call(
        tools,
        path="f.txt",
        edits=[
            {"old": "x", "new": "y"},  # buf becomes "y\ny\n" → 2 occurrences of "y"
            {"old": "y", "new": "z"},
        ],
    )
    assert "<error: batch rejected at index 1:" in out
    assert "matches 2 times" in out
    assert p.read_bytes() == before
    assert renderer.call_count == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_edits_list(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("a\n")
    before = p.read_bytes()
    tools = make_toolset(tmp_path, renderer=_FakeRenderer())
    out = await _call(tools, path="f.txt", edits=[])
    assert out == "<error: empty edits list>"
    assert p.read_bytes() == before


@pytest.mark.asyncio
async def test_empty_old_string(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("a\n")
    before = p.read_bytes()
    tools = make_toolset(tmp_path, renderer=_FakeRenderer())
    out = await _call(
        tools, path="f.txt", edits=[{"old": "", "new": "x"}]
    )
    assert "<error: batch rejected at index 0: empty `old`>" in out
    assert p.read_bytes() == before


@pytest.mark.asyncio
async def test_not_found(tmp_path: Path) -> None:
    tools = make_toolset(tmp_path, renderer=_FakeRenderer())
    out = await _call(
        tools, path="missing.txt", edits=[{"old": "a", "new": "b"}]
    )
    assert out == "<error: not found: missing.txt>"


@pytest.mark.asyncio
async def test_is_directory(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    tools = make_toolset(tmp_path, renderer=_FakeRenderer())
    out = await _call(
        tools, path="subdir", edits=[{"old": "a", "new": "b"}]
    )
    assert out == "<error: is a directory: subdir>"


@pytest.mark.asyncio
async def test_binary_file(tmp_path: Path) -> None:
    p = tmp_path / "bin.dat"
    p.write_bytes(b"\xff\xfe\x00\x01\x02")
    before = p.read_bytes()
    tools = make_toolset(tmp_path, renderer=_FakeRenderer())
    out = await _call(
        tools, path="bin.dat", edits=[{"old": "a", "new": "b"}]
    )
    assert out == "<error: binary file: bin.dat>"
    assert p.read_bytes() == before


@pytest.mark.asyncio
async def test_jail_violation_raises(tmp_path: Path) -> None:
    tools = make_toolset(tmp_path, renderer=_FakeRenderer())
    with pytest.raises(SandboxError):
        await _call(
            tools,
            path="../../etc/passwd",
            edits=[{"old": "a", "new": "b"}],
        )


# ---------------------------------------------------------------------------
# Registration + coexistence (D-10)
# ---------------------------------------------------------------------------


def test_registered_with_is_mutating_true(tmp_path: Path) -> None:
    tools = make_toolset(tmp_path)
    assert "fs_edit_many" in tools
    assert tools["fs_edit_many"].is_mutating is True


def test_fs_edit_still_registered(tmp_path: Path) -> None:
    tools = make_toolset(tmp_path)
    assert "fs_edit" in tools
    assert tools["fs_edit"].is_mutating is True


def test_both_tools_coexist_independently(tmp_path: Path) -> None:
    tools = make_toolset(tmp_path)
    assert tools["fs_edit"].descriptor is not tools["fs_edit_many"].descriptor
    assert tools["fs_edit"].descriptor.name == "fs_edit"
    assert tools["fs_edit_many"].descriptor.name == "fs_edit_many"


# ---------------------------------------------------------------------------
# Renderer = None test-friendly path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_renderer_none_skips_modal(tmp_path: Path) -> None:
    """make_toolset(cwd, renderer=None) writes after validation without modal."""
    p = tmp_path / "f.txt"
    p.write_text("a\nb\n")
    tools = make_toolset(tmp_path)  # no renderer kwarg → None
    out = await _call(
        tools,
        path="f.txt",
        edits=[{"old": "a", "new": "x"}, {"old": "b", "new": "y"}],
    )
    assert "edited f.txt" in out
    assert "2 hunks" in out
    assert p.read_text() == "x\ny\n"


@pytest.mark.asyncio
async def test_renderer_without_show_diff_modal_skips_modal(tmp_path: Path) -> None:
    """Non-TUI renderer (no show_diff_modal attribute) bypasses modal phase."""

    class _PlainRenderer:
        def show_tool_call(self, *a, **kw): pass

    p = tmp_path / "f.txt"
    p.write_text("a\n")
    tools = make_toolset(tmp_path, renderer=_PlainRenderer())
    out = await _call(
        tools, path="f.txt", edits=[{"old": "a", "new": "x"}]
    )
    assert "edited f.txt" in out
    assert p.read_text() == "x\n"


# ---------------------------------------------------------------------------
# Hunk construction shape (visible to modal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hunks_passed_to_modal_have_expected_shape(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text("alpha\nbeta\ngamma\n")
    renderer = _FakeRenderer(
        decisions=[_accept("f.txt"), _accept("f.txt")]
    )
    tools = make_toolset(tmp_path, renderer=renderer)
    await _call(
        tools,
        path="f.txt",
        edits=[
            {"old": "alpha", "new": "ALPHA"},
            {"old": "gamma", "new": "GAMMA"},
        ],
    )
    assert len(renderer.last_hunks) == 2
    h0, h1 = renderer.last_hunks
    assert h0.file == "f.txt"
    assert h0.start == 1
    assert any(l.startswith("- ") for l in h0.lines)
    assert any(l.startswith("+ ") for l in h0.lines)
    assert h1.start == 3
