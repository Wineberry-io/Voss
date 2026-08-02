"""R3 git-worktree-per-member lifecycle tests (SWARM-RECONCILIATION).

Real temp git repos throughout (mirrors tests/harness/test_layout.py's `_git`
+ fixture style). Exercises create/list/remove, change detection for tracked
edits and untracked new files, and fan-in merge bringing a member's change back
to the main checkout's HEAD.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from voss.harness.swarm_worktree import (
    CandidateExistsError,
    MemberWorktree,
    NotAGitRepoError,
    WorktreeMergeConflict,
    changed_files,
    create_member_worktree,
    list_member_worktrees,
    merge_member,
    remove_member_worktree,
)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """git init repo with a committed file (worktree add needs a HEAD)."""
    root = tmp_path / "proj"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@test"], root)
    _git(["config", "user.name", "test"], root)
    (root / "base.txt").write_text("base\n")
    _git(["add", "base.txt"], root)
    _git(["commit", "-q", "-m", "init"], root)
    return root


SWARM = "sw123456"


class TestCreate:
    def test_create_makes_worktree_on_branch(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        assert mw.role == "builder-1"
        assert mw.branch == f"swarm/{SWARM}/builder-1"
        assert mw.path.is_dir()
        # The worktree is a real checkout: the committed base file is present.
        assert (mw.path / "base.txt").read_text() == "base\n"

    def test_create_preserves_existing_candidate(self, repo: Path) -> None:
        create_member_worktree(repo, SWARM, "builder-1")
        with pytest.raises(CandidateExistsError):
            create_member_worktree(repo, SWARM, "builder-1")

    def test_not_a_git_repo_raises(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(NotAGitRepoError):
            create_member_worktree(plain, SWARM, "builder-1")


class TestList:
    def test_list_returns_swarm_members_only(self, repo: Path) -> None:
        a = create_member_worktree(repo, SWARM, "builder-1")
        b = create_member_worktree(repo, SWARM, "reviewer")
        # A worktree from a *different* swarm must not appear.
        create_member_worktree(repo, "other999", "builder-1")

        members = list_member_worktrees(repo, SWARM)
        roles = {m.role for m in members}
        assert roles == {"builder-1", "reviewer"}
        paths = {m.path for m in members}
        assert paths == {a.path, b.path}
        branches = {m.branch for m in members}
        assert branches == {a.branch, b.branch}

    def test_list_empty_when_no_members(self, repo: Path) -> None:
        assert list_member_worktrees(repo, SWARM) == []


class TestChangedFiles:
    def test_tracked_edit_detected(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        (mw.path / "base.txt").write_text("changed\n")
        assert changed_files(mw) == ["base.txt"]

    def test_untracked_create_detected(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        (mw.path / "new_file.py").write_text("print('hi')\n")
        assert changed_files(mw) == ["new_file.py"]

    def test_no_changes_is_empty(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        assert changed_files(mw) == []


class TestMerge:
    def test_merge_brings_member_change_to_main(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        # Member commits a new file on its branch...
        (mw.path / "feature.py").write_text("FEATURE\n")
        _git(["add", "feature.py"], mw.path)
        _git(["commit", "-q", "-m", "feature"], mw.path)

        # ...fan-in merges it into the main checkout's HEAD.
        merge_member(repo, mw)
        assert (repo / "feature.py").read_text() == "FEATURE\n"

    def test_disjoint_members_merge_conflict_free(self, repo: Path) -> None:
        a = create_member_worktree(repo, SWARM, "builder-1")
        b = create_member_worktree(repo, SWARM, "builder-2")
        (a.path / "a.py").write_text("A\n")
        _git(["add", "a.py"], a.path)
        _git(["commit", "-q", "-m", "a"], a.path)
        (b.path / "b.py").write_text("B\n")
        _git(["add", "b.py"], b.path)
        _git(["commit", "-q", "-m", "b"], b.path)

        merge_member(repo, a)
        merge_member(repo, b)
        assert (repo / "a.py").read_text() == "A\n"
        assert (repo / "b.py").read_text() == "B\n"

    def test_overlapping_change_raises_conflict(self, repo: Path) -> None:
        # If VSWARM-06 disjointness were violated, the merge must fail loudly,
        # leaving HEAD clean (not half-merged).
        mw = create_member_worktree(repo, SWARM, "builder-1")
        # Main and member edit the SAME committed file divergently.
        (repo / "base.txt").write_text("main-edit\n")
        _git(["commit", "-aqm", "main edit"], repo)
        (mw.path / "base.txt").write_text("member-edit\n")
        _git(["commit", "-aqm", "member edit"], mw.path)

        with pytest.raises(WorktreeMergeConflict):
            merge_member(repo, mw)
        # HEAD is clean — the abort left no in-progress merge.
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        assert "UU" not in status.stdout


class TestRemove:
    def test_remove_deletes_worktree_and_branch(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        assert mw.path.is_dir()
        remove_member_worktree(repo, mw)
        assert not mw.path.exists()
        assert list_member_worktrees(repo, SWARM) == []
        # The branch is gone too.
        branches = subprocess.run(
            ["git", "-C", str(repo), "branch", "--list", mw.branch],
            capture_output=True,
            text=True,
        )
        assert branches.stdout.strip() == ""

    def test_remove_with_uncommitted_changes_forced(self, repo: Path) -> None:
        mw = create_member_worktree(repo, SWARM, "builder-1")
        (mw.path / "base.txt").write_text("dirty\n")  # uncommitted
        remove_member_worktree(repo, mw)  # --force must still tear it down
        assert not mw.path.exists()


def test_member_worktree_is_frozen() -> None:
    mw = MemberWorktree(path=Path("/x"), branch="b", role="r")
    with pytest.raises(Exception):
        mw.role = "other"  # type: ignore[misc]
