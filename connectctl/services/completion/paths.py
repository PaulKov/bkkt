from __future__ import annotations

import os
import platform
from pathlib import Path


def detect_os_name() -> str:
    try:
        return (platform.system() or "").strip().lower() or "unknown"
    except Exception:
        return "unknown"


def _pick_existing_dir(candidates: list[Path], *, fallback: Path) -> Path:
    for d in candidates:
        try:
            if d.is_dir():
                return d
        except Exception:
            continue
    return fallback


def _pick_existing_file(candidates: list[Path], *, fallback: Path) -> Path:
    for f in candidates:
        try:
            if f.exists():
                return f
        except Exception:
            continue
    return fallback


def default_install_path(
    *, shell: str, prog: str, rc_file: str | None, system: bool
) -> Path:
    """Определить путь установки completion.

    Приоритет:
    1) явный `--rc-file`
    2) user/system defaults

    `--system` использует OS-aware дефолты (Linux/macOS) и выбирает первый существующий каталог.
    """

    if rc_file:
        return Path(os.path.expanduser(rc_file)).resolve()

    os_name = detect_os_name()

    if not system:
        if shell == "bash":
            bashrc = Path(os.path.expanduser("~/.bashrc")).resolve()
            # macOS: у части пользователей bash стартует как login shell и читает ~/.bash_profile.
            # Если ~/.bashrc отсутствует, а ~/.bash_profile есть — установим туда, чтобы completion реально заработал.
            if os_name == "darwin":
                bash_profile = Path(os.path.expanduser("~/.bash_profile")).resolve()
                try:
                    if not bashrc.exists() and bash_profile.exists():
                        return bash_profile
                except Exception:
                    pass
            return bashrc
        if shell == "zsh":
            return Path(os.path.expanduser("~/.zshrc")).resolve()
        # fish
        return Path(
            os.path.expanduser(f"~/.config/fish/completions/{prog}.fish")
        ).resolve()

    # system-wide
    if shell == "bash":
        candidates = (
            [
                Path("/opt/homebrew/etc/bash_completion.d"),
                Path("/usr/local/etc/bash_completion.d"),
                Path("/etc/bash_completion.d"),
                Path("/opt/homebrew/share/bash-completion/completions"),
                Path("/usr/local/share/bash-completion/completions"),
                Path("/usr/share/bash-completion/completions"),
            ]
            if os_name == "darwin"
            else [
                Path("/etc/bash_completion.d"),
                Path("/usr/local/etc/bash_completion.d"),
                Path("/usr/share/bash-completion/completions"),
            ]
        )
        base = _pick_existing_dir(
            list(candidates), fallback=Path("/etc/bash_completion.d")
        )
        return (base / prog).resolve()

    if shell == "zsh":
        candidates = (
            [
                Path("/etc/zshrc"),
                Path("/etc/zsh/zshrc"),
                Path("/opt/homebrew/etc/zshrc"),
                Path("/usr/local/etc/zshrc"),
            ]
            if os_name == "darwin"
            else [
                Path("/etc/zshrc"),
                Path("/etc/zsh/zshrc"),
                Path("/usr/local/etc/zshrc"),
            ]
        )
        return _pick_existing_file(
            list(candidates), fallback=Path("/etc/zshrc")
        ).resolve()

    # fish
    candidates = (
        [
            Path("/opt/homebrew/share/fish/vendor_completions.d"),
            Path("/usr/local/share/fish/vendor_completions.d"),
            Path("/usr/share/fish/vendor_completions.d"),
        ]
        if os_name == "darwin"
        else [
            Path("/usr/local/share/fish/vendor_completions.d"),
            Path("/usr/share/fish/vendor_completions.d"),
        ]
    )
    base = _pick_existing_dir(
        list(candidates), fallback=Path("/usr/share/fish/vendor_completions.d")
    )
    return (base / f"{prog}.fish").resolve()
