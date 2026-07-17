from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from ..exceptions import ValidationError
from ..models import ConnectorManifest, Environment
from .policies_lint import lint_policies


def validate_policies(
    manifest: ConnectorManifest,
    *,
    env: Optional[Environment] = None,
    layers: Optional[Sequence[Path]] = None,
) -> None:
    """Поднять ValidationError, если есть policy issues с severity=error."""
    issues = lint_policies(manifest, env=env, layers=layers)
    errors = [i for i in issues if i.severity == "error"]
    if not errors:
        return

    # Keep error message short-ish (CLI friendly)
    sample = errors[:5]
    details = "; ".join(
        [
            f"{e.policy} ({e.key or '-'})"
            + (f" in {e.file_path}" if e.file_path else "")
            for e in sample
        ]
    )
    more = "" if len(errors) <= 5 else f" (+{len(errors) - 5} more)"
    raise ValidationError(
        f"Policy validation failed for {manifest.name} in env={(env or manifest.info.env).value}: {details}{more}"
    )
