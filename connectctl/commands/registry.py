from __future__ import annotations

import argparse
from functools import partial
from typing import Callable

from . import (
    apply_cmd,
    compare_cmd,
    completion_cmd,
    diff_cmd,
    drift_cmd,
    export_cmd,
    functions_cmd,
    get_connector_cmd,
    help_cmd,
    init_cmd,
    inspect_cmd,
    lineage_cmd,
    oss_cmd,
    plan_cmd,
    reconcile_cmd,
    render_cmd,
    search_cmd,
    sync_cmd,
    validate_cmd,
    validate_connect_cmd,
    vars_cmd,
)
from .base import Command
from .config import (
    clusters_cmd as config_clusters_cmd,
    explain_cmd as config_explain_cmd,
    find_cmd as config_find_cmd,
    hosts_cmd as config_hosts_cmd,
    render_cmd as config_render_cmd,
    runtimes_cmd as config_runtimes_cmd,
    validate_cmd as config_validate_cmd,
)
from .connect import (
    create_cmd as connect_create_cmd,
    delete_cmd as connect_delete_cmd,
    endpoints_cmd as connect_endpoints_cmd,
    offsets_cmd as connect_offsets_cmd,
    patch_cmd as connect_patch_cmd,
    pause_cmd as connect_pause_cmd,
    plugins_cmd as connect_plugins_cmd,
    restart_cmd as connect_restart_cmd,
    resume_cmd as connect_resume_cmd,
    runtime_cmd as connect_runtime_cmd,
    status_cmd as connect_status_cmd,
    stop_cmd as connect_stop_cmd,
    update_cmd as connect_update_cmd,
    workers_cmd as connect_workers_cmd,
)
from .demo import init_cmd as demo_init_cmd
from .demo import smoke_cmd as demo_smoke_cmd
from .docs import generate_cli_reference_cmd, update_dev_metrics_cmd
from .func_command import CommandGroup, FuncCommand
from .kafka import (
    brokers_cmd as kafka_brokers_cmd,
    groups_cmd as kafka_groups_cmd,
    topics_cmd as kafka_topics_cmd,
)
from .repo import bootstrap_cmd as repo_bootstrap_cmd
from .repo import doctor_cmd as repo_doctor_cmd
from .repo import migrate_connector_dir_cmd as repo_migrate_connector_dir_cmd
from .schema import (
    compatibility_cmd as schema_compatibility_cmd,
    impact_cmd as schema_impact_cmd,
    plan_cmd as schema_plan_cmd,
    preflight_cmd as schema_preflight_cmd,
    register_cmd as schema_register_cmd,
    subjects_cmd as schema_subjects_cmd,
)


ParserFactory = Callable[[argparse._SubParsersAction], argparse.ArgumentParser]


