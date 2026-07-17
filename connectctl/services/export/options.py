from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern

from ...exceptions import ConfigError
from ...models import ConnectorType
from ...settings_models import Settings
from ..name_variants import normalize_source_mode_token, split_csv, uniq_preserve
from .models import (
    ExportFilters,
    ExportFlags,
    ExportPlacementOverrides,
    ExportReuse,
    ExportSelection,
    ExportVariants,
    IcebergScaffolding,
)


def parse_variants(*, args) -> ExportVariants:
    """Разобрать `--modes/--kinds/--init-only`.

    Это логика "как в init": поддерживаем оба варианта (init/cdc и kinds).
    """

    modes_raw: List[str] = [m.strip() for m in split_csv(getattr(args, "modes", None))]
    kinds: List[str] = [
        k.strip().lower() for k in split_csv(getattr(args, "kinds", None))
    ]

    # Нормализуем modes:
    # - lower-case
    # - алиасы: initial->init, stream->cdc
    # - allow custom modes (валидный token для dot-naming)
    modes_norm: List[str] = [normalize_source_mode_token(m) for m in modes_raw if m]
    modes = uniq_preserve([m for m in modes_norm if m])
    kinds = uniq_preserve([k for k in kinds if k])

    init_only = bool(getattr(args, "init_only", False))
    if init_only and not any(m == "init" for m in modes):
        # UX: если пользователь забыл добавить init в --modes, добавляем автоматически.
        modes.append("init")

    # Если пользователь указал --type, валидируем совместимость параметров.
    if getattr(args, "type", None):
        t = str(getattr(args, "type")).strip().lower()
        if (modes or init_only) and t != "source":
            raise ConfigError(
                "--modes/--init-only are only applicable for source connectors (use --type source)"
            )
        if kinds and t != "sink":
            raise ConfigError(
                "--kinds is only applicable for sink connectors (use --type sink)"
            )

    return ExportVariants(source_modes=modes, sink_kinds=kinds, init_only=init_only)


def parse_filters(*, args) -> ExportFilters:
    patterns: List[Pattern[str]] = []
    if getattr(args, "regexp", None):
        for pat in getattr(args, "regexp"):
            patterns.append(re.compile(pat, re.IGNORECASE))

    filter_type = (
        ConnectorType.from_str(args.type) if getattr(args, "type", None) else None
    )
    filter_domain = str(args.domain).strip() if getattr(args, "domain", None) else None
    filter_system = str(args.system).strip() if getattr(args, "system", None) else None

    return ExportFilters(
        patterns=patterns,
        filter_type=filter_type,
        filter_domain=filter_domain,
        filter_system=filter_system,
    )


def parse_placement_overrides(*, args) -> ExportPlacementOverrides:
    """Overrides для explicit export (НЕ для `--all`)."""
    domain = str(args.domain).strip() if getattr(args, "domain", None) else None
    connector_type = (
        ConnectorType.from_str(str(args.type)) if getattr(args, "type", None) else None
    )
    system = str(args.system).strip() if getattr(args, "system", None) else None
    connector_dir = (
        str(args.connector_dir).strip()
        if getattr(args, "connector_dir", None)
        else None
    )
    return ExportPlacementOverrides(
        domain=domain,
        connector_type=connector_type,
        system=system,
        connector_dir=connector_dir,
    )


def parse_reuse(*, args, repo_root: Path) -> ExportReuse:
    override_only_paths: Optional[List[Path]] = None
    if getattr(args, "reuse_from", None):
        override_only_paths = []
        for p in getattr(args, "reuse_from"):
            pp = (
                (repo_root / p).resolve()
                if not Path(p).is_absolute()
                else Path(p).resolve()
            )
            override_only_paths.append(pp)
    return ExportReuse(override_only_paths=override_only_paths)


def parse_iceberg_scaffolding(*, args) -> IcebergScaffolding:
    iceberg_kinds: List[str] = []
    for raw in getattr(args, "iceberg_generate_kinds", None) or []:
        for k in str(raw).split(","):
            kk = k.strip()
            if kk:
                iceberg_kinds.append(kk)
    iceberg_kinds = uniq_preserve(iceberg_kinds)

    iceberg_generate_overrides = bool(getattr(args, "iceberg_generate_overrides", True))
    iceberg_generate_manifests = bool(getattr(args, "iceberg_generate_manifests", True))

    iceberg_table_id_columns: Dict[str, str] = {}
    for raw in getattr(args, "iceberg_table_id_columns", None) or []:
        s = str(raw).strip()
        if not s:
            continue
        if "=" not in s:
            raise ConfigError(
                f"Invalid --iceberg-table-id-columns value: {s}. Expected <table>=<col1,col2,...>"
            )
        table, cols = s.split("=", 1)
        table = table.strip()
        cols = cols.strip()
        if not table or not cols:
            raise ConfigError(
                f"Invalid --iceberg-table-id-columns value: {s}. Expected <table>=<col1,col2,...>"
            )
        iceberg_table_id_columns[table] = cols

    return IcebergScaffolding(
        kinds=iceberg_kinds,
        generate_overrides=iceberg_generate_overrides,
        generate_manifests=iceberg_generate_manifests,
        table_id_columns=iceberg_table_id_columns,
    )


