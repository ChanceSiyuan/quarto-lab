"""Shared value objects for trusted-knowledge parsing and validation."""

from __future__ import annotations


class Diagnostic(str):
    """A sortable source diagnostic that remains CLI-compatible as a string."""

    file: str
    line: int
    column: int
    code: str
    message: str

    def __new__(
        cls,
        *,
        file: str,
        line: int,
        column: int,
        code: str,
        message: str,
    ) -> Diagnostic:
        rendered = f"{file}:{line}:{column} [{code}] {message}"
        diagnostic = super().__new__(cls, rendered)
        diagnostic.file = file
        diagnostic.line = line
        diagnostic.column = column
        diagnostic.code = code
        diagnostic.message = message
        return diagnostic

    @property
    def sort_key(self) -> tuple[str, int, int, str, str]:
        return (self.file, self.line, self.column, self.code, self.message)
