from __future__ import annotations

from ..repo import ConnectorRepo, LayerResolver
from ..settings_models import Settings
from ..ports import FileSystem
from ..template_runtime import TemplateRuntime
from .renderer import ConnectorRenderer


def build_renderer(
    settings: Settings,
    *,
    fs: FileSystem | None = None,
    routing_cli_cluster: str | None = None,
    routing_suppress_tag_conflicts: bool = False,
) -> ConnectorRenderer:
    """Собрать `ConnectorRenderer` из `Settings`.

    Публичная точка сборки рендерера для сервисов/команд.
    """

    repo = ConnectorRepo(settings.repo, fs=fs)
    layers = LayerResolver(settings.repo, fs=fs)
    template_runtime = TemplateRuntime.from_settings(settings)
    return ConnectorRenderer(
        repo=repo,
        layers=layers,
        settings=settings,
        routing_cli_cluster=routing_cli_cluster,
        routing_suppress_tag_conflicts=routing_suppress_tag_conflicts,
        template_runtime=template_runtime,
    )
