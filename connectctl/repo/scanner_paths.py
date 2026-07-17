from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..exceptions import RepoLayoutError
from ..models import ConnectorPathInfo, ConnectorType, Environment, RepoConfig
from ..naming.hints import (
    extract_dataset_from_connector_dir,
    format_deployable_name_hints,
)
from ..ports import FileSystem
from .scanner_mode import guess_mode
from .scanner_regex import match_deployable
from .scanner_variants import infer_sink_variant


def _guess_layer_from_filename(name: str) -> Optional[str]:
    parts = [p for p in str(name or "").replace(".json", "").split(".") if p]
    if "sink" in parts:
        i = parts.index("sink")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def parse_connector_path(
    cfg: RepoConfig,
    path: Path,
    must_exist: bool = True,
    *,
    fs: FileSystem | None = None,
) -> ConnectorPathInfo:
    """Parse a deployable connector manifest path into structured metadata.

    Args:
        cfg: RepoConfig (root + connectors_root + ignore dirs).
        path: Path to a deployable env manifest.
        must_exist: Accepted for backward/forward compatibility. The parser does not
            require the file to exist on disk (historical behavior).
    """
    # NOTE: Historically this parser did not require the path to exist on disk.
    # Keep that behavior for backward compatibility; the flag is accepted so that
    # callers (e.g., export/render dry-runs) can be explicit about intent.
    # We intentionally do not enforce existence here.

    try:
        rel = path.resolve().relative_to(cfg.root.resolve())
    except ValueError:
        rel = path

    parts = list(rel.parts)

    # Support optional leading 'connectors/'.
    if parts and parts[0] == "connectors":
        parts = parts[1:]

    if len(parts) < 5:
        raise RepoLayoutError(
            f"Connector path is too short: {rel}. Expected <domain>/<type>/<system>/<connector_dir>/<env>_...json or <env>.<...>.json"
        )

    domain = parts[0]
    ctype = ConnectorType.from_str(parts[1])
    system = parts[2]
    connector_dir = parts[3]

    m_us, m_dot = match_deployable(path.name)
    if not (m_us or m_dot):
        dataset = extract_dataset_from_connector_dir(
            connector_dir=connector_dir, domain=domain
        )
        layer_hint = _guess_layer_from_filename(path.name)
        hint = format_deployable_name_hints(
            connector_type=ctype,
            domain=domain,
            system=system,
            dataset=dataset,
            layer=layer_hint,
        )
        raise RepoLayoutError(
            "\n".join(
                [
                    f"File is not a deployable connector manifest: {rel}",
                    "",
                    hint,
                    "",
                    "Если вы делаете export из кластера и remote имя коннектора не соответствует стандарту BKKT — ",
                    "используйте 'bkkt export ... <remote_name> --as-name <нормализованное_имя>'.",
                ]
            )
        )
    if m_us:
        env = Environment.from_str(m_us.group(1).lower())
        remainder = path.name.split("_", 1)[1]  # everything after env_
        remainder_noext = (
            remainder[:-5] if remainder.lower().endswith(".json") else remainder
        )
        underscore_style = True
    else:
        assert m_dot is not None
        env = Environment.from_str(m_dot.group(1).lower())
        remainder = path.name.split(".", 1)[1]
        remainder_noext = (
            remainder[:-5] if remainder.lower().endswith(".json") else remainder
        )
        underscore_style = False

    variant: Optional[str] = None
    if ctype == ConnectorType.sink:
        variant = infer_sink_variant(
            cfg=cfg,
            fs=fs,
            domain=domain,
            system=system,
            connector_dir=connector_dir,
            remainder_noext=remainder_noext,
            underscore_style=underscore_style,
        )

    def _mode_exists(tok: str) -> bool:
        """Check whether mode overlays exist for a given token.

        We check the same places where the LayerResolver will look for mode layers.
        This is used only for **best-effort** inference of custom modes to avoid
        false positives for tokens that are not modes.
        """

        t = str(tok or "").strip().lower()
        if not t:
            return False

        candidates = [
            cfg.root / "__global" / "source" / system / "modes" / t,
            cfg.connectors_root / domain / "source" / system / "modes" / t,
            cfg.connectors_root
            / domain
            / "source"
            / system
            / connector_dir
            / "modes"
            / t,
        ]
        for p in candidates:
            if fs is not None:
                if fs.is_dir(p):
                    return True
            else:
                if p.is_dir():
                    return True
        return False

    return ConnectorPathInfo(
        path=path.resolve(),
        relpath=rel,
        domain=domain,
        connector_type=ctype,
        system=system,
        connector_dir=connector_dir,
        env=env,
        remainder=remainder_noext,
        variant=variant,
        mode=guess_mode(
            connector_dir,
            remainder_noext,
            connector_type=ctype,
            mode_exists=_mode_exists,
        ),
    )


def find_base_file_for(
    cfg: RepoConfig, env_file: Path, *, fs: FileSystem | None = None
) -> Optional[Path]:
    """Given <env>_X.json OR <env>.<X>.json, try to find base.<X>.json in the same directory."""
    name = env_file.name
    m_us, m_dot = match_deployable(name)
    if not (m_us or m_dot):
        return None
    if m_us:
        remainder = name.split("_", 1)[1]  # includes .json
    else:
        remainder = name.split(".", 1)[1]  # includes .json
    base_name = f"base.{remainder}"
    candidate = env_file.parent / base_name
    return candidate if (fs.exists(candidate) if fs else candidate.exists()) else None
