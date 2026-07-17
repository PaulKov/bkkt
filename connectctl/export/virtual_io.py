from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..ports import FileSystem

from ..rendering.json_loader import load_json_file
from ..utils import expand_env_in_obj


def load_json_virtual(
    path: Path,
    planned: Mapping[Path, Mapping[str, Any]],
    *,
    fs: FileSystem | None = None,
) -> Any:
    """Загрузить JSON либо из «виртуального плана» (planned files), либо с диска.

    Во время export часть файлов может ещё не существовать в репозитории.
    При этом `Path`-объекты могут отличаться между платформами (например, macOS),
    поэтому здесь есть несколько попыток найти planned-файл по эквивалентным путям.
    """

    if path in planned:
        return expand_env_in_obj(planned[path])

    try:
        rp = path.resolve()
    except Exception:
        rp = path

    if rp in planned:
        return expand_env_in_obj(planned[rp])

    # Small planned sets: fall back to string compare on resolved paths.
    try:
        rp_str = str(rp)
        for k, v in planned.items():
            try:
                if str(k.resolve()) == rp_str:
                    return expand_env_in_obj(v)
            except Exception:
                if str(k) == rp_str:
                    return expand_env_in_obj(v)
    except Exception:
        pass

    return load_json_file(path, fs=fs)
