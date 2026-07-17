"""Naming validation and linting.

This module is intentionally kept small: the implementation is split into
several focused modules (strict validation, linting, markdown rendering).

Public API:
- validate_strict_naming
- lint_strict_naming
- build_naming_lint_markdown
"""

from __future__ import annotations

from .naming_strict import validate_strict_naming
from .naming_lint import lint_strict_naming
from .naming_markdown import build_naming_lint_markdown

__all__ = [
    "validate_strict_naming",
    "lint_strict_naming",
    "build_naming_lint_markdown",
]
