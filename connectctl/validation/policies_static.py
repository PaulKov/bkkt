from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

from ..models import ConnectorManifest, Environment
from ..rendering.prune import should_prune_key
from ..rendering.json_loader import normalize_fragment
from .policies_models import BOOTSTRAP_KEYS, SCHEMA_REGISTRY_SUFFIX, PolicyIssue
from .policies_utils import iter_strings_in_mapping, load_json_no_env


def lint_static_layers(
    manifest: ConnectorManifest,
    *,
    env: Environment,
    layers: Sequence[Path],
    ignored_keys: Iterable[str] = (),
) -> List[PolicyIssue]:
    """Статические проверки (по исходным layer-файлам).

    Мы специально читаем raw JSON (без expand env vars), чтобы
    ловить literal endpoints и подсказать точный файл-источник.
    """
    issues: List[PolicyIssue] = []

    for layer in layers:
        try:
            obj = load_json_no_env(layer)
        except Exception:
            # Если файл невалидный JSON — renderer упал бы раньше.
            continue

        try:
            frag = normalize_fragment(obj)
        except Exception:
            continue

        cfg = frag.get("config") or {}
        if not isinstance(cfg, Mapping):
            continue

        for k, v in iter_strings_in_mapping(cfg):
            k_norm = k.strip()
            v_norm = v.strip()

            if should_prune_key(k_norm, ignored_keys):
                continue

            # bootstrap keys: must be placeholder-based
            if k_norm in BOOTSTRAP_KEYS and "${" not in v_norm:
                issues.append(
                    PolicyIssue(
                        severity="error",
                        policy="BOOTSTRAP_HARDCODED",
                        manifest_path=str(manifest.info.relpath),
                        file_path=str(layer),
                        key=k_norm,
                        message="Hard-coded bootstrap servers are forbidden (must come from shared vars / env).",
                        hint="Use ${kafka.bootstrap_servers} (or an env-backed var) instead of a literal host:port list.",
                    )
                )

            # schema registry url keys: must be placeholder-based
            if k_norm.lower().endswith(SCHEMA_REGISTRY_SUFFIX) and "${" not in v_norm:
                issues.append(
                    PolicyIssue(
                        severity="error",
                        policy="SCHEMA_REGISTRY_HARDCODED",
                        manifest_path=str(manifest.info.relpath),
                        file_path=str(layer),
                        key=k_norm,
                        message="Hard-coded schema registry URL is forbidden (must come from shared vars / env).",
                        hint="Use ${kafka.schema_registry_url} (or an env-backed var) instead of a literal URL.",
                    )
                )

    return issues
