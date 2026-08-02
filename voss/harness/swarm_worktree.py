"""Git-worktree-per-member lifecycle for the R3 all-CLI swarm.

Under R3 (see `SWARM-RECONCILIATION.md`) every swarm member is a black-box CLI
(`claude`/`codex`/`opencode`/…) that writes to disk directly — voss cannot gate
its writes in-process the way it gates a native session. The reconciliation
resolves this by giving each member its **own `git worktree` checkout** as its
cwd. That buys two properties the ownership guarantee rests on:

- **attribution** — a change is attributable to exactly one member (its
  worktree), with none of the racy mtime-diff heuristics a shared cwd would
  force; and
- **revertibility** — an out-of-scope write is undone with a plain
  `git restore` in that one worktree, never clobbering another member's
  concurrent legit write.

Fan-in is then a `git merge` of the member branches; VSWARM-06 overlap
validation (`swarm_store.validate_no_overlap`) guarantees disjoint
`owned_files`, which is exactly what makes that merge conflict-free.

This module is subprocess-`git` only (mirroring `voss.layout._git_rev_parse`),
holds no global state, and never reads `.voss` — the file-bus lives in the MAIN
checkout and the host hands members their task inline, so worktrees stay
hermetic.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class NotAGitRepoError(RuntimeError):
    """`repo_root` is not inside a git work tree, so no worktree can be added."""


class CandidateExistsError(RuntimeError):
    """A preserved candidate already occupies this swarm role."""


class WorktreeMergeConflict(RuntimeError):
    """`git merge` of a member branch reported a conflict.

    Under R3 this should not happen — VSWARM-06 guarantees disjoint
    `owned_files`, so a conflict means that invariant was violated upstream (or
    the member wrote outside its scope and the watcher did not revert it). Raised
    with the conflicting paths so the operator escalation has something concrete.
    """


@dataclass(frozen=True)
class MemberWorktree:
    """A member's isolated checkout. `path` is its cwd; `branch` is fanned in."""

    path: Path
    branch: str
    role: str


