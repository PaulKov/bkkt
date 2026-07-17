from __future__ import annotations

import argparse
import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, cast

from ...app.context import CliContext
from ...exceptions import ValidationError
from ...logging_utils import get_logger


@dataclass(frozen=True)
class GeneratedFile:
    path: Path
    content: str


@dataclass(frozen=True)
class GeneratedFileMismatch:
    path: Path
    current: Optional[str]
    generated: str


# Keep help text rendering deterministic.
#
# Argparse wraps help output based on terminal width (via shutil.get_terminal_size)
# which is influenced by the TTY and env vars like COLUMNS. That makes generated
# docs flaky across environments (and breaks the "docs are up to date" test).
#
# 78 matches argparse's typical default width for 80-column terminals (80 - 2).
_ARGPARSE_HELP_WIDTH = 78


_FIXED_WIDTH_FORMATTERS: dict[
    type[argparse.HelpFormatter], type[argparse.HelpFormatter]
] = {}


def _fixed_width_formatter_class(
    base: type[argparse.HelpFormatter],
) -> type[argparse.HelpFormatter]:
    cached = _FIXED_WIDTH_FORMATTERS.get(base)
    if cached:
        return cached

    class _FixedWidthFormatter(base):  # type: ignore[misc, valid-type]
        def __init__(self, prog: str) -> None:
            super().__init__(prog, width=_ARGPARSE_HELP_WIDTH)

        def _format_usage(
            self,
            usage: str | None,
            actions: Iterable[argparse.Action],
            groups: Iterable[argparse._MutuallyExclusiveGroup],
            prefix: str | None,
        ) -> str:
            """Keep `usage:` blocks stable across Python argparse versions.

            Python minor versions differ in how they wrap long required
            arguments. Only generated docs use this formatter, so prefer a
            single long usage line over flaky generated-doc diffs.
            """
            original_width = int(getattr(self, "_width"))
            setattr(self, "_width", 10_000)
            try:
                return super()._format_usage(usage, actions, groups, prefix)
            finally:
                setattr(self, "_width", original_width)

        def _format_action_invocation(self, action: argparse.Action) -> str:
            """Render option aliases consistently across Python versions.

            Python 3.11 renders aliases as `--foo FOO, --bar FOO`, while newer
            versions render the same action as `--foo, --bar FOO`. Generated
            CLI docs should not depend on the Python minor used by CI or a
            maintainer laptop, so keep one compact canonical representation.
            """
            if not action.option_strings:
                return super()._format_action_invocation(action)
            if action.nargs == 0:
                return ", ".join(action.option_strings)
            default = self._get_default_metavar_for_optional(action)
            args_string = self._format_args(action, default)
            return f"{', '.join(action.option_strings)} {args_string}"

    _FixedWidthFormatter.__name__ = f"{base.__name__}FixedWidth"
    _FIXED_WIDTH_FORMATTERS[base] = _FixedWidthFormatter
    return _FixedWidthFormatter


def _find_subparsers_action(
    p: argparse.ArgumentParser,
) -> Optional[argparse._SubParsersAction]:
    for a in getattr(p, "_actions", []):
        if isinstance(a, argparse._SubParsersAction):
            return a
    return None


def _walk_parsers(
    p: argparse.ArgumentParser,
    *,
    path: Tuple[str, ...] = (),
) -> Iterable[Tuple[Tuple[str, ...], argparse.ArgumentParser]]:
    """Walk argparse tree and yield (command_path, parser).

    command_path excludes the top-level executable name ("bkkt").
    """
    yield path, p
    sub = _find_subparsers_action(p)
    if not sub:
        return
    # Argparse stores choices in insertion order (Python dict preserves order).
    for name, sp in sub.choices.items():
        yield from _walk_parsers(sp, path=path + (name,))


def _translate_argparse_help(help_text: str) -> str:
    """Best-effort перевод стандартных заголовков argparse на русский для docs.

    Важно: это *только* для документации. CLI output при `--help` остаётся как есть.
    """
    replacements = {
        "usage:": "использование:",
        "options:": "опции:",
        "positional arguments:": "позиционные аргументы:",
        "optional arguments:": "опциональные аргументы:",
        "show this help message and exit": "показать эту справку и выйти",
        "(default:": "(по умолчанию:",
        " default:": " по умолчанию:",
        "default:": "по умолчанию:",
        "Default:": "По умолчанию:",
    }
    out_lines = []
    for line in help_text.splitlines():
        for src, dst in replacements.items():
            if src in line:
                line = line.replace(src, dst)
        out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if help_text.endswith("\n") else "")


def _render_help_text(p: argparse.ArgumentParser, *, cmd_path: Tuple[str, ...]) -> str:
    """Render --help text with stable `prog` ("bkkt ...")."""
    p.prog = "bkkt" + ("" if not cmd_path else " " + " ".join(cmd_path))

    # NOTE: format_help() is sensitive to the terminal width.
    # Force a fixed width to make generated docs stable across environments.
    orig_formatter_class = cast(type[argparse.HelpFormatter], p.formatter_class)
    p.formatter_class = _fixed_width_formatter_class(orig_formatter_class)
    try:
        # format_help() already includes trailing newline
        return _translate_argparse_help(p.format_help().rstrip() + "\n")
    finally:
        p.formatter_class = orig_formatter_class


def _build_common_preamble_md() -> str:
    return (
        "# Справочник CLI: `bkkt` / `connectctl`\n\n"
        "Этот документ **генерируется автоматически** из актуального `argparse --help`.\n\n"
        "- Команда генерации: `bkkt docs generate-cli-reference`\n"
        "- Живые примеры: `docs/CLI_EXAMPLES.md`\n\n"
        "⚠️ Не редактируйте блок **Команды** вручную — он перезаписывается генератором.\n\n"
        "## Команды\n\n"
    )


