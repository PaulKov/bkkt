from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..models import ConnectorManifest, Environment
from .policies_models import PolicyIssue
from .policies_static import lint_static_layers
from .policies_runtime import lint_runtime_manifest
from .policies_utils import dedupe


def lint_policies(
    manifest: ConnectorManifest,
    *,
    env: Optional[Environment] = None,
    layers: Optional[Sequence[Path]] = None,
    ignored_static_keys: Iterable[str] = (),
) -> List[PolicyIssue]:
    """Проверить rendered manifest против repo-политик.

    - Static checks (когда переданы layers): сканируем layer-файлы на запрещённые literal endpoints.
      Важно: сканируем *raw JSON* без expand env placeholders.
    - Runtime checks: сканируем итоговый rendered manifest.config на явные утечки окружения.

    Возвращает список PolicyIssue. НЕ кидает исключение.
    """
    issues: List[PolicyIssue] = []

    env_eff = env or manifest.info.env

    if layers:
        issues.extend(
            lint_static_layers(
                manifest,
                env=env_eff,
                layers=layers,
                ignored_keys=ignored_static_keys,
            )
        )

    issues.extend(lint_runtime_manifest(manifest, env=env_eff))

    return dedupe(issues)
