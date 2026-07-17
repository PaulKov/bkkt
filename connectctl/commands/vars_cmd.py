from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..app.context import CliContext
from ..cli_helpers.output_args import add_output_format_args
from ..computed_vars import (
    ComputedVarContext,
    ComputedVarContractLoader,
    ComputedVarContractRunner,
    ComputedVarScaffold,
    ComputedVarRuntime,
    default_test_path,
)
from ..computed_vars.dependencies import render_mermaid as render_computed_mermaid
from ..exceptions import ConnectCtlError
from ..functions_dx import (
    CoverageGateOptions,
    VariableCatalogService,
    VariableCoverageService,
    VariableRefactorPlanner,
    VariableReviewService,
)
from ..output import OutputFormat, resolve_output_format, write_payload, write_text
from ..rendering.factory import build_renderer
from ..settings_models import ComputedVarsSettings, VarProvidersSettings
from ..template_docs import TemplateDocsGenerator
from ..template_impact import TemplateImpactService
from ..template_runtime import FunctionContext, TemplateRuntime
from ..template_graph import TemplateExecutionGraphBuilder, render_mermaid
from ..template_inventory import TemplateInventoryScanner
from ..template_trace import TemplateTracer, TraceContractEnricher
from ..utils import resolve_placeholders
from ..var_preflight import (
    ProviderContractInferer,
    ProviderContractLoader,
    ProviderContractRunner,
    VarsPreflightService,
)
from ..var_providers import VarProviderContext, VarProviderRuntime
from ..vars_profiles import VarsProfileService
from ..vars_contracts import (
    RepoVarsValidator,
    VarsSchemaInferer,
    VarsSchemaLoader,
    VarsRedactor,
    VarsSchemaValidator,
    write_schema_file,
)


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "vars",
        help="Inspect BKKT placeholder variables and provenance",
    )


def register_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("list", help="List effective variables for a manifest")
    p.add_argument("manifest", help="Manifest path")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_explain)
    return p


def register_explain_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("explain", help="Explain variables for a manifest")
    p.add_argument("manifest", help="Manifest path")
    p.add_argument("key", nargs="?", default=None, help="Optional variable key")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_explain)
    return p


def register_resolve_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("resolve", help="Resolve a placeholder expression")
    p.add_argument("manifest", help="Manifest path")
    p.add_argument(
        "--expr", required=True, help="Expression or string with placeholders"
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_resolve)
    return p


def register_trace_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("trace", help="Explain one variable value and usages")
    p.add_argument("manifest", help="Manifest path")
    p.add_argument("key", help="Variable key, for example `db.secret`")
    p.add_argument(
        "--include-contracts",
        action="store_true",
        help="Include typed variable contract metadata in trace output",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_trace)
    return p


def register_doctor_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "doctor", help="Validate typed vars schema for a manifest"
    )
    p.add_argument("manifest", help="Manifest path")
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_doctor)
    return p


def register_coverage_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "coverage",
        help="Report repo-wide variable usage and typed schema coverage",
    )
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when governance coverage issues are errors",
    )
    p.add_argument(
        "--today",
        default=None,
        help="ISO date used for remove_after checks (default: today)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_coverage)
    return p


def register_validate_repo_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "validate-repo", help="Validate every deployable manifest against vars schema"
    )
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_validate_repo)
    return p


def build_schema_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("schema", help="Infer and manage typed vars schema")


def build_profile_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "profile", help="Named runtime vars profiles for safe dry-runs"
    )


def register_profile_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("list", help="List runtime vars profiles")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_profile_list)
    return p


def register_profile_explain_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("explain", help="Explain one runtime vars profile")
    p.add_argument("name", help="Profile name")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_profile_explain)
    return p


def register_profile_diff_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "diff", help="Show how a vars profile changes one manifest context"
    )
    p.add_argument("name", help="Profile name")
    p.add_argument("manifest", help="Manifest path")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_profile_diff)
    return p


