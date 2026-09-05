"""V21 global memory tests (VGMEM-* requirements)."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

import voss.harness.memory_store as memory_store_api
from voss.harness.memory_store import Hit

try:
    from voss.harness.memory_store import (
        MemoryStore,
        make_global_store,
        _global_memory_root,
        _repo_id,
    )
except ImportError as exc:
    from voss.harness.memory_store import MemoryStore

    _MEMORY_API_IMPORT_ERROR = exc

    def _missing_memory_api(name: str) -> None:
        pytest.fail(
            f"planned V21 API voss.harness.memory_store.{name} is absent: "
            f"{_MEMORY_API_IMPORT_ERROR}"
        )

    def make_global_store():
        _missing_memory_api("make_global_store")

    def _global_memory_root():
        _missing_memory_api("_global_memory_root")

    def _repo_id(cwd: Path) -> str:
        _missing_memory_api("_repo_id")
else:
    _MEMORY_API_IMPORT_ERROR = None

try:
    from voss.harness.config import get_global_memory_enabled
except ImportError as exc:
    _CONFIG_API_IMPORT_ERROR = exc

    def get_global_memory_enabled() -> bool:
        pytest.fail(
            "planned V21 API voss.harness.config.get_global_memory_enabled "
            f"is absent: {_CONFIG_API_IMPORT_ERROR}"
        )
else:
    _CONFIG_API_IMPORT_ERROR = None


def _cli_env(tmp_voss_global: Path) -> dict[str, str]:
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[2]
    env["VOSS_HOME"] = str(tmp_voss_global.parent)
    env["PYTHONPATH"] = (
        str(repo_root)
        if not env.get("PYTHONPATH")
        else f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
    )
    return env


def _run_voss(args: list[str], *, cwd: Path, tmp_voss_global: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "voss.cli", *args],
        cwd=str(cwd),
        env=_cli_env(tmp_voss_global),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _seed_project_note(tmp_voss_repo: Path, text: str = "global promotion candidate") -> str:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    path = store.write_note(text, session_id="s1")
    return f"note:{path.stem}"


def _seed_project_convention(tmp_voss_repo: Path) -> str:
    store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    path = store.write_convention(
        SimpleNamespace(
            statement="global conventions are curated manually",
            confidence=0.9,
            evidence_quote="curated manually",
            evidence_turn_idx=0,
        ),
        session_id="s1",
    )
    return f"convention:{path.stem}"


def test_root_override(tmp_path: Path) -> None:
    override = tmp_path / "custom" / "memory"
    store = MemoryStore(tmp_path, root_override=override)
    assert store.root == override
    assert store.cwd == tmp_path


def test_voss_home_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOSS_HOME", str(tmp_path / "voss_home"))
    root = _global_memory_root()
    assert root == tmp_path / "voss_home" / "memory"


def test_global_layout_mirror(tmp_path: Path, tmp_voss_global: Path) -> None:
    store = MemoryStore(tmp_path, root_override=tmp_voss_global).bind(session_id="global")
    assert store.root == tmp_voss_global
    for sub in ("turns", "ledgers", "decisions", "conventions", "notes", "chroma", ".locks"):
        assert (tmp_voss_global / sub).is_dir()


def test_agent_cannot_write_global(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    from voss.harness.tools import attach_memory_tools

    project_store = MemoryStore(tmp_voss_repo).bind(session_id="s1")
    global_store = mock.Mock()
    global_store.recall.return_value = []
    tools: dict = {}

    attach_memory_tools(
        tools,
        store=project_store,
        session_id="s1",
        global_store=global_store,
    )

    out = asyncio.run(tools["memory_remember"].invoke(text="project-only durable fact"))
    assert out.startswith("remembered:")
    global_store.write_note.assert_not_called()
    assert list((tmp_voss_repo / ".voss" / "memory" / "notes").glob("*.md"))
    assert not list((tmp_voss_global / "notes").glob("*.md"))


def test_promote_copies_with_provenance(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    locator = _seed_project_note(tmp_voss_repo)

    result = _run_voss(
        ["memory", "promote", locator, "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert result.returncode == 0, result.stderr
    promoted_notes = list((tmp_voss_global / "notes").glob("*.md"))
    assert len(promoted_notes) == 1
    assert "global promotion candidate" in promoted_notes[0].read_text()
    assert f"promoted_from: {_repo_id(tmp_voss_repo)}/{locator}" in promoted_notes[0].read_text()


def test_promote_dedup_on_repromote(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    locator = _seed_project_note(tmp_voss_repo, "dedup candidate")

    first = _run_voss(
        ["memory", "promote", locator, "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )
    second = _run_voss(
        ["memory", "promote", locator, "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    promoted = [p for p in (tmp_voss_global / "notes").glob("*.md") if "dedup candidate" in p.read_text()]
    assert len(promoted) == 1


def test_promote_rejects_turn_ledger(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    result = _run_voss(
        ["memory", "promote", "turn:s1:000", "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )
    assert result.returncode == 1
    assert "cannot be promoted" in result.stderr


def test_promote_list(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    note_locator = _seed_project_note(tmp_voss_repo)
    convention_locator = _seed_project_convention(tmp_voss_repo)
    decisions_dir = tmp_voss_repo / ".voss" / "memory" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / "global-policy.md").write_text("# Decision\n\nglobal policy\n")

    result = _run_voss(
        ["memory", "promote", "--list", "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert result.returncode == 0, result.stderr
    assert note_locator in result.stdout
    assert convention_locator in result.stdout
    assert "decision:memory/decisions/global-policy.md" in result.stdout
    assert "turn:" not in result.stdout
    assert "ledger:" not in result.stdout


def test_forget_global_tombstones_global(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    project_store = MemoryStore(tmp_voss_repo).bind(session_id="project")
    global_store = MemoryStore(tmp_voss_repo, root_override=tmp_voss_global).bind(session_id="global")
    project_store.write_note("project note survives global forget", session_id="project")
    global_store.write_note("global note is tombstoned", session_id="global")

    result = _run_voss(
        ["memory", "forget", "note:*", "--global", "--yes", "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_voss_global / ".tombstones.jsonl").exists()
    assert "note:" in (tmp_voss_global / ".tombstones.jsonl").read_text()
    assert list((tmp_voss_repo / ".voss" / "memory" / "notes").glob("*.md"))


def test_forget_project_default(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    project_store = MemoryStore(tmp_voss_repo).bind(session_id="project")
    global_store = MemoryStore(tmp_voss_repo, root_override=tmp_voss_global).bind(session_id="global")
    project_store.write_note("project note tombstoned by default", session_id="project")
    global_store.write_note("global note survives default forget", session_id="global")

    result = _run_voss(
        ["memory", "forget", "note:*", "--yes", "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_voss_repo / ".voss" / "memory" / ".tombstones.jsonl").exists()
    assert not (tmp_voss_global / ".tombstones.jsonl").exists()
    assert list((tmp_voss_global / "notes").glob("*.md"))


def test_vacuum_global(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    global_store = MemoryStore(tmp_voss_repo, root_override=tmp_voss_global).bind(session_id="global")
    global_store.write_note("global vacuum candidate", session_id="global")
    assert global_store.forget("note:*", confirm=True) == 1

    result = _run_voss(
        ["memory", "vacuum", "--global", "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert result.returncode == 0, result.stderr
    assert "reclaimed:" in result.stdout
    assert not list((tmp_voss_global / "notes").glob("*.md"))


def test_concurrent_promote_lock(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    locator = _seed_project_note(tmp_voss_repo, "concurrent promote candidate")
    cmd = [
        sys.executable,
        "-m",
        "voss.cli",
        "memory",
        "promote",
        locator,
        "--cwd",
        str(tmp_voss_repo),
    ]
    env = _cli_env(tmp_voss_global)

    first = subprocess.Popen(cmd, cwd=str(tmp_voss_repo), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = subprocess.Popen(cmd, cwd=str(tmp_voss_repo), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    first_out, first_err = first.communicate(timeout=30)
    second_out, second_err = second.communicate(timeout=30)

    assert first.returncode == 0, first_err
    assert second.returncode == 0, second_err
    assert "promoted:" in first_out + second_out
    promoted = [p for p in (tmp_voss_global / "notes").glob("*.md") if "concurrent promote candidate" in p.read_text()]
    assert len(promoted) == 1


def test_recall_fusion_rrf(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    from voss.harness.tools import attach_memory_tools

    project_store = mock.Mock()
    global_store = mock.Mock()
    project_store.recall.return_value = [
        Hit(source="note", locator="note:project", score=1.0, excerpt="project memory hit")
    ]
    global_store.recall.return_value = [
        Hit(source="note", locator="note:global", score=1.0, excerpt="global memory hit")
    ]
    tools: dict = {}

    attach_memory_tools(
        tools,
        store=project_store,
        session_id="s1",
        global_store=global_store,
    )
    out = asyncio.run(tools["memory_recall"].invoke(query="memory hit", top_k=5))

    assert "project memory hit" in out
    assert "global memory hit" in out
    assert "[global]" in out


def test_global_label_in_recall(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    from voss.harness.tools import attach_memory_tools

    project_store = mock.Mock()
    global_store = mock.Mock()
    project_store.recall.return_value = []
    global_store.recall.return_value = [
        Hit(source="note", locator="note:global-label", score=1.0, excerpt="global label hit")
    ]
    tools: dict = {}

    attach_memory_tools(
        tools,
        store=project_store,
        session_id="s1",
        global_store=global_store,
    )
    out = asyncio.run(tools["memory_recall"].invoke(query="label", top_k=5))

    assert "[global]" in out
    assert "global label hit" in out


def test_global_off_switch_no_init(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    (config_dir / "voss").mkdir(parents=True)
    (config_dir / "voss" / "config.toml").write_text("[memory]\nglobal = false\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("VOSS_HOME", str(tmp_path / "global_home"))

    with mock.patch.object(memory_store_api, "SemanticMemory") as semantic_memory:
        assert get_global_memory_enabled() is False
        assert make_global_store() is None

    semantic_memory.assert_not_called()


def test_voss_recall_global_corpus(tmp_voss_repo: Path, tmp_voss_global: Path) -> None:
    global_store = MemoryStore(tmp_voss_repo, root_override=tmp_voss_global).bind(session_id="global")
    global_store.write_note("cross project global corpus recipe", session_id="global")

    result = _run_voss(
        ["recall", "cross", "project", "recipe", "--cwd", str(tmp_voss_repo)],
        cwd=tmp_voss_repo,
        tmp_voss_global=tmp_voss_global,
    )

    assert result.returncode == 0, result.stderr
    assert "[global]" in result.stdout
    assert "cross project global corpus recipe" in result.stdout


def test_do_cmd_wires_global_store(tmp_path: Path) -> None:
    import voss.harness.cli as cli

    class Renderer:
        def banner(self, **_kwargs):
            return None

        def show_user(self, _text: str):
            return None

        def show_final(self, *_args, **_kwargs):
            return None

    record = SimpleNamespace(id="sess-1", runs=[])
    result = SimpleNamespace(final="done", confidence=1.0, cost_usd=0.0, run=None)
    auth = SimpleNamespace(source="stub", detail="ok")
    bundle = SimpleNamespace(
        initialized=False,
        permissions=None,
        safety=None,
        load_errors=[],
    )
    sentinel_global_store = object()

    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(cli, "_resolve_default_model"))
        stack.enter_context(mock.patch.object(cli, "_resolve_auth_or_die", return_value=(auth, object())))
        stack.enter_context(
            mock.patch.object(
                cli,
                "_apply_boot_model",
                side_effect=lambda provider, user_explicit=None, auth_source=None: provider,
            )
        )
        stack.enter_context(mock.patch.object(cli, "get_config", return_value=SimpleNamespace(default_model="stub-model")))
        stack.enter_context(mock.patch.object(cli, "_emit_harness_boot_telemetry"))
        stack.enter_context(mock.patch.object(cli, "make_renderer", return_value=Renderer()))
        stack.enter_context(mock.patch.object(cli, "make_toolset", return_value={}))
        stack.enter_context(mock.patch.object(cli, "_get_net_session", return_value=None))
        stack.enter_context(mock.patch.object(cli.voss_md, "ensure_migrated"))
        stack.enter_context(mock.patch.object(cli.voss_md, "read_and_inject", return_value=""))
        stack.enter_context(mock.patch.object(cli.cognition_mod, "load", return_value=bundle))
        stack.enter_context(mock.patch.object(cli, "_render_project_index_text", return_value=""))
        stack.enter_context(mock.patch.object(cli.PermissionStore, "load", return_value=object()))
        stack.enter_context(mock.patch.object(cli, "PermissionGate", return_value=object()))
        stack.enter_context(mock.patch.object(cli, "_wire_tui_permissions_if_textual"))
        stack.enter_context(mock.patch.object(cli, "attach_subagent_tool"))
        stack.enter_context(mock.patch.object(cli, "default_subagent_registry", return_value=object()))
        stack.enter_context(mock.patch.object(cli.session_store.SessionRecord, "new", return_value=record))
        stack.enter_context(mock.patch.object(cli, "_git_status", return_value="clean"))
        stack.enter_context(mock.patch.object(cli, "_resolve_run_turn", return_value=lambda *args, **kwargs: object()))
        stack.enter_context(mock.patch.object(cli, "_run_turn_cancellable", return_value=result))
        stack.enter_context(mock.patch.object(cli, "_code_recall_kwargs", return_value={}))
        stack.enter_context(mock.patch.object(cli.conventions, "run_on_clean_exit"))
        stack.enter_context(mock.patch.object(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True)))
        make_global = stack.enter_context(
            mock.patch.object(cli, "make_global_store", return_value=sentinel_global_store, create=True)
        )
        attach_memory = stack.enter_context(mock.patch.object(cli, "attach_memory_tools"))
        cli.do_cmd.callback(
            task=("remember this",),
            model=None,
            cwd_str=str(tmp_path),
            json_mode=False,
            plain=True,
            no_unicode=False,
            mode="plan",
            yes_to_all=False,
            allow_net=None,
            auth_pref="auto",
            no_pack=False,
        )

    make_global.assert_called_once()
    assert attach_memory.call_args is not None
    assert attach_memory.call_args.kwargs["global_store"] is sentinel_global_store
