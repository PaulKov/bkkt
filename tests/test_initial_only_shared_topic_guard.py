from __future__ import annotations

from types import SimpleNamespace

import pytest

from connectctl.exceptions import ValidationError
from connectctl.kafka.topics import infer_topics_from_config
from connectctl.models import ConnectorStatus
from connectctl.services.apply.initial_only_shared_topic_guard import (
    enforce_initial_only_shared_topic_guard,
)


def _businessapps_source_config(
    *,
    snapshot_mode: str,
    init: bool,
    tables: str = "users.documents,users.withdrawal_distributions",
) -> dict[str, str]:
    mode = ".init" if init else ""
    return {
        "connector.class": "io.debezium.connector.mariadb.MariaDbConnector",
        "snapshot.mode": snapshot_mode,
        "topic.prefix": f"prod.businessapps.businessapps_common.source.mariadb{mode}.8.changes",
        "table.include.list": tables,
        "transforms": "replaceTopicName",
        "transforms.replaceTopicName.type": "org.apache.kafka.connect.transforms.RegexRouter",
        "transforms.replaceTopicName.regex": (
            r"prod\.businessapps\.businessapps_common\.source\.mariadb"
            r"(?:\.init)?\.8\.changes\.([^.]+)\.(.*)"
        ),
        "transforms.replaceTopicName.replacement": (
            "cdc.prod.businessapps.businessapps_common.$1.$2.8"
        ),
    }


class _FakeConnect:
    def __init__(self, configs: dict[str, dict[str, str]]) -> None:
        self.configs = configs

    def list_connectors(self):
        return sorted(self.configs)

    def get_config_optional(self, name: str):
        return self.configs.get(name)

    def get_status(self, name: str) -> ConnectorStatus:
        return ConnectorStatus(
            name=name,
            connector_state="PAUSED",
            worker_id=None,
            task_states=("PAUSED",),
            raw={},
        )


def test_debezium_topic_inference_returns_exact_regex_router_topics() -> None:
    topics = infer_topics_from_config(
        _businessapps_source_config(snapshot_mode="initial_only", init=True)
    )

    assert topics.produced_topics == [
        "cdc.prod.businessapps.businessapps_common.users.documents.8",
        "cdc.prod.businessapps.businessapps_common.users.withdrawal_distributions.8",
    ]


def test_initial_only_guard_blocks_shared_topics_even_when_source_is_paused() -> None:
    manifest = SimpleNamespace(
        name="prod.businessapps.businessapps_common.source.mariadb.init.8",
        config=_businessapps_source_config(snapshot_mode="initial_only", init=True),
    )
    live_source_name = "prod.businessapps.businessapps_common.source.mariadb.8"
    connect = _FakeConnect(
        {
            live_source_name: _businessapps_source_config(
                snapshot_mode="no_data", init=False
            )
        }
    )

    with pytest.raises(ValidationError) as exc_info:
        enforce_initial_only_shared_topic_guard(connect=connect, manifest=manifest)

    message = str(exc_info.value)
    assert "snapshot.mode=initial_only" in message
    assert live_source_name in message
    assert "cdc.prod.businessapps.businessapps_common.users.documents.8" in message


def test_initial_only_guard_allows_disjoint_source_topics() -> None:
    manifest = SimpleNamespace(
        name="prod.businessapps.businessapps_common.source.mariadb.init.8",
        config=_businessapps_source_config(
            snapshot_mode="initial_only",
            init=True,
            tables="users.documents",
        ),
    )
    connect = _FakeConnect(
        {
            "prod.businessapps.businessapps_common.source.mariadb.8": _businessapps_source_config(
                snapshot_mode="no_data",
                init=False,
                tables="users.withdrawal_distributions",
            )
        }
    )

    enforce_initial_only_shared_topic_guard(connect=connect, manifest=manifest)
