"""Skill smoke tests — one per SKL + a registry-count guard.

Each stub fails with `pytest.fail("not yet")` until its owning downstream
plan turns it green. Test names are FINAL contracts — do not rename.

Ownership:
  T7-02 → test_rename_symbol (SKL-01), test_voss_lint (SKL-06)  [GREEN]
  T7-03 → test_summarize_diff (SKL-03), test_audit_cognition (SKL-05)
  T7-04 → test_add_test (SKL-02), test_port_py_to_voss (SKL-04)

`test_registry_count` is the last-to-green guard: it asserts the FINAL
registry count of 7 and is owned by T7-04. It legitimately stays RED through
T7-02 and T7-03 and MUST NOT be weakened (T7-01-PLAN registry-count
contract). T7-02 proves its own two registrations via direct
`default_skill_registry().get(...)` checks inside the two tests it owns.
"""
import io
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import patch


from voss.harness.skill_registry import default_skill_registry

from tests.skills.conftest import (
    FakeProvider,
    PermissionGate,
    Plan,
    PlainRenderer,
    ToolCall,
    make_toolset,
    seed_git_repo,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_rename_symbol(tmp_path: Path) -> None:  # SKL-01 — owned by T7-02
    from voss.harness.skills.rename_symbol import run

    for f in (FIXTURES / "rename-symbol").glob("*.py"):
        shutil.copy(f, tmp_path / f.name)

    before = {p.name: p.read_text() for p in tmp_path.glob("*.py")}

    # (a) plan mode — clean refusal, ZERO bytes mutated, no escalation.
    run(
        cwd=tmp_path,
        provider=None,
        history=None,
        record=None,
        renderer=PlainRenderer(),
        tools=make_toolset(tmp_path),
        gate=PermissionGate(mode="plan"),
        args=["foo", "bar"],
    )
    after_plan = {p.name: p.read_text() for p in tmp_path.glob("*.py")}
    assert after_plan == before, "plan mode mutated files — gate bypass"

    # (b) edit/auto — rename foo -> bar across every *.py via gated fs_edit.
    run(
        cwd=tmp_path,
        provider=None,
        history=None,
        record=None,
        renderer=PlainRenderer(),
        tools=make_toolset(tmp_path),
        gate=PermissionGate(auto_yes=True),
        args=["foo", "bar"],
    )
    joined = "\n".join(p.read_text() for p in sorted(tmp_path.glob("*.py")))
    assert "foo" not in joined and "bar" in joined, joined

    entry = default_skill_registry().get("rename-symbol")
    assert entry is not None and entry.mutating is True


def test_voss_lint(tmp_path: Path) -> None:  # SKL-06 — owned by T7-02
    from voss.harness.skills.voss_lint_as_skill import run

    shutil.copy(FIXTURES / "voss-lint" / "bad.voss", tmp_path / "bad.voss")

    buf = io.StringIO()
    with patch("click.echo", side_effect=lambda s, **kw: buf.write(str(s) + "\n")):
        run(
            cwd=tmp_path,
            provider=None,
            history=None,
            record=types.SimpleNamespace(model="fake", id="t"),
            renderer=PlainRenderer(),
            tools=make_toolset(tmp_path),
            gate=PermissionGate(auto_yes=True),
            args=[str(tmp_path)],
        )

    schema = json.loads(buf.getvalue())
    assert schema["version"] == 1
    assert isinstance(schema["findings"], list)
    assert schema["findings"], "expected the seeded bad.voss violation"

    expected_keys = ("file", "line", "col", "rule", "severity", "msg", "hint")
    for finding in schema["findings"]:
        assert tuple(finding) == expected_keys, finding

    seeded = [f for f in schema["findings"] if f["rule"] == "ANLY001"]
    assert seeded, schema["findings"]
    assert seeded[0]["severity"] == "warning"
    assert "unguarded" in seeded[0]["msg"]

    entry = default_skill_registry().get("voss-lint-as-skill")
    assert entry is not None and entry.mutating is False


_FAILING_TEST_SRC = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\n"
    "from target import add\n\n\n"
    "def test_add():\n"
    "    assert add(1, 2) == 99\n"
)


