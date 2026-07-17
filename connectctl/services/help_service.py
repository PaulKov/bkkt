from __future__ import annotations

import re
from dataclasses import dataclass
import logging
from typing import List, Optional
import argparse

from ..app.context import CliContext
from ..exceptions import ConfigError
from ..logging_utils import get_logger
from ..output import write_text


@dataclass
class HelpService:
    """Сервис `bkkt help`.

    Показывает короткую шпаргалку с примерами команд из docs/CLI_EXAMPLES.md.
    Без дублирования: примеры остаются в документации и переиспользуются CLI.
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = (
        None  # logging.Logger, но не тащим typing в рантайм
    )

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        topic_tokens: List[str] = list(getattr(args, "topic", []) or [])
        topic = " ".join(t.strip() for t in topic_tokens if str(t).strip()).strip()

        docs_path = (self.ctx.repo_root / "docs" / "CLI_EXAMPLES.md").resolve()
        if not docs_path.exists():
            return self._run_from_argparse(topic=topic, docs_path=docs_path)

        text = docs_path.read_text(encoding="utf-8")

        if not topic or bool(getattr(args, "list", False)):
            topics = self._list_topics(text)
            write_text(
                "Доступные темы (из docs/CLI_EXAMPLES.md):\n\n"
                + "\n".join(f"- {t}" for t in topics)
                + "\n"
            )
            return 0

        section = self._extract_section(text, topic)
        if section is None:
            topics = self._list_topics(text)
            raise ConfigError(
                "Не удалось найти тему в docs/CLI_EXAMPLES.md: "
                + repr(topic)
                + "\n"
                + "Доступные темы: "
                + ", ".join(topics)
            )

        write_text(section.rstrip() + "\n")
        return 0

    @staticmethod
    def _run_from_argparse(*, topic: str, docs_path) -> int:
        from ..cli_parser import build_parser

        parser = build_parser()
        if topic:
            topic_parser = HelpService._find_argparse_topic(parser, topic.split())
            if topic_parser is None:
                raise ConfigError(
                    "Не удалось найти тему в argparse help: "
                    + repr(topic)
                    + f"\nФайл с живыми примерами тоже не найден: {docs_path}"
                )
            write_text(topic_parser.format_help())
            return 0

        topics = HelpService._list_argparse_topics(parser)
        write_text(
            "Доступные команды (argparse --help; docs/CLI_EXAMPLES.md не найден):\n\n"
            + "\n".join(f"- {t}" for t in topics)
            + "\n"
        )
        return 0

    @staticmethod
    def _list_argparse_topics(parser: argparse.ArgumentParser) -> List[str]:
        subparsers = HelpService._subparsers_action(parser)
        if subparsers is None:
            return []
        return sorted(str(name) for name in subparsers.choices)

    @staticmethod
    def _find_argparse_topic(
        parser: argparse.ArgumentParser, tokens: List[str]
    ) -> argparse.ArgumentParser | None:
        current = parser
        for token in tokens:
            subparsers = HelpService._subparsers_action(current)
            if subparsers is None:
                return None
            next_parser = subparsers.choices.get(token)
            if next_parser is None:
                return None
            current = next_parser
        return current

    @staticmethod
    def _subparsers_action(
        parser: argparse.ArgumentParser,
    ) -> argparse._SubParsersAction | None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action
        return None

    @staticmethod
    def _list_topics(text: str) -> List[str]:
        out: List[str] = []
        for m in re.finditer(r"^##\s+(.+?)\s*$", text, flags=re.M):
            out.append(m.group(1).strip())
        return out

    @staticmethod
    def _extract_section(text: str, topic: str) -> str | None:
        topic_re = re.escape(topic.strip())
        m = re.search(rf"^##\s+{topic_re}\s*$", text, flags=re.M)
        if not m:
            return None
        start = m.start()
        m2 = re.search(r"^##\s+", text[m.end() :], flags=re.M)
        end = (m.end() + m2.start()) if m2 else len(text)
        return text[start:end]
