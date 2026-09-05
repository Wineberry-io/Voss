from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal as _signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from voss_runtime import ToolDescriptor, tool

from .net import NetSession
from .sandbox import jail_path, shell_allowed, split_command, SandboxError
from .tui.widgets.diff_modal import Hunk
from .memory_store import MemoryStore


SHELL_OUTPUT_CAP_BYTES = 30720

# V1-01 / D-05: the EXACTLY nine capability groups every ToolEntry must declare.
# No tenth bucket (e.g. "orchestration") — the subagent/task family maps to
# "review" (the run-artifact / meta-work bucket). Group + scope_requirements are
# auditable data at registration (D-01), never name-prefix guesswork.
CAPABILITY_GROUPS = ("fs", "git", "test", "shell", "net", "code", "memory", "review", "mcp")

_AUDIT_BEHAVIORS = ("full", "redact_args", "metadata_only")


def _line_anchor(line: str) -> str:
    """First 8 hex of SHA-256 of a line's raw content (no newline). Mirrors
    crates/voss-tools/src/anchor.rs for hashline-edit parity."""
    return hashlib.sha256(line.encode("utf-8", "surrogatepass")).hexdigest()[:8]


def _annotate(text: str) -> str:
    """Render text with a per-line `{anchor}│{line}` gutter. Canonical line
    list is `split("\\n")`; a trailing empty segment is not emitted."""
    segs = text.split("\n")
    n = len(segs)
    out: list[str] = []
    for i, seg in enumerate(segs):
        if i + 1 == n and seg == "":
            break
        out.append(f"{_line_anchor(seg)}│{seg}")
    return "\n".join(out) + ("\n" if out else "")


def _resolve_anchor(segs: list[str], anchor: str) -> tuple[int | None, str]:
    """Resolve anchor to a unique line index. Returns (index, "") or
    (None, error_message)."""
    hits = [i for i, seg in enumerate(segs) if _line_anchor(seg) == anchor]
    if len(hits) == 0:
        return None, f"anchor `{anchor}` not found (stale — re-read with annotate=true)"
    if len(hits) > 1:
        lns = ",".join(str(i + 1) for i in hits)
        return None, f"anchor `{anchor}` matches lines {lns} — ambiguous, use `old` instead"
    return hits[0], ""


