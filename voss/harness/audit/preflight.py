"""O6 blocking preflight: verify O1-O5 audit inputs exist before execution.

Returns a structured result with ok, missing, and warnings. If not ok,
downstream O6 code must not run.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ok: bool
    missing: tuple[str, ...]
    warnings: tuple[str, ...]


# Surface name → (module path, attribute name)
_REQUIRED_SURFACES: dict[str, tuple[str, str]] = {
    "SessionTreeNode": ("voss.harness.session_tree", "SessionTreeNode"),
    "ReviewerVerdict": ("voss.harness.board.verdict", "ReviewerVerdict"),
    "Reviewer": ("voss.harness.board.verdict", "Reviewer"),
    "Card": ("voss.harness.board.machine", "Card"),
    "Ticket": ("voss.harness.em.tickets", "Ticket"),
    "RoutingRationale": ("voss.harness.em.tickets", "RoutingRationale"),
    "KillRecord": ("voss.harness.em.tickets", "KillRecord"),
    "RescopeRecord": ("voss.harness.em.tickets", "RescopeRecord"),
    "RunFinal": ("voss.harness.em.tickets", "RunFinal"),
}

_REQUIRED_NODE_FIELDS: tuple[str, ...] = (
    "transitions",
    "retry_notes",
    "terminal_state",
    "envelope",
)


def run_o6_preflight() -> PreflightResult:
    """Check that all O1-O5 audit surfaces are importable and well-shaped."""
    missing: list[str] = []
    warnings: list[str] = []

    for name, (mod_path, attr) in _REQUIRED_SURFACES.items():
        try:
            mod = importlib.import_module(mod_path)
        except ImportError:
            missing.append(f"{name} (module {mod_path} not importable)")
            continue
        if not hasattr(mod, attr):
            missing.append(f"{name} (attribute {attr} missing from {mod_path})")

    # Check SessionTreeNode has expected fields for audit data.
    try:
        from voss.harness.session_tree import SessionTreeNode
        import dataclasses as _dc

        node_fields = {f.name for f in _dc.fields(SessionTreeNode)}
        for fname in _REQUIRED_NODE_FIELDS:
            if fname not in node_fields:
                missing.append(
                    f"SessionTreeNode.{fname} (field missing from session_tree)"
                )
    except ImportError:
        pass  # Already caught above.

    # Check EM ticket kinds are discoverable.
    try:
        from voss.harness.em.tickets import (
            KillRecord as _KR,
            RescopeRecord as _RR,
            RoutingRationale as _Rt,
            Ticket as _Tk,
        )

        for cls, expected_kind in [
            (_Tk, "em.ticket"),
            (_Rt, "em.routing"),
            (_KR, "em.kill"),
            (_RR, "em.rescope"),
        ]:
            import dataclasses as _dc2

            fields = {f.name for f in _dc2.fields(cls)}
            if "kind" not in fields:
                missing.append(f"{cls.__name__}.kind field missing")
    except ImportError:
        pass  # Already caught above.

    # Check ReviewerVerdict has source field.
    try:
        from voss.harness.board.verdict import ReviewerVerdict as _RV
        import dataclasses as _dc3

        rv_fields = {f.name for f in _dc3.fields(_RV)}
        for fname in ("source", "verdict", "conf", "tier"):
            if fname not in rv_fields:
                missing.append(f"ReviewerVerdict.{fname} field missing")
    except ImportError:
        pass

    return PreflightResult(
        ok=len(missing) == 0,
        missing=tuple(missing),
        warnings=tuple(warnings),
    )
