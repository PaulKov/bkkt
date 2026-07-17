from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ...ports import FileSystem


@dataclass(frozen=True)
class InitTemplateOverride:
    """Источник переопределения значений для init-templates."""

    label: str
    kind: str  # json|kv
    payload: dict
    # Опциональный scope (glob) для применения override только к части файлов.
    # Пример: "types/events/*" или "modes/init/*".
    # Если None — применяется ко всем генерируемым файлам.
    scope: Optional[str] = None


@dataclass(frozen=True)
class InitOptions:
    repo_root: Path
    target_dir: Path

    # DI ports
    fs: FileSystem

    # init-templates root (по умолчанию: <repo>/__init_templates)
    templates_root: Path

    # Переопределения значений (env/CLI) для шаблонов init
    template_overrides: List[InitTemplateOverride]

    domain: str
    connector_type: str  # source|sink
    system: str

    dataset: str
    connector_dir: str

    envs: List[str]
    layer: str
    index: int

    # Only one of these lists is expected to be "real" depending on connector_type.
    # For source: modes contains [None] or tokens like 'cdc'/'init'/'initial'.
    # For sink: kinds contains [None] or tokens like 'events'/'flatten'/...
    modes: List[Optional[str]]
    kinds: List[Optional[str]]

    # UX/behaviour: were variants requested explicitly by user (CLI/env),
    # or are they just implicit defaults.
    #
    # Examples:
    # - `bkkt init --type source ...` (no --modes) => modes=['cdc'] but modes_explicit=False
    # - `bkkt init --type source ... --modes cdc` => modes=['cdc'] and modes_explicit=True
    # - `bkkt init --type source ... --init-only` => modes contains init and modes_explicit=True
    # - `bkkt init --type sink ...` (no --kinds) => kinds=[None] and kinds_explicit=False
    # - `bkkt init --type sink ... --kinds events,flatten` => kinds=[...] and kinds_explicit=True
    modes_explicit: bool
    kinds_explicit: bool

    explicit_name: Optional[str]
    name_template: Optional[str]

    create_all: bool
    init_only: bool
    force: bool
    dry_run: bool
