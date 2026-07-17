"""Layout helpers (facade).

В прошлых версиях весь код по авто-детекту layout/коллизиям/имёнам файлов
лежал в одном модуле. Для удобства поддержки он разнесён по SRP‑модулям,
а этот файл оставлен как стабильный фасад.

Импорты вида:

    from connectctl.export.layout import DetectedLayout, autodetect_layout_from_name

должны продолжать работать.
"""

from __future__ import annotations

from .layout_models import DetectedLayout
from .layout_detect import autodetect_layout_from_name
from .layout_files import build_sink_manifest_filename, build_source_manifest_filename
from .layout_collision import resolve_sink_export_collision

__all__ = [
    "DetectedLayout",
    "autodetect_layout_from_name",
    "build_sink_manifest_filename",
    "build_source_manifest_filename",
    "resolve_sink_export_collision",
]
