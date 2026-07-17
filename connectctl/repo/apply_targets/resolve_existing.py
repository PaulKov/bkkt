from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ...models import Environment
from ...ports import FileSystem
from ..scanner import ConnectorRepo

from .instances import load_instances
from .models import ApplyItem, TemplateExpansionEvent
from .resolve_items import make_nonvirtual_item
from .scanning import scan_dir_for_env
from .templates import expand_template


def _instances_source(inst_path: Path | None, explicit: str | None) -> str:
    return explicit or (f"instances:{inst_path.name}" if inst_path else "instances")


def expand_template_or_fallback(
    *,
    template_path: Path,
    env: Environment,
    repo_root: Path,
    fs: FileSystem | None,
) -> Tuple[List[ApplyItem], TemplateExpansionEvent | None]:
    inst, inst_path, src = load_instances(
        template_path.parent, env=env, repo_root=repo_root, fs=fs
    )
    if inst:
        items, ev = expand_template(
            template_path,
            env=env,
            repo_root=repo_root,
            instances=inst,
            instances_source=_instances_source(inst_path, src),
            fs=fs,
        )
        return items, ev

    return [make_nonvirtual_item(template_path)], None


def resolve_existing_dir(
    *,
    repo: ConnectorRepo,
    path: Path,
    env: Environment,
    repo_root: Path,
    expand_templates: bool,
    fs: FileSystem | None,
) -> Tuple[List[ApplyItem], List[TemplateExpansionEvent]]:
    normal, templates = scan_dir_for_env(repo, path, env, fs=fs)

    items: List[ApplyItem] = [make_nonvirtual_item(f) for f in normal]
    expansions: List[TemplateExpansionEvent] = []

    for t in templates:
        if not expand_templates:
            items.append(make_nonvirtual_item(t))
            continue

        tmpl_items, ev = expand_template_or_fallback(
            template_path=t, env=env, repo_root=repo_root, fs=fs
        )
        items.extend(tmpl_items)
        if ev is not None:
            expansions.append(ev)

    return items, expansions


def resolve_existing_file(
    *,
    path: Path,
    env: Environment,
    repo_root: Path,
    expand_templates: bool,
    fs: FileSystem | None,
) -> Tuple[List[ApplyItem], List[TemplateExpansionEvent]]:
    if expand_templates and "${" in path.name:
        items, ev = expand_template_or_fallback(
            template_path=path, env=env, repo_root=repo_root, fs=fs
        )
        return items, [ev] if ev is not None else []

    return [make_nonvirtual_item(path)], []
