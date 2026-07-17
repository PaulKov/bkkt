from __future__ import annotations

import json
from typing import Any, Dict, Sequence

from ..exceptions import ConnectApiError
from .client_base import ConnectClientBase


class ConnectAdminMixin(ConnectClientBase):
    """Административные endpoints Kafka Connect REST.

    Эти методы используются в `bkkt doctor` (preflight).

    Замечания:
    - Некоторые инсталляции Kafka Connect (прокси/фильтры) могут ограничивать
      часть endpoints. В таком случае методы выбрасывают ConnectApiError.
    """

    def get_server_info(self) -> Any:
        """Получить информацию о сервере Kafka Connect.

        Обычно это `GET /` и ответ похож на:
          {"version": "3.7.0", "commit": "...", "kafka_cluster_id": "..."}

        Но конкретный формат зависит от дистрибутива.

        Возвращаем:
        - dict/list если удалось распарсить JSON
        - str (raw text) если JSON не распарсился
        """

        resp = self._request("GET", "/")
        if resp.status_code != 200:
            raise ConnectApiError(f"GET / failed: HTTP {resp.status_code}: {resp.text}")

        try:
            return resp.json()
        except Exception:
            return resp.text

    def list_connector_plugins(self) -> Sequence[Dict[str, Any]]:
        """Получить список доступных коннектор-плагинов.

        Kafka Connect REST API:
          GET /connector-plugins

        Обычно возвращает список объектов вида:
          [{"class": "...", "type": "source|sink", "version": "..."}, ...]
        """

        resp = self._request("GET", "/connector-plugins")
        if resp.status_code != 200:
            raise ConnectApiError(
                f"GET /connector-plugins failed: HTTP {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        if isinstance(data, list):
            out: list[Dict[str, Any]] = []
            for item in data:
                if isinstance(item, dict):
                    out.append(dict(item))
            return out

        # Some deployments may return an object; keep it readable.
        try:
            txt = json.dumps(data)
        except Exception:
            txt = str(data)
        raise ConnectApiError(
            f"GET /connector-plugins returned unexpected payload: {txt}"
        )
