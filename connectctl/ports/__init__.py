"""Порты (интерфейсы) для DIP/DI.

В BKKT порты определяют контракты внешних зависимостей:
- Kafka Connect REST API
- FileSystem

Сервисы зависят от портов (Protocol), а реальные реализации подключаются
через CliContext (адаптеры).
"""

from .connect_api import ConnectApi
from .filesystem import FileSystem

__all__ = ["ConnectApi", "FileSystem"]