def _git(repo: Path, *args: str) -> str:
    """Run `git -C <repo> <args>`, returning stripped stdout.

    Raises CalledProcessError on non-zero exit so callers can inspect stderr;
    only the not-a-repo case is special-cased into a clear domain error.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            ["git", "-C", str(repo), *args],
            result.stdout,
            result.stderr,
        )
    return result.stdout.strip()


def _require_repo(repo_root: Path) -> None:
    """Fail fast with a clear error if `repo_root` is not a git work tree."""
    try:
        inside = _git(repo_root, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.SubprocessError):
        inside = ""
    if inside != "true":
        raise NotAGitRepoError(f"{repo_root} is not a git work tree")


def _branch_name(swarm_id: str, role_name: str) -> str:
    return f"swarm/{swarm_id}/{role_name}"


def _worktrees_dir(repo_root: Path, swarm_id: str) -> Path:
    # Kept under .voss/swarm/<id>/worktrees so the whole swarm's scratch state is
    # co-located with its file-bus + audit, and trivially cleanable per swarm.
    return repo_root / ".voss" / "swarm" / swarm_id / "worktrees"


def create_member_worktree(
    repo_root: Path, swarm_id: str, role_name: str
) -> MemberWorktree:
    """`git worktree add` a fresh checkout for one member on a new branch.

    The branch (`swarm/<swarm_id>/<role_name>`) is created off the current HEAD,
    so every member starts from the same base and fan-in is a straightforward
    merge back into HEAD. A pre-existing worktree or branch is treated as a
    preserved candidate and must be handled explicitly before this role is run
    again; automatic cleanup could destroy unreviewed work.
    """
    repo_root = repo_root.resolve()
    _require_repo(repo_root)

    branch = _branch_name(swarm_id, role_name)
    wt_path = _worktrees_dir(repo_root, swarm_id) / role_name
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    branch_exists = bool(_git(repo_root, "branch", "--list", branch))
    if wt_path.exists() or branch_exists:
        raise CandidateExistsError(
            f"candidate already exists for swarm {swarm_id!r} role {role_name!r}"
        )

    _git(repo_root, "worktree", "add", "-b", branch, str(wt_path), "HEAD")
    return MemberWorktree(path=wt_path.resolve(), branch=branch, role=role_name)


def list_member_worktrees(repo_root: Path, swarm_id: str) -> list[MemberWorktree]:
    """All member worktrees currently registered for `swarm_id`.

    Parses `git worktree list --porcelain` (the stable machine format) and keeps
    only entries living under this swarm's worktrees dir, recovering the role
    from the directory name and the branch from the porcelain `branch` line.
    """
    repo_root = repo_root.resolve()
    _require_repo(repo_root)
    base = _worktrees_dir(repo_root, swarm_id).resolve()

    out = _git(repo_root, "worktree", "list", "--porcelain")
    members: list[MemberWorktree] = []
    cur_path: Path | None = None
    cur_branch: str = ""
    for line in out.splitlines() + [""]:  # trailing "" flushes the last record
        if line.startswith("worktree "):
            cur_path = Path(line[len("worktree ") :]).resolve()
            cur_branch = ""
        elif line.startswith("branch "):
            # e.g. "branch refs/heads/swarm/<id>/<role>"
            cur_branch = line[len("branch ") :].removeprefix("refs/heads/")
        elif line == "" and cur_path is not None:
            try:
                rel = cur_path.relative_to(base)
            except ValueError:
                cur_path = None
                continue
            members.append(
                MemberWorktree(path=cur_path, branch=cur_branch, role=rel.parts[0])
            )
            cur_path = None
    members.sort(key=lambda m: m.role)
    return members


def changed_files(mw: MemberWorktree) -> list[str]:
    """Repo-relative paths the member changed in its worktree vs its base.

    Uses `git status --porcelain` so it covers tracked edits, deletes, AND
    untracked new files (a CLI creating an out-of-scope file is the exact case
    the watcher must catch). Paths are returned relative to the worktree root,
    which equals the member's cwd — the same frame `owned_files` is expressed in.
    """
    # NOT via _git(): porcelain status lines begin with a significant leading
    # space (e.g. " M path"), which _git's .strip() would eat and shift the path
    # slice. Run raw and slice each NUL-separated entry's 2-char XY + space.
    result = subprocess.run(
        ["git", "-C", str(mw.path), "status", "--porcelain", "-z"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, ["git", "status"], result.stdout, result.stderr
        )
    files: list[str] = []
    # -z gives NUL-separated entries; a rename record carries two NUL fields
    # (old\0new) but a swarm member's edits are creates/edits/deletes, so the
    # simple split is sufficient and each entry's path starts at offset 3.
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        files.append(entry[3:])
    return files


def merge_member(repo_root: Path, mw: MemberWorktree) -> None:
    """Fan-in: merge the member's branch into the main checkout's HEAD branch.

    `--no-ff` keeps each member's contribution as a visible merge in history.
    Disjoint `owned_files` (VSWARM-06) make this conflict-free; if git still
    reports a conflict the merge is aborted (leaving HEAD clean) and
    `WorktreeMergeConflict` is raised with the conflicting paths.
    """
    repo_root = repo_root.resolve()
    _require_repo(repo_root)
    try:
        _git(
            repo_root,
            "merge",
            "--no-ff",
            "-m",
            f"swarm: fan-in {mw.role}",
            mw.branch,
        )
    except subprocess.CalledProcessError as exc:
        conflicts = _conflicted_paths(repo_root)
        # Leave HEAD in a clean state — a half-merged repo is worse than no merge.
        _safe(repo_root, "merge", "--abort")
        detail = ", ".join(conflicts) if conflicts else (exc.stderr or "").strip()
        raise WorktreeMergeConflict(
            f"merging member {mw.role!r} (branch {mw.branch!r}) conflicted on [{detail}]"
        ) from exc


def remove_member_worktree(repo_root: Path, mw: MemberWorktree) -> None:
    """Tear down a member: `git worktree remove --force` + delete its branch."""
    repo_root = repo_root.resolve()
    _require_repo(repo_root)
    _safe_remove_worktree(repo_root, mw.path)
    _safe_delete_branch(repo_root, mw.branch)


# ---------------------------------------------------------------------------
# Internal best-effort helpers (teardown / recovery must not raise on absence)
# ---------------------------------------------------------------------------
def _conflicted_paths(repo: Path) -> list[str]:
    try:
        out = _git(repo, "diff", "--name-only", "--diff-filter=U")
    except (OSError, subprocess.SubprocessError):
        return []
    return [p for p in out.splitlines() if p]


def _safe(repo: Path, *args: str) -> None:
    """Run a git command, swallowing failure — for teardown/cleanup paths."""
    try:
        _git(repo, *args)
    except (OSError, subprocess.SubprocessError):
        pass


def _safe_remove_worktree(repo: Path, path: Path) -> None:
    _safe(repo, "worktree", "remove", "--force", str(path))
    # `worktree remove` can leave a stale prune entry if the dir vanished; prune
    # so a subsequent add on the same path is never blocked.
    _safe(repo, "worktree", "prune")


def _safe_delete_branch(repo: Path, branch: str) -> None:
    _safe(repo, "branch", "-D", branch)


__all__ = [
    "MemberWorktree",
    "NotAGitRepoError",
    "WorktreeMergeConflict",
    "create_member_worktree",
    "list_member_worktrees",
    "changed_files",
    "merge_member",
    "remove_member_worktree",
]