def resolve_auto_suffix_on_collision(*, args, settings: Settings) -> bool:
    auto_suffix = getattr(args, "auto_index_suffix_on_collision", None)
    if auto_suffix is None:
        auto_suffix = getattr(
            getattr(settings, "export", None), "auto_index_suffix_on_collision", None
        )
        if auto_suffix is None:
            auto_suffix = True
    return bool(auto_suffix)


def resolve_flags(*, args, settings: Settings) -> ExportFlags:
    return ExportFlags(
        dry_run=bool(getattr(args, "dry_run", False)),
        force=bool(getattr(args, "force", False)),
        reuse_overrides=bool(getattr(args, "reuse_overrides", True)),
        save_diffs=bool(getattr(args, "save_diffs", False)),
        auto_index_suffix_on_collision=resolve_auto_suffix_on_collision(
            args=args, settings=settings
        ),
    )


def resolve_selection(
    *, args, names_from_cli: List[str], all_names: Optional[List[str]] = None
) -> ExportSelection:
    """Сконструировать ExportSelection.

    `all_names` передаётся тогда, когда `--all` уже был развернут в список.
    """
    if bool(getattr(args, "all", False)):
        if all_names is None:
            raise ConfigError("Internal error: --all requires all_names")
        return ExportSelection(all=True, names=all_names)
    if not names_from_cli:
        raise ConfigError("Provide connector names or use --all")
    return ExportSelection(all=False, names=names_from_cli)


def parse_name_overrides(*, args, selection: ExportSelection) -> Dict[str, str]:
    """Разобрать `--as-name` для export.

    Нужен кейс, когда "remote" имя коннектора в Kafka Connect не соответствует
    стандартам BKKT (dot-style с <env> в начале), но в репозитории мы хотим
    хранить нормализованное имя.

    Поддерживаемые форматы:
      1) --as-name <new_name>                       (если экспортируется ровно 1 коннектор)
      2) --as-name <remote>=<new_name>              (явное сопоставление)
      3) N раз --as-name <new_name>                 (по порядку для N имён)
    """

    raw: List[str] = list(getattr(args, "as_names", None) or [])
    if not raw:
        return {}

    if selection.all:
        raise ConfigError(
            "--as-name нельзя использовать вместе с --all. "
            "Если нужно нормализовать имена — экспортируйте явный список коннекторов (positional names)."
        )

    remote_names = list(selection.names)

    has_eq = [("=" in str(x)) for x in raw]
    if any(has_eq) and not all(has_eq):
        raise ConfigError(
            "--as-name: нельзя смешивать форматы '<remote>=<new>' и просто '<new>'. "
            "Используйте один стиль для всех значений."
        )

    mapping: Dict[str, str] = {}

    if all(has_eq):
        for item in raw:
            s = str(item)
            left, right = s.split("=", 1)
            old = left.strip()
            new = right.strip()
            if not old or not new:
                raise ConfigError(
                    f"--as-name: некорректное значение {s!r}. Ожидается '<remote>=<new_name>'."
                )
            if old in mapping:
                raise ConfigError(
                    f"--as-name: имя {old!r} указано более одного раза. Это двусмысленно."
                )
            mapping[old] = new

        unknown = [n for n in mapping.keys() if n not in remote_names]
        if unknown:
            raise ConfigError(
                "--as-name: указаны remote имена, которых нет в списке коннекторов для export: "
                f"{unknown}."
            )

        return mapping

    # Order-based mapping.
    if len(raw) == 1 and len(remote_names) == 1:
        return {remote_names[0]: str(raw[0]).strip()}

    if len(raw) == len(remote_names):
        for i, remote in enumerate(remote_names):
            mapping[remote] = str(raw[i]).strip()
        return mapping

    raise ConfigError(
        "--as-name: количество значений не совпадает с количеством коннекторов. "
        f"Коннекторов: {len(remote_names)}, --as-name: {len(raw)}. "
        "Подсказка: для нескольких коннекторов используйте либо N раз '--as-name <new_name>' по порядку, "
        "либо формат '--as-name <remote>=<new_name>' для явной привязки."
    )
