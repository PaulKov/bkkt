from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from ...ports import FileSystem
from ...utils import flatten_dict

from .models import ApplyItem
from .resolve_items import make_virtual_item
from .templates import extract_vars_from_requested, try_resolve_to_template


def resolve_missing_template(
    *,
    requested_path: Path,
    expand_templates: bool,
    fs: FileSystem | None,
) -> Optional[Tuple[ApplyItem, Tuple[Path, Path]]]:
    """Try to resolve missing requested path as a virtual instance of an existing template."""

    if not expand_templates:
        return None

    tmpl = try_resolve_to_template(requested_path, fs=fs)
    if tmpl is None:
        return None

    inst_vars = extract_vars_from_requested(tmpl, requested_path)
    flat = flatten_dict(inst_vars)
    src = {k: "auto:requested_filename" for k in flat.keys()}

    item = make_virtual_item(
        template_path=tmpl,
        requested_path=requested_path,
        runtime_vars=inst_vars,
        runtime_var_sources=src,
    )
    mapping = (requested_path.resolve(), tmpl.resolve())
    return item, mapping
