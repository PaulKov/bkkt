from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from connectctl.config_models import (
    ExportConfig,
    NamingConfig,
    SafetyConfig,
    SyncConfig,
)
from connectctl.exceptions import TagConflictError
from connectctl.models import ConnectClusterConfig, Environment, RepoConfig
from connectctl.routing import ClusterRouter
from connectctl.settings_models import Settings, TagSettings


def _mk_settings(*, tags: TagSettings, default_cluster: str = "c1") -> Settings:
    repo = RepoConfig(root=Path("."), connectors_root=Path("./connectors"))

    c1 = ConnectClusterConfig(env=Environment.dev, urls=("http://c1",), name="c1")
    c2 = ConnectClusterConfig(env=Environment.dev, urls=("http://c2",), name="c2")

    return Settings(
        repo=repo,
        clusters={Environment.dev: c1},
        cluster_groups={
            "c1": {Environment.dev: c1},
            "c2": {Environment.dev: c2},
        },
        default_cluster=default_cluster,
        tags=tags,
        naming=NamingConfig(),
        sync=SyncConfig(),
        safety=SafetyConfig(),
        export=ExportConfig(),
        config_tests={},
    )


def test_tag_conflict_hard_param_always_errors_even_when_suppressed() -> None:
    settings = _mk_settings(
        tags=TagSettings(
            definitions={
                "blue": {"cluster": "c1"},
                "green": {"cluster": "c2"},
            },
            hard_conflict_params=("cluster",),
        )
    )

    router = ClusterRouter(
        settings=settings, env=Environment.dev, suppress_tag_conflicts=True
    )

    with pytest.raises(TagConflictError) as e:
        router.route(
            connector_name="dev.test.connector",
            connectctl_meta={"tags": ["blue", "green"]},
            connectctl_sources={"tags": {}},
        )

    assert "param 'cluster'" in str(e.value)


def test_tag_conflict_soft_param_can_be_suppressed_and_last_wins() -> None:
    msgs: List[str] = []

    settings = _mk_settings(
        tags=TagSettings(
            definitions={
                "a": {"cluster": "c1", "owner": "team1"},
                "b": {"cluster": "c1", "owner": "team2"},
            },
            hard_conflict_params=("cluster",),
        )
    )

    router = ClusterRouter(
        settings=settings,
        env=Environment.dev,
        suppress_tag_conflicts=True,
        logger=msgs.append,
    )

    decision = router.route(
        connector_name="dev.test.connector",
        connectctl_meta={"tags": ["a", "b"]},
        connectctl_sources={"tags": {}},
    )

    assert decision.cluster_name == "c1"
    assert any("WARN:" in m and "owner" in m for m in msgs)


def test_tag_conflict_soft_param_errors_when_not_suppressed() -> None:
    settings = _mk_settings(
        tags=TagSettings(
            definitions={
                "a": {"cluster": "c1", "owner": "team1"},
                "b": {"cluster": "c1", "owner": "team2"},
            },
            hard_conflict_params=("cluster",),
        )
    )

    router = ClusterRouter(
        settings=settings, env=Environment.dev, suppress_tag_conflicts=False
    )

    with pytest.raises(TagConflictError):
        router.route(
            connector_name="dev.test.connector",
            connectctl_meta={"tags": ["a", "b"]},
            connectctl_sources={"tags": {}},
        )
