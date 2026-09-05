"""S0.3 — AGENTS.md / CLAUDE.md bundle loader (AC-S0-1, AC-S0-2, AC-S0-3, AC-S0-7)."""
from __future__ import annotations

from pathlib import Path

from voss.harness import instructions as instr


def _w(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_ac_s0_1_nested_order_collapse_and_stable_hash(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "# Root rules\n\nRun pnpm test.\n")
    _w(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _w(tmp_path / "src" / "AGENTS.md", "# src rules\n\nNo default exports.\n")

    b = instr.load(tmp_path, "src")

    assert b.paths == ["AGENTS.md", "src/AGENTS.md"]
    assert b.collapsed == ("CLAUDE.md",)
    assert [f.kind for f in b.files] == ["agents", "agents"]
    assert [f.scope_dir for f in b.files] == [".", "src"]
    assert b.merged_text.index("Root rules") < b.merged_text.index("src rules")
    assert b.load_errors == ()
    assert b.bundle_hash == instr.load(tmp_path, "src").bundle_hash


def test_root_only_load_excludes_nested(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "root\n")
    _w(tmp_path / "src" / "AGENTS.md", "nested\n")
    assert instr.load(tmp_path).paths == ["AGENTS.md"]


def test_claude_with_own_prose_keeps_prose_drops_duplicate_import(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "shared rules\n")
    _w(tmp_path / "CLAUDE.md", "@AGENTS.md\n\nClaude-only: use plan mode.\n")

    b = instr.load(tmp_path)

    assert b.paths == ["AGENTS.md", "CLAUDE.md"]
    assert b.merged_text.count("shared rules") == 1
    assert "Claude-only" in b.merged_text
    assert b.files[1].imports == ("AGENTS.md",)


def test_ac_s0_2_import_cycle_never_raises(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "@B.md\nroot text\n")
    _w(tmp_path / "B.md", "@AGENTS.md\nb text\n")

    b = instr.load(tmp_path)

    assert b.paths == ["AGENTS.md"]
    assert any("cycle" in e for e in b.load_errors)
    assert b.merged_text.count("root text") == 1
    assert b.merged_text.count("b text") == 1


def test_missing_import_is_an_error_not_a_crash(tmp_path: Path) -> None:
    _w(tmp_path / "CLAUDE.md", "@does-not-exist.md\nkeep me\n")
    b = instr.load(tmp_path)
    assert b.paths == ["CLAUDE.md"]
    assert any("not found" in e for e in b.load_errors)
    assert "keep me" in b.merged_text


def test_ac_s0_3_budget_truncates_and_records(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "rule\n" * 30_000)

    b = instr.load(tmp_path, config={"budget_tokens": 4000, "per_file_tokens": 4000})

    assert b.truncated == ("AGENTS.md",)
    assert b.tokens <= 4000 + 50
    assert "(truncated: instruction budget)" in b.merged_text
    untruncated = instr.load(tmp_path, config={"budget_tokens": 100_000, "per_file_tokens": 100_000})
    assert untruncated.truncated == ()
    assert b.bundle_hash != untruncated.bundle_hash
    assert b.bundle_hash == instr.load(tmp_path, config={"budget_tokens": 4000, "per_file_tokens": 4000}).bundle_hash


def test_per_file_cap_applies_before_total(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "a\n" * 6000)
    _w(tmp_path / "CLAUDE.md", "b\n" * 10)
    b = instr.load(tmp_path, config={"budget_tokens": 4000, "per_file_tokens": 1000})
    assert b.truncated == ("AGENTS.md",)
    assert b.paths == ["AGENTS.md", "CLAUDE.md"]
    assert b.files[0].tokens > 1000


def test_identical_content_kept_once(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "same\n")
    _w(tmp_path / "CLAUDE.md", "same\n")
    b = instr.load(tmp_path)
    assert b.paths == ["AGENTS.md"]
    assert b.collapsed == ("CLAUDE.md",)


def test_ac_s0_7_global_files_opt_in(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    _w(home / ".claude" / "CLAUDE.md", "global claude\n")
    _w(home / ".codex" / "AGENTS.md", "global codex\n")
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    _w(repo / "AGENTS.md", "repo\n")

    off = instr.load(repo)
    assert off.paths == ["AGENTS.md"]

    on = instr.load(repo, config={"read_global": True})
    assert on.paths == ["~/.codex/AGENTS.md", "~/.claude/CLAUDE.md", "AGENTS.md"]
    assert [f.kind for f in on.files] == ["global", "global", "agents"]
    assert on.merged_text.index("global codex") < on.merged_text.index("repo")


def test_empty_repo_has_stable_empty_hash(tmp_path: Path) -> None:
    b = instr.load(tmp_path)
    assert b.files == ()
    assert b.merged_text == ""
    assert b.bundle_hash == instr.load(tmp_path).bundle_hash


def test_disabled_returns_empty_bundle(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "x\n")
    b = instr.load(tmp_path, config={"enabled": False})
    assert b.files == ()
    assert b.bundle_hash == instr.empty_bundle_hash()


def test_target_outside_root_is_an_error(tmp_path: Path) -> None:
    _w(tmp_path / "repo" / "AGENTS.md", "x\n")
    b = instr.load(tmp_path / "repo", tmp_path / "elsewhere")
    assert b.paths == ["AGENTS.md"]
    assert any("outside project root" in e for e in b.load_errors)


def test_unreadable_file_is_reported_not_raised(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_bytes(b"\xff\xfe\x00bad utf8 \xff")
    b = instr.load(tmp_path)
    assert b.files == ()
    assert b.load_errors


def test_nested_import_resolved_when_sibling_import_already_loaded(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "shared\n")
    _w(tmp_path / "docs" / "extra.md", "@more.md\nextra body\n")
    _w(tmp_path / "docs" / "more.md", "nested body\n")
    _w(tmp_path / "CLAUDE.md", "@AGENTS.md\n@docs/extra.md\nclaude prose\n")

    b = instr.load(tmp_path)

    assert b.paths == ["AGENTS.md", "CLAUDE.md"]
    assert b.merged_text.count("shared") == 1
    assert "extra body" in b.merged_text
    assert "nested body" in b.merged_text
    assert "@more.md" not in b.merged_text
    assert b.load_errors == ()


def test_imports_outside_root_are_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET\n", encoding="utf-8")
    repo = tmp_path / "repo"
    _w(repo / "AGENTS.md", "@../outside.md\n@/etc/hostname\n@~/.ssh/id_rsa\nsafe\n")

    b = instr.load(repo)

    assert "SECRET" not in b.merged_text
    assert "safe" in b.merged_text
    assert sum("outside instruction root" in e for e in b.load_errors) == 3


def test_symlink_import_escaping_root_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("SECRET\n", encoding="utf-8")
    repo = tmp_path / "repo"
    _w(repo / "AGENTS.md", "@link.md\nsafe\n")
    (repo / "link.md").symlink_to(outside)

    b = instr.load(repo)

    assert "SECRET" not in b.merged_text
    assert any("outside instruction root" in e for e in b.load_errors)


def test_global_file_imports_confined_to_its_own_dir(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    _w(home / ".claude" / "CLAUDE.md", "@rules.md\n@../.ssh/id_rsa\n")
    _w(home / ".claude" / "rules.md", "global rules\n")
    _w(home / ".ssh" / "id_rsa", "PRIVATE\n")
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()

    b = instr.load(repo, config={"read_global": True})

    assert "global rules" in b.merged_text
    assert "PRIVATE" not in b.merged_text


def test_budget_dropping_every_file_still_reports_truncation(tmp_path: Path) -> None:
    _w(tmp_path / "AGENTS.md", "rule\n" * 500)
    b = instr.load(tmp_path, config={"budget_tokens": 50, "per_file_tokens": 50})
    assert b.merged_text == ""
    assert b.truncated == ("AGENTS.md",)