def register_schema_infer_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "infer", help="Infer a starter vars schema from rendered repo manifests"
    )
    p.add_argument(
        "--from-repo",
        action="store_true",
        help="Infer from all deployable manifests in the current repo",
    )
    p.add_argument(
        "--output-file",
        default="bkkt/vars.schema.yaml",
        help="Target schema file relative to repo root when not using --dry-run",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Print schema without writing"
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing --output-file",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_schema_infer)
    return p


def register_graph_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("graph", help="Show placeholder variable/function graph")
    p.add_argument("manifest", help="Manifest path")
    p.add_argument(
        "--format",
        choices=["payload", "mermaid"],
        default="payload",
        help="Graph renderer for text output (default: payload)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_graph)
    return p


def build_computed_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "computed", help="Repo-local computed variables and diagnostics"
    )


def build_providers_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "providers", help="Repo-local variable providers and diagnostics"
    )


def build_providers_contract_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "contract", help="Variable provider contract authoring and validation"
    )


def register_providers_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("list", help="List repo-local variable providers")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_list)
    return p


def register_providers_explain_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("explain", help="Explain one variable provider")
    p.add_argument("name", help="Variable provider name")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_explain)
    return p


def register_providers_run_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "run", help="Evaluate one variable provider for a manifest context"
    )
    p.add_argument("name", help="Variable provider name")
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest path used to build render context",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_run)
    return p


def register_providers_doctor_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("doctor", help="Validate variable provider loading")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_doctor)
    return p


def register_providers_test_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("test", help="Run variable provider contracts")
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest path used to build provider context",
    )
    p.add_argument(
        "--contract",
        action="append",
        default=[],
        help=(
            "Provider contract file or directory relative to repo root "
            "(default: bkkt/var_providers/contracts/**/*.yaml)"
        ),
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_contract_validate)
    return p


def register_providers_contract_infer_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "infer", help="Infer a starter contract for one variable provider"
    )
    p.add_argument("name", help="Variable provider name")
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest path used to build provider context",
    )
    p.add_argument(
        "--output-file",
        default=None,
        help=(
            "Target contract file relative to repo root "
            "(default: bkkt/var_providers/contracts/<provider>.yaml)"
        ),
    )
    p.add_argument("--dry-run", action="store_true", help="Print contract only")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing --output-file",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_contract_infer)
    return p


def register_providers_contract_validate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "validate", help="Validate variable providers against contracts"
    )
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest path used to build provider context",
    )
    p.add_argument(
        "--contract",
        action="append",
        default=[],
        help=(
            "Provider contract file or directory relative to repo root "
            "(default: bkkt/var_providers/contracts/**/*.yaml)"
        ),
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_providers_contract_validate)
    return p


def register_computed_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("list", help="List repo-local computed variables")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_list)
    return p


def register_computed_explain_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("explain", help="Explain one computed variable")
    p.add_argument("name", help="Computed variable name")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_explain)
    return p


def register_computed_run_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "run", help="Evaluate one computed variable for a manifest context"
    )
    p.add_argument("name", help="Computed variable name")
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest path used to build render context",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_run)
    return p


def register_computed_doctor_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("doctor", help="Validate computed variable loading")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_doctor)
    return p


def register_computed_test_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("test", help="Run repo-local computed var tests")
    p.add_argument(
        "--pattern",
        default=None,
        help="Glob for YAML test files (default: bkkt/computed_vars/tests/**/*.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_test)
    return p


def register_computed_graph_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("graph", help="Show computed variable dependency graph")
    p.add_argument(
        "--format",
        choices=["payload", "mermaid"],
        default="payload",
        help="Graph renderer for text output (default: payload)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_graph)
    return p


def register_computed_impact_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "impact",
        help="Find computed variables and manifests affected by a computed var change",
    )
    p.add_argument("name", help="Computed variable name")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_impact)
    return p


def register_computed_scaffold_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "scaffold", help="Create a repo-local computed variable template and test"
    )
    p.add_argument("name", help="Computed variable name, for example platform.topic")
    p.add_argument(
        "--path",
        default="bkkt/computed_vars/custom.py",
        help="Target Python file relative to repo root",
    )
    p.add_argument(
        "--test-path",
        default=None,
        help=(
            "Target YAML contract file relative to repo root "
            "(default: bkkt/computed_vars/tests/<name>.yaml)"
        ),
    )
    p.add_argument("--dry-run", action="store_true", help="Print templates only")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_computed_scaffold)
    return p


