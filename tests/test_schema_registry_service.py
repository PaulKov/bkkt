from __future__ import annotations

from argparse import Namespace

from connectctl.cli_parser import build_parser
from connectctl.models import (
    ConnectClusterConfig,
    Environment,
    SchemaRegistryConfig,
)
from connectctl.schema_registry import (
    CompatibilityCheck,
    CompatibilityUpdate,
    SchemaDiff,
    SchemaImpact,
    SchemaRegistration,
    SchemaVersion,
    SubjectDescription,
    infer_topic_from_subject,
)
from connectctl.services.schema_registry import SchemaRegistryService


class _DummyCtx:
    def __init__(self) -> None:
        self.logger = None
        self.cluster = ConnectClusterConfig(
            env=Environment.prod,
            urls=("http://connect:8083",),
            schema_registry=SchemaRegistryConfig(
                urls=("http://schema-registry-a:8081",),
            ),
            name="acme-main",
        )

    def resolve_cluster(self, env, cluster_name):
        assert env == Environment.prod
        assert cluster_name in (None, "acme-main")
        return self.cluster


class _FakeSchemaRegistry:
    set_calls = []
    register_calls = []

    def __init__(self, cfg: SchemaRegistryConfig) -> None:
        self.cfg = cfg

    def list_subjects(self, **kwargs):
        assert self.cfg.urls == ("http://schema-registry-a:8081",)
        subjects = ["orders-value", "orders-key", "payments-value"]
        if kwargs.get("prefix"):
            subjects = [s for s in subjects if s.startswith(kwargs["prefix"])]
        return subjects[: kwargs.get("limit") or len(subjects)]

    def list_versions(self, subject):
        assert subject == "orders-value"
        return [1, 2]

    def get_version(self, subject, version="latest"):
        return SchemaVersion(
            subject=subject,
            version="2" if str(version) == "latest" else str(version),
            schema_id=42,
            schema_type="PROTOBUF",
            schema='syntax = "proto3";',
        )

    def describe_subject(self, subject):
        return SubjectDescription(
            subject=subject,
            versions=(1, 2),
            latest=self.get_version(subject, "latest"),
        )

    def diff_versions(self, *, subject, from_version, to_version):
        return SchemaDiff(
            subject=subject,
            from_version=str(from_version),
            to_version=str(to_version),
            from_schema_type="PROTOBUF",
            to_schema_type="PROTOBUF",
            unified_diff=("- old", "+ new"),
        )

    def get_compatibility(self, subject=None):
        return "BACKWARD"

    def set_compatibility(self, *, subject=None, mode):
        self.set_calls.append({"subject": subject, "mode": mode})
        return CompatibilityUpdate(subject=subject, compatibility=mode)

    def check_compatibility(self, **kwargs):
        return CompatibilityCheck(
            subject=kwargs["subject"],
            version=kwargs["version"],
            compatible=True,
        )

    def register_schema(self, **kwargs):
        self.register_calls.append(kwargs)
        return SchemaRegistration(
            subject=kwargs["subject"],
            schema_id=101,
            version="3",
            schema_type=kwargs.get("schema_type") or "AVRO",
        )

    def impact(self, subject):
        topic, kind = infer_topic_from_subject(subject)
        return SchemaImpact(
            subject=subject,
            topic=topic,
            key_or_value=kind,
            suggested_commands=(f"bkkt explain '{topic}'",),
        )


def _args(**overrides):
    base = {
        "env": "prod",
        "cluster": "acme-main",
        "url": None,
        "timeout_seconds": None,
        "output": "json",
        "json": False,
    }
    base.update(overrides)
    return Namespace(**base)


def _service() -> SchemaRegistryService:
    return SchemaRegistryService(
        ctx=_DummyCtx(),
        client_factory=_FakeSchemaRegistry,
    )


def test_parser_exposes_schema_namespace() -> None:
    parser = build_parser()

    assert (
        parser.parse_args(["schema", "subjects", "list", "--env", "prod"]).schema_cmd
        == "subjects"
    )
    assert (
        parser.parse_args(
            ["schema", "compatibility", "get", "--env", "prod"]
        ).schema_compatibility_cmd
        == "get"
    )
    assert (
        parser.parse_args(
            ["schema", "impact", "--env", "prod", "orders-value"]
        ).schema_cmd
        == "impact"
    )
    assert (
        parser.parse_args(
            [
                "schema",
                "compatibility",
                "set",
                "--env",
                "prod",
                "--mode",
                "BACKWARD",
                "--dry-run",
            ]
        ).schema_compatibility_cmd
        == "set"
    )
    assert (
        parser.parse_args(
            [
                "schema",
                "register",
                "--env",
                "prod",
                "orders-value",
                "--schema-file",
                "schema.proto",
                "--schema-type",
                "PROTOBUF",
                "--dry-run",
            ]
        ).schema_cmd
        == "register"
    )


def test_subjects_list_outputs_json(capsys) -> None:
    rc = _service().run_subjects_list(_args(prefix="orders", regexp=None, limit=10))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_subjects_list"' in out
    assert '"subject_count": 2' in out
    assert '"orders-value"' in out


