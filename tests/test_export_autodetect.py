from connectctl.exporting import (
    autodetect_layout_from_name,
    build_sink_manifest_filename,
)
from connectctl.models import ConnectorType, Environment


def test_autodetect_sink_events_kind():
    name = "prod.users.acme_common.sink.raw.iceberg.cdc.events.dbt.0"
    layout = autodetect_layout_from_name(name)
    assert layout is not None
    assert layout.env == Environment.prod
    assert layout.domain == "users"
    assert layout.connector_type == ConnectorType.sink
    assert layout.system == "iceberg"
    assert layout.connector_dir == "connector_users__acme_common"
    assert layout.dataset == "acme_common"
    assert layout.layer == "raw"
    assert layout.kind == "events"
    assert build_sink_manifest_filename(layout, name) == name + ".json"


def test_autodetect_sink_default_kind_does_not_treat_dbt_as_kind():
    name = "prod.users.acme_common.sink.raw.iceberg.cdc.dbt.0"
    layout = autodetect_layout_from_name(name)
    assert layout is not None
    assert layout.kind == "default"
    assert build_sink_manifest_filename(layout, name) == name + ".json"


def test_autodetect_source_mariadb():
    name = "prod.merchants.acme_common.source.mariadb.cdc.dbt.0"
    layout = autodetect_layout_from_name(name)
    assert layout is not None
    assert layout.env == Environment.prod
    assert layout.domain == "merchants"
    assert layout.connector_type == ConnectorType.source
    assert layout.system == "mariadb"
    assert layout.connector_dir == "connector_merchants__acme_common__cdc__dbt"
    assert layout.dataset == "acme_common"


def test_autodetect_sink_custom_kind():
    name = "prod.users.acme_common.sink.raw.iceberg.cdc.audit.dbt.0"
    layout = autodetect_layout_from_name(name)
    assert layout is not None
    assert layout.kind == "audit"
