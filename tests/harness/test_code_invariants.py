"""
M10-06 forbidden-scope and runtime invariant regression suite.
"""


from pathlib import Path


def test_no_forbidden_watch_or_lsp_features():
    """M10 must never introduce file-watch, completion, hover, diagnostics, rename, etc."""
    forbidden = [
        "watchdog",
        "watchfiles",
        "file.?watch",
        "completion",
        "hover",
        "diagnostic",
        "rename",
        "formatting",
        "codeAction",
    ]
    root = Path("voss/harness/code")
    bad = []
    for p in root.rglob("*.py"):
        text = p.read_text()
        for f in forbidden:
            if f in text:
                bad.append(f"{p}:{f}")
    assert not bad, f"Forbidden features found in code package: {bad}"


def test_no_new_memory_classes():
    """Only the pre-existing MemoryStore from M8 is allowed."""
    import re
    from pathlib import Path

    root = Path("voss/harness")
    pattern = re.compile(r"class \w+Memory\b")
    matches = []
    for p in root.rglob("*.py"):
        for m in pattern.finditer(p.read_text()):
            name = m.group().split()[-1]
            if name != "MemoryStore":
                matches.append(f"{p}:{m.group()}")
    assert not matches, f"New memory classes introduced: {matches}"