def register_used_by_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("used-by", help="Find manifests using a variable")
    p.add_argument("name", help="Variable key, for example `db.secret`")
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_used_by)
    return p


def register_impact_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "impact", help="Find manifests affected by a variable change"
    )
    p.add_argument("name", help="Variable key, for example `db.secret`")
    p.add_argument(
        "--with-render-diff",
        action="store_true",
        help="Render affected manifests before/after temporary overrides",
    )
    p.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Temporary variable override used only for --with-render-diff",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_impact)
    return p


def register_review_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "review",
        help="Review variable schema, usage impact, and optional render diff",
    )
    p.add_argument("name", help="Variable key, for example `db.secret`")
    p.add_argument(
        "--with-render-diff",
        action="store_true",
        help="Render affected manifests before/after temporary overrides",
    )
    p.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Temporary variable override used only for --with-render-diff",
    )
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_review)
    return p


def register_lint_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("lint", help="Lint repo variable declarations")
    p.add_argument(
        "--unused",
        action="store_true",
        help="Report vars schema entries that are declared but never used",
    )
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_lint)
    return p


def register_rename_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "rename",
        help="Plan a safe repo-wide variable rename without rewriting manifests",
    )
    p.add_argument("old_key", help="Current variable key")
    p.add_argument("new_key", help="New variable key")
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Required in v1; prints the reviewable rename plan",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_rename)
    return p


def register_deprecate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "deprecate",
        help="Plan variable deprecation metadata and usage impact",
    )
    p.add_argument("key", help="Variable key")
    p.add_argument("--replacement", default=None, help="Replacement variable key")
    p.add_argument("--remove-after", default=None, help="Target removal date")
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Required in v1; prints the reviewable deprecation plan",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_deprecate)
    return p


def register_preflight_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "preflight",
        help="Validate provider contracts and external variable references",
    )
    p.add_argument("manifest", help="Manifest path")
    p.add_argument(
        "--provider-contract",
        action="append",
        default=[],
        help=(
            "Provider contract file or directory relative to repo root "
            "(default: bkkt/var_providers/contracts/**/*.yaml)"
        ),
    )
    p.add_argument(
        "--secret-index",
        default=None,
        help=(
            "Optional static secret reference index. Without it, secret refs are "
            "reported as unverified warnings."
        ),
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_preflight)
    return p


def build_docs_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("docs", help="Generate variable reference docs")


def build_catalog_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("catalog", help="Generate variable catalog docs")


def register_catalog_generate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "generate",
        help="Generate Markdown catalog from variable coverage",
    )
    p.add_argument("--output-file", required=True, help="Target Markdown file")
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_vars_catalog_generate)
    return p


def register_docs_generate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "generate", help="Generate Markdown docs for vars schema entries"
    )
    p.add_argument("--output-file", required=True, help="Target Markdown file")
    p.add_argument(
        "--schema",
        default=None,
        help="Vars schema path relative to repo root (default: bkkt/vars.schema.yaml)",
    )
    p.set_defaults(func=cmd_vars_docs_generate)
    return p


