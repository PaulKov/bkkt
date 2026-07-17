"""Runner export (facade).

Исторически `ExportRunner` жил в одном файле.
Чтобы упростить сопровождение, реализация разнесена по SRP‑модулям,
а этот файл оставлен как стабильная точка импорта:

    from connectctl.services.export.runner import ExportRunner
"""

from __future__ import annotations

from .runner_impl import ExportRunner

__all__ = ["ExportRunner"]
