from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from ...models import Environment
from ...ports import FileSystem
from ...utils import flatten_dict

from .models import ApplyItem, TemplateExpansionEvent

_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")


def substitute_placeholders(s: str, vars_map: Mapping[str, str]) -> str:
    """Подставить плейсхолдеры ${var} в имени файла.

    - НЕ подставляет provider placeholders типа ${secretManager:...}
    - Неизвестные vars оставляет как есть.
    """

    def repl(m: re.Match) -> str:
        inner = (m.group(1) or "").strip()
        if not inner:
            return m.group(0)
        if ":" in inner:
            return m.group(0)
        if inner in vars_map:
            return str(vars_map[inner])
        return m.group(0)

    return _PLACEHOLDER_RE.sub(repl, s)


def template_to_regex(template_name: str) -> re.Pattern:
    r"""Конвертировать template имя файла в regex с named groups.

    Пример:
      prod.foo.${index}.json -> ^prod\.foo\.(?P<index>[^/]+)\.json$
    """

    parts: List[str] = []
    i = 0
    while True:
        m = _PLACEHOLDER_RE.search(template_name, i)
        if not m:
            parts.append(re.escape(template_name[i:]))
            break
        parts.append(re.escape(template_name[i : m.start()]))
        inner = (m.group(1) or "").strip()
        if inner and ":" not in inner:
            parts.append(rf"(?P<{re.escape(inner)}>[^/]+)")
        else:
            parts.append(re.escape(m.group(0)))
        i = m.end()

    rx = "^" + "".join(parts) + "$"
    return re.compile(rx)


def expand_template(
    template_path: Path,
    *,
    env: Environment,
    repo_root: Path,
    instances: List[Dict[str, str]],
    instances_source: str,
    fs: FileSystem | None = None,
) -> Tuple[List[ApplyItem], Optional[TemplateExpansionEvent]]:
    if not instances:
        return [], None

    generated: List[Path] = []
    skipped: List[Path] = []
    items: List[ApplyItem] = []
    seen: set[str] = set()

    for inst in instances:
        vars_map = {"env": env.value}
        vars_map.update({k: str(v) for k, v in inst.items()})
        virt_name = substitute_placeholders(template_path.name, vars_map)
        requested = template_path.parent / virt_name

        if fs.exists(requested) if fs else requested.exists():
            skipped.append(requested)
            continue

        if virt_name in seen:
            continue
        seen.add(virt_name)
        generated.append(requested)

        flat = flatten_dict(inst)
        sources = {k: instances_source for k in flat.keys()}
        items.append(
            ApplyItem(
                actual_path=template_path.resolve(),
                requested_path=requested.resolve(),
                runtime_vars=inst,
                runtime_var_sources=sources,
                is_virtual=True,
            )
        )

    ev = TemplateExpansionEvent(
        template_path=template_path.resolve(),
        source=instances_source,
        generated=tuple(p.resolve() for p in generated),
        skipped_existing=tuple(p.resolve() for p in skipped),
    )
    return items, ev


def try_resolve_to_template(
    requested: Path, *, fs: FileSystem | None = None
) -> Optional[Path]:
    parent = requested.parent

    if fs:
        if not fs.exists(parent) or not fs.is_dir(parent):
            return None
        candidates = sorted(
            [p for p in fs.glob(parent, "*.json") if "${" in p.name],
            key=lambda p: str(p),
        )
    else:
        if not parent.exists() or not parent.is_dir():
            return None
        candidates = sorted([p for p in parent.glob("*.json") if "${" in p.name])
    for cand in candidates:
        rx = template_to_regex(cand.name)
        if rx.match(requested.name):
            return cand
    return None


def extract_vars_from_requested(template_path: Path, requested: Path) -> Dict[str, str]:
    rx = template_to_regex(template_path.name)
    m = rx.match(requested.name)
    if not m:
        return {}
    return {k: v for k, v in m.groupdict().items() if v is not None}
