from __future__ import annotations
from dataclasses import dataclass

class VossError(Exception):
    """Base for all voss compiler errors."""

@dataclass
class VossParseError(VossError):
    file: str
    line: int
    col: int
    expected: list[str]
    got: str
    hint: str | None = None
    source_excerpt: str = ""

    def __post_init__(self) -> None:
        msg = f"{self.file}:{self.line}:{self.col}: parse error: expected {', '.join(self.expected) or '<input>'}, got {self.got}"
        if self.hint:
            msg += f"\n  hint: {self.hint}"
        if self.source_excerpt:
            msg += f"\n{self.source_excerpt}"
        super().__init__(msg)
