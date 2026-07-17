from __future__ import annotations

from dataclasses import dataclass

from .command_catalog import FailureCommandCatalog
from .models import FailureAnalysisContext, FailureRemediation


def _contains_any(message: str, signals: tuple[str, ...]) -> bool:
    return any(signal in message for signal in signals)


@dataclass(frozen=True)
class TlsTruststoreRule:
    signals: tuple[str, ...] = (
        "pkix path building failed",
        "ssl handshake failed",
        "sslhandshakeexception",
        "sslauthenticationexception",
        "suncertpathbuilderexception",
        "unable to find valid certification path",
    )

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not _contains_any(context.normalized_message, self.signals):
            return None

        actions = [
            "Check worker-side trust/JRE on the target Kafka Connect cluster; this usually is not a per-connector config bug.",
            "If the cluster is worker-managed for Kafka TLS/SASL, avoid re-adding `ssl.truststore.*` and `sasl.*` overrides into the connector manifest.",
            "After fixing trust on the workers, revalidate the manifest or restart only the failed connector/task.",
        ]

        return FailureRemediation(
            category="tls_truststore",
            summary=(
                "Kafka client/worker does not trust the broker certificate chain."
                + context.pruned_hint
            ),
            actions=tuple(actions),
            commands=commands.select(
                "get_connector",
                "inspect",
                "compare",
                "validate_connect",
                "restart_failed_tasks",
                "restart_failed_tasks_bulk",
            ),
            references=("docs/CONNECTCTL_RUNBOOK.md",),
        )


@dataclass(frozen=True)
class TagConflictRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if context.error_type != "TagConflictError":
            return None
        return FailureRemediation(
            category="tag_conflict",
            summary="Routing tags resolve to conflicting target parameters.",
            actions=(
                "Inspect tag-derived routing and resolve the conflicting tag values in repo overlays.",
                "Only if the conflict is expected and non-hard, rerun the command with `--suppress-tag-conflicts`.",
            ),
            commands=commands.select("inspect", "inspect_vars"),
            references=("docs/ROUTING.md",),
        )


@dataclass(frozen=True)
class EnvMismatchRule:
    signals: tuple[str, ...] = ("manifest env mismatch", "while --env=")

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not _contains_any(context.normalized_message, self.signals):
            return None
        return FailureRemediation(
            category="env_mismatch",
            summary="The selected manifest belongs to a different environment than the command target.",
            actions=(
                "Use the manifest file for the same env as `--env`, or rerun the command with the correct env.",
                "Recheck the manifest path/name and rendered `name` field before retrying.",
            ),
            commands=commands.select("inspect", "render", "validate"),
        )


@dataclass(frozen=True)
class StatusOutputModeRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not (
            context.command == "connect-status"
            and context.stage == "options"
            and "текстов" in context.normalized_message
            and "--watch" in context.normalized_message
        ):
            return None
        return FailureRemediation(
            category="status_output_mode",
            summary="`connect status --watch` supports only text output.",
            actions=(
                "Rerun watch mode without `--output json|yaml`.",
                "If you need machine-readable output, use one-shot `connect status --output json` without `--watch`.",
            ),
            commands=commands.select("connect_status_watch", "connect_status"),
            references=("docs/CLI_EXAMPLES.md",),
        )


@dataclass(frozen=True)
class LivePayloadInputRule:
    signals: tuple[str, ...] = (
        "valid json",
        "json object",
        "got empty stdin json",
        "expected json via stdin",
        "patch payload",
    )

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not (
            context.error_type == "ConfigError"
            and (
                context.stage == "read_payload"
                or _contains_any(context.normalized_message, self.signals)
            )
        ):
            return None
        return FailureRemediation(
            category="live_payload_input",
            summary="BKKT could not parse the live config payload from file/stdin/patch flags.",
            actions=(
                "Validate the JSON or patch payload shape before retrying.",
                "Prefer `--dry-run` for `connect create/update/patch` before sending the live request.",
            ),
            commands=commands.select(
                "connect_create_dry_run",
                "connect_update_dry_run",
                "connect_patch_dry_run",
            ),
            references=("docs/CLI_EXAMPLES.md",),
        )


@dataclass(frozen=True)
class ConnectorExistsRule:
    signals: tuple[str, ...] = ("already exists", "уже существует", "http 409")

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not _contains_any(context.normalized_message, self.signals):
            return None
        return FailureRemediation(
            category="connector_exists",
            summary="The target connector already exists on the selected Kafka Connect cluster.",
            actions=(
                "Inspect the live connector before overwriting anything.",
                "If you intend a full replacement, rerun the operation as `connect update`; for a small change, prefer `connect patch --dry-run --diff` first.",
            ),
            commands=commands.select(
                "get_connector",
                "connect_status",
                "connect_update_dry_run",
                "connect_patch_dry_run",
            ),
            references=("docs/CLI_EXAMPLES.md",),
        )