def cmd_vars_explain(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    rr, path = _render(ctx, args.manifest)
    redactor = _redactor(ctx)
    variables = {
        k: str(redactor.redact_value(k, v))
        for k, v in sorted(rr.placeholder_context.items())
        if args.key is None or k == args.key
    }
    payload = {
        "manifest": str(path),
        "variables": variables,
        "sources": {
            k: v
            for k, v in sorted(rr.placeholder_sources.items())
            if args.key is None or k == args.key
        },
        "used": [item.__dict__ for item in rr.vars_used],
    }
    return _emit(payload, args)


def cmd_vars_resolve(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    rr, path = _render(ctx, args.manifest)
    runtime = TemplateRuntime.from_settings(ctx.settings)
    function_context = FunctionContext.from_flat_context(
        rr.placeholder_context,
        sources=rr.placeholder_sources,
        repo_root=ctx.repo_root,
        manifest_path=path,
    )
    result = resolve_placeholders(
        args.expr,
        rr.placeholder_context,
        template_runtime=runtime,
        function_context=function_context,
    )
    return _emit({"manifest": str(path), "expr": args.expr, "result": result}, args)


def cmd_vars_trace(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    rr, path = _render(ctx, args.manifest)
    graph = TemplateExecutionGraphBuilder(ctx.settings).build(rr)
    report = TemplateTracer(repo_root=ctx.repo_root).trace_var(
        rr,
        graph,
        variable=args.key,
    )
    payload = report.to_payload()
    schema = VarsSchemaLoader(ctx.repo_root).load()
    redactor = VarsRedactor(schema)
    payload["value"] = redactor.redact_value(args.key, payload.get("value"))
    if getattr(args, "include_contracts", False):
        payload = TraceContractEnricher(schema).enrich_payload(payload)
    else:
        payload["steps"] = _redact_trace_steps(payload.get("steps", []), redactor)
    return _emit(payload, args)


def cmd_vars_doctor(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    rr, path = _render(ctx, args.manifest)
    schema = VarsSchemaLoader(ctx.repo_root, schema_path=args.schema).load()
    result = VarsSchemaValidator().validate(
        schema,
        rr.placeholder_context,
        sources=rr.placeholder_sources,
    )
    redactor = VarsRedactor(schema)
    payload = {"manifest": str(path), **result.to_payload()}
    payload["issues"] = [
        redactor.redact_issue_payload(issue) for issue in payload["issues"]
    ]
    _emit(payload, args)
    return result.exit_code


def cmd_vars_coverage(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    payload = VariableCoverageService(
        ctx.settings,
        schema_path=args.schema,
        gate=_coverage_gate_options(args),
    ).report()
    _emit(payload, args)
    return 1 if args.strict and payload.get("status") == "failed" else 0


def _coverage_gate_options(args: argparse.Namespace) -> CoverageGateOptions:
    return CoverageGateOptions(
        strict=bool(getattr(args, "strict", False)),
        today=_parse_iso_date(getattr(args, "today", None)),
    )


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise ConnectCtlError(
            f"--today expects ISO date YYYY-MM-DD, got {value!r}"
        ) from e


def cmd_vars_validate_repo(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    schema = VarsSchemaLoader(ctx.repo_root, schema_path=args.schema).load()
    result = RepoVarsValidator(ctx.settings).validate(schema)
    _emit(result.to_payload(), args)
    return result.exit_code


def cmd_vars_schema_infer(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    if not args.from_repo:
        raise ConnectCtlError("vars schema infer currently requires --from-repo")
    schema = VarsSchemaInferer(ctx.settings).infer()
    fmt = resolve_output_format(args)
    if args.dry_run:
        if fmt == OutputFormat.json:
            write_payload(schema.to_schema_payload(), fmt=fmt)
        else:
            write_text(schema.to_yaml())
        return 0

    target = Path(args.output_file)
    if not target.is_absolute():
        target = ctx.repo_root / target
    write_schema_file(schema, path=target.resolve(), overwrite=args.overwrite)
    if fmt == OutputFormat.json:
        write_payload({"status": "created", "path": str(target)}, fmt=fmt)
    else:
        write_text(f"Created {target}\n")
    return 0


def cmd_vars_profile_list(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    return _emit(VarsProfileService(ctx.repo_root).list_payload(), args)


def cmd_vars_profile_explain(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    return _emit(VarsProfileService(ctx.repo_root).explain_payload(args.name), args)


def cmd_vars_profile_diff(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    rr, path = _render(ctx, args.manifest)
    report = VarsProfileService(ctx.repo_root).diff(
        args.name,
        manifest=str(path),
        render_result=rr,
    )
    return _emit(report.to_payload(), args)


def cmd_vars_graph(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    rr, path = _render(ctx, args.manifest)
    graph = TemplateExecutionGraphBuilder(ctx.settings).build(rr)
    fmt = resolve_output_format(args)
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload({"manifest": str(path), **graph.to_payload()}, fmt=fmt)
        return 0
    if args.format == "mermaid":
        write_text(render_mermaid(graph))
        return 0
    write_text(f"Manifest: {path}\n")
    for edge in graph.edges:
        write_text(f"{edge.from_id}\t{edge.kind}\t{edge.to_id}\n")
    return 0


def cmd_vars_providers_list(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = VarProviderRuntime.from_settings(ctx.settings)
    return _emit(
        {
            "summary": {"providers": len(runtime.list_providers())},
            "providers": [item.to_payload() for item in runtime.list_providers()],
        },
        args,
    )


def cmd_vars_providers_explain(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = VarProviderRuntime.from_settings(ctx.settings)
    return _emit(runtime.registry.get(args.name).to_payload(), args)


def cmd_vars_providers_run(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = VarProviderRuntime.from_settings(ctx.settings)
    provider_context = _provider_context_from_manifest(ctx, args.manifest)
    result = runtime.evaluate_one(
        args.name,
        provider_context.variables.values,
        provider_context=provider_context,
    )
    return _emit(result.to_payload(), args)


def cmd_vars_providers_doctor(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = VarProviderRuntime.from_settings(ctx.settings)
    providers = runtime.list_providers()
    return _emit(
        {
            "status": "ok",
            "summary": {"providers": len(providers)},
            "providers": [item.to_payload() for item in providers],
        },
        args,
    )


def cmd_vars_providers_contract_infer(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = VarProviderRuntime.from_settings(ctx.settings)
    provider_context = _provider_context_from_manifest(ctx, args.manifest)
    run_result = runtime.evaluate_one(
        args.name,
        provider_context.variables.values,
        provider_context=provider_context,
    )
    suite = ProviderContractInferer().infer(run_result)
    payload = suite.to_schema_payload()
    fmt = resolve_output_format(args)
    if args.dry_run:
        if fmt == OutputFormat.json:
            write_payload(payload, fmt=fmt)
        else:
            write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        return 0

    target = _provider_contract_output_path(ctx.repo_root, args.name, args.output_file)
    if target.exists() and not args.overwrite:
        raise ConnectCtlError(
            f"Provider contract target already exists: {target}. "
            "Use --overwrite explicitly."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    if fmt == OutputFormat.json:
        write_payload({"status": "created", "path": str(target)}, fmt=fmt)
    else:
        write_text(f"Created {target}\n")
    return 0


def cmd_vars_providers_contract_validate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = VarProviderRuntime.from_settings(ctx.settings)
    suite = ProviderContractLoader(
        ctx.repo_root,
        paths=args.contract or None,
    ).load()
    provider_context = _provider_context_from_manifest(ctx, args.manifest)
    results = ProviderContractRunner(runtime, suite).run(
        provider_context=provider_context
    )
    issues = tuple(issue for result in results for issue in result.issues)
    payload = {
        "status": "failed" if issues else "ok",
        "summary": {
            "provider_contracts": len(results),
            "issues": len(issues),
        },
        "provider_contracts": [result.to_payload() for result in results],
        "issues": [issue.to_payload() for issue in issues],
    }
    _emit(payload, args)
    return 1 if issues else 0


def cmd_vars_computed_list(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    payload = [item.to_payload() for item in runtime.list_computed_vars()]
    return _emit(payload, args)


def cmd_vars_computed_explain(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    descriptor = runtime.registry.get(args.name)
    return _emit(descriptor.to_payload(), args)


def cmd_vars_computed_run(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    descriptor = runtime.registry.get(args.name)
    computed_context = _computed_context_from_manifest(ctx, args.manifest)
    result = runtime.evaluate_one(args.name, computed_context=computed_context)
    return _emit(
        {
            "variable": descriptor.to_payload(),
            "result": str(result),
        },
        args,
    )


def cmd_vars_computed_doctor(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    payload = {
        "status": "ok",
        "computed_vars": [item.to_payload() for item in runtime.list_computed_vars()],
    }
    return _emit(payload, args)


def cmd_vars_computed_test(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    cases = ComputedVarContractLoader(ctx.repo_root, pattern=args.pattern).load()
    suite = ComputedVarContractRunner(
        runtime,
        context_factory=lambda manifest: _computed_context_from_manifest(ctx, manifest),
    ).run(cases)
    _emit(suite.to_payload(), args)
    return suite.exit_code


def cmd_vars_computed_graph(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    graph = runtime.graph()
    fmt = resolve_output_format(args)
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload(graph.to_payload(), fmt=fmt)
        return 0
    if args.format == "mermaid":
        write_text(render_computed_mermaid(graph))
        return 0
    for edge in graph.edges:
        write_text(f"{edge.from_id}\t{edge.kind}\t{edge.to_id}\n")
    return 0


def cmd_vars_computed_impact(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = ComputedVarRuntime.from_settings(ctx.settings)
    dependents = runtime.impact(args.name)
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    usage_names = (args.name, *dependents)
    manifest_usages = sorted(
        {
            (
                usage.manifest,
                usage.config_key,
                usage.kind,
                usage.via_function,
            )
            for name in usage_names
            for usage in inventory.used_by_variable(name)
        }
    )
    return _emit(
        {
            "query": args.name,
            "computed_dependents": list(dependents),
            "manifest_usages": [
                {
                    "manifest": manifest,
                    "config_key": config_key,
                    "kind": kind,
                    "via_function": via_function,
                }
                for manifest, config_key, kind, via_function in manifest_usages
            ],
        },
        args,
    )


def cmd_vars_computed_scaffold(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    test_path = Path(args.test_path) if args.test_path else default_test_path(args.name)
    scaffold = ComputedVarScaffold(
        name=args.name,
        function_path=Path(args.path),
        test_path=test_path,
    )
    if args.dry_run:
        return _emit(scaffold.preview_payload(repo_root=ctx.repo_root), args)
    scaffold.write(repo_root=ctx.repo_root)
    write_text(
        "Created computed variable scaffold:\n"
        f"- function: {ctx.repo_root / args.path}\n"
        f"- test: {ctx.repo_root / test_path}\n"
    )
    return 0


def cmd_vars_used_by(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    matches = inventory.used_by_variable(args.name)
    return _emit(
        {
            "query": {"kind": "variable", "name": args.name},
            "summary": {"matches": len(matches)},
            "matches": [item.to_payload() for item in matches],
        },
        args,
    )


def cmd_vars_impact(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    override_value = _impact_override_value(args.name, args.set or [])
    report = TemplateImpactService(ctx.settings).variable_impact(
        args.name,
        override_value=override_value,
        with_render_diff=bool(args.with_render_diff),
    )
    return _emit(report.to_payload(), args)


def cmd_vars_review(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    override_value = _impact_override_value(args.name, args.set or [])
    payload = VariableReviewService(ctx.settings).review(
        args.name,
        schema_path=args.schema,
        override_value=override_value,
        with_render_diff=bool(args.with_render_diff),
    )
    _emit(payload, args)
    return 1 if payload.get("status") == "failed" else 0


def cmd_vars_lint(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    schema = VarsSchemaLoader(ctx.repo_root, schema_path=args.schema).load()
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    issues = []
    if getattr(args, "unused", False):
        used = inventory.used_variables
        for entry in sorted(schema.entries, key=lambda item: item.key):
            if entry.key not in used:
                issues.append(
                    {
                        "code": "unused_var",
                        "name": entry.key,
                        "message": (
                            f"Variable {entry.key!r} is declared but not used by any manifest"
                        ),
                    }
                )
    payload = {
        "status": "failed" if issues else "ok",
        "issues": issues,
        "summary": {"total": len(issues)},
    }
    _emit(payload, args)
    return 1 if issues else 0


def cmd_vars_rename(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    payload = VariableRefactorPlanner(
        ctx.settings,
        schema_path=args.schema,
    ).rename(
        args.old_key,
        args.new_key,
        dry_run=bool(args.dry_run),
    )
    return _emit(payload, args)


def cmd_vars_deprecate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = VariableRefactorPlanner(
        ctx.settings,
        schema_path=args.schema,
    ).deprecate(
        args.key,
        replacement=args.replacement,
        remove_after=args.remove_after,
        dry_run=bool(args.dry_run),
    )
    return _emit(payload, args)


def cmd_vars_preflight(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    result = VarsPreflightService(ctx.settings).run(
        _manifest_path(ctx, args.manifest),
        provider_contracts=args.provider_contract or None,
        secret_index=args.secret_index,
    )
    _emit(result.to_payload(), args)
    return result.exit_code


def cmd_vars_docs_generate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    schema = VarsSchemaLoader(ctx.repo_root, schema_path=args.schema).load()
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    markdown = TemplateDocsGenerator().vars_markdown(
        schema=schema,
        inventory=inventory,
    )
    target = Path(args.output_file)
    if not target.is_absolute():
        target = ctx.repo_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    write_text(f"Generated {target}\n")
    return 0


def cmd_vars_catalog_generate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = VariableCatalogService(
        ctx.settings,
        schema_path=args.schema,
    ).generate(output_file=Path(args.output_file))
    return _emit(payload, args)


def _render(ctx: CliContext, manifest: str):
    path = _manifest_path(ctx, manifest)
    return build_renderer(ctx.settings).render(path), path


def _redactor(ctx: CliContext) -> VarsRedactor:
    return VarsRedactor(VarsSchemaLoader(ctx.repo_root).load())


def _computed_context_from_manifest(
    ctx: CliContext, manifest: str | None
) -> ComputedVarContext:
    if not manifest:
        return ComputedVarContext.from_flat_context({}, repo_root=ctx.repo_root)
    rr, path = _render(ctx, manifest)
    values = {
        key: value
        for key, value in rr.placeholder_context.items()
        if not str(rr.placeholder_sources.get(key, "")).startswith("computed:")
    }
    sources = {
        key: value for key, value in rr.placeholder_sources.items() if key in values
    }
    return ComputedVarContext.from_flat_context(
        values,
        sources=sources,
        repo_root=ctx.repo_root,
        manifest_path=path,
    )


def _provider_context_from_manifest(
    ctx: CliContext, manifest: str | None
) -> VarProviderContext:
    if not manifest:
        return VarProviderContext.from_flat_context({}, repo_root=ctx.repo_root)
    path = _manifest_path(ctx, manifest)
    base_settings = replace(
        ctx.settings,
        var_providers=VarProvidersSettings(enabled=False),
        computed_vars=ComputedVarsSettings(enabled=False),
    )
    rr = build_renderer(base_settings).render(path)
    values = dict(rr.placeholder_context)
    sources = dict(rr.placeholder_sources)
    return VarProviderContext.from_flat_context(
        values,
        sources=sources,
        repo_root=ctx.repo_root,
        manifest_path=path,
    )


def _manifest_path(ctx: CliContext, manifest: str) -> Path:
    path = Path(manifest)
    if not path.is_absolute():
        path = ctx.repo_root / path
    return path


def _provider_contract_output_path(
    repo_root: Path,
    provider_name: str,
    output_file: str | None,
) -> Path:
    target = (
        Path(output_file)
        if output_file
        else Path("bkkt/var_providers/contracts") / f"{provider_name}.yaml"
    )
    if not target.is_absolute():
        target = repo_root / target
    return target.resolve()


def _redact_trace_steps(
    steps: list[dict[str, Any]],
    redactor: VarsRedactor,
) -> list[dict[str, Any]]:
    redacted: list[dict[str, Any]] = []
    for step in steps:
        item = dict(step)
        if "value" in item:
            item["value"] = redactor.redact_value(str(item.get("name")), item["value"])
        redacted.append(item)
    return redacted


def _impact_override_value(name: str, items: list[str]) -> Any | None:
    if not items:
        return None
    values: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ConnectCtlError(
                "--set expects KEY=VALUE, for example --set db.secret=dbz-next"
            )
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ConnectCtlError("--set key must not be empty")
        values[key] = _parse_impact_literal(value.strip())
    return values.get(name)


def _parse_impact_literal(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value


def _emit(payload: Any, args: argparse.Namespace) -> int:
    fmt = resolve_output_format(args)
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload(payload, fmt=fmt)
    else:
        if isinstance(payload, dict) and "variables" in payload:
            for key, value in payload["variables"].items():
                source = payload.get("sources", {}).get(key, "meta")
                write_text(f"{key}\t{value}\t{source}\n")
        else:
            write_text(str(payload) + "\n")
    return 0
