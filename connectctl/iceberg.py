from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .aws.glue_catalog import GlueDatabaseSpec, ensure_glue_database
from .models import ConnectorManifest


def _get_first(cfg: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = cfg.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None


@dataclass(frozen=True)
class IcebergGlueBootstrap:
    db_name: str
    location_uri: Optional[str]
    region: Optional[str]


def extract_iceberg_glue_bootstrap(
    manifest: ConnectorManifest,
) -> Optional[IcebergGlueBootstrap]:
    """If the manifest looks like an IcebergSinkConnector using AWS Glue catalog,
    return the parameters needed to ensure the database exists.

    Returns None if connector is not Iceberg+Glue or if critical fields are missing.
    """

    cfg = manifest.config
    cls = str(cfg.get("connector.class", ""))
    if "IcebergSinkConnector" not in cls:
        return None

    catalog_type = str(cfg.get("iceberg.catalog.type", "")).strip().lower()
    if catalog_type and catalog_type != "glue":
        return None

    # Database name is typically provided via the table-name transform.
    db_name = _get_first(
        cfg,
        "transforms.setTableName.db.name",
        "iceberg.db.name",
        "iceberg.db_name",
        "iceberg.tables.default-namespace",
    )
    if not db_name:
        return None

    # Warehouse path: choose the most specific known key first.
    warehouse = _get_first(
        cfg,
        "iceberg.catalog.glue.warehouse",
        "iceberg.catalog.warehouse",
        "iceberg.warehouse",
    )
    location_uri = None
    if warehouse:
        # Glue expects a URI. Keep it stable with a trailing slash.
        location_uri = warehouse.rstrip("/") + "/"

    region = _get_first(cfg, "iceberg.catalog.region", "aws.region", "AWS_REGION")

    return IcebergGlueBootstrap(
        db_name=db_name, location_uri=location_uri, region=region
    )


def ensure_iceberg_glue_database(
    manifest: ConnectorManifest,
    *,
    enabled: bool = True,
    dry_run: bool = False,
    cache: Optional[set[tuple[str, str]]] = None,
) -> Optional[bool]:
    """Ensure Glue database exists for Iceberg sink manifests.

    Returns:
      - None if the manifest is not an Iceberg sink using Glue catalog, or when disabled.
      - True if a CreateDatabase call was issued (or would have been in dry-run).
      - False if the database already existed (or was skipped due to cache).
    """

    if not enabled:
        return None

    bootstrap = extract_iceberg_glue_bootstrap(manifest)
    if not bootstrap:
        return None

    cache_key = (bootstrap.region or "", bootstrap.db_name)
    if cache is not None and cache_key in cache:
        return False

    spec = GlueDatabaseSpec(
        name=bootstrap.db_name,
        location_uri=bootstrap.location_uri,
        description="Auto-created by connectctl (Iceberg Glue bootstrap)",
    )
    created = ensure_glue_database(spec, region=bootstrap.region, dry_run=dry_run)

    if cache is not None:
        cache.add(cache_key)

    return created


def maybe_bootstrap_glue_database(
    manifest: ConnectorManifest,
    *,
    enabled: bool = True,
    dry_run: bool = False,
    cache: Optional[set[tuple[str, str]]] = None,
) -> Optional[str]:
    """User-facing wrapper used by connectctl CLI.

    Returns a short human-readable message when the manifest is an Iceberg sink
    using AWS Glue catalog, otherwise returns None.
    """

    created = ensure_iceberg_glue_database(
        manifest,
        enabled=enabled,
        dry_run=dry_run,
        cache=cache,
    )

    if created is None:
        return None

    # Re-compute names for message (cheap and keeps ensure_* focused)
    cfg = manifest.config
    db_name = None
    for k, v in cfg.items():
        if str(k).endswith(".db.name") and str(v).strip():
            db_name = str(v).strip()
            break
    if not db_name:
        db_name = _get_first(cfg, "iceberg.db_name", "iceberg.db.name")

    region = _get_first(cfg, "iceberg.catalog.region") or ""

    if dry_run:
        return f"iceberg/glue: would ensure database '{db_name}' (region='{region}')"

    if created:
        return f"iceberg/glue: created database '{db_name}' (region='{region}')"

    return f"iceberg/glue: database '{db_name}' already exists (region='{region}')"
