"""Виртуальный рендер манифестов (без записи на диск).

Это SRP-фасад.

Ранее вся реализация находилась в одном файле `virtual_renderer.py`. В рамках
рефакторинга мы разнесли код по маленьким модулям:

- `virtual_renderer_layers.py` — вычисление списка слоёв (layers)
- `virtual_renderer_fragments.py` — сбор и merge фрагментов (vars/config/name)
- `virtual_renderer_name.py` — инференс имени из dot-style имени файла
- `virtual_renderer_placeholders.py` — сбор контекста и resolve плейсхолдеров
- `virtual_renderer_impl.py` — публичные функции `render_virtual*`

Публичный API и импорты сохранены.
"""

from .virtual_renderer_impl import render_virtual, render_virtual_with_sources

__all__ = ["render_virtual", "render_virtual_with_sources"]
