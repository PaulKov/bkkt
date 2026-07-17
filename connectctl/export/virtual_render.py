"""Обратносуместимый фасад для «виртуального» рендера.

Ранее весь код жил в одном модуле `virtual_render.py`. В рамках рефакторинга
мы разнесли реализацию по SRP-модулям:

- `virtual_io.py` — загрузка JSON из planned/disk
- `virtual_layers.py` — вычисление списка override-слоёв
- `virtual_renderer.py` — рендер + источники значений

Публичные функции и импорты сохранены.
"""

from .virtual_layers import resolve_layers_virtual
from .virtual_renderer import render_virtual, render_virtual_with_sources

__all__ = ["resolve_layers_virtual", "render_virtual", "render_virtual_with_sources"]