def _group_parser(
    subparsers: argparse._SubParsersAction,
    *,
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    """Create a parser for a command family with nested subcommands."""

    return subparsers.add_parser(name, help=help_text)


def _named_group_parser(name: str, help_text: str) -> ParserFactory:
    """Bind a command family name and help text to a parser factory."""

    return partial(_group_parser, name=name, help_text=help_text)


def _func(
    name: str,
    register_parser: ParserFactory,
    handler: Callable[..., int],
) -> FuncCommand:
    """Create a function-backed command without importing excluded families."""

    return FuncCommand(name, register_parser, handler)


def _build_functions_group() -> CommandGroup:
    package_docs_group = CommandGroup(
        name="docs",
        help="Function package docs",
        build_parser=functions_cmd.build_package_docs_parser,
        subcommands=[
            _func(
                "generate",
                functions_cmd.register_package_docs_generate_parser,
                functions_cmd.cmd_functions_package_docs_generate,
            )
        ],
        subdest="functions_package_docs_cmd",
    )
    package_group = CommandGroup(
        name="package",
        help="Function namespace packages",
        build_parser=functions_cmd.build_package_parser,
        subcommands=[
            _func(
                "list",
                functions_cmd.register_package_list_parser,
                functions_cmd.cmd_functions_package_list,
            ),
            _func(
                "doctor",
                functions_cmd.register_package_doctor_parser,
                functions_cmd.cmd_functions_package_doctor,
            ),
            _func(
                "lock",
                functions_cmd.register_package_lock_parser,
                functions_cmd.cmd_functions_package_lock,
            ),
            _func(
                "diff",
                functions_cmd.register_package_diff_parser,
                functions_cmd.cmd_functions_package_diff,
            ),
            _func(
                "check",
                functions_cmd.register_package_check_parser,
                functions_cmd.cmd_functions_package_check,
            ),
            package_docs_group,
        ],
        subdest="functions_package_cmd",
    )
    contract_group = CommandGroup(
        name="contract",
        help="Function contract-test authoring",
        build_parser=functions_cmd.build_contract_parser,
        subcommands=[
            _func(
                "infer",
                functions_cmd.register_contract_infer_parser,
                functions_cmd.cmd_functions_contract_infer,
            )
        ],
        subdest="functions_contract_cmd",
    )
    catalog_group = CommandGroup(
        name="catalog",
        help="Function catalog docs",
        build_parser=functions_cmd.build_catalog_parser,
        subcommands=[
            _func(
                "generate",
                functions_cmd.register_catalog_generate_parser,
                functions_cmd.cmd_functions_catalog_generate,
            )
        ],
        subdest="functions_catalog_cmd",
    )
    docs_group = CommandGroup(
        name="docs",
        help="Function reference docs",
        build_parser=functions_cmd.build_docs_parser,
        subcommands=[
            _func(
                "generate",
                functions_cmd.register_docs_generate_parser,
                functions_cmd.cmd_functions_docs_generate,
            )
        ],
        subdest="functions_docs_cmd",
    )
    return CommandGroup(
        name="functions",
        help="Repo-local placeholder functions",
        build_parser=functions_cmd.build_parser,
        subcommands=[
            _func(
                "list",
                functions_cmd.register_list_parser,
                functions_cmd.cmd_functions_list,
            ),
            _func(
                "explain",
                functions_cmd.register_explain_parser,
                functions_cmd.cmd_functions_explain,
            ),
            _func(
                "run",
                functions_cmd.register_run_parser,
                functions_cmd.cmd_functions_run,
            ),
            _func(
                "doctor",
                functions_cmd.register_doctor_parser,
                functions_cmd.cmd_functions_doctor,
            ),
            _func(
                "coverage",
                functions_cmd.register_coverage_parser,
                functions_cmd.cmd_functions_coverage,
            ),
            _func(
                "test",
                functions_cmd.register_test_parser,
                functions_cmd.cmd_functions_test,
            ),
            _func(
                "validate-calls",
                functions_cmd.register_validate_calls_parser,
                functions_cmd.cmd_functions_validate_calls,
            ),
            contract_group,
            _func(
                "used-by",
                functions_cmd.register_used_by_parser,
                functions_cmd.cmd_functions_used_by,
            ),
            _func(
                "impact",
                functions_cmd.register_impact_parser,
                functions_cmd.cmd_functions_impact,
            ),
            _func(
                "review",
                functions_cmd.register_review_parser,
                functions_cmd.cmd_functions_review,
            ),
            _func(
                "lint",
                functions_cmd.register_lint_parser,
                functions_cmd.cmd_functions_lint,
            ),
            _func(
                "rename",
                functions_cmd.register_rename_parser,
                functions_cmd.cmd_functions_rename,
            ),
            _func(
                "deprecate",
                functions_cmd.register_deprecate_parser,
                functions_cmd.cmd_functions_deprecate,
            ),
            package_group,
            catalog_group,
            docs_group,
            _func(
                "scaffold",
                functions_cmd.register_scaffold_parser,
                functions_cmd.cmd_functions_scaffold,
            ),
        ],
        subdest="functions_cmd",
    )


def _build_vars_group() -> CommandGroup:
    profile_group = CommandGroup(
        name="profile",
        help="Runtime vars profiles",
        build_parser=vars_cmd.build_profile_parser,
        subcommands=[
            _func(
                "list",
                vars_cmd.register_profile_list_parser,
                vars_cmd.cmd_vars_profile_list,
            ),
            _func(
                "explain",
                vars_cmd.register_profile_explain_parser,
                vars_cmd.cmd_vars_profile_explain,
            ),
            _func(
                "diff",
                vars_cmd.register_profile_diff_parser,
                vars_cmd.cmd_vars_profile_diff,
            ),
        ],
        subdest="vars_profile_cmd",
    )
    schema_group = CommandGroup(
        name="schema",
        help="Typed vars schema authoring",
        build_parser=vars_cmd.build_schema_parser,
        subcommands=[
            _func(
                "infer",
                vars_cmd.register_schema_infer_parser,
                vars_cmd.cmd_vars_schema_infer,
            )
        ],
        subdest="vars_schema_cmd",
    )
    catalog_group = CommandGroup(
        name="catalog",
        help="Variable catalog docs",
        build_parser=vars_cmd.build_catalog_parser,
        subcommands=[
            _func(
                "generate",
                vars_cmd.register_catalog_generate_parser,
                vars_cmd.cmd_vars_catalog_generate,
            )
        ],
        subdest="vars_catalog_cmd",
    )
    docs_group = CommandGroup(
        name="docs",
        help="Variable reference docs",
        build_parser=vars_cmd.build_docs_parser,
        subcommands=[
            _func(
                "generate",
                vars_cmd.register_docs_generate_parser,
                vars_cmd.cmd_vars_docs_generate,
            )
        ],
        subdest="vars_docs_cmd",
    )
    providers_contract_group = CommandGroup(
        name="contract",
        help="Variable provider contract authoring",
        build_parser=vars_cmd.build_providers_contract_parser,
        subcommands=[
            _func(
                "infer",
                vars_cmd.register_providers_contract_infer_parser,
                vars_cmd.cmd_vars_providers_contract_infer,
            ),
            _func(
                "validate",
                vars_cmd.register_providers_contract_validate_parser,
                vars_cmd.cmd_vars_providers_contract_validate,
            ),
        ],
        subdest="vars_providers_contract_cmd",
    )
    providers_group = CommandGroup(
        name="providers",
        help="Repo-local variable providers",
        build_parser=vars_cmd.build_providers_parser,
        subcommands=[
            _func(
                "list",
                vars_cmd.register_providers_list_parser,
                vars_cmd.cmd_vars_providers_list,
            ),
            _func(
                "explain",
                vars_cmd.register_providers_explain_parser,
                vars_cmd.cmd_vars_providers_explain,
            ),
            _func(
                "run",
                vars_cmd.register_providers_run_parser,
                vars_cmd.cmd_vars_providers_run,
            ),
            _func(
                "doctor",
                vars_cmd.register_providers_doctor_parser,
                vars_cmd.cmd_vars_providers_doctor,
            ),
            _func(
                "test",
                vars_cmd.register_providers_test_parser,
                vars_cmd.cmd_vars_providers_contract_validate,
            ),
            providers_contract_group,
        ],
        subdest="vars_providers_cmd",
    )
    computed_group = CommandGroup(
        name="computed",
        help="Repo-local computed variables",
        build_parser=vars_cmd.build_computed_parser,
        subcommands=[
            _func(
                "list",
                vars_cmd.register_computed_list_parser,
                vars_cmd.cmd_vars_computed_list,
            ),
            _func(
                "explain",
                vars_cmd.register_computed_explain_parser,
                vars_cmd.cmd_vars_computed_explain,
            ),
            _func(
                "run",
                vars_cmd.register_computed_run_parser,
                vars_cmd.cmd_vars_computed_run,
            ),
            _func(
                "scaffold",
                vars_cmd.register_computed_scaffold_parser,
                vars_cmd.cmd_vars_computed_scaffold,
            ),
            _func(
                "doctor",
                vars_cmd.register_computed_doctor_parser,
                vars_cmd.cmd_vars_computed_doctor,
            ),
            _func(
                "test",
                vars_cmd.register_computed_test_parser,
                vars_cmd.cmd_vars_computed_test,
            ),
            _func(
                "graph",
                vars_cmd.register_computed_graph_parser,
                vars_cmd.cmd_vars_computed_graph,
            ),
            _func(
                "impact",
                vars_cmd.register_computed_impact_parser,
                vars_cmd.cmd_vars_computed_impact,
            ),
        ],
        subdest="vars_computed_cmd",
    )
    return CommandGroup(
        name="vars",
        help="Placeholder variables and provenance",
        build_parser=vars_cmd.build_parser,
        subcommands=[
            _func(
                "list",
                vars_cmd.register_list_parser,
                vars_cmd.cmd_vars_explain,
            ),
            _func(
                "explain",
                vars_cmd.register_explain_parser,
                vars_cmd.cmd_vars_explain,
            ),
            _func(
                "resolve",
                vars_cmd.register_resolve_parser,
                vars_cmd.cmd_vars_resolve,
            ),
            _func(
                "trace",
                vars_cmd.register_trace_parser,
                vars_cmd.cmd_vars_trace,
            ),
            _func(
                "doctor",
                vars_cmd.register_doctor_parser,
                vars_cmd.cmd_vars_doctor,
            ),
            _func(
                "coverage",
                vars_cmd.register_coverage_parser,
                vars_cmd.cmd_vars_coverage,
            ),
            _func(
                "validate-repo",
                vars_cmd.register_validate_repo_parser,
                vars_cmd.cmd_vars_validate_repo,
            ),
            _func(
                "graph",
                vars_cmd.register_graph_parser,
                vars_cmd.cmd_vars_graph,
            ),
            _func(
                "used-by",
                vars_cmd.register_used_by_parser,
                vars_cmd.cmd_vars_used_by,
            ),
            _func(
                "impact",
                vars_cmd.register_impact_parser,
                vars_cmd.cmd_vars_impact,
            ),
            _func(
                "review",
                vars_cmd.register_review_parser,
                vars_cmd.cmd_vars_review,
            ),
            _func(
                "lint",
                vars_cmd.register_lint_parser,
                vars_cmd.cmd_vars_lint,
            ),
            _func(
                "rename",
                vars_cmd.register_rename_parser,
                vars_cmd.cmd_vars_rename,
            ),
            _func(
                "deprecate",
                vars_cmd.register_deprecate_parser,
                vars_cmd.cmd_vars_deprecate,
            ),
            _func(
                "preflight",
                vars_cmd.register_preflight_parser,
                vars_cmd.cmd_vars_preflight,
            ),
            profile_group,
            schema_group,
            catalog_group,
            docs_group,
            providers_group,
            computed_group,
        ],
        subdest="vars_cmd",
    )


def _build_config_group() -> CommandGroup:
    runtimes_group = CommandGroup(
        name="runtimes",
        help="Kafka Connect runtime inventory/checks",
        build_parser=config_runtimes_cmd.build_parser,
        subcommands=[
            _func(
                "list",
                config_runtimes_cmd.register_list_parser,
                config_runtimes_cmd.cmd_config_runtimes_list,
            ),
            _func(
                "explain",
                config_runtimes_cmd.register_explain_parser,
                config_runtimes_cmd.cmd_config_runtimes_explain,
            ),
            _func(
                "check",
                config_runtimes_cmd.register_check_parser,
                config_runtimes_cmd.cmd_config_runtimes_check,
            ),
        ],
        subdest="runtimes_cmd",
    )
    hosts_group = CommandGroup(
        name="hosts",
        help="Manage Kafka Connect REST hosts",
        build_parser=config_hosts_cmd.build_parser,
        subcommands=[
            _func(
                "check",
                config_hosts_cmd.register_check_parser,
                config_hosts_cmd.cmd_config_hosts_check,
            ),
            _func(
                "add",
                config_hosts_cmd.register_add_parser,
                config_hosts_cmd.cmd_config_hosts_add,
            ),
            _func(
                "remove",
                config_hosts_cmd.register_remove_parser,
                config_hosts_cmd.cmd_config_hosts_remove,
            ),
        ],
        subdest="hosts_cmd",
    )
    return CommandGroup(
        name="config",
        help="Manage connectctl.yaml",
        build_parser=_named_group_parser("config", "Manage connectctl.yaml"),
        subcommands=[
            _func(
                "validate",
                config_validate_cmd.register_parser,
                config_validate_cmd.cmd_config_validate,
            ),
            _func(
                "clusters",
                config_clusters_cmd.register_parser,
                config_clusters_cmd.cmd_config_clusters,
            ),
            runtimes_group,
            _func(
                "find",
                config_find_cmd.register_parser,
                config_find_cmd.cmd_config_find,
            ),
            hosts_group,
            _func(
                "explain",
                config_explain_cmd.register_parser,
                config_explain_cmd.cmd_config_explain,
            ),
            _func(
                "render",
                config_render_cmd.register_parser,
                config_render_cmd.cmd_config_render,
            ),
        ],
        subdest="config_cmd",
    )


def _build_repo_group() -> CommandGroup:
    return CommandGroup(
        name="repo",
        help="Repository operations",
        build_parser=_named_group_parser("repo", "Repository operations"),
        subcommands=[
            _func(
                "bootstrap",
                repo_bootstrap_cmd.register_parser,
                repo_bootstrap_cmd.cmd_repo_bootstrap,
            ),
            _func(
                "doctor",
                repo_doctor_cmd.register_parser,
                repo_doctor_cmd.cmd_repo_doctor,
            ),
            _func(
                "migrate-connector-dir",
                repo_migrate_connector_dir_cmd.register_parser,
                repo_migrate_connector_dir_cmd.cmd_repo_migrate_connector_dir,
            ),
        ],
        subdest="repo_cmd",
    )


def _build_docs_group() -> CommandGroup:
    return CommandGroup(
        name="docs",
        help="Documentation utilities",
        build_parser=_named_group_parser("docs", "Documentation utilities"),
        subcommands=[
            _func(
                "generate-cli-reference",
                generate_cli_reference_cmd.register_parser,
                generate_cli_reference_cmd.cmd_docs_generate_cli_reference,
            ),
            _func(
                "update-dev-metrics",
                update_dev_metrics_cmd.register_parser,
                update_dev_metrics_cmd.cmd_docs_update_dev_metrics,
            ),
        ],
        subdest="docs_cmd",
    )


def _build_demo_group() -> CommandGroup:
    return CommandGroup(
        name="demo",
        help="Local OSS-friendly demo scaffold",
        build_parser=_named_group_parser("demo", "Local OSS-friendly demo scaffold"),
        subcommands=[
            _func(
                "init",
                demo_init_cmd.register_parser,
                demo_init_cmd.cmd_demo_init,
            ),
            _func(
                "smoke",
                demo_smoke_cmd.register_parser,
                demo_smoke_cmd.cmd_demo_smoke,
            ),
        ],
        subdest="demo_cmd",
    )


def _build_oss_group() -> CommandGroup:
    return CommandGroup(
        name="oss",
        help="OSS readiness and public-asset hygiene",
        build_parser=oss_cmd.build_parser,
        subcommands=[
            _func(
                "hygiene",
                oss_cmd.register_hygiene_parser,
                oss_cmd.cmd_oss_hygiene,
            ),
            _func(
                "readiness",
                oss_cmd.register_readiness_parser,
                oss_cmd.cmd_oss_readiness,
            ),
        ],
        subdest="oss_cmd",
    )


def _build_connect_group() -> CommandGroup:
    offsets_group = CommandGroup(
        name="offsets",
        help="Kafka Connect framework-managed offsets",
        build_parser=connect_offsets_cmd.build_parser,
        subcommands=[
            _func(
                "get",
                connect_offsets_cmd.register_get_parser,
                connect_offsets_cmd.cmd_connect_offsets_get,
            ),
            _func(
                "patch",
                connect_offsets_cmd.register_patch_parser,
                connect_offsets_cmd.cmd_connect_offsets_patch,
            ),
        ],
        subdest="offsets_cmd",
    )
    workers_group = CommandGroup(
        name="workers",
        help="Kafka Connect worker inventory",
        build_parser=connect_workers_cmd.build_parser,
        subcommands=[
            _func(
                "inventory",
                connect_workers_cmd.register_inventory_parser,
                connect_workers_cmd.cmd_connect_workers_inventory,
            )
        ],
        subdest="workers_cmd",
    )
    plugins_group = CommandGroup(
        name="plugins",
        help="Kafka Connect plugin inventory",
        build_parser=connect_plugins_cmd.build_parser,
        subcommands=[
            _func(
                "inventory",
                connect_plugins_cmd.register_inventory_parser,
                connect_plugins_cmd.cmd_connect_plugins_inventory,
            )
        ],
        subdest="plugins_cmd",
    )
    runtime_group = CommandGroup(
        name="runtime",
        help="Kafka Connect runtime diagnostics",
        build_parser=connect_runtime_cmd.build_parser,
        subcommands=[
            _func(
                "diff",
                connect_runtime_cmd.register_diff_parser,
                connect_runtime_cmd.cmd_connect_runtime_diff,
            )
        ],
        subdest="runtime_cmd",
    )
    return CommandGroup(
        name="connect",
        help="Kafka Connect REST client",
        build_parser=_named_group_parser("connect", "Kafka Connect REST client"),
        subcommands=[
            _func(
                "status",
                connect_status_cmd.register_parser,
                connect_status_cmd.cmd_connect_status,
            ),
            _func(
                "endpoints",
                connect_endpoints_cmd.register_parser,
                connect_endpoints_cmd.cmd_connect_endpoints,
            ),
            workers_group,
            plugins_group,
            runtime_group,
            offsets_group,
            _func(
                "restart",
                connect_restart_cmd.register_parser,
                connect_restart_cmd.cmd_connect_restart,
            ),
            _func(
                "pause",
                connect_pause_cmd.register_parser,
                connect_pause_cmd.cmd_connect_pause,
            ),
            _func(
                "resume",
                connect_resume_cmd.register_parser,
                connect_resume_cmd.cmd_connect_resume,
            ),
            _func(
                "stop",
                connect_stop_cmd.register_parser,
                connect_stop_cmd.cmd_connect_stop,
            ),
            _func(
                "delete",
                connect_delete_cmd.register_parser,
                connect_delete_cmd.cmd_connect_delete,
            ),
            _func(
                "create",
                connect_create_cmd.register_parser,
                connect_create_cmd.cmd_connect_create,
            ),
            _func(
                "update",
                connect_update_cmd.register_parser,
                connect_update_cmd.cmd_connect_update,
            ),
            _func(
                "patch",
                connect_patch_cmd.register_parser,
                connect_patch_cmd.cmd_connect_patch,
            ),
        ],
        subdest="connect_cmd",
    )


def _build_kafka_group() -> CommandGroup:
    topics_group = CommandGroup(
        name="topics",
        help="Kafka topics",
        build_parser=kafka_topics_cmd.build_parser,
        subcommands=[
            _func(
                "list",
                kafka_topics_cmd.register_list_parser,
                kafka_topics_cmd.cmd_kafka_topics_list,
            ),
            _func(
                "describe",
                kafka_topics_cmd.register_describe_parser,
                kafka_topics_cmd.cmd_kafka_topics_describe,
            ),
            _func(
                "plan",
                kafka_topics_cmd.register_plan_parser,
                kafka_topics_cmd.cmd_kafka_topics_plan,
            ),
            _func(
                "apply",
                kafka_topics_cmd.register_apply_parser,
                kafka_topics_cmd.cmd_kafka_topics_apply,
            ),
        ],
        subdest="kafka_topics_cmd",
    )
    groups_group = CommandGroup(
        name="groups",
        help="Kafka consumer groups",
        build_parser=kafka_groups_cmd.build_parser,
        subcommands=[
            _func(
                "list",
                kafka_groups_cmd.register_list_parser,
                kafka_groups_cmd.cmd_kafka_groups_list,
            ),
            _func(
                "describe",
                kafka_groups_cmd.register_describe_parser,
                kafka_groups_cmd.cmd_kafka_groups_describe,
            ),
            _func(
                "lag",
                kafka_groups_cmd.register_lag_parser,
                kafka_groups_cmd.cmd_kafka_groups_lag,
            ),
        ],
        subdest="kafka_groups_cmd",
    )
    brokers_group = CommandGroup(
        name="brokers",
        help="Kafka brokers",
        build_parser=kafka_brokers_cmd.build_parser,
        subcommands=[
            _func(
                "describe",
                kafka_brokers_cmd.register_describe_parser,
                kafka_brokers_cmd.cmd_kafka_brokers_describe,
            ),
            _func(
                "health",
                kafka_brokers_cmd.register_health_parser,
                kafka_brokers_cmd.cmd_kafka_brokers_health,
            ),
        ],
        subdest="kafka_brokers_cmd",
    )
    return CommandGroup(
        name="kafka",
        help="Kafka platform operations",
        build_parser=_named_group_parser("kafka", "Kafka platform operations"),
        subcommands=[topics_group, groups_group, brokers_group],
        subdest="kafka_cmd",
    )


def _build_schema_group() -> CommandGroup:
    subjects_group = CommandGroup(
        name="subjects",
        help="Schema Registry subjects",
        build_parser=schema_subjects_cmd.build_parser,
        subcommands=[
            _func(
                "list",
                schema_subjects_cmd.register_list_parser,
                schema_subjects_cmd.cmd_schema_subjects_list,
            ),
            _func(
                "versions",
                schema_subjects_cmd.register_versions_parser,
                schema_subjects_cmd.cmd_schema_subjects_versions,
            ),
            _func(
                "describe",
                schema_subjects_cmd.register_describe_parser,
                schema_subjects_cmd.cmd_schema_subjects_describe,
            ),
            _func(
                "diff",
                schema_subjects_cmd.register_diff_parser,
                schema_subjects_cmd.cmd_schema_subjects_diff,
            ),
        ],
        subdest="schema_subjects_cmd",
    )
    compatibility_group = CommandGroup(
        name="compatibility",
        help="Schema Registry compatibility",
        build_parser=schema_compatibility_cmd.build_parser,
        subcommands=[
            _func(
                "get",
                schema_compatibility_cmd.register_get_parser,
                schema_compatibility_cmd.cmd_schema_compatibility_get,
            ),
            _func(
                "check",
                schema_compatibility_cmd.register_check_parser,
                schema_compatibility_cmd.cmd_schema_compatibility_check,
            ),
            _func(
                "set",
                schema_compatibility_cmd.register_set_parser,
                schema_compatibility_cmd.cmd_schema_compatibility_set,
            ),
        ],
        subdest="schema_compatibility_cmd",
    )
    return CommandGroup(
        name="schema",
        help="Schema Registry governance",
        build_parser=_named_group_parser("schema", "Schema Registry governance"),
        subcommands=[
            subjects_group,
            compatibility_group,
            _func(
                "impact",
                schema_impact_cmd.register_parser,
                schema_impact_cmd.cmd_schema_impact,
            ),
            _func(
                "plan",
                schema_plan_cmd.register_parser,
                schema_plan_cmd.cmd_schema_plan,
            ),
            _func(
                "preflight",
                schema_preflight_cmd.register_parser,
                schema_preflight_cmd.cmd_schema_preflight,
            ),
            _func(
                "register",
                schema_register_cmd.register_parser,
                schema_register_cmd.cmd_schema_register,
            ),
        ],
        subdest="schema_cmd",
    )


def get_commands() -> list[Command]:
    """Return the approved public command families in stable help order."""

    return [
        _func("help", help_cmd.register_parser, help_cmd.cmd_help),
        _func(
            "completion",
            completion_cmd.register_parser,
            completion_cmd.cmd_completion,
        ),
        _build_config_group(),
        _build_functions_group(),
        _build_vars_group(),
        _build_repo_group(),
        _build_docs_group(),
        _build_demo_group(),
        _build_oss_group(),
        _func("inspect", inspect_cmd.register_parser, inspect_cmd.cmd_inspect),
        _func("search", search_cmd.register_parser, search_cmd.cmd_search),
        _func("lineage", lineage_cmd.register_parser, lineage_cmd.cmd_lineage),
        _func("render", render_cmd.register_parser, render_cmd.cmd_render),
        _func("compare", compare_cmd.register_parser, compare_cmd.cmd_compare),
        _func("plan", plan_cmd.register_parser, plan_cmd.cmd_plan),
        _func("diff", diff_cmd.register_parser, diff_cmd.cmd_diff),
        _func("drift", drift_cmd.register_parser, drift_cmd.cmd_drift),
        _func(
            "get-connector",
            get_connector_cmd.register_parser,
            get_connector_cmd.cmd_get_connector,
        ),
        _func("apply", apply_cmd.register_parser, apply_cmd.cmd_apply),
        _func("export", export_cmd.register_parser, export_cmd.cmd_export),
        _func(
            "reconcile",
            reconcile_cmd.register_parser,
            reconcile_cmd.cmd_reconcile,
        ),
        _build_kafka_group(),
        _build_schema_group(),
        _build_connect_group(),
        _func("sync", sync_cmd.register_parser, sync_cmd.cmd_sync),
        _func("init", init_cmd.register_parser, init_cmd.cmd_init),
        _func("validate", validate_cmd.register_parser, validate_cmd.cmd_validate),
        _func(
            "validate-connect",
            validate_connect_cmd.register_parser,
            validate_connect_cmd.cmd_validate_connect,
        ),
    ]


def register_all(subparsers: argparse._SubParsersAction) -> None:
    """Register the approved public command surface."""

    for command in get_commands():
        command.register(subparsers)
