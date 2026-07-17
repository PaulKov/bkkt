from __future__ import annotations

import argparse
from typing import Callable


def register_parser(
    subparsers: argparse._SubParsersAction,
    *,
    handler: Callable[[argparse.Namespace], int],
) -> argparse.ArgumentParser:
    s = subparsers.add_parser(
        "completion",
        help="Сгенерировать shell snippet для автодополнения (argcomplete)",
    )
    s.add_argument(
        "--shell",
        required=True,
        choices=["bash", "zsh", "fish"],
        help="Целевая оболочка",
    )
    s.add_argument(
        "--program",
        default="bkkt",
        help="Имя CLI entrypoint (bkkt или connectctl). По умолчанию: bkkt",
    )
    s.add_argument(
        "--no-comments",
        action="store_true",
        help='Вывести только snippet без комментариев (удобно для eval "$(...)")',
    )
    s.add_argument(
        "--install",
        action="store_true",
        help="Автоматически установить автодополнение в конфиг оболочки (с подтверждением)",
    )
    s.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Предпросмотр установки: показать, куда будет установлен completion и какой diff будет применён, "
            "но ничего не изменять на диске. Если указано без --install — BKKT автоматически переходит в режим предпросмотра."
        ),
    )
    s.add_argument(
        "--system",
        action="store_true",
        help=(
            "Установить completion в системный путь (для всех пользователей). "
            "Может потребоваться sudo. BKKT автоматически подбирает системный путь "
            "в зависимости от ОС (Linux/macOS) и наличия каталогов. Примеры путей: "
            "bash=/etc/bash_completion.d/<program> или /opt/homebrew/etc/bash_completion.d/<program>, "
            "zsh=/etc/zshrc, fish=/usr/share/fish/vendor_completions.d/<program>.fish."
        ),
    )
    s.add_argument(
        "--rc-file",
        default=None,
        help=(
            "Путь для установки completion. По умолчанию: ~/.bashrc (bash), ~/.zshrc (zsh), "
            "~/.config/fish/completions/<program>.fish (fish)."
        ),
    )
    s.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение при --install",
    )
    s.set_defaults(func=handler, requires_config=False)
    return s
