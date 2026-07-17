from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

from ..models import ConnectorPathInfo, RepoConfig
from ..ports import FileSystem


class LayerResolver:
    """Resolves a deterministic list of override files (low -> high priority)."""

    def __init__(self, repo_cfg: RepoConfig, fs: FileSystem | None = None):
        self.repo_cfg = repo_cfg
        self.root = repo_cfg.root
        self.connectors_root = repo_cfg.connectors_root
        self.fs = fs

    def _exists(self, base: Path, rel: Path) -> Optional[Path]:
        p = (base / rel).resolve()
        return p if (self.fs.exists(p) if self.fs else p.exists()) else None

    def _connector_rel(self, rel: Path) -> Path:
        try:
            prefix = self.connectors_root.resolve().relative_to(self.root.resolve())
        except ValueError:
            prefix = Path()
        return (prefix / rel) if str(prefix) not in {"", "."} else rel

    def resolve(
        self,
        info: ConnectorPathInfo,
        *,
        base_file: Optional[Path],
        env_file: Path,
        reuse_overrides: bool = True,
        reuse_from: Optional[Sequence[Path]] = None,
    ) -> List[Path]:
        env = info.env.value
        ctype = info.connector_type.value
        domain = info.domain
        system = info.system
        connector_dir = info.connector_dir
        mode = info.mode

        sink_kind = (info.variant or "default") if ctype == "sink" else None

        candidates: List[Path] = []

        def add_repo(rel: Path) -> None:
            p = self._exists(self.root, rel)
            if p:
                candidates.append(p)

        def add_connector(rel: Path) -> None:
            p = self._exists(self.root, self._connector_rel(rel))
            if p:
                candidates.append(p)

        # 1) Global
        add_repo(Path("__global/all.json"))
        add_repo(Path(f"__global/{env}.json"))

        # 2) Global by connector type
        add_repo(Path(f"__global/{ctype}/all.json"))
        add_repo(Path(f"__global/{ctype}/{env}.json"))

        # 2b) Global by connector type + system (e.g. __global/source/mariadb/all.json)
        add_repo(Path(f"__global/{ctype}/{system}/all.json"))
        add_repo(Path(f"__global/{ctype}/{system}/{env}.json"))

        # 2c) Global sink kind overrides (kind is independent; no implicit inheritance)
        if ctype == "sink":
            kind = sink_kind or "default"
            add_repo(Path(f"__global/{ctype}/{system}/types/{kind}/all.json"))
            add_repo(Path(f"__global/{ctype}/{system}/types/{kind}/{env}.json"))

        # 2m) Mode-specific global overlays (optional), e.g. __global/source/postgres/modes/cdc/all.json
        if mode:
            add_repo(Path(f"__global/{ctype}/{system}/modes/{mode}/all.json"))
            add_repo(Path(f"__global/{ctype}/{system}/modes/{mode}/{env}.json"))

        # 2cm) Global sink kind + mode overlays (optional)
        if ctype == "sink" and mode:
            kind = sink_kind or "default"
            add_repo(
                Path(f"__global/{ctype}/{system}/types/{kind}/modes/{mode}/all.json")
            )
            add_repo(
                Path(f"__global/{ctype}/{system}/types/{kind}/modes/{mode}/{env}.json")
            )

        # 3) Domain-level
        add_connector(Path(f"{domain}/all.json"))
        add_connector(Path(f"{domain}/{env}.json"))

        # 4) Domain + type
        add_connector(Path(f"{domain}/{ctype}/all.json"))
        add_connector(Path(f"{domain}/{ctype}/{env}.json"))

        # 5) Domain + type + system
        add_connector(Path(f"{domain}/{ctype}/{system}/all.json"))
        add_connector(Path(f"{domain}/{ctype}/{system}/{env}.json"))

        # 5b) Domain + type + system + sink kind (optional; kind is independent)
        if ctype == "sink":
            kind = sink_kind or "default"
            add_connector(Path(f"{domain}/{ctype}/{system}/types/{kind}/all.json"))
            add_connector(Path(f"{domain}/{ctype}/{system}/types/{kind}/{env}.json"))

        # 5m) Domain + type + system + mode (optional)
        if mode:
            add_connector(Path(f"{domain}/{ctype}/{system}/modes/{mode}/all.json"))
            add_connector(Path(f"{domain}/{ctype}/{system}/modes/{mode}/{env}.json"))

        # 5bm) Domain + type + system + sink kind + mode (optional; kind is independent)
        if ctype == "sink" and mode:
            kind = sink_kind or "default"
            add_connector(
                Path(f"{domain}/{ctype}/{system}/types/{kind}/modes/{mode}/all.json")
            )
            add_connector(
                Path(f"{domain}/{ctype}/{system}/types/{kind}/modes/{mode}/{env}.json")
            )

        # 6) Connector dir shared overrides (optional)
        add_connector(Path(f"{domain}/{ctype}/{system}/{connector_dir}/all.json"))
        add_connector(Path(f"{domain}/{ctype}/{system}/{connector_dir}/{env}.json"))

        # 6b) Connector dir + sink kind (optional; kind is independent)
        if ctype == "sink":
            kind = sink_kind or "default"
            add_connector(
                Path(f"{domain}/{ctype}/{system}/{connector_dir}/types/{kind}/all.json")
            )
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/{kind}/{env}.json"
                )
            )

        # 6m) Connector dir + mode (optional)
        if mode:
            add_connector(
                Path(f"{domain}/{ctype}/{system}/{connector_dir}/modes/{mode}/all.json")
            )
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/modes/{mode}/{env}.json"
                )
            )

        # 6bm) Connector dir + sink kind + mode (optional; kind is independent)
        if ctype == "sink" and mode:
            kind = sink_kind or "default"
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/{kind}/modes/{mode}/all.json"
                )
            )
            add_connector(
                Path(
                    f"{domain}/{ctype}/{system}/{connector_dir}/types/{kind}/modes/{mode}/{env}.json"
                )
            )

        # 7) Connector base + env-specific
        if base_file and (self.fs.exists(base_file) if self.fs else base_file.exists()):
            candidates.append(base_file.resolve())
        candidates.append(env_file.resolve())

        # Optional layer minimization:
        # - reuse_overrides=False keeps only base_file + env_file (raw-ish mode)
        # - reuse_from keeps only selected override files (plus base_file + env_file)
        always_keep = {env_file.resolve()}
        if base_file:
            always_keep.add(base_file.resolve())

        keep_set = set(always_keep)
        if reuse_from:
            for p in reuse_from:
                if not p:
                    continue
                p_abs = (p if p.is_absolute() else (self.root / p)).resolve()
                keep_set.add(p_abs)

        if reuse_from:
            candidates = [p for p in candidates if p.resolve() in keep_set]
        elif not reuse_overrides:
            candidates = [p for p in candidates if p.resolve() in always_keep]

        return candidates
