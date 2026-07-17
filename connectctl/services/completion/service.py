from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Optional

from ...app.context import CliContext
from ...exceptions import ConfigError
from ...logging_utils import get_logger
from ...output import write_text
from .diff_utils import format_unified_diff
from .models import InstallAction
from .paths import default_install_path, detect_os_name
from .rc_block import upsert_marked_block, wrap_rc_block


@dataclass
class CompletionService:
    """Сервис `bkkt completion`.

    Генерирует shell snippet для включения argcomplete.
    """

    ctx: CliContext
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self.log = get_logger(self.logger or self.ctx.logger)

    def run(self, args) -> int:
        shell = str(getattr(args, "shell", "")).strip().lower()
        prog = str(getattr(args, "program", "bkkt")).strip() or "bkkt"
        no_comments = bool(getattr(args, "no_comments", False))
        install = bool(getattr(args, "install", False))
        dry_run = bool(getattr(args, "dry_run", False))
        system = bool(getattr(args, "system", False))
        yes = bool(getattr(args, "yes", False))
        rc_file = getattr(args, "rc_file", None)

        if shell not in {"bash", "zsh", "fish"}:
            raise ConfigError("--shell должен быть одним из: bash, zsh, fish")

        # UX: если пользователь указал --dry-run без --install, трактуем это как "предпросмотр установки".
        if dry_run and not install:
            install = True

        if install:
            # Для установки в rc-файл/директорию лучше использовать чистый snippet (без подсказок).
            # В dry-run для fish допускаем fallback (без реального скрипта), чтобы можно было
            # посмотреть target path и пример diff даже на машинах без argcomplete.
            txt = self._render(
                shell, prog, no_comments=True, require_fish_script=not dry_run
            )
            if (
                dry_run
                and shell == "fish"
                and txt.strip().startswith("register-python-argcomplete --shell fish")
            ):
                self.log.warning(
                    "Fish completion: не удалось сгенерировать реальный completion script. "
                    "В dry-run показан fallback-командный snippet. Для реальной установки установите argcomplete."
                )
            self._install(
                shell=shell,
                prog=prog,
                rc_file=rc_file,
                txt=txt,
                yes=yes,
                system=system,
                dry_run=dry_run,
            )
            return 0

        txt = self._render(
            shell, prog, no_comments=no_comments, require_fish_script=False
        )
        write_text(txt.rstrip() + "\n")
        return 0

    def _install(
        self,
        *,
        shell: str,
        prog: str,
        rc_file: str | None,
        txt: str,
        yes: bool,
        system: bool,
        dry_run: bool,
    ) -> None:
        target = default_install_path(
            shell=shell, prog=prog, rc_file=rc_file, system=system
        )
        mode = "system" if system else "user"
        os_name = detect_os_name()
        self.log.info(
            "BKKT completion install: mode=%s os=%s shell=%s program=%s target=%s",
            mode,
            os_name,
            shell,
            prog,
            target,
        )

        if dry_run:
            self.log.info("Режим dry-run: файлы не будут изменены")

        if not yes and not dry_run:
            ans = (
                input(f"Установить автодополнение BKKT в {target}? [y/N]: ")
                .strip()
                .lower()
            )
            if ans != "y":
                self.log.info("Отменено")
                return

        if shell in {"bash", "zsh"}:
            block = wrap_rc_block(shell=shell, prog=prog, snippet=txt)
            try:
                existing = ""
                can_read = True
                if target.exists():
                    try:
                        existing = target.read_text(encoding="utf-8")
                    except PermissionError as e:
                        if dry_run:
                            can_read = False
                            self.log.warning(
                                "Не удалось прочитать %s (нет прав). Diff будет недоступен. Оригинальная ошибка: %s",
                                target,
                                e,
                            )
                        else:
                            raise

                up = upsert_marked_block(existing, block=block) if can_read else None
                install_action: InstallAction = (
                    up.action if up else ("updated" if target.exists() else "inserted")
                )
                start_marker = up.start_marker if up else block.splitlines()[0]
                end_marker = up.end_marker if up else block.splitlines()[-1]

                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if up and up.action != "unchanged":
                        target.write_text(up.text, encoding="utf-8")

                self._log_install_result(
                    shell=shell,
                    prog=prog,
                    target=target,
                    system=system,
                    action=install_action,
                    start_marker=start_marker,
                    end_marker=end_marker,
                    dry_run=dry_run,
                )

                if can_read and up and up.action != "unchanged":
                    diff_txt = format_unified_diff(
                        existing,
                        up.text,
                        fromfile=f"{target} (до)",
                        tofile=f"{target} (после)",
                    )
                    if diff_txt.strip():
                        self.log.info("Diff (что изменилось):\n%s", diff_txt.rstrip())
                elif dry_run and not can_read:
                    self.log.info("Блок, который будет установлен:\n%s", block.rstrip())
                return
            except PermissionError as e:
                raise ConfigError(
                    f"Нет прав на запись в {target}. "
                    f"Попробуйте запустить с sudo или укажите пользовательский путь через --rc-file. "
                    f"Оригинальная ошибка: {e}"
                ) from e

        # fish: completion хранится в отдельном файле completions/<prog>.fish
        try:
            new_txt = txt.rstrip() + "\n"
            old_txt = ""
            can_read = True
            if target.exists():
                try:
                    old_txt = target.read_text(encoding="utf-8")
                except PermissionError as e:
                    if dry_run:
                        can_read = False
                        self.log.warning(
                            "Не удалось прочитать %s (нет прав). Diff будет недоступен. Оригинальная ошибка: %s",
                            target,
                            e,
                        )
                    else:
                        raise
                action: InstallAction = (
                    "unchanged" if can_read and old_txt == new_txt else "updated"
                )
            else:
                action = "inserted"

            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                if action != "unchanged":
                    target.write_text(new_txt, encoding="utf-8")

            self._log_install_result(
                shell=shell,
                prog=prog,
                target=target,
                system=system,
                action=action,
                dry_run=dry_run,
            )
            if can_read and action != "unchanged":
                diff_txt = format_unified_diff(
                    old_txt,
                    new_txt,
                    fromfile=f"{target} (до)",
                    tofile=f"{target} (после)",
                )
                if diff_txt.strip():
                    self.log.info("Diff (что изменилось):\n%s", diff_txt.rstrip())
            elif dry_run and not can_read:
                self.log.info("Блок, который будет установлен:\n%s", new_txt.rstrip())
        except PermissionError as e:
            raise ConfigError(
                f"Нет прав на запись в {target}. "
                f"Попробуйте запустить с sudo или укажите пользовательский путь через --rc-file. "
                f"Оригинальная ошибка: {e}"
            ) from e

    def _log_install_result(
        self,
        *,
        shell: str,
        prog: str,
        target: Path,
        system: bool,
        action: InstallAction,
        start_marker: str | None = None,
        end_marker: str | None = None,
        dry_run: bool = False,
    ) -> None:
        mode = "system" if system else "user"
        human_action = {
            "inserted": "будет добавлено" if dry_run else "добавлено",
            "updated": "будет обновлено" if dry_run else "обновлено",
            "unchanged": "уже актуально",
        }.get(action, action)

        prefix = "BKKT completion (dry-run)" if dry_run else "BKKT completion"
        self.log.info(
            "%s: %s (%s). shell=%s program=%s", prefix, human_action, mode, shell, prog
        )
        self.log.info("Файл: %s", target)
        if start_marker and end_marker:
            self.log.info("Блок: %s ... %s", start_marker, end_marker)
        if dry_run:
            self.log.info("Подсказка: уберите --dry-run, чтобы применить изменения.")
        else:
            self.log.info(
                "Подсказка: откройте новый терминал/сессию shell, чтобы completion подхватился."
            )

    def _render(
        self, shell: str, prog: str, *, no_comments: bool, require_fish_script: bool
    ) -> str:
        if shell == "bash":
            return self._bash(prog, no_comments=no_comments)
        if shell == "zsh":
            return self._zsh(prog, no_comments=no_comments)
        return self._fish(
            prog, no_comments=no_comments, require_script=require_fish_script
        )

    @staticmethod
    def _bash(prog: str, *, no_comments: bool) -> str:
        snippet = f'eval "$(register-python-argcomplete {prog})"\n'
        if no_comments:
            return snippet
        return (
            "# BKKT автодополнение (bash)\n"
            "# 1) pip install argcomplete\n"
            "# 2) добавьте в ~/.bashrc или выполните eval для текущей сессии\n"
            + snippet
        )

    @staticmethod
    def _zsh(prog: str, *, no_comments: bool) -> str:
        snippet = (
            "autoload -U bashcompinit && bashcompinit\n"
            f'eval "$(register-python-argcomplete {prog})"\n'
        )
        if no_comments:
            return snippet
        return (
            "# BKKT автодополнение (zsh)\n"
            "# 1) pip install argcomplete\n"
            "# 2) добавьте в ~/.zshrc или выполните snippet для текущей сессии\n"
            + snippet
        )

    def _fish(self, prog: str, *, no_comments: bool, require_script: bool) -> str:
        # Лучший вариант: вывести реальный fish script от argcomplete.
        # Он удобен для `bkkt completion --shell fish > ~/.config/fish/completions/bkkt.fish`.
        exe = shutil.which("register-python-argcomplete")
        if exe:
            try:
                p = subprocess.run(
                    [exe, "--shell", "fish", prog],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                out = (p.stdout or "").rstrip() + "\n"
                if out.strip():
                    return out
            except Exception:
                # Падаем в fallback ниже.
                pass

        if require_script:
            raise ConfigError(
                "Не удалось сгенерировать fish completion script. "
                "Проверьте, что установлен пакет argcomplete и доступна команда register-python-argcomplete."
            )

        # Fallback: инструктивный snippet (без выполнения).
        cmd = f"register-python-argcomplete --shell fish {prog} > ~/.config/fish/completions/{prog}.fish\n"
        if no_comments:
            return cmd
        return (
            "# BKKT автодополнение (fish)\n"
            "# 1) pip install argcomplete\n"
            "# 2) выполните:\n" + cmd
        )