def _render_commands_markdown(parser: argparse.ArgumentParser) -> str:
    parts: List[str] = []
    parts.append("<!-- BKKT_CLI_REFERENCE_COMMANDS_START -->\n")
    for cmd_path, sp in _walk_parsers(parser, path=()):
        # skip empty root here? no, include root help as first section.
        depth = len(cmd_path)
        if depth == 0:
            title = "`bkkt --help` (общая справка)"
            level = 3
        else:
            title = "`bkkt " + " ".join(cmd_path) + " --help`"
            level = min(3 + (depth - 1), 6)
        parts.append(f'{"#"*level} {title}\n\n')
        help_text = _render_help_text(sp, cmd_path=cmd_path)
        parts.append("```text\n")
        parts.append(help_text.rstrip())
        parts.append("\n```\n\n")
    parts.append("<!-- BKKT_CLI_REFERENCE_COMMANDS_END -->\n")
    return "".join(parts)


def _replace_block(existing: str, *, start: str, end: str, new_block: str) -> str:
    if start in existing and end in existing:
        before = existing.split(start)[0]
        after = existing.split(end, 1)[1]
        return before + new_block + after
    # If markers are missing, return full new content.
    return new_block


class GenerateCliReferenceService:
    """Generate CLI_REFERENCE docs from argparse --help.

    Supports:
      - docs/CLI_REFERENCE.md (Markdown)
    """

    def __init__(self, *, ctx: CliContext, logger=None):
        self.ctx = ctx
        self.log = get_logger(logger or ctx.logger)

    def run(self, args) -> int:
        docs_dir = Path(str(getattr(args, "docs_dir", "docs") or "docs"))
        target = str(getattr(args, "target", "all") or "all").strip().lower()
        check = bool(getattr(args, "check", False))
        show_diff = bool(getattr(args, "show_diff", False))
        diff_lines = int(getattr(args, "diff_lines", 200) or 0)

        # local import to avoid circular import with cli_parser/registry
        from ...cli_parser import build_parser

        parser = build_parser()

        files: List[GeneratedFile] = []
        if target in {"all", "md", "markdown"}:
            files.append(self._gen_md(parser, docs_dir=docs_dir))

        if not files:
            raise ValidationError(f"Неизвестный target={target!r}. Допустимо: all|md")

        mismatched: List[GeneratedFileMismatch] = []

        def _normalize_doc(text: str) -> str:
            """Normalize docs for stable comparisons across platforms.

            This makes `--check` robust to:
              - git/autocrlf (CRLF vs LF)
              - editors adding trailing whitespace
            """
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            lines = [ln.rstrip() for ln in text.split("\n")]
            return "\n".join(lines).rstrip("\n") + "\n"

        for gf in files:
            if check:
                if not self.ctx.fs.exists(gf.path):
                    mismatched.append(
                        GeneratedFileMismatch(
                            path=gf.path,
                            current=None,
                            generated=gf.content,
                        )
                    )
                    continue
                cur = _normalize_doc(self.ctx.fs.read_text(gf.path))
                gen = _normalize_doc(gf.content)
                if cur != gen:
                    mismatched.append(
                        GeneratedFileMismatch(
                            path=gf.path,
                            current=cur,
                            generated=gen,
                        )
                    )
            else:
                self.ctx.fs.mkdirs(gf.path.parent, exist_ok=True)
                self.ctx.fs.write_text(gf.path, _normalize_doc(gf.content))

        if check:
            if mismatched:
                if show_diff and diff_lines != 0:
                    for mm in mismatched:
                        self._log_doc_diff(mm, max_lines=diff_lines)
                self.log.error(
                    "CLI reference docs устарели (%s). Выполните: bkkt docs generate-cli-reference",
                    ", ".join(str(mm.path) for mm in mismatched),
                )
                return 2
            self.log.info("CLI reference docs актуальны.")
            return 0

        for gf in files:
            self.log.info("✅ Сгенерирован файл: %s", gf.path.as_posix())
        return 0

    def _gen_md(
        self, parser: argparse.ArgumentParser, *, docs_dir: Path
    ) -> GeneratedFile:
        path = (self.ctx.repo_root / docs_dir / "CLI_REFERENCE.md").resolve()
        block = _render_commands_markdown(parser)
        content = _build_common_preamble_md() + block
        return GeneratedFile(path=path, content=content)

    def _log_doc_diff(self, mm: GeneratedFileMismatch, *, max_lines: int) -> None:
        try:
            rel = mm.path.relative_to(self.ctx.repo_root)
        except Exception:
            rel = mm.path

        cur = mm.current if mm.current is not None else ""
        gen = mm.generated

        diff_text = "".join(
            difflib.unified_diff(
                cur.splitlines(keepends=True),
                gen.splitlines(keepends=True),
                fromfile=f"current:{rel.as_posix()}",
                tofile=f"generated:{rel.as_posix()}",
            )
        )
        if not diff_text:
            if mm.current is None:
                diff_text = f"(missing file; would create {rel.as_posix()})\n"
            else:
                diff_text = "(no textual diff available)\n"

        if max_lines > 0:
            lines = diff_text.splitlines()
            if len(lines) > max_lines:
                diff_text = "\n".join(lines[:max_lines]) + "\n... (diff truncated)"

        self.log.error("CLI reference diff for %s:\n%s", rel.as_posix(), diff_text)
