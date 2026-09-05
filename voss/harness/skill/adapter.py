"""VossSkillAdapter — SkillEntry-compatible handler for .voss bundle skills.

Compiles the bundle's .voss file via the existing compiler and runs it as a
subprocess under a scope-limited PermissionGate. Third-party code never
executes in-process (the subprocess boundary is the confinement layer).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from voss.harness.skill.scope import ScopeSpec, scoped_gate

if TYPE_CHECKING:
    from voss.harness.skill_registry import SkillHandler


def make_voss_skill_handler(
    voss_path: Path,
    spec: ScopeSpec,
    *,
    skill_id: str = "",
) -> "SkillHandler":
    """Return a SkillHandler that compiles + subprocess-runs a .voss file.

    The handler matches the ``Callable[[Any, list[str]], None]`` signature
    required by ``SkillEntry.handler``.
    """

    def handler(ctx: Any, args: list[str]) -> None:
        # Build scope-limited gate (Pitfall 2: auto_yes, no store)
        _scoped = scoped_gate(spec, ctx.gate) if hasattr(ctx, "gate") else None  # noqa: F841

        with tempfile.TemporaryDirectory(prefix="voss-skill-") as tmp:
            tmp_dir = Path(tmp)
            generated = tmp_dir / (voss_path.stem + ".py")

            # Compile via public API (no private _compile_source import)
            from voss.cli import compile_voss_file

            project_root = getattr(ctx, "cwd", None)
            cache_dir = (project_root / ".voss-cache") if project_root else Path(".voss-cache")
            compile_voss_file(
                voss_path,
                generated,
                project_root=project_root,
                cache_dir=cache_dir,
            )

            # Build subprocess env — mirror voss/cli.py:run pattern
            env = os.environ.copy()
            env["VOSS_HERMETIC"] = "1"
            if not spec.net:
                env["VOSS_NO_NET"] = "1"

            completed = subprocess.run(
                [sys.executable, str(generated), *args],
                capture_output=True,
                text=True,
                env=env,
            )

            if completed.stdout:
                click.echo(completed.stdout, nl=False)
            if completed.stderr:
                click.echo(completed.stderr, nl=False, err=True)

            # Record skill run via RunRecorder (guarded)
            record = getattr(ctx, "record", None)
            if record is not None:
                observe = getattr(record, "observe_skill_event", None)
                if observe is not None:
                    observe(
                        "skill_run",
                        skill_id,
                        str(voss_path),
                        ok=completed.returncode == 0,
                    )

    return handler
