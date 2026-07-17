from __future__ import annotations

import requests

from connectctl.models import SchemaRegistryConfig
from connectctl.schema_registry import (
    SchemaRegistryReadClient,
    infer_topic_from_subject,
)


class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")


def test_subject_list_falls_back_from_unhealthy_endpoint() -> None:
    calls: list[str] = []

    def transport(method, url, **kwargs):
        calls.append(url)
        if url.startswith("http://sr-a"):
            raise requests.Timeout("slow registry")
        return _Response(200, ["orders-value", "payments-value"])

    client = SchemaRegistryReadClient(
        SchemaRegistryConfig(urls=("http://sr-a:8081", "http://sr-b:8081")),
        transport=transport,
    )

    assert client.list_subjects(prefix="orders") == ["orders-value"]
    assert calls == [
        "http://sr-a:8081/subjects",
        "http://sr-b:8081/subjects",
    ]


def test_subject_404_is_final_only_after_all_endpoints_miss() -> None:
    calls: list[str] = []

    def transport(method, url, **kwargs):
        calls.append(url)
        if url.startswith("http://sr-a"):
            return _Response(404, {"message": "not found"})
        return _Response(
            200,
            {
                "subject": "orders-value",
                "version": 2,
                "id": 42,
                "schemaType": "PROTOBUF",
                "schema": 'syntax = "proto3";',
            },
        )

    client = SchemaRegistryReadClient(
        SchemaRegistryConfig(urls=("http://sr-a:8081", "http://sr-b:8081")),
        transport=transport,
    )

    version = client.get_version("orders-value", "latest")

    assert version.schema_id == 42
    assert version.schema_type == "PROTOBUF"
    assert calls == [
        "http://sr-a:8081/subjects/orders-value/versions/latest",
        "http://sr-b:8081/subjects/orders-value/versions/latest",
    ]


def test_compatibility_check_sends_schema_type_and_body() -> None:
    captured = {}

    def transport(method, url, **kwargs):
        captured.update({"method": method, "url": url, "json": kwargs.get("json")})
        return _Response(200, {"is_compatible": True, "messages": []})

    client = SchemaRegistryReadClient(
        SchemaRegistryConfig(urls=("http://sr:8081",)),
        transport=transport,
    )

    result = client.check_compatibility(
        subject="orders-value",
        schema='syntax = "proto3";',
        schema_type="PROTOBUF",
    )

    assert result.compatible is True
    assert captured == {
        "method": "POST",
        "url": "http://sr:8081/compatibility/subjects/orders-value/versions/latest",
        "json": {"schema": 'syntax = "proto3";', "schemaType": "PROTOBUF"},
    }


def test_compatibility_set_uses_config_endpoint() -> None:
    captured = {}

    def transport(method, url, **kwargs):
        captured.update({"method": method, "url": url, "json": kwargs.get("json")})
        return _Response(200, {"compatibility": "FULL"})

    client = SchemaRegistryReadClient(
        SchemaRegistryConfig(urls=("http://sr:8081",)),
        transport=transport,
    )

    result = client.set_compatibility(subject="orders-value", mode="FULL")

    assert result.compatibility == "FULL"
    assert captured == {
        "method": "PUT",
        "url": "http://sr:8081/config/orders-value",
        "json": {"compatibility": "FULL"},
    }


def test_register_schema_posts_to_subject_versions() -> None:
    captured = {}

    def transport(method, url, **kwargs):
        captured.update({"method": method, "url": url, "json": kwargs.get("json")})
        return _Response(200, {"id": 99, "version": 3})

    client = SchemaRegistryReadClient(
        SchemaRegistryConfig(urls=("http://sr:8081",)),
        transport=transport,
    )

    result = client.register_schema(
        subject="orders-value",
        schema='syntax = "proto3";',
        schema_type="PROTOBUF",
    )

    assert result.schema_id == 99
    assert result.version == "3"
    assert captured == {
        "method": "POST",
        "url": "http://sr:8081/subjects/orders-value/versions",
        "json": {"schema": 'syntax = "proto3";', "schemaType": "PROTOBUF"},
    }


def test_subject_to_topic_inference() -> None:
    assert infer_topic_from_subject("cdc.prod.orders-value") == (
        "cdc.prod.orders",
        "value",
    )
    assert infer_topic_from_subject("cdc.prod.orders-key") == (
        "cdc.prod.orders",
        "key",
    )
    assert infer_topic_from_subject("custom-subject") == (None, None)
