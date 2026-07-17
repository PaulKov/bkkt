from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..models import ConnectorManifest, ConnectorType
from .naming_common import extract_layer_from_filename


def infer_dataset_vars(
    manifest: ConnectorManifest,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (dataset_short, dataset_full, dataset_source) best-effort.

    Priority order:
    1) For Debezium-style sources: database.dbname (ONLY if it is a literal value,
       not a config-provider placeholder like `${secretManager:...}`).
    2) For sources with placeholder dbname: infer dataset from connector_dir (best-effort).
    3) Connector name: <env>.<domain>.<dataset>....
    4) Legacy fallback: parse from manifest filename remainder.

    dataset_source values (human/debug friendly):
      - "database.dbname"   (literal value, NOT placeholder)
      - "connector_dir"    (best-effort parsing from connector_dir)
      - "name"             (3rd dot-segment of manifest.name)
      - "filename"         (legacy underscore filename fallback)
      - None                (cannot infer)
    """

    info = manifest.info
    cfg = manifest.config

    def _is_placeholder(v: str) -> bool:
        # We must NOT treat placeholders as a literal dataset name.
        # Common cases:
        #   - Kafka Connect config providers: ${secretManager:...}
        #   - env/vars placeholders in templates: ${env}, ${dbname}, ...
        s = str(v).strip()
        return s.startswith("${") and s.endswith("}")

    def _infer_from_connector_dir() -> Optional[str]:
        cd = (info.connector_dir or "").strip()
        if not cd.startswith("connector_"):
            return None
        rem = cd[len("connector_") :]
        if not rem:
            return None

        # Most common patterns:
        #   connector_<domain>__<dataset>{__...}
        #   connector_<dataset>{__...}   (short form)
        if "__" not in rem:
            # short form: connector_<dataset>
            return rem

        toks = [t for t in rem.split("__") if t]
        if not toks:
            return None
        # If domain is the first token, dataset is the second token.
        if info.domain and toks[0] == info.domain and len(toks) >= 2:
            return toks[1]
        # Generic: connector_<something>__<dataset>...
        if len(toks) >= 2:
            return toks[1]
        return toks[0]

    # 1) For Debezium-style sources, database.dbname can be a good signal,
    # but only if it is a literal string.
    dbname = cfg.get("database.dbname") if isinstance(cfg, dict) else None
    if info.connector_type == ConnectorType.source and dbname:
        if not _is_placeholder(str(dbname)):
            dbname_ds = str(dbname)
            return dbname_ds, dbname_ds, "database.dbname"

        # 2) If dbname is a placeholder (common in GitOps), fall back to connector_dir.
        ds_dir = _infer_from_connector_dir()
        if ds_dir:
            ds_dir = str(ds_dir)
            return ds_dir, ds_dir, "connector_dir"

    # 3) For your naming convention, dataset is the 3rd dot-part in the connector name.
    name = manifest.name or ""
    parts_name = name.split(".") if name else []
    if len(parts_name) >= 3 and parts_name[2]:
        ds = str(parts_name[2])
        return ds, ds, "name"

    # 4) Parse from the manifest file naming convention (fallback).
    rem = info.remainder or ""
    if info.connector_type == ConnectorType.source and rem.startswith("source_"):
        slug = rem[len("source_") :]
    elif info.connector_type == ConnectorType.sink and rem.startswith("sink_"):
        # sink_<layer>_<slug>
        parts = rem.split("_", 2)
        slug = parts[2] if len(parts) == 3 else rem
    else:
        slug = rem

    tokens = [t for t in slug.split("__") if t]
    # common pattern: <domain>__<dataset>__...
    ds_short: str | None = (
        tokens[1] if len(tokens) >= 2 else (tokens[0] if tokens else None)
    )
    if ds_short is not None:
        ds_short = str(ds_short)

    ds_full = ds_short
    if ds_short is None:
        return None, None, None
    return ds_short, ds_full, "filename"


def build_template_vars(manifest: ConnectorManifest) -> Dict[str, Optional[str]]:
    """Extract variables used by naming rules.

    Those vars are used to evaluate naming.rules templates/regex and to produce
    helpful suggested names.
    """

    info = manifest.info
    name = manifest.name or ""

    layer = extract_layer_from_filename(info.path.name)
    ds_short, ds_full, ds_src = infer_dataset_vars(manifest)

    idx: Optional[str] = None
    parts = name.split(".") if name else []
    if parts and parts[-1].isdigit():
        idx = parts[-1]

    return {
        "env": info.env.value,
        "domain": info.domain,
        "type": info.connector_type.value,
        "system": info.system,
        "connector_dir": info.connector_dir,
        "layer": layer,
        "mode": info.mode,
        "remainder": info.remainder,
        "dataset_short": ds_short,
        "dataset": ds_full,
        "dataset_source": ds_src,
        "index": idx,
    }
