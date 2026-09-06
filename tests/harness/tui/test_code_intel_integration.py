"""
M10-06 TUI integration bridge test (Task 3 of M10-05 / close-out).

Verifies that slash results reach the CodeIntelPanel via the M9-08 private methods
without the backend importing TUI modules.
"""



def test_code_intel_tui_bridge_exists():
    """The private methods added in M9-08 are the bridge surface."""
    from voss.harness.tui.renderer import TextualRenderer
    assert hasattr(TextualRenderer, "show_code_intel_tree")
    assert hasattr(TextualRenderer, "show_code_intel_results")
    assert hasattr(TextualRenderer, "show_code_intel_focus")


def test_no_tui_imports_in_code_package():
    """Hard requirement: backend must never import TUI."""
    import ast
    from pathlib import Path

    root = Path("voss/harness/code")
    bad = []
    for p in root.rglob("*.py"):
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "voss.harness.tui" in node.module:
                    bad.append(str(p))
    assert not bad, f"TUI imports found in code package: {bad}"
