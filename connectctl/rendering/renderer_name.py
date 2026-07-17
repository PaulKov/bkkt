from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..exceptions import RenderError


_DOT_STYLE_ENV_PREFIX_RE = re.compile(r"^(dev|stage|prod)\.", re.IGNORECASE)


def is_dot_style_env_manifest(path: Path) -> bool:
    """Return True when file name looks like dot-style env manifest: dev.<...>.json."""

    return path.suffix.lower() == ".json" and bool(
        _DOT_STYLE_ENV_PREFIX_RE.match(path.name)
    )


def infer_name_from_filename(path: Path) -> Optional[str]:
    """Infer connector name from dot-style env manifest filename.

    Example: prod.payments.orders.source.postgres.cdc.0.json -> prod.payments.orders.source.postgres.cdc.0
    """

    if not is_dot_style_env_manifest(path):
        return None
    return path.stem


def guard_against_cyclic_name_reference(name: str, *, env_file: Path) -> None:
    """Prevent a common foot-gun: `name` referencing `${connector.name}`.

    `connector.name` is derived from the manifest name itself, so referencing it in `name`
    can never be resolved.
    """

    if re.search(r"\$\{[^}]*\b(?:global\.)?connector\.name\b[^}]*\}", name):
        raise RenderError(
            "Cyclic reference detected in manifest 'name': it references connector.name. "
            "The placeholder ${connector.name} is derived from the manifest name itself. "
            "Fix: remove 'name' (dot-style manifests can infer it from the filename) or "
            "construct 'name' from other vars (env/domain/dataset/system/index). "
            f"File: {env_file}"
        )