def test_subject_describe_includes_latest_schema(capsys) -> None:
    rc = _service().run_subjects_describe(_args(subject="orders-value", version=None))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_subject_describe"' in out
    assert '"schema_type": "PROTOBUF"' in out


def test_subject_diff_outputs_unified_diff(capsys) -> None:
    rc = _service().run_subjects_diff(
        _args(subject="orders-value", from_version="1", to_version="latest")
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_subject_diff"' in out
    assert '"- old"' in out
    assert '"+ new"' in out


def test_compatibility_check_reads_schema_file(tmp_path, capsys) -> None:
    schema_path = tmp_path / "schema.proto"
    schema_path.write_text('syntax = "proto3";', encoding="utf-8")

    rc = _service().run_compatibility_check(
        _args(
            subject="orders-value",
            schema_file=str(schema_path),
            schema_type="PROTOBUF",
            version="latest",
        )
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_compatibility_check"' in out
    assert '"compatible": true' in out


def test_compatibility_set_dry_run_does_not_mutate(capsys) -> None:
    _FakeSchemaRegistry.set_calls = []

    rc = _service().run_compatibility_set(
        _args(subject="orders-value", mode="FULL", dry_run=True, yes=False)
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_compatibility_set_plan"' in out
    assert '"desired_compatibility": "FULL"' in out
    assert _FakeSchemaRegistry.set_calls == []


def test_compatibility_set_requires_yes_without_dry_run() -> None:
    try:
        _service().run_compatibility_set(
            _args(subject="orders-value", mode="FULL", dry_run=False, yes=False)
        )
    except Exception as exc:
        assert "without --yes" in str(exc)
    else:
        raise AssertionError("compatibility set without --yes must fail")


def test_compatibility_set_applies_with_yes(capsys) -> None:
    _FakeSchemaRegistry.set_calls = []

    rc = _service().run_compatibility_set(
        _args(subject="orders-value", mode="FULL", dry_run=False, yes=True)
    )

    assert rc == 0
    assert _FakeSchemaRegistry.set_calls == [
        {"subject": "orders-value", "mode": "FULL"}
    ]
    out = capsys.readouterr().out
    assert '"kind": "schema_compatibility_set"' in out
    assert '"applied": true' in out


def test_schema_plan_includes_protobuf_package_warning(tmp_path, capsys) -> None:
    schema_path = tmp_path / "schema.proto"
    schema_path.write_text(
        'syntax = "proto3";\npackage next.orders;\nmessage Order {}\n',
        encoding="utf-8",
    )

    rc = _service().run_plan(
        _args(
            subject="orders-value",
            schema_file=str(schema_path),
            schema_type="PROTOBUF",
            version="latest",
        )
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_evolution_plan"' in out
    assert "PACKAGE_CHANGED risk" in out
    assert '"safe_to_register": false' in out


def test_schema_register_dry_run_does_not_mutate(tmp_path, capsys) -> None:
    _FakeSchemaRegistry.register_calls = []
    schema_path = tmp_path / "schema.avsc"
    schema_path.write_text(
        '{"type":"record","name":"Order","fields":[]}', encoding="utf-8"
    )

    rc = _service().run_register(
        _args(
            subject="orders-value",
            schema_file=str(schema_path),
            schema_type="AVRO",
            version="latest",
            dry_run=True,
            yes=False,
        )
    )

    assert rc == 0
    assert _FakeSchemaRegistry.register_calls == []
    out = capsys.readouterr().out
    assert '"kind": "schema_register_plan"' in out
    assert '"applied": false' in out


def test_schema_register_requires_yes(tmp_path) -> None:
    schema_path = tmp_path / "schema.avsc"
    schema_path.write_text(
        '{"type":"record","name":"Order","fields":[]}', encoding="utf-8"
    )

    try:
        _service().run_register(
            _args(
                subject="orders-value",
                schema_file=str(schema_path),
                schema_type="AVRO",
                version="latest",
                dry_run=False,
                yes=False,
            )
        )
    except Exception as exc:
        assert "without --yes" in str(exc)
    else:
        raise AssertionError("schema register without --yes must fail")


def test_schema_register_applies_with_yes(tmp_path, capsys) -> None:
    _FakeSchemaRegistry.register_calls = []
    schema_path = tmp_path / "schema.avsc"
    schema_path.write_text(
        '{"type":"record","name":"Order","fields":[]}', encoding="utf-8"
    )

    rc = _service().run_register(
        _args(
            subject="orders-value",
            schema_file=str(schema_path),
            schema_type="AVRO",
            version="latest",
            dry_run=False,
            yes=True,
        )
    )

    assert rc == 0
    assert _FakeSchemaRegistry.register_calls
    out = capsys.readouterr().out
    assert '"kind": "schema_register"' in out
    assert '"id": 101' in out


def test_impact_infers_topic_from_subject(capsys) -> None:
    rc = _service().run_impact(_args(subject="orders-value"))

    assert rc == 0
    out = capsys.readouterr().out
    assert '"kind": "schema_impact"' in out
    assert '"topic": "orders"' in out
    assert '"key_or_value": "value"' in out
