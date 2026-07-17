from __future__ import annotations


from .models import DriftOptions


def options_from_args(args) -> DriftOptions:
    """Собрать :class:`~connectctl.services.drift.models.DriftOptions` из argparse args."""

    include_diffs = bool(getattr(args, "include_diffs", False))
    max_lines = int(getattr(args, "max_lines", 80))
    top_n = int(getattr(args, "top", 15))

    strict_naming = bool(getattr(args, "strict_naming", True))
    policies = bool(getattr(args, "policies", True))
    fail_on_drift = bool(getattr(args, "fail_on_drift", False))

    return DriftOptions(
        include_diffs=include_diffs,
        max_lines=max_lines,
        top_n=top_n,
        strict_naming=strict_naming,
        policies=policies,
        fail_on_drift=fail_on_drift,
    )
