from __future__ import annotations

# Backwards-compatible facade:
#   from connectctl.validation.policies import PolicyIssue, lint_policies, validate_policies, build_policies_lint_markdown

from .policies_models import PolicyIssue
from .policies_lint import lint_policies
from .policies_markdown import build_policies_lint_markdown
from .policies_validate import validate_policies

__all__ = [
    "PolicyIssue",
    "lint_policies",
    "validate_policies",
    "build_policies_lint_markdown",
]
