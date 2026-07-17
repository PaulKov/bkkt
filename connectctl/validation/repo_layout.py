"""Repo layout lint.

This module is kept as a small facade for backwards compatibility.
The implementation is split into SRP-friendly submodules.
"""

from __future__ import annotations

from .repo_layout_format import format_repo_layout_issues
from .repo_layout_lint import lint_connector_dir_pattern
from .repo_layout_models import RepoLayoutIssue

__all__ = [
    "RepoLayoutIssue",
    "lint_connector_dir_pattern",
    "format_repo_layout_issues",
]
