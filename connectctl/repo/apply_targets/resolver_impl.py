from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

from ...models import Environment
from ...ports import FileSystem
from ..scanner import ConnectorRepo

from .globs import expand_globs
from .models import ApplyItem, ApplyTargets, TemplateExpansionEvent
from .resolve_existing import resolve_existing_dir, resolve_existing_file
from .resolve_items import add_unique_item
from .resolve_missing import resolve_missing_template


def resolve_apply_targets(
    *,
    raw_paths: Sequence[str],
    env: Environment,
    repo_root: Path,
    repo: ConnectorRepo,
    expand_templates: bool,
    fs: FileSystem | None = None,
) -> ApplyTargets:
    """Resolve CLI-provided paths for `connectctl apply`.

    Поддерживает:
      - файлы
      - директории (рекурсивно)
      - globs (если переданы в кавычках; shell может развернуть раньше)
      - optional template expansion (когда --expand-templates включён):
          - если путь не существует: пробуем сопоставить "виртуальный" файл с существующим template
            и вытащить vars из requested filename
          - template файлы, найденные при scan директории: расширяются в несколько виртуальных инстансов
            по instances из <env>.instances.* / instances.* / vars.index|vars.instances

    Возвращает:
      ApplyTargets(items=[...], template_mappings=[(requested, template)], expansions=[...])
    """

    repo_root = repo_root.resolve()
    fs = fs or repo.fs

    items: List[ApplyItem] = []
    mappings: List[Tuple[Path, Path]] = []
    expansions: List[TemplateExpansionEvent] = []

    for raw in raw_paths:
        expanded = expand_globs(raw, repo_root, fs=fs)
        if not expanded:
            expanded = [Path(raw) if Path(raw).is_absolute() else (repo_root / raw)]

        for p0 in expanded:
            p = p0 if p0.is_absolute() else p0.resolve()

            exists = fs.exists(p) if fs else p.exists()
            if exists:
                is_dir = fs.is_dir(p) if fs else p.is_dir()
                if is_dir:
                    new_items, new_exp = resolve_existing_dir(
                        repo=repo,
                        path=p,
                        env=env,
                        repo_root=repo_root,
                        expand_templates=expand_templates,
                        fs=fs,
                    )
                else:
                    new_items, new_exp = resolve_existing_file(
                        path=p,
                        env=env,
                        repo_root=repo_root,
                        expand_templates=expand_templates,
                        fs=fs,
                    )

                for it in new_items:
                    add_unique_item(items, it)
                expansions.extend(new_exp)
                continue

            # not exists
            missing = resolve_missing_template(
                requested_path=p,
                expand_templates=expand_templates,
                fs=fs,
            )
            if missing is not None:
                it, mapping = missing
                mappings.append(mapping)
                add_unique_item(items, it)
                continue

            raise FileNotFoundError(f"No such file or directory: {p}")

    items.sort(key=lambda it: str(it.requested_path))
    return ApplyTargets(items=items, template_mappings=mappings, expansions=expansions)
