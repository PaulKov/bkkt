"""Kafka Connect REST client.

Этот файл — фасад: реальная реализация разнесена по миксинам, чтобы соблюсти SRP
и уменьшить размер модулей.

Публичный класс `ConnectClient` остаётся доступным по прежнему пути импорта:

    from connectctl.connect import ConnectClient

"""

from __future__ import annotations
from .client_base import ConnectClientBase
from .client_admin import ConnectAdminMixin
from .client_lifecycle import ConnectLifecycleMixin
from .client_validation import ConnectValidationMixin


class ConnectClient(
    ConnectAdminMixin,
    ConnectValidationMixin,
    ConnectLifecycleMixin,
    ConnectClientBase,
):
    """Kafka Connect REST API client with failover across multiple worker URLs.

    Notes:
    - Connect clusters often have multiple workers behind different endpoints.
    - We try each base URL until one succeeds (or errors are considered transient).
    - This keeps GitOps deploy stable even if some workers are temporarily unreachable.
    """

    pass
