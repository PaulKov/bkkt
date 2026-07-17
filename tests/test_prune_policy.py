from pathlib import Path

from connectctl.models import (
    ConnectorManifest,
    ConnectorPathInfo,
    ConnectorType,
    Environment,
)
from connectctl.syncing import compute_sync_plan


def _mk_manifest(name: str, env: Environment) -> ConnectorManifest:
    p = Path(f"/tmp/{name}.json")
    info = ConnectorPathInfo(
        path=p,
        relpath=Path(f"x/{name}.json"),
        domain="acme",
        connector_type=ConnectorType.source,
        system="postgres",
        connector_dir="connector_acme__configuration",
        env=env,
        remainder="source_acme__configuration__common_tables",
        mode=None,
    )
    return ConnectorManifest(
        name=name, config={"connector.class": "X"}, source_path=p, info=info
    )


def test_prune_allow_deny_lists_and_env_placeholder():
    env = Environment.stage

    desired = [_mk_manifest("stage.acme.configuration.source.postgres.0", env)]

    existing = [
        "stage.acme.configuration.source.postgres.0",  # desired
        "stage.acme.configuration.source.postgres.1",  # should be pruned
        "prod.acme.configuration.source.postgres.0",  # must NOT be pruned (env allow)
        "_manual.connector",  # must NOT be pruned (deny)
    ]

    plan = compute_sync_plan(
        env=env,
        desired=desired,
        existing_names=existing,
        prune=True,
        allow_regexes=[r"^{env}\."],
        deny_regexes=[r"^_"],
    )

    assert plan.to_delete == ("stage.acme.configuration.source.postgres.1",)


def test_prune_explicit_deny_name():
    env = Environment.stage
    desired = []
    existing = [
        "stage.keep.me",  # explicitly denied
        "stage.delete.me",
    ]

    plan = compute_sync_plan(
        env=env,
        desired=desired,
        existing_names=existing,
        prune=True,
        allow_regexes=[r"^{env}\."],
        deny_names=["stage.keep.me"],
    )

    assert plan.to_delete == ("stage.delete.me",)


def test_prune_keeps_protected_disabled_connectors():
    env = Environment.stage
    desired = []
    existing = [
        "stage.keep.disabled",
        "stage.delete.me",
    ]

    plan = compute_sync_plan(
        env=env,
        desired=desired,
        existing_names=existing,
        protected_names=["stage.keep.disabled"],
        prune=True,
        allow_regexes=[r"^{env}\."],
    )

    assert plan.protected_names == ("stage.keep.disabled",)
    assert plan.to_delete == ("stage.delete.me",)
