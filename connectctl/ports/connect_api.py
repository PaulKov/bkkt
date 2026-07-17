"""Порт (интерфейс) для Kafka Connect REST API.

Зачем нужен порт:
- Сервисы BKKT должны зависеть от абстракций (DIP), а не от конкретной реализации
  HTTP клиента.
- Это упрощает тестирование (можно подменить реализацию моками/фейками),
  а также снижает связность между слоями.

В проде порт реализуется классом :class:`connectctl.connect.ConnectClient`.
"""

from __future__ import annotations
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, Tuple

from ..models import ConnectorManifest, ConnectorStatus


class ConnectApi(Protocol):
    """Минимальный контракт, который используют сервисы BKKT."""

    # Для логов/репортов удобно уметь печатать, куда ходит клиент.
    # В ConnectClient это список base_urls.
    base_urls: Sequence[str]

    # CRUD
    def list_connectors(self) -> Sequence[str]: ...

    def get_status(self, name: str) -> ConnectorStatus: ...

    def get_config(self, name: str) -> Dict[str, Any]: ...

    def get_config_optional(self, name: str) -> Optional[Dict[str, Any]]: ...

    def upsert(self, manifest: ConnectorManifest) -> None: ...

    def delete(self, name: str) -> None: ...

    def create_connector(self, name: str, config: Mapping[str, Any]) -> None: ...

    def update_connector(self, name: str, config: Mapping[str, Any]) -> None: ...

    def get_offsets(self, name: str) -> Dict[str, Any]: ...

    def patch_offsets(
        self, name: str, payload: Mapping[str, Any]
    ) -> Dict[str, Any]: ...

    # Lifecycle
    def restart(
        self, name: str, *, include_tasks: bool = True, only_failed: bool = False
    ) -> None: ...

    def restart_task(self, name: str, task_id: int) -> None: ...

    def pause(self, name: str) -> None: ...

    def resume(self, name: str) -> None: ...

    def stop(self, name: str) -> None: ...

    def wait_for_healthy(
        self,
        name: str,
        *,
        initial_delay_s: float = 10,
        timeout_s: float = 300,
        poll_interval_s: float = 5,
    ) -> ConnectorStatus: ...

    # Validation
    def validate_config(
        self, connector_class: str, config: Dict[str, Any]
    ) -> Dict[str, Any]: ...

    def validate_manifest(
        self, manifest: ConnectorManifest, *, max_errors: int = 20
    ) -> Dict[str, Any]: ...

    # Admin / introspection (используется в `bkkt doctor`)
    def get_server_info(self) -> Any: ...

    def list_connector_plugins(self) -> Sequence[Dict[str, Any]]: ...

    def list_endpoint_diagnostics(
        self,
        *,
        name: str | None = None,
        config_timeout: Tuple[float, float] = (1.0, 3.0),
    ) -> Sequence[Any]: ...
