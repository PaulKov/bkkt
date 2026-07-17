from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class GlueDatabaseSpec:
    name: str
    location_uri: Optional[str] = None
    description: Optional[str] = None


def ensure_glue_database(
    spec: GlueDatabaseSpec,
    *,
    region: Optional[str] = None,
    dry_run: bool = False,
    client: Any = None,
) -> bool:
    """Ensure an AWS Glue Data Catalog database exists.

    Returns True if a database was created, False if it already existed.

    This function requires boto3 unless a preconfigured Glue client is injected.
    """
    if dry_run:
        # Can't reliably check existence without calling AWS; keep deterministic.
        return False

    if client is None:
        try:
            import boto3
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "boto3 is required for Glue auto-catalog bootstrap. Install extras or add boto3 to dependencies."
            ) from e

        client = boto3.client("glue", region_name=region)

    try:
        client.get_database(Name=spec.name)
        return False
    except Exception as e:
        code = _extract_error_code(e)
        if code not in {"EntityNotFoundException", "AccessDeniedException"}:
            # AccessDenied might happen if the role can't read but can create; treat as error
            raise
        if code == "AccessDeniedException":
            raise

    db_input: dict = {"Name": spec.name}
    if spec.description:
        db_input["Description"] = spec.description
    if spec.location_uri:
        db_input["LocationUri"] = spec.location_uri

    try:
        client.create_database(DatabaseInput=db_input)
        return True
    except Exception as e:
        code = _extract_error_code(e)
        # Race: database created by parallel job
        if code in {"AlreadyExistsException", "EntityAlreadyExistsException"}:
            return False
        raise


def _extract_error_code(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        err = response.get("Error")
        if isinstance(err, dict):
            code = err.get("Code")
            if code:
                return str(code)
    return ""