@dataclass(frozen=True)
class ToolEntry:
    """Registry entry pairing a ToolDescriptor with structural classification.

    `is_mutating` drives mode-tier denial in PermissionGate (see D-06):
    classification is data at registration, not name-pattern matching.

    `is_network` drives the allow_net gate in PermissionGate (T3-02). It is
    independent of `is_mutating`: a network tool may be read-only
    (web_fetch) yet still must clear the allow_net check.
    """

    descriptor: ToolDescriptor
    is_mutating: bool
    # V1-01 CAP-01: `group` is REQUIRED (no default) so every construction site
    # must tag it explicitly (D-01). It sits before the defaulted fields so the
    # frozen dataclass allows a required field here; an untagged site TypeErrors
    # loudly rather than mislabeling silently.
    group: str
    is_network: bool = False
    # CAP-03: coarse permission buckets (group-level only, D-03) drawn from
    # CAPABILITY_GROUPS. CAP-06: audit shaping. is_stateful → order-dependent.
    scope_requirements: tuple[str, ...] = ()
    audit_behavior: str = "full"
    is_stateful: bool = False
    output_schema: dict | None = None

    def __post_init__(self) -> None:
        if self.group not in CAPABILITY_GROUPS:
            raise ValueError(
                f"ToolEntry group {self.group!r} not in CAPABILITY_GROUPS {CAPABILITY_GROUPS}"
            )
        for s in self.scope_requirements:
            if s not in CAPABILITY_GROUPS:
                raise ValueError(
                    f"ToolEntry scope_requirement {s!r} not in CAPABILITY_GROUPS"
                )
        if self.audit_behavior not in _AUDIT_BEHAVIORS:
            raise ValueError(
                f"ToolEntry audit_behavior {self.audit_behavior!r} not in {_AUDIT_BEHAVIORS}"
            )

    @property
    def name(self) -> str:
        return self.descriptor.name

    @property
    def description(self) -> str:
        return self.descriptor.description

    @property
    def parameters(self) -> dict:
        return self.descriptor.parameters

    def capability_dict(self) -> dict:
        """CAP-02 normalized capability view for downstream CLI/MCP/recorder."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
            "output_schema": self.output_schema,
            "is_mutating": self.is_mutating,
            "is_network": self.is_network,
            "group": self.group,
            "scope_requirements": list(self.scope_requirements),
            "audit_behavior": self.audit_behavior,
            "is_stateful": self.is_stateful,
        }

    def invoke(self, **kwargs: Any) -> Any:
        return self.descriptor.invoke(**kwargs)

    def invoke_dict(self, args: dict) -> Any:
        return self.descriptor.invoke(**args)


def _read_one_for_bundle(cwd: Path, path: str) -> str:
    """Per-slot reader for fs_read_many. Never raises; returns content OR error envelope."""
    try:
        p = jail_path(cwd, path)
    except SandboxError:
        return f"<error: path outside cwd: {path}>"
    if not p.exists():
        return f"<error: not found: {path}>"
    if p.is_dir():
        return f"<error: is a directory: {path}>"
    try:
        text = p.read_text()
    except UnicodeDecodeError:
        return f"<error: binary file: {path}>"
    if len(text) > 30720:  # 30KB cap (T2-CONTEXT.md D-13)
        text = text[:30720] + f"\n<truncated, total {len(text)} bytes>"
    return text


def attach_memory_tools(
    tools: dict[str, "ToolEntry"],
    *,
    store,
    session_id: str,
    external_service=None,
    global_store=None,
) -> None:
    """Register agent-callable durable-memory tools backed by `MemoryStore`.

    Exposes the recall/retain verbs the model can drive itself (previously
    only user/CLI-driven via /recall and /save). `memory_recall` is read-only
    (fans out concurrently); `memory_remember` writes a note (mutating). The
    store is bound to a session elsewhere; `session_id` tags written notes.

    V22-05: When `external_service` is provided, recall fuses its hits with
    durable-memory hits via reciprocal-rank fusion.

    V21 (VGMEM-*): When `global_store` is provided, recall also queries the
    cross-project global corpus and fuses those hits in; global hits render
    with a `[global]` label. `memory_remember` only ever writes the
    project-scoped `store` — the agent can never write the global corpus.
    """

    @tool(
        name="memory_recall",
        description=(
            "Search durable project memory by query. Covers past turns, "
            "ledgers, decisions, conventions, and saved notes. Optional "
            "`source` filters to one of: turns, ledgers, decisions, "
            "conventions, notes. Returns top hits with source, locator, and a "
            "short excerpt."
        ),
    )
    async def memory_recall(query: str, top_k: int = 5, source: str | None = None) -> str:
        query = query.strip()
        if not query:
            return "<error: empty query>"
        try:
            hits = store.recall(query, top_k=top_k, source=source)
        except Exception as exc:  # noqa: BLE001 — recall must not crash the turn
            return f"<error: recall failed: {exc}>"
        if external_service is not None:
            try:
                ext = external_service.query_all(query, top_k=top_k)
                if ext:
                    hits = MemoryStore._rrf_merge([hits, *ext], top_k=top_k)
            except Exception:  # noqa: BLE001 — external recall must not break the turn
                pass
        # V21 (VGMEM-*): fuse the cross-project global corpus. Global hits carry
        # a `global:` locator prefix so they survive RRF dedup distinctly and
        # render with a `[global]` label (stripped from the displayed locator).
        if global_store is not None:
            try:
                global_hits = global_store.recall(query, top_k=top_k, source=source)
                if global_hits:
                    import dataclasses as _dc

                    tagged = [_dc.replace(h, locator=f"global:{h.locator}") for h in global_hits]
                    hits = MemoryStore._rrf_merge([hits, tagged], top_k=top_k)
            except Exception:  # noqa: BLE001 — global recall must not break the turn
                pass
        if not hits:
            return "(no hits)"
        # VRNK-01: agent-path recall records retrieval telemetry (sidecar only;
        # memory files stay immutable). CLI recall stays no-touch. V23-06 wires
        # global_store telemetry post-V21 — out of scope here. Guarded so a
        # store without telemetry support (or any fs error) never breaks recall.
        record_telemetry = getattr(store, "_record_telemetry", None)
        if callable(record_telemetry):
            try:
                record_telemetry(hits)
            except Exception:  # noqa: BLE001 — telemetry must never break the turn
                pass
        lines: list[str] = []
        for h in hits:
            if h.locator.startswith("global:"):
                label = "global"
                locator = h.locator[len("global:"):]
            else:
                label = h.source
                locator = h.locator
            lines.append(f"[{label}] {locator} (score {h.score:.2f})")
            excerpt = (h.excerpt or "").replace("\n", " ")[:160]
            if excerpt:
                lines.append(f"  {excerpt}")
        return "\n".join(lines)

    @tool(
        name="memory_remember",
        description=(
            "Persist a durable note to project memory for future sessions. "
            "Use for facts, decisions, or gotchas worth recalling later. "
            "Returns the saved note id."
        ),
    )
    async def memory_remember(text: str) -> str:
        text = text.strip()
        if not text:
            return "<error: empty note>"
        try:
            path = store.write_note(text, session_id=session_id)
        except Exception as exc:  # noqa: BLE001 — persistence failure is recoverable
            return f"<error: {exc}>"
        return f"remembered: {path.name}"

    tools["memory_recall"] = ToolEntry(descriptor=memory_recall, is_mutating=False, group="memory", scope_requirements=("memory",))
    tools["memory_remember"] = ToolEntry(descriptor=memory_remember, is_mutating=True, group="memory", scope_requirements=("memory",))


def attach_code_recall_tool(tools: dict[str, "ToolEntry"], *, code_index_service) -> None:
    """Register the semantic `code_recall` tool backed by a CodeIndexService.

    Read-only concept search over the V19 code index. Distinct from M10's
    lexical `code_search` (the description steers the model accordingly).
    """

    @tool(
        name="code_recall",
        description=(
            "Semantic concept search over the code index: returns file:line-"
            "anchored chunk hits ranked by BM25+vector RRF fusion. Use for "
            "concept queries like 'where is retry handled' or 'how do we "
            "throttle requests'. For exact symbol/name lookup use "
            "`code_search` instead. Degrades to lexical-only hits before the "
            "index finishes building."
        ),
    )
    async def code_recall(query: str, top_k: int = 5) -> str:
        query = query.strip()
        if not query:
            return "<error: empty query>"
        try:
            hits = code_index_service.query(query, top_k=top_k)
        except Exception as exc:  # noqa: BLE001 — recall must not crash the turn
            return f"<error: code recall failed: {exc}>"
        if not hits:
            return "(no hits)"
        lines: list[str] = []
        for h in hits:
            # locator is code:<rel_path>:<seq> — surface as path:line_start.
            parts = h.locator.split(":")
            path = ":".join(parts[1:-1]) if len(parts) >= 3 else h.locator
            anchor = f"{path}:{h.line_start}" if h.line_start else path
            lines.append(f"[code] {anchor} (score {h.score:.2f})")
            excerpt = (h.excerpt or "").replace("\n", " ")[:160]
            if excerpt:
                lines.append(f"  {excerpt}")
        return "\n".join(lines)

    tools["code_recall"] = ToolEntry(descriptor=code_recall, is_mutating=False, group="code", scope_requirements=("code",))


def make_toolset(
    cwd: Path,
    *,
    renderer=None,
    net: NetSession | None = None,
    session_id: str | None = None,
    background_indexing: bool = True,
) -> dict[str, ToolEntry]:
    """Build the harness toolset bound to a project cwd.

    Returns a dict of tool name -> ToolEntry. Each entry carries an
    explicit `is_mutating` boolean used by PermissionGate.

    Ephemeral callers can disable background indexing so worker threads do
    not outlive and write into a temporary cwd during teardown.

    T2-04: When `renderer` is provided AND exposes `show_diff_modal`,
    `fs_edit_many` routes through the M9-05 DiffModal for per-hunk
    approval. When `renderer is None` (test-friendly path) or the
    renderer lacks `show_diff_modal` (e.g., JSON / plain renderers),
    the modal step is skipped and the tool writes after validation.
    The LLM agent never controls this kwarg — it is set by the
    in-process harness construction site (cli.py, eval/runner.py,
    subagents.py) at production startup.
    """

    @tool(name="fs_read", description="Read a UTF-8 text file from the project. Path must be inside cwd. Pass annotate=true for per-line content-hash anchors usable by fs_edit.")
    async def fs_read(path: str, annotate: bool = False) -> str:
        p = jail_path(cwd, path)
        if not p.exists():
            return f"<error: not found: {path}>"
        if p.is_dir():
            return f"<error: is a directory: {path}>"
        try:
            text = p.read_text()
        except UnicodeDecodeError:
            return f"<error: binary file: {path}>"
        return _annotate(text) if annotate else text

    @tool(
        name="fs_read_many",
        description=(
            "Read N files as one bundle. Returns sections separated by "
            "`=== {path} ===`. Per-path errors are inline (other paths "
            "still readable). Each file capped at 30KB."
        ),
    )
    async def fs_read_many(paths: list[str]) -> str:
        if not paths:
            return "<no paths requested>"
        sections: list[str] = []
        for path in paths:
            body = _read_one_for_bundle(cwd, path)
            sections.append(f"=== {path} ===\n{body}\n")
        return "\n".join(sections)

    @tool(name="fs_glob", description="List files matching a glob pattern, relative to cwd.")
    async def fs_glob(pattern: str) -> str:
        results = sorted(str(p.relative_to(cwd)) for p in cwd.glob(pattern) if p.is_file())
        return "\n".join(results) if results else "<no matches>"

    @tool(name="shell_run", description="Run an allowlisted command (no shell). Output truncated to 30KB.")
    async def shell_run(cmd: str) -> str:
        # Allowlist + metacharacter check first. shell_allowed rejects pipelines,
        # redirection, command substitution, chaining — anything that requires a
        # shell to interpret. The actual invocation uses `create_subprocess_exec`
        # so the binary is executed directly, never via `/bin/sh -c`.
        ok, reason = shell_allowed(cmd)
        if not ok:
            return f"<denied: {reason}>"
        try:
            argv = split_command(cmd)
        except SandboxError as e:
            return f"<denied: {e}>"
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    await proc.wait()
                except Exception:
                    pass
                return "<timeout: 30s>"
        except (OSError, SandboxError) as e:
            return f"<error: {e}>"
        text = out.decode("utf-8", errors="replace")
        # T5 cap: 30720 bytes via SHELL_OUTPUT_CAP_BYTES.
        if len(text) > SHELL_OUTPUT_CAP_BYTES:
            text = text[:SHELL_OUTPUT_CAP_BYTES] + f"\n<truncated, total {len(out)} bytes>"
        return f"[exit {proc.returncode}]\n{text}"

    @tool(
        name="shell_run_background",
        description=(
            "Run an allowlisted command in the background; returns a bg-NNN "
            "handle. Use shell_monitor(handle) to read incremental output and "
            "shell_signal(handle, 'INT'|'TERM') to stop it. Background jobs "
            "are reaped on session exit."
        ),
    )
    async def shell_run_background(
        cmd: str,
        no_output_deadline_s: float = 30.0,
    ) -> str:
        # Allowlist + metacharacter check first. shell_allowed rejects pipelines,
        # redirection, command substitution, chaining — anything that requires a
        # shell to interpret. The actual invocation uses `create_subprocess_exec`
        # so the binary is executed directly, never via `/bin/sh -c`.
        ok, reason = shell_allowed(cmd)
        if not ok:
            return f"<denied: {reason}>"
        try:
            argv = split_command(cmd)
        except SandboxError as e:
            return f"<denied: {e}>"
        from . import lifecycle

        return await lifecycle.register_job(
            cmd=cmd,
            argv=argv,
            cwd=cwd,
            session_id=session_id or "_nosession",
            no_output_deadline_s=no_output_deadline_s,
        )

    @tool(
        name="shell_monitor",
        description=(
            "Read incremental output from a background job by handle. since_ms "
            "is an opaque byte cursor (0 = from start); pass back the returned "
            "cursor to continue. Non-blocking. Returns [cursor N][running|exit M] "
            "then the new output."
        ),
    )
    async def shell_monitor(handle: str, since_ms: int = 0) -> str:
        from . import lifecycle

        return lifecycle.monitor_job(
            handle,
            since_ms=since_ms,
            session_id=session_id or "_nosession",
        )

    @tool(
        name="shell_signal",
        description="Send INT or TERM to a background job by handle. KILL is not supported.",
    )
    async def shell_signal(handle: str, signal: str) -> str:
        if signal == "INT":
            sig = _signal.SIGINT
        elif signal == "TERM":
            sig = _signal.SIGTERM
        else:
            return "<denied: unsupported signal>"

        from . import lifecycle

        if not lifecycle.signal_job(
            handle,
            sig,
            session_id=session_id or "_nosession",
        ):
            return f"<error: unknown handle {handle}>"
        return f"[signal {signal} -> {handle}]"

    @tool(
        name="fs_watch",
        description=(
            "Register a file-system watcher for glob patterns. Patterns are "
            "fnmatch-style matched against the full path (not recursive ** "
            "globbing); '*' spans '/'. Paths under .voss-cache are ignored."
        ),
    )
    async def fs_watch(globs: list[str], debounce_ms: int = 200) -> str:
        from . import lifecycle

        return await lifecycle.register_watcher(
            globs,
            cwd,
            session_id=session_id or "_nosession",
            debounce_ms=debounce_ms,
        )

    @tool(
        name="fs_watch_poll",
        description=(
            "Read incremental file-watch events by handle. since_ms "
            "is an opaque byte cursor (0 = from start); pass back the returned "
            "cursor to continue. Non-blocking. Returns [cursor N][watching|stopped] "
            "then JSONL event lines."
        ),
    )
    def fs_watch_poll(handle: str, since_ms: int = 0) -> str:
        from . import lifecycle

        rec = lifecycle._find_watcher(handle, session_id=session_id or "_nosession")
        if rec is None:
            return f"<error: unknown handle {handle}>"
        return lifecycle._read_log_cursor(
            Path(rec.log_path),
            since_ms,
            status=rec.status,
        )

    def _maybe_queue_rehash(*paths: str) -> None:
        # D-13 reindex trigger #2: targeted off-thread re-hash of agent-written
        # code files. Not-ready → no-op (in-flight full build covers the file).
        # Never raises and never blocks the write return path.
        # `_code_index_service` is bound later in this function body (closure
        # lookup happens at call time, after make_toolset completes).
        svc = _code_index_service
        if svc is None or not svc.is_ready():
            return
        try:
            from voss.harness.code.index import LANGUAGE_EXTS as _code_exts

            for path_str in paths:
                if Path(path_str).suffix.lower() in _code_exts:
                    svc.queue_rehash(jail_path(cwd, path_str))
        except Exception:  # noqa: BLE001 — index upkeep must never break a write
            pass

    @tool(name="fs_write", description="Write text to a file inside cwd. Creates parent dirs. Overwrites existing.")
    async def fs_write(path: str, content: str) -> str:
        p = jail_path(cwd, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        _maybe_queue_rehash(path)
        return f"wrote {len(content)} bytes to {path}"

    @tool(
        name="fs_edit",
        description=(
            "Replace text with `new` in a file. Supply either `old` (verbatim, "
            "must match exactly once) or `anchor` (line content-hash from "
            "fs_read annotate=true; add `end_anchor` for a multi-line span). "
            "Routes through the diff modal (preview-then-accept) when a TUI "
            "renderer is active; rejecting leaves the file untouched. Returns "
            "line count delta."
        ),
    )
    async def fs_edit(
        path: str,
        new: str,
        old: str | None = None,
        anchor: str | None = None,
        end_anchor: str | None = None,
    ) -> str:
        p = jail_path(cwd, path)
        if not p.exists():
            return f"<error: not found: {path}>"
        text = p.read_text()
        if old is not None and anchor is not None:
            return "<error: supply `old` OR `anchor`, not both>"
        if anchor is None and end_anchor is not None:
            return "<error: `end_anchor` requires `anchor`>"
        # Resolve the change into (new_text, replaced-old-block, 1-based start
        # line) so a single diff Hunk can be staged before any write.
        if anchor is not None:
            segs = text.split("\n")
            start, err = _resolve_anchor(segs, anchor)
            if start is None:
                return f"<error: {err}>"
            if end_anchor is not None:
                end, err = _resolve_anchor(segs, end_anchor)
                if end is None:
                    return f"<error: {err}>"
            else:
                end = start
            if end < start:
                return "<error: `end_anchor` is before `anchor`>"
            new_text = "\n".join(segs[:start] + new.split("\n") + segs[end + 1:])
            old_block = "\n".join(segs[start : end + 1])
            line_start = start + 1
        elif old is not None:
            count = text.count(old)
            if count == 0:
                return f"<error: `old` not found in {path}>"
            if count > 1:
                return f"<error: `old` matches {count} times, must be unique>"
            new_text = text.replace(old, new, 1)
            old_block = old
            line_start = text.count("\n", 0, text.find(old)) + 1
        else:
            return "<error: supply `old` or `anchor`>"

        # Preview-then-accept: stage one Hunk through the diff modal when the
        # renderer supports it (TUI). Non-textual renderers (JSON/plain/None,
        # e.g. tests) skip the modal and write after validation — same policy
        # as fs_edit_many.
        modal = getattr(renderer, "show_diff_modal", None) if renderer is not None else None
        if modal is not None:
            hunk = Hunk(
                file=path,
                start=line_start,
                lines=[f"- {ln}" for ln in (old_block.splitlines() or [""])]
                + [f"+ {ln}" for ln in (new.splitlines() or [""])],
            )
            decisions = modal([hunk], timeout_s=300.0)
            if not decisions:
                return "<denied: modal cancelled or timed out>"
            # STRICT: skip is treated as reject (matches fs_edit_many).
            if decisions[0].decision in ("reject", "skip"):
                return "<denied: edit rejected>"

        p.write_text(new_text)
        _maybe_queue_rehash(path)
        delta = new_text.count("\n") - text.count("\n")
        sign = "+" if delta >= 0 else ""
        return f"edited {path} ({sign}{delta} lines)"

    @tool(
        name="fs_edit_many",
        description=(
            "Atomically apply N edits to one file. Each `edits` entry is "
            "{old, new}; each `old` must match uniquely in the working "
            "buffer (left-to-right). Routes through the diff modal with "
            "one Hunk per edit. Rejecting OR skipping any hunk cancels "
            "the whole batch — file unchanged on disk."
        ),
    )
    async def fs_edit_many(path: str, edits: list[dict]) -> str:
        # T2-04 / PAR-03: validate-then-write-once single-file multi-edit.
        if not edits:
            return "<error: empty edits list>"
        p = jail_path(cwd, path)
        if not p.exists():
            return f"<error: not found: {path}>"
        if p.is_dir():
            return f"<error: is a directory: {path}>"
        try:
            snapshot = p.read_text()
        except UnicodeDecodeError:
            return f"<error: binary file: {path}>"

        # Phase 1: validate each edit against the CURRENT working buffer
        # (not the original snapshot — Pitfall 5: left-to-right propagation).
        buf = snapshot
        hunks: list[Hunk] = []
        for i, e in enumerate(edits):
            old = e.get("old", "")
            new = e.get("new", "")
            if not old:
                return f"<error: batch rejected at index {i}: empty `old`>"
            count = buf.count(old)
            if count == 0:
                return f"<error: batch rejected at index {i}: `old` not found>"
            if count > 1:
                return (
                    f"<error: batch rejected at index {i}: "
                    f"`old` matches {count} times>"
                )
            idx = buf.find(old)
            line_start = buf.count("\n", 0, idx) + 1
            old_lines = [f"- {ln}" for ln in (old.splitlines() or [""])]
            new_lines = [f"+ {ln}" for ln in (new.splitlines() or [""])]
            hunks.append(
                Hunk(file=path, start=line_start, lines=old_lines + new_lines)
            )
            buf = buf[:idx] + new + buf[idx + len(old):]

        # Phase 2: per-hunk modal approval (skipped when renderer lacks
        # show_diff_modal — test or non-TUI renderers).
        modal = getattr(renderer, "show_diff_modal", None) if renderer is not None else None
        if modal is not None:
            decisions = modal(hunks, timeout_s=300.0)
            if not decisions:
                return "<denied: modal cancelled or timed out>"
            for i, d in enumerate(decisions):
                # STRICT skip semantics: skip is treated as reject (resolves
                # RESEARCH.md Open Question 1 per the recommendation).
                if d.decision in ("reject", "skip"):
                    return f"<denied: hunk {i} rejected>"

        # Phase 3: atomic single write (file untouched until here).
        p.write_text(buf)
        _maybe_queue_rehash(path)
        delta = buf.count("\n") - snapshot.count("\n")
        sign = "+" if delta >= 0 else ""
        return f"edited {path} ({sign}{delta} lines, {len(edits)} hunks)"

    @tool(name="fs_grep", description="Recursively search for a regex pattern. Returns matching lines with file:line.")
    async def fs_grep(pattern: str, glob: str = "**/*") -> str:
        import re

        try:
            rx = re.compile(pattern)
        except re.error as e:
            return f"<error: bad regex: {e}>"
        hits: list[str] = []
        for p in cwd.glob(glob):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(cwd)
            except ValueError:
                continue
            try:
                for i, line in enumerate(p.read_text().splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{rel}:{i}: {line}")
                        if len(hits) >= 200:
                            break
            except (UnicodeDecodeError, OSError):
                continue
            if len(hits) >= 200:
                break
        return "\n".join(hits) if hits else "<no matches>"

    @tool(name="git_status", description="Run `git status --porcelain`.")
    async def git_status() -> str:
        return await _shell_capture(cwd, ["git", "status", "--porcelain"])

    @tool(name="git_diff", description="Run `git diff` (unstaged) or `git diff --cached` (staged) on optional path.")
    async def git_diff(staged: bool = False, path: str = "") -> str:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        if path:
            cmd.append(path)
        return await _shell_capture(cwd, cmd)

    @tool(
        name="voss_check",
        description="Run `voss check` on a .voss file or directory. Returns analyzer diagnostics.",
    )
    async def voss_check(path: str = ".") -> str:
        p = jail_path(cwd, path)
        return await _shell_capture(cwd, ["voss", "check", str(p)])

    @tool(
        name="voss_probable_inspect",
        description="Inspect recorded probable decisions for a persisted Voss session.",
    )
    async def voss_probable_inspect(
        session: str,
        decision: int | None = None,
    ) -> str:
        from voss.harness import voss_inspect

        try:
            run = voss_inspect.load_run(cwd, session)
            return voss_inspect.render_decision_sequence(
                run,
                decision_index=decision,
            )
        except (FileNotFoundError, ValueError, IndexError) as exc:
            return f"<error: {exc}>"

    @tool(
        name="voss_budget_trace",
        description="Inspect recorded per-iteration budget usage for a persisted Voss session.",
    )
    async def voss_budget_trace(session: str) -> str:
        from voss.harness import voss_inspect

        try:
            run = voss_inspect.load_run(cwd, session)
            return voss_inspect.render_budget_timeline(run)
        except (FileNotFoundError, ValueError, IndexError) as exc:
            return f"<error: {exc}>"

    @tool(
        name="voss_py_diff",
        description="Show read-only source vs generated Python for a .voss file.",
    )
    async def voss_py_diff(path: str) -> str:
        raw = path.strip()
        if not raw:
            return "<error: missing source: expected .voss file>"
        try:
            source = jail_path(cwd, raw)
        except SandboxError:
            return f"<error: path outside cwd: {raw}>"
        if not source.exists():
            return f"<error: not found: {raw}>"
        if source.is_dir():
            return f"<error: expected .voss file, got directory: {raw}>"
        if source.suffix != ".voss":
            return f"<error: expected .voss source file, got {raw}>"
        try:
            from voss.harness.voss_diff import render_voss_py_diff
        except ModuleNotFoundError as exc:
            if exc.name == "voss.harness.voss_diff":
                return "<error: voss diff core unavailable>"
            return f"<error: {exc}>"
        try:
            return render_voss_py_diff(source, cwd=cwd)
        except Exception as exc:  # noqa: BLE001
            return f"<error: {exc}>"

    @tool(
        name="record_run",
        description=(
            "(privileged) Close the current turn with semantic fields. "
            "Dispatched by the harness; never include in plan steps."
        ),
    )
    async def record_run(
        goal: str = "",
        avoided: list | None = None,
        assumptions: list | None = None,
        decisions: list | None = None,
        risks: list | None = None,
        follow_ups: list | None = None,
    ) -> str:
        return "ok"

    @tool(
        name="web_fetch",
        description=(
            "Fetch a URL via HTTP GET. Requires --allow-net. Body returned "
            "as UTF-8 text; responses >1 MB truncate; timeout clamped to "
            "[1, 120] seconds."
        ),
    )
    async def web_fetch(url: str, timeout_s: float = 30.0) -> str:
        if net is None:
            return (
                "<error: net disabled: set tools.allow_net = true in "
                "harness.toml or pass --allow-net>"
            )
        return await net.fetch(url, timeout_s=timeout_s)

    @tool(
        name="web_search",
        description=(
            "Search the web via Brave Search. Requires --allow-net and "
            "BRAVE_SEARCH_API_KEY env var. Returns a numbered bundle of "
            "{count} results."
        ),
    )
    async def web_search(query: str, count: int = 10) -> str:
        if not os.environ.get("BRAVE_SEARCH_API_KEY", "").strip():
            return "<error: web_search disabled: set BRAVE_SEARCH_API_KEY env var>"
        if net is None:
            return (
                "<error: net disabled: set tools.allow_net = true in "
                "harness.toml or pass --allow-net>"
            )
        return await net.search(query, count)

    result = {
        "fs_read": ToolEntry(descriptor=fs_read, is_mutating=False, group="fs", scope_requirements=("fs",)),
        "fs_read_many": ToolEntry(descriptor=fs_read_many, is_mutating=False, group="fs", scope_requirements=("fs",)),
        "fs_glob": ToolEntry(descriptor=fs_glob, is_mutating=False, group="fs", scope_requirements=("fs",)),
        "fs_grep": ToolEntry(descriptor=fs_grep, is_mutating=False, group="fs", scope_requirements=("fs",)),
        "fs_write": ToolEntry(descriptor=fs_write, is_mutating=True, group="fs", scope_requirements=("fs",)),
        "fs_edit": ToolEntry(descriptor=fs_edit, is_mutating=True, group="fs", scope_requirements=("fs",)),
        "fs_edit_many": ToolEntry(descriptor=fs_edit_many, is_mutating=True, group="fs", scope_requirements=("fs",)),
        "shell_run": ToolEntry(descriptor=shell_run, is_mutating=True, group="shell", scope_requirements=("shell",)),
        "shell_run_background": ToolEntry(
            descriptor=shell_run_background,
            is_mutating=True,
            group="shell",
            scope_requirements=("shell",),
            is_stateful=True,
        ),
        "shell_monitor": ToolEntry(descriptor=shell_monitor, is_mutating=False, group="shell", scope_requirements=("shell",), is_stateful=True),
        "shell_signal": ToolEntry(descriptor=shell_signal, is_mutating=True, group="shell", scope_requirements=("shell",), is_stateful=True),
        "fs_watch": ToolEntry(descriptor=fs_watch, is_mutating=False, group="fs", scope_requirements=("fs",), is_stateful=True),
        "fs_watch_poll": ToolEntry(descriptor=fs_watch_poll, is_mutating=False, group="fs", scope_requirements=("fs",), is_stateful=True),
        "git_status": ToolEntry(descriptor=git_status, is_mutating=False, group="git", scope_requirements=("git",)),
        "git_diff": ToolEntry(descriptor=git_diff, is_mutating=False, group="git", scope_requirements=("git",)),
        "voss_check": ToolEntry(descriptor=voss_check, is_mutating=False, group="test", scope_requirements=("test",)),
        "voss_probable_inspect": ToolEntry(
            descriptor=voss_probable_inspect,
            is_mutating=False,
            group="test",
            scope_requirements=("test",),
        ),
        "voss_budget_trace": ToolEntry(
            descriptor=voss_budget_trace,
            is_mutating=False,
            group="test",
            scope_requirements=("test",),
        ),
        "voss_py_diff": ToolEntry(
            descriptor=voss_py_diff,
            is_mutating=False,
            group="test",
            scope_requirements=("test",),
        ),
        # record_run writes the run artifact (potentially large payloads); audit
        # keeps metadata only to avoid echoing the full run blob into the log.
        "record_run": ToolEntry(descriptor=record_run, is_mutating=True, group="review", scope_requirements=("review",), audit_behavior="metadata_only"),
        "web_fetch": ToolEntry(
            descriptor=web_fetch, is_mutating=False, is_network=True, group="net", scope_requirements=("net",)
        ),
        "web_search": ToolEntry(descriptor=web_search, is_mutating=False, is_network=True, group="net", scope_requirements=("net",)),
    }
    if net is not None:
        _merge_mcp_tools(result, cwd)

    # --- M10-04 Code Intelligence tools (read-only) ---
    try:
        from voss.harness.code.service import CodeIntelService as _CodeIntelService
    except Exception:
        _CodeIntelService = None  # type: ignore

    def _code_service():
        if _CodeIntelService is None:
            raise RuntimeError("code intelligence not available (install voss[code]?)")
        return _CodeIntelService.for_cwd(cwd, session_id=session_id)

    @tool(name="code_search", description="Structural code search using ast-grep (with regex fallback).")
    async def code_search(pattern: str, path: str = ".", max_results: int = 50) -> str:
        svc = _code_service()
        res = await svc.search(pattern, path=path, max_results=max_results)
        return json.dumps(res, indent=2)

    @tool(name="find_definition", description="Find definition of a symbol using LSP + index.")
    async def find_definition(symbol: str, path: str | None = None) -> str:
        svc = _code_service()
        res = await svc.find_definition(symbol, path=path)
        return json.dumps(res, indent=2)

    @tool(name="find_references", description="Find references to a symbol using LSP + index.")
    async def find_references(symbol: str, path: str | None = None, max_results: int = 50) -> str:
        svc = _code_service()
        res = await svc.find_references(symbol, path=path, max_results=max_results)
        return json.dumps(res, indent=2)

    @tool(name="code_refresh", description="Rebuild the project code index (cache only, read-only to source).")
    async def code_refresh(paths: list[str] | None = None) -> str:
        svc = _code_service()
        res = await svc.code_refresh(paths)
        return json.dumps(res, indent=2)

    result["code_search"] = ToolEntry(descriptor=code_search, is_mutating=False, group="code", scope_requirements=("code",))
    result["find_definition"] = ToolEntry(descriptor=find_definition, is_mutating=False, group="code", scope_requirements=("code",))
    result["find_references"] = ToolEntry(descriptor=find_references, is_mutating=False, group="code", scope_requirements=("code",))
    result["code_refresh"] = ToolEntry(descriptor=code_refresh, is_mutating=False, group="code", scope_requirements=("code",))

    # --- V19-03 semantic code recall (VSEM-03/04) ---
    # ONE held service (one Chroma client) per toolset; the accessor threads
    # session_id through and kicks off the background build so session start
    # never blocks on the embedding cold-load.
    if _CodeIntelService is not None and background_indexing:
        try:
            # Construct directly — NOT via _code_service()/for_cwd(), whose
            # synchronous M10 build_index walks the cwd on the boot thread
            # (an os.walk over a large non-git cwd hangs `voss chat` before
            # the TUI appears). build_index stays lazy in the tool calls.
            _code_index_service = _CodeIntelService(
                cwd, session_id=session_id
            )._get_code_index_service()
        except Exception:  # noqa: BLE001 — missing code subsystem degrades cleanly
            _code_index_service = None
    else:
        _code_index_service = None
    if _code_index_service is not None:
        attach_code_recall_tool(result, code_index_service=_code_index_service)

    # --- V22-05 external-source recall ---
    if background_indexing:
        try:
            from voss.harness.recall.external_index import ExternalRecallService

            external_service = ExternalRecallService(cwd, session_id=session_id)
            external_service.ensure_background_build()
        except Exception:  # noqa: BLE001 — external recall is optional
            pass

    return result


async def _shell_capture(cwd: Path, argv: list[str], timeout: float = 30.0) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as e:
        return f"<error: {e}>"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
        return f"<timeout: {timeout}s>"
    text = out.decode("utf-8", errors="replace")
    if len(text) > SHELL_OUTPUT_CAP_BYTES:
        text = text[:SHELL_OUTPUT_CAP_BYTES] + f"\n<truncated, total {len(out)} bytes>"
    return f"[exit {proc.returncode}]\n{text}"


def _merge_mcp_tools(result: dict[str, ToolEntry], cwd: Path) -> None:
    try:
        from voss.harness import cognition as cognition_mod
        from voss.harness import telemetry
        from voss.harness.mcp import McpClient, load_mcp_config, register_mcp_tools
    except Exception as exc:  # noqa: BLE001
        _emit_mcp_boot_error("import", exc)
        return

    try:
        mcp_config = load_mcp_config(cwd)
        if mcp_config is None or not mcp_config.servers:
            return

        client = McpClient(mcp_config)
        client.set_cwd(cwd)

        async def launch_all() -> None:
            for server_name in mcp_config.servers:
                try:
                    await client.ensure_launched(server_name)
                except Exception as exc:  # noqa: BLE001
                    if telemetry.enabled():
                        telemetry.emit(
                            "mcp.launch_error",
                            "warn",
                            data={
                                "server": server_name,
                                "error": f"{type(exc).__name__}: {exc}",
                            },
                        )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(launch_all())
        else:
            if telemetry.enabled():
                telemetry.emit(
                    "mcp.boot_error",
                    "warn",
                    data={"error": "make_toolset called from running event loop"},
                )
            return

        bundle = cognition_mod.load(cwd)
        permissions_mcp = bundle.permissions.mcp if bundle.permissions else {}
        result.update(register_mcp_tools(mcp_config, permissions_mcp, client))
    except Exception as exc:  # noqa: BLE001
        _emit_mcp_boot_error("boot", exc)


def _emit_mcp_boot_error(stage: str, exc: Exception) -> None:
    from voss.harness import telemetry

    if telemetry.enabled():
        telemetry.emit(
            "mcp.boot_error",
            "warn",
            data={"stage": stage, "error": f"{type(exc).__name__}: {exc}"},
        )