def test_add_test(tmp_path: Path) -> None:  # SKL-02 — owned by T7-04
    from voss.harness.skills.add_test import run

    shutil.copy(FIXTURES / "add-test" / "target.py", tmp_path / "target.py")

    plan = Plan(
        rationale="write a failing pytest test for add()",
        steps=[
            ToolCall(
                name="fs_write",
                args={"path": "tests/test_target.py", "content": _FAILING_TEST_SRC},
            )
        ],
        confidence=0.95,
        final_when_done="wrote tests/test_target.py",
    )
    run(
        cwd=tmp_path,
        provider=FakeProvider(plan),
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(tmp_path),
        gate=PermissionGate(auto_yes=True),
    )

    generated = tmp_path / "tests" / "test_target.py"
    assert generated.exists(), "add-test did not write the test through fs_write"

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/test_target.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "test_add" in proc.stdout, proc.stdout

    # plan mode: gated write refuses cleanly, nothing created (D-09/D-11).
    clean = tmp_path / "clean"
    clean.mkdir()
    shutil.copy(FIXTURES / "add-test" / "target.py", clean / "target.py")
    run(
        cwd=clean,
        provider=FakeProvider(plan),
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(clean),
        gate=PermissionGate(mode="plan"),
    )
    assert not (clean / "tests" / "test_target.py").exists(), "plan mode mutated"

    entry = default_skill_registry().get("add-test")
    assert entry is not None and entry.mutating is True


