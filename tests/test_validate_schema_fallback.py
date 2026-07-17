from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from connectctl.adapters.filesystem_memory import InMemoryFileSystem
from connectctl.services.validate_service import ValidateService


def test_validate_service_schema_fallback_works_without_repo_schemas_dir() -> None:
    fs = InMemoryFileSystem()
    ctx = SimpleNamespace(repo_root=Path("/repo"), fs=fs, logger=None)
    svc = ValidateService(ctx=ctx)

    schema = svc._load_schema_with_fallback(
        name="connectctl.schema.json", repo_root=Path("/repo")
    )

    assert isinstance(schema, dict)
    assert schema.get("title") == "connectctl.yaml schema"
