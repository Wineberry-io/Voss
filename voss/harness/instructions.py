"""Agent instruction files (AGENTS.md / CLAUDE.md) as one hashed bundle.

Pure module in the `cognition.load()` mould: never raises out of `load()`,
failures land in `InstructionBundle.load_errors`.

Discovery order (injection order): optional global files, then the project
root, then every directory from the root down to `target_dir`. Within a
directory AGENTS.md precedes CLAUDE.md. A CLAUDE.md whose only content is
`@`-imports of files already in the bundle collapses (Claude Code convention
for "CLAUDE.md just points at AGENTS.md").
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional

InstructionKind = Literal["agents", "claude", "global"]

AGENTS_FILENAME = "AGENTS.md"
CLAUDE_FILENAME = "CLAUDE.md"
GLOBAL_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("~/.codex/AGENTS.md", "agents"),
    ("~/.claude/CLAUDE.md", "claude"),
)

MAX_FILE_BYTES = 1_048_576
MAX_IMPORT_DEPTH = 3
MIN_TAIL_TOKENS = 200

DEFAULT_CONFIG: dict = {
    "enabled": True,
    "budget_tokens": 4000,
    "per_file_tokens": 2000,
    "read_global": False,
}

_IMPORT_LINE = re.compile(r"^@(\S+)\s*$")


@dataclass(frozen=True)
class InstructionFile:
    path: str
    kind: InstructionKind
    scope_dir: str
    sha256: str
    bytes: int
    tokens: int
    text: str
    imports: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstructionBundle:
    files: tuple[InstructionFile, ...] = ()
    merged_text: str = ""
    bundle_hash: str = ""
    tokens: int = 0
    truncated: tuple[str, ...] = ()
    collapsed: tuple[str, ...] = ()
    load_errors: tuple[str, ...] = ()

    @property
    def paths(self) -> list[str]:
        return [f.path for f in self.files]


def _approx_tokens(text: str) -> int:
    return max(len(text) // 4, 1) if text else 0


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def empty_bundle_hash() -> str:
    return _sha256("")


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        home = Path.home()
        try:
            return "~/" + path.resolve().relative_to(home.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def _read(path: Path, errors: list[str]) -> Optional[str]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        errors.append(f"{path}: {exc}")
        return None
    if size > MAX_FILE_BYTES:
        errors.append(f"{path}: {size} bytes exceeds {MAX_FILE_BYTES}")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: {exc}")
        return None


def _resolve_imports(
    text: str,
    base_dir: Path,
    *,
    seen: set[Path],
    depth: int,
    errors: list[str],
    imports_out: list[str],
) -> tuple[str, list[Path]]:
    """Inline `@path` import lines. Returns (text, imported_paths)."""
    out_lines: list[str] = []
    imported: list[Path] = []
    for line in text.splitlines():
        m = _IMPORT_LINE.match(line)
        if not m:
            out_lines.append(line)
            continue
        raw = m.group(1)
        target = (Path(os.path.expanduser(raw)) if raw.startswith("~") else base_dir / raw)
        try:
            target = target.resolve()
        except OSError:
            target = target.absolute()
        imports_out.append(raw)
        if target in seen:
            errors.append(f"import cycle: {target}")
            continue
        if depth >= MAX_IMPORT_DEPTH:
            errors.append(f"import depth exceeded at {target}")
            continue
        body = _read(target, errors) if target.is_file() else None
        if body is None:
            if not target.is_file():
                errors.append(f"import not found: {target}")
            continue
        imported.append(target)
        nested, nested_paths = _resolve_imports(
            body,
            target.parent,
            seen=seen | {target},
            depth=depth + 1,
            errors=errors,
            imports_out=imports_out,
        )
        imported.extend(nested_paths)
        out_lines.append(nested)
    return "\n".join(out_lines), imported


def _only_imports(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return bool(lines) and all(_IMPORT_LINE.match(ln) for ln in lines)


def _candidate_dirs(root: Path, target_dir: Optional[Path], errors: list[str]) -> list[Path]:
    dirs = [root]
    if target_dir is None:
        return dirs
    try:
        rel = target_dir.resolve().relative_to(root.resolve())
    except ValueError:
        errors.append(f"target_dir outside project root: {target_dir}")
        return dirs
    cur = root
    for part in rel.parts:
        cur = cur / part
        dirs.append(cur)
    return dirs


def load(
    cwd: Path,
    target_dir: Optional[Path | str] = None,
    *,
    config: Optional[dict] = None,
    token_count: Optional[Callable[[str], int]] = None,
) -> InstructionBundle:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    if not cfg.get("enabled", True):
        return InstructionBundle(bundle_hash=empty_bundle_hash())

    root = Path(cwd)
    errors: list[str] = []
    count = token_count or _approx_tokens
    target = Path(target_dir) if target_dir is not None else None
    if target is not None and not target.is_absolute():
        target = root / target

    candidates: list[tuple[Path, InstructionKind, str]] = []
    if cfg.get("read_global"):
        for raw, kind in GLOBAL_CANDIDATES:
            p = Path(os.path.expanduser(raw))
            if p.is_file():
                candidates.append((p, "global", raw))
    for d in _candidate_dirs(root, target, errors):
        for name, kind in ((AGENTS_FILENAME, "agents"), (CLAUDE_FILENAME, "claude")):
            p = d / name
            if p.is_file():
                candidates.append((p, kind, _display_path(p, root)))  # type: ignore[arg-type]

    files: list[InstructionFile] = []
    collapsed: list[str] = []
    seen_hashes: set[str] = set()
    seen_paths: set[Path] = set()

    for path, kind, display in candidates:
        raw = _read(path, errors)
        if raw is None:
            continue
        resolved = path.resolve()
        imports: list[str] = []
        text, imported = _resolve_imports(
            raw,
            path.parent,
            seen={resolved},
            depth=0,
            errors=errors,
            imports_out=imports,
        )
        if _only_imports(raw):
            if not imported or all(p in seen_paths for p in imported):
                collapsed.append(display)
                continue
        elif any(p in seen_paths for p in imported):
            text = _inline_imports_skipping(
                raw, path.parent, {p for p in imported if p in seen_paths}, errors
            )
        digest = _sha256(text)
        if digest in seen_hashes:
            collapsed.append(display)
            continue
        seen_hashes.add(digest)
        seen_paths.add(resolved)
        for p in imported:
            seen_paths.add(p)
        files.append(
            InstructionFile(
                path=display,
                kind=kind,
                scope_dir=_display_path(path.parent, root) if kind != "global" else "",
                sha256=digest,
                bytes=len(text.encode("utf-8")),
                tokens=count(text),
                text=text,
                imports=tuple(imports),
            )
        )

    bundle_hash = _sha256("".join(f"{f.path}:{f.sha256}\n" for f in files))

    budget = int(cfg.get("budget_tokens", DEFAULT_CONFIG["budget_tokens"]))
    per_file = int(cfg.get("per_file_tokens", DEFAULT_CONFIG["per_file_tokens"]))
    truncated: list[str] = []
    sections: list[str] = []
    remaining = budget
    for f in files:
        text = f.text
        tokens = f.tokens
        limit = min(per_file, remaining)
        if tokens > limit:
            if limit < MIN_TAIL_TOKENS:
                truncated.append(f.path)
                continue
            text = _cut_to_tokens(text, limit, count) + "\n\n(truncated: instruction budget)"
            tokens = count(text)
            truncated.append(f.path)
        remaining -= tokens
        sections.append(f"### {f.path}\n\n{text.rstrip()}\n")
        if remaining <= 0:
            remaining = 0
    merged = "\n".join(sections).rstrip() + ("\n" if sections else "")

    return InstructionBundle(
        files=tuple(files),
        merged_text=merged,
        bundle_hash=bundle_hash,
        tokens=count(merged) if merged else 0,
        truncated=tuple(truncated),
        collapsed=tuple(collapsed),
        load_errors=tuple(errors),
    )


def _inline_imports_skipping(
    text: str, base_dir: Path, skip: set[Path], errors: list[str]
) -> str:
    """Inline imports except those whose bodies an earlier bundle file already carries."""
    out: list[str] = []
    for line in text.splitlines():
        m = _IMPORT_LINE.match(line)
        if not m:
            out.append(line)
            continue
        raw = m.group(1)
        target = (Path(os.path.expanduser(raw)) if raw.startswith("~") else base_dir / raw)
        try:
            target = target.resolve()
        except OSError:
            target = target.absolute()
        if target in skip:
            continue
        body = _read(target, errors) if target.is_file() else None
        if body is not None:
            out.append(body)
    return "\n".join(out)


def _cut_to_tokens(text: str, limit: int, count: Callable[[str], int]) -> str:
    lo, hi = 0, len(text)
    best = ""
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = text[:mid]
        if count(candidate) <= limit:
            best = candidate
            lo = mid
        else:
            hi = mid - 1
    return best.rstrip()
