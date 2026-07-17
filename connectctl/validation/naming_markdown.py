from __future__ import annotations

from typing import Sequence

from .naming_common import NamingLintIssue


def build_naming_lint_markdown(
    issues: Sequence[NamingLintIssue],
    *,
    title: str = "connectctl naming lint",
    show_vars: bool = False,
) -> str:
    """Build a portable markdown report for naming issues."""

    md: list[str] = []
    md.append(f"## {title}\n\n")

    if not issues:
        md.append("✅ Ошибок нейминга не найдено.\n")
        return "".join(md)

    md.append(f"Найдено **{len(issues)}** проблем(ы) нейминга.\n\n")
    md.append(
        "| Манифест | Имя | Dataset (источник) | Ожидалось | Suggested | Ошибки |\n"
    )
    md.append("|---|---|---|---|---|---|\n")

    def _code(x: str) -> str:
        return f"`{x}`" if x else ""

    for it in issues:
        expected = it.expected_template or it.expected_pattern or "(no rule)"
        suggested = it.suggested_name or ""
        errs = "<br>".join(it.errors) if it.errors else ""
        ds = str((it.vars or {}).get("dataset") or "")
        ds_src = str((it.vars or {}).get("dataset_source") or "")
        ds_cell = _code(ds) + (f" ({ds_src})" if ds and ds_src else "")
        md.append(
            "| {path} | {actual} | {ds} | {expected} | {suggested} | {errs} |\n".format(
                path=_code(it.relpath),
                actual=_code(it.actual_name),
                ds=ds_cell,
                expected=_code(expected),
                suggested=_code(suggested),
                errs=errs,
            )
        )

    if show_vars:
        md.append("\n### Извлечённые переменные (debug)\n\n")
        for it in issues:
            md.append(f"<details><summary>{it.relpath}</summary>\n\n")
            md.append("```\n")
            for k in sorted(it.vars.keys()):
                md.append(f"{k}: {it.vars.get(k)}\n")
            md.append("```\n")
            md.append("</details>\n")

    md.append("\n> Что делать:\n")
    md.append(
        "> - Исправить `name` в манифесте так, чтобы он соответствовал шаблону/правилу; или\n"
    )
    md.append(
        "> - Подправить `connectctl.yaml:naming.rules`, если конвенция изменилась; или\n"
    )
    md.append(
        "> - Для легаси имён добавить `naming.extra_allowed_patterns` как escape hatch.\n"
    )
    md.append("> - Подробности: `docs/NAMING.md` (или `bkkt help naming`).\n")

    return "".join(md)