@dataclass(frozen=True)
class ConnectorMissingRule:
    signals: tuple[str, ...] = (
        "not exist",
        "не существует",
        "http 404",
        "config_missing",
    )

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not _contains_any(context.normalized_message, self.signals):
            return None
        return FailureRemediation(
            category="connector_missing",
            summary="The target connector was not found on the selected Kafka Connect cluster.",
            actions=(
                "Recheck `--env`, `--cluster` and connector name against the target cluster.",
                "If workers disagree, inspect every configured Connect endpoint before using a single-host fallback.",
                "If the connector should be created from scratch, switch to `connect create`; otherwise inspect the live cluster first.",
            ),
            commands=commands.select(
                "connect_endpoints",
                "connectors",
                "get_connector",
                "connect_status",
                "connect_create_dry_run",
            ),
            references=("docs/CLI_EXAMPLES.md",),
        )


@dataclass(frozen=True)
class LiveConfigOperationRule:
    commands: tuple[str, ...] = ("connect-create", "connect-update", "connect-patch")
    stages: tuple[str, ...] = ("create", "update", "patch_update", "fetch_config")

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not (context.command in self.commands and context.stage in self.stages):
            return None
        return FailureRemediation(
            category="live_config_operation",
            summary=(
                "Kafka Connect rejected or failed the live config operation."
                + context.pruned_hint
            ),
            actions=(
                "Inspect Kafka Connect endpoint health; BKKT can now fail over across healthy workers without a temporary single-host config.",
                "Inspect the live connector config/status before retrying.",
                "Repeat the same operation with `--dry-run` first so you can review the exact planned change.",
            ),
            commands=commands.select(
                "connect_endpoints",
                "get_connector",
                "connect_status",
                "connect_update_dry_run",
                "connect_patch_dry_run",
            ),
            references=("docs/CLI_EXAMPLES.md",),
        )


@dataclass(frozen=True)
class LocalValidationRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if context.stage != "local_validate":
            return None
        return FailureRemediation(
            category="local_validation",
            summary=(
                "BKKT validation failed before any Kafka Connect REST call."
                + context.pruned_hint
            ),
            actions=(
                "Fix naming, policy, config-tests or required-field issues in the manifest/overlays.",
                "Use inspect/render output to see the exact prepared config before retrying.",
            ),
            commands=commands.select("validate", "inspect_vars", "render"),
        )


@dataclass(frozen=True)
class ConnectValidationRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if context.stage != "connect_validate":
            return None
        return FailureRemediation(
            category="connect_validation",
            summary=(
                "Kafka Connect plugin validation rejected the prepared manifest."
                + context.pruned_hint
            ),
            actions=(
                "Review plugin-specific validation errors together with the prepared manifest and routing decision.",
                "Compare the repo manifest with the target cluster expectation before rerunning validation.",
            ),
            commands=commands.select(
                "inspect",
                "validate_connect",
                "compare",
                "get_connector",
            ),
        )


@dataclass(frozen=True)
class DeployFailureRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if context.stage != "deploy":
            return None
        return FailureRemediation(
            category="deploy_failure",
            summary=(
                "The manifest passed BKKT preparation, but Kafka Connect failed during deploy/update."
                + context.pruned_hint
            ),
            actions=(
                "Check whether all configured Kafka Connect REST endpoints are healthy and consistent.",
                "Check live connector status and compare live config with repo before retrying apply.",
                "If the cluster created/updated the connector partially, prefer a targeted retry instead of rerunning the whole batch blindly.",
            ),
            commands=commands.select(
                "connect_endpoints",
                "get_connector",
                "compare",
                "apply_dry_run",
                "restart_failed_tasks",
                "restart_failed_tasks_bulk",
            ),
        )


@dataclass(frozen=True)
class ConnectEndpointHealthRule:
    signals: tuple[str, ...] = (
        "failed on all endpoints",
        "endpoint unhealthy",
        "read timed out",
        "connecttimeout",
        "readtimeout",
    )

    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation | None:
        if not _contains_any(context.normalized_message, self.signals):
            return None
        return FailureRemediation(
            category="connect_endpoint_health",
            summary="One or more Kafka Connect REST endpoints are unhealthy or inconsistent.",
            actions=(
                "Run endpoint diagnostics for the selected cluster group.",
                "Retry through BKKT after confirming at least one endpoint is healthy; avoid hand-written raw REST fallback for normal connector operations.",
                "If all endpoints fail, treat this as a Kafka Connect control-plane incident.",
            ),
            commands=commands.select(
                "connect_endpoints", "get_connector", "connect_status"
            ),
            references=("docs/CONNECT_CONTROL_PLANE.md",),
        )


@dataclass(frozen=True)
class GenericRule:
    def apply(
        self,
        context: FailureAnalysisContext,
        commands: FailureCommandCatalog,
    ) -> FailureRemediation:
        return FailureRemediation(
            category="generic",
            summary=(
                "BKKT failed before completion; inspect the prepared manifest and routing details to identify the next fix."
                + context.pruned_hint
            ),
            actions=(
                "Start with the prepared manifest and routing output stored in this bundle.",
                "Retry the same command only after confirming the underlying repo/config/cluster issue is fixed.",
            ),
            commands=commands.select(
                "inspect",
                "inspect_vars",
                "render",
                "compare",
                "validate_connect",
            ),
        )