def _tracked_snapshot(root: Path) -> dict[str, bytes]:
    """Bytes of every git-tracked file — the read-only invariant target.

    Deliberately excludes untracked paths (run_turn writes session JSON
    under XDG_STATE_HOME, which the autouse isolated_state fixture points at
    the same tmp_path); only tracked-file mutation breaks the contract.
    """
    import subprocess

    out = subprocess.run(
        ["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.split()
    return {rel: (root / rel).read_bytes() for rel in out if (root / rel).is_file()}


def test_summarize_diff(tmp_path: Path, capsys) -> None:  # SKL-03 — T7-03
    from voss.harness.skills.summarize_diff import run

    seed_git_repo(tmp_path)
    # Unstaged working-tree modification so `git diff` is non-empty.
    (tmp_path / "README.md").write_text("# t\n\nan extra working-tree line\n")

    before = _tracked_snapshot(tmp_path)

    plan = Plan(
        rationale="summarize the working-tree diff",
        steps=[ToolCall(name="git_diff", args={})],
        confidence=0.95,
        final_when_done="## Title\nUpdate README\n## Summary\nAdds a line.\n## Changes\n- README.md: +1 line",
    )
    provider = FakeProvider(plan)

    run(
        cwd=tmp_path,
        provider=provider,
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(tmp_path),
        gate=PermissionGate(auto_yes=True),
    )

    out = capsys.readouterr().out
    assert "## Title" in out and "## Summary" in out and "## Changes" in out, out
    # Read-only invariant: no tracked/working file changed by the skill.
    assert _tracked_snapshot(tmp_path) == before, "summarize-diff mutated the tree"

    entry = default_skill_registry().get("summarize-diff")
    assert entry is not None and entry.mutating is False


_VALID_VOSS_SRC = (
    "# generated by port-py-to-voss test\n"
    'fn classify(text: string) -> string {\n'
    '    return "unknown"\n'
    "}\n\n"
    'let result = classify("cancel my subscription")\n'
    "print(result)\n"
)


def test_port_py_to_voss(tmp_path: Path) -> None:  # SKL-04 — owned by T7-04
    from voss.harness.skills.port_py_to_voss import run

    shutil.copy(
        FIXTURES / "port-py-to-voss" / "classify_intent.py",
        tmp_path / "classify_intent.py",
    )

    plan = Plan(
        rationale="translate classify_intent.py to .voss",
        steps=[
            ToolCall(
                name="fs_write",
                args={"path": "classify_intent.voss", "content": _VALID_VOSS_SRC},
            )
        ],
        confidence=0.95,
        final_when_done="wrote classify_intent.voss",
    )
    run(
        cwd=tmp_path,
        provider=FakeProvider(plan),
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(tmp_path),
        gate=PermissionGate(auto_yes=True),
        source="classify_intent.py",
    )

    generated = tmp_path / "classify_intent.voss"
    assert generated.exists(), "port-py-to-voss did not write via fs_write"
    proc = subprocess.run(
        [sys.executable, "-m", "voss.cli", "check", "classify_intent.voss"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    # Path-traversal control (block-on-high): jail_path confines fs_write to
    # cwd, so a "../escape.voss" write creates NO file outside the project.
    escape_plan = Plan(
        rationale="attempt escape",
        steps=[
            ToolCall(
                name="fs_write",
                args={"path": "../escape.voss", "content": _VALID_VOSS_SRC},
            )
        ],
        confidence=0.95,
        final_when_done="done",
    )
    esc_dir = tmp_path / "proj"
    esc_dir.mkdir()
    run(
        cwd=esc_dir,
        provider=FakeProvider(escape_plan),
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(esc_dir),
        gate=PermissionGate(auto_yes=True),
        source="classify_intent.py",
    )
    assert not (tmp_path / "escape.voss").exists(), "fs_write escaped cwd jail"
    assert not (esc_dir.parent / "escape.voss").exists(), "fs_write escaped cwd jail"

    # plan mode: gated write refuses cleanly, no .voss written (D-09/D-11).
    plan_dir = tmp_path / "planmode"
    plan_dir.mkdir()
    shutil.copy(
        FIXTURES / "port-py-to-voss" / "classify_intent.py",
        plan_dir / "classify_intent.py",
    )
    run(
        cwd=plan_dir,
        provider=FakeProvider(plan),
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(plan_dir),
        gate=PermissionGate(mode="plan"),
        source="classify_intent.py",
    )
    assert not (plan_dir / "classify_intent.voss").exists(), "plan mode mutated"

    entry = default_skill_registry().get("port-py-to-voss")
    assert entry is not None and entry.mutating is True


def test_audit_cognition(tmp_path: Path, capsys) -> None:  # SKL-05 — T7-03
    from voss.harness.skills.audit_cognition import run

    seed_git_repo(tmp_path)
    voss_dir = tmp_path / ".voss"
    voss_dir.mkdir()
    shutil.copy(
        FIXTURES / "audit-cognition" / ".voss" / "architecture.md",
        voss_dir / "architecture.md",
    )

    arch = voss_dir / "architecture.md"
    arch_before = arch.read_bytes()
    voss_md = tmp_path / "VOSS.md"
    assert not voss_md.exists()

    plan = Plan(
        rationale="audit cognition drift",
        steps=[],
        confidence=0.95,
        final_when_done="PROPOSAL: the architecture is now a skills bootstrap layer.",
    )
    provider = FakeProvider(plan)

    run(
        cwd=tmp_path,
        provider=provider,
        history=None,
        record=types.SimpleNamespace(model="fake", id="t"),
        renderer=PlainRenderer(),
        tools=make_toolset(tmp_path),
        gate=PermissionGate(auto_yes=True),
    )

    out = capsys.readouterr().out
    assert "PROPOSAL:" in out, out
    # HARD invariant (Pitfall 3): the skill proposes, never writes.
    assert arch.read_bytes() == arch_before, "audit-cognition wrote architecture.md"
    assert not voss_md.exists(), "audit-cognition created VOSS.md"

    entry = default_skill_registry().get("audit-cognition")
    assert entry is not None and entry.mutating is False


def test_registry_count():  # last-to-green guard — satisfied by T7-04
    assert len(default_skill_registry().ids()) == 7
