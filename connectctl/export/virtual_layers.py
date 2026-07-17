from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from ..ports import FileSystem


def resolve_layers_virtual(
    *,
    repo_root: Path,
    connectors_root: Path,
    info: Any,
    env_file: Path,
    planned_paths: Set[Path],
    fs: FileSystem | None = None,
    base_file: Optional[Path] = None,
) -> Tuple[Path, ...]:
    """Разрешить все override-слои, которые *должны* примениться к env манифесту.

    Аналогично :class:`connectctl.repo.layers.LayerResolver`, но используется в export,
    когда часть путей может быть «виртуальной» (запланирована, но ещё не записана на диск).
    """

    def exists_or_planned(base: Path, rel: Path) -> Optional[Path]:
        abs_path = (base / rel).resolve()
        if abs_path in planned_paths or (
            fs.exists(abs_path) if fs else abs_path.exists()
        ):
            return abs_path
        return None

    layers: List[Path] = []

    def add_repo(rel: Path) -> None:
        p = exists_or_planned(repo_root, rel)
        if p:
            layers.append(p)

    def add_connector(rel: Path) -> None:
        p = exists_or_planned(connectors_root, rel)
        if p:
            layers.append(p)

    env_name = info.env.value
    ctype = info.connector_type.value
    domain = info.domain
    system = info.system
    connector_dir = info.connector_dir
    mode = info.mode
    # ConnectorPathInfo uses `variant` for sink "kind" (best-effort).
    # Keep naming consistent with LayerResolver.
    sink_kind = (info.variant or "default") if ctype == "sink" else None

    # 1) Global all
    add_repo(Path("__global/all.json"))
    add_repo(Path(f"__global/{env_name}.json"))

    # 2) Global by connector type
    add_repo(Path(f"__global/{ctype}/all.json"))
    add_repo(Path(f"__global/{ctype}/{env_name}.json"))

    # 2b) Global by system
    add_repo(Path(f"__global/{ctype}/{system}/all.json"))
    add_repo(Path(f"__global/{ctype}/{system}/{env_name}.json"))

    # 2m) Global by mode
    if mode:
        add_repo(Path(f"__global/{ctype}/{system}/modes/{mode}/all.json"))
        add_repo(Path(f"__global/{ctype}/{system}/modes/{mode}/{env_name}.json"))

    # 2c) Sink kinds (types)
    if ctype == "sink":
        add_repo(Path(f"__global/{ctype}/{system}/types/default/all.json"))
        add_repo(Path(f"__global/{ctype}/{system}/types/default/{env_name}.json"))
        if sink_kind and sink_kind != "default":
            add_repo(Path(f"__global/{ctype}/{system}/types/{sink_kind}/all.json"))
            add_repo(
                Path(f"__global/{ctype}/{system}/types/{sink_kind}/{env_name}.json")
            )

        # 2cm) Sink kinds + mode
        if mode:
            add_repo(
                Path(f"__global/{ctype}/{system}/types/default/modes/{mode}/all.json")
            )
            add_repo(
                Path(
                    f"__global/{ctype}/{system}/types/default/modes/{mode}/{env_name}.json"
                )
            )
            if sink_kind and sink_kind != "default":
                add_repo(
                    Path(
                        f"__global/{ctype}/{system}/types/{sink_kind}/modes/{mode}/all.json"
                    )
                )
                add_repo(
                    Path(
                        f"__global/{ctype}/{system}/types/{sink_kind}/modes/{mode}/{env_name}.json"
                    )
                )

    # 3) Domain
    add_connector(Path(f"{domain}/all.json"))
    add_connector(Path(f"{domain}/{env_name}.json"))

    # 3b) Domain by connector type
    add_connector(Path(f"{domain}/{ctype}/all.json"))
    add_connector(Path(f"{domain}/{ctype}/{env_name}.json"))

    # 3c) Domain by system
    add_connector(Path(f"{domain}/{ctype}/{system}/all.json"))
    add_connector(Path(f"{domain}/{ctype}/{system}/{env_name}.json"))

    # 3m) Domain by mode
    if mode:
        add_connector(Path(f"{domain}/{ctype}/{system}/modes/{mode}/all.json"))
        add_connector(Path(f"{domain}/{ctype}/{system}/modes/{mode}/{env_name}.json"))

    # 3k) Domain sink kinds
    if ctype == "sink":
        add_connector(Path(f"{domain}/{ctype}/{system}/types/default/all.json"))
        add_connector(Path(f"{domain}/{ctype}/{system}/types/default/{env_name}.json"))
        if sink_kind and sink_kind != "default":
            add_connector(Path(f"{domain}/{ctype}/{system}/types/{sink_kind}/all.json"))
            add_connector(
                Path(f"{domain}/{ctype}/{system}/types/{sink_kind}/{env_name}.json")
            )

        # 3km) Domain sink kinds + mode
        if mode:
            add_connector(
                Path(f"{domain}/{ctype}/{system}/types/default/modes/{mode}/all.json")
            )
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/types/default/modes/{mode}/{env_name}.json"
                )
            )
            if sink_kind and sink_kind != "default":
                add_connector(
                    Path(
                        f"{domain}/{ctype}/{system}/types/{sink_kind}/modes/{mode}/all.json"
                    )
                )
                add_connector(
                    Path(
                        f"{domain}/{ctype}/{system}/types/{sink_kind}/modes/{mode}/{env_name}.json"
                    )
                )

    # 4) Connector directory
    add_connector(Path(f"{domain}/{ctype}/{system}/{connector_dir}/all.json"))
    add_connector(Path(f"{domain}/{ctype}/{system}/{connector_dir}/{env_name}.json"))

    # 4m) Connector dir by mode
    if mode:
        add_connector(
            Path(f"{domain}/{ctype}/{system}/{connector_dir}/modes/{mode}/all.json")
        )
        add_connector(
            Path(
                f"{domain}/{ctype}/{system}/{connector_dir}/modes/{mode}/{env_name}.json"
            )
        )

    # 4k) Connector dir sink kinds
    if ctype == "sink":
        add_connector(
            Path(f"{domain}/{ctype}/{system}/{connector_dir}/types/default/all.json")
        )
        add_connector(
            Path(
                f"{domain}/{ctype}/{system}/{connector_dir}/types/default/{env_name}.json"
            )
        )
        if sink_kind and sink_kind != "default":
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/{sink_kind}/all.json"
                )
            )
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/{sink_kind}/{env_name}.json"
                )
            )

        # 4km) Connector dir sink kinds + mode
        if mode:
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/default/modes/{mode}/all.json"
                )
            )
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/default/modes/{mode}/{env_name}.json"
                )
            )
            if sink_kind and sink_kind != "default":
                add_connector(
                    Path(
                        f"{domain}/{ctype}/{system}/{connector_dir}/types/{sink_kind}/modes/{mode}/all.json"
                    )
                )
                add_connector(
                    Path(
                        f"{domain}/{ctype}/{system}/{connector_dir}/types/{sink_kind}/modes/{mode}/{env_name}.json"
                    )
                )

    if base_file is not None:
        layers.append(base_file.resolve())

    # Env-манифест — всегда последний слой (как в LayerResolver), даже если он «виртуальный».
    layers.append(env_file.resolve())

    return tuple(layers)
