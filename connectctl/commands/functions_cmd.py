from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..app.context import CliContext
from ..cli_helpers.output_args import add_output_format_args
from ..exceptions import ConnectCtlError
from ..functions_dx import (
    CoverageGateOptions,
    FunctionCatalogService,
    FunctionCoverageService,
    FunctionRefactorPlanner,
    FunctionReviewService,
    FunctionScaffoldService,
)
from ..function_contracts import (
    FunctionCallValidator,
    FunctionContractLoader,
    FunctionContractRunner,
    FunctionRunPreflight,
    InferredFunctionContract,
    StrictFunctionDoctor,
    default_contract_path,
)
from ..function_locks import DEFAULT_LOCKFILE, FunctionLockService
from ..output import OutputFormat, resolve_output_format, write_payload, write_text
from ..rendering.factory import build_renderer
from ..template_docs import TemplateDocsGenerator
from ..template_impact import TemplateImpactService
from ..template_inventory import TemplateInventoryScanner
from ..template_runtime import FunctionContext, TemplateRuntime
from ..template_runtime.packages import group_functions


def build_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "functions",
        help="Repo-local `${fn:...}` function registry and diagnostics",
    )


def register_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("list", help="List builtin and repo-local functions")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_list)
    return p


def register_explain_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("explain", help="Explain one registered function")
    p.add_argument("name", help="Function name")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_explain)
    return p


def register_run_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("run", help="Run a function locally for debugging")
    p.add_argument("name", help="Function name")
    p.add_argument("--arg", action="append", default=[], help="Positional argument")
    p.add_argument(
        "--kw",
        action="append",
        default=[],
        help="Keyword argument as key=value; value may be JSON literal",
    )
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest path used to build the same variable context as render",
    )
    p.add_argument(
        "--contract-check",
        action="store_true",
        help="Validate typed function arguments before executing the function",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_run)
    return p


def register_doctor_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("doctor", help="Validate repo-local function loading")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Also scan repo-local functions for risky non-deterministic code",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_doctor)
    return p


def register_coverage_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "coverage",
        help="Report repo-wide function usage and contract-test coverage",
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
    p.set_defaults(func=cmd_functions_coverage)
    return p


def register_test_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("test", help="Run repo-local function contract tests")
    p.add_argument(
        "--pattern",
        default=None,
        help="Glob for YAML test files (default: bkkt/functions/tests/**/*.yaml)",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_test)
    return p


def register_validate_calls_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "validate-calls", help="Validate `${fn:...}` calls in one manifest"
    )
    p.add_argument("manifest", help="Manifest path")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_validate_calls)
    return p


def build_contract_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser(
        "contract", help="Generate and manage function contract tests"
    )


def build_package_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("package", help="Function namespace package UX")


def build_package_docs_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("docs", help="Generate function package docs")


def register_package_list_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("list", help="List function packages")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_package_list)
    return p


def register_package_doctor_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("doctor", help="Validate function package hygiene")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Include strict deterministic capability diagnostics",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_package_doctor)
    return p


def register_package_docs_generate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("generate", help="Generate docs for one package")
    p.add_argument("name", help="Package name, for example `platform`")
    p.add_argument("--output-file", required=True, help="Target Markdown file")
    p.set_defaults(func=cmd_functions_package_docs_generate)
    return p


def register_package_lock_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "lock", help="Create or check the repo-local function lockfile"
    )
    p.add_argument(
        "--write",
        action="store_true",
        help="Write the current lockfile instead of printing it",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Check the existing lockfile against current functions",
    )
    p.add_argument(
        "--lock-file",
        default=str(DEFAULT_LOCKFILE),
        help="Lockfile path. Default: bkkt/functions.lock.yaml",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_package_lock)
    return p


def register_package_diff_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("diff", help="Diff lockfile vs current functions")
    p.add_argument(
        "--lock-file",
        default=str(DEFAULT_LOCKFILE),
        help="Lockfile path. Default: bkkt/functions.lock.yaml",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_package_diff)
    return p


def register_package_check_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("check", help="Run function lock and impact gate checks")
    p.add_argument(
        "--lock-file",
        default=str(DEFAULT_LOCKFILE),
        help="Lockfile path. Default: bkkt/functions.lock.yaml",
    )
    p.add_argument(
        "--impact-artifact",
        default=None,
        help="Optional YAML/JSON artifact acknowledging changed functions",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_package_check)
    return p


def register_contract_infer_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "infer", help="Create a function contract-test case from sample inputs"
    )
    p.add_argument("name", help="Function name")
    p.add_argument("--arg", action="append", default=[], help="Positional argument")
    p.add_argument(
        "--kw",
        action="append",
        default=[],
        help="Keyword argument as key=value; value may be JSON literal",
    )
    p.add_argument(
        "--expect",
        required=True,
        help="Expected result; value may be JSON literal",
    )
    p.add_argument(
        "--manifest",
        default=None,
        help="Optional manifest context to include in the contract case",
    )
    p.add_argument(
        "--output-file",
        default=None,
        help="Target YAML file (default: bkkt/functions/tests/<name>.yaml)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print contract only")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing --output-file",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_contract_infer)
    return p


def register_used_by_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("used-by", help="Find manifests using a function")
    p.add_argument("name", help="Function name")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_used_by)
    return p


def register_impact_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "impact", help="Find manifests affected by a function change"
    )
    p.add_argument("name", help="Function name")
    p.add_argument(
        "--with-render-diff",
        action="store_true",
        help="Render affected manifests and report config diffs if any",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_impact)
    return p


def register_lint_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("lint", help="Lint repo-local function usage")
    p.add_argument(
        "--unused",
        action="store_true",
        help="Report repo-local functions that are declared but never used",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_lint)
    return p


def register_rename_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "rename",
        help="Plan a safe repo-wide function rename without rewriting manifests",
    )
    p.add_argument("old_name", help="Current function name")
    p.add_argument("new_name", help="New function name")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Required in v1; prints the reviewable rename plan",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_rename)
    return p


def register_deprecate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "deprecate",
        help="Plan function deprecation metadata and usage impact",
    )
    p.add_argument("name", help="Function name")
    p.add_argument("--replacement", default=None, help="Replacement function name")
    p.add_argument("--remove-after", default=None, help="Target removal date")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Required in v1; prints the reviewable deprecation plan",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_deprecate)
    return p


def build_catalog_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("catalog", help="Generate function catalog docs")


def register_catalog_generate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "generate",
        help="Generate Markdown catalog from function coverage",
    )
    p.add_argument("--output-file", required=True, help="Target Markdown file")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_catalog_generate)
    return p


def build_docs_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    return subparsers.add_parser("docs", help="Generate function reference docs")


def register_docs_generate_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "generate", help="Generate Markdown docs for registered functions"
    )
    p.add_argument("--output-file", required=True, help="Target Markdown file")
    p.set_defaults(func=cmd_functions_docs_generate)
    return p


def register_scaffold_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("scaffold", help="Create a repo-local function template")
    p.add_argument("name", help="Function name")
    p.add_argument(
        "--path",
        default="bkkt/functions/custom.py",
        help="Target Python file relative to repo root",
    )
    p.add_argument(
        "--with-fixture",
        action="store_true",
        help="Also create a function contract and golden render fixture/test",
    )
    p.add_argument(
        "--contract-path",
        default=None,
        help="Optional function contract test path relative to repo root",
    )
    p.add_argument(
        "--fixture-path",
        default=None,
        help="Optional render fixture manifest path relative to repo root",
    )
    p.add_argument(
        "--template-test-path",
        default=None,
        help="Optional golden template test path relative to repo root",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing generated scaffold files",
    )
    p.add_argument("--dry-run", action="store_true", help="Print template only")
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_scaffold)
    return p


def register_review_parser(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "review",
        help="Review function contracts, impact, and lock status before a change",
    )
    p.add_argument("name", help="Function name")
    p.add_argument(
        "--with-render-diff",
        action="store_true",
        help="Render affected manifests and include config diffs if any",
    )
    p.add_argument(
        "--pattern",
        default=None,
        help="Glob for YAML function contract files",
    )
    p.add_argument(
        "--lock-file",
        default=str(DEFAULT_LOCKFILE),
        help="Function lockfile path. Default: bkkt/functions.lock.yaml",
    )
    add_output_format_args(p)
    p.set_defaults(func=cmd_functions_review)
    return p


def cmd_functions_list(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    payload = [item.to_payload() for item in runtime.list_functions()]
    return _emit(payload, args)


def cmd_functions_explain(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    descriptor = runtime.registry.get(args.name)
    return _emit(descriptor.to_payload(), args)


def cmd_functions_run(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    descriptor = runtime.registry.get(args.name)
    fn_args = [_parse_literal(value) for value in (args.arg or [])]
    kwargs = _parse_kwargs(args.kw or [])
    function_context = _function_context_from_manifest(ctx, args.manifest)
    if "ctx" in descriptor.fn.__code__.co_varnames and "ctx" not in kwargs:
        kwargs["ctx"] = function_context
    public_kwargs = {k: v for k, v in kwargs.items() if k != "ctx"}
    contract_payload: dict[str, Any] | None = None
    if getattr(args, "contract_check", False):
        preflight = FunctionRunPreflight().validate(
            descriptor,
            args=tuple(fn_args),
            kwargs=dict(kwargs),
        )
        contract_payload = preflight.to_payload()
        if preflight.exit_code:
            _emit(
                {
                    "status": "failed",
                    "function": descriptor.to_payload(),
                    "args": fn_args,
                    "kwargs": public_kwargs,
                    "contract": contract_payload,
                    "contract_issues": contract_payload["issues"],
                },
                args,
            )
            return preflight.exit_code
    result = descriptor.fn(*fn_args, **kwargs)
    if not isinstance(result, (str, int, float, bool)):
        raise ConnectCtlError(
            f"Function {descriptor.name!r} must return scalar str/int/float/bool, "
            f"got {type(result).__name__}."
        )
    payload: dict[str, Any] = {
        "function": descriptor.to_payload(),
        "args": fn_args,
        "kwargs": public_kwargs,
        "result": str(result),
    }
    if contract_payload is not None:
        payload["status"] = "ok"
        payload["contract"] = contract_payload
    return _emit(payload, args)


def cmd_functions_doctor(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    strict_issues = []
    if getattr(args, "strict", False):
        strict_issues = [
            issue.to_payload()
            for issue in StrictFunctionDoctor(
                repo_root=ctx.repo_root,
                paths=ctx.settings.functions.paths,
            ).scan()
        ]
    payload = {
        "status": "failed" if strict_issues else "ok",
        "functions": [item.to_payload() for item in runtime.list_functions()],
        "strict_issues": strict_issues,
    }
    _emit(payload, args)
    return 1 if strict_issues else 0


def cmd_functions_coverage(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = FunctionCoverageService(
        ctx.settings,
        gate=_coverage_gate_options(args),
    ).report()
    _emit(payload, args)
    return 1 if args.strict and payload.get("status") == "failed" else 0


def cmd_functions_test(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    cases = FunctionContractLoader(ctx.repo_root, pattern=args.pattern).load()
    runner = FunctionContractRunner(
        runtime,
        context_factory=lambda manifest: _function_context_from_manifest(ctx, manifest),
    )
    suite = runner.run(cases)
    _emit(suite.to_payload(), args)
    return suite.exit_code


def cmd_functions_validate_calls(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ctx.repo_root / manifest_path
    result = FunctionCallValidator(
        TemplateRuntime.from_settings(ctx.settings),
        repo_root=ctx.repo_root,
    ).validate_manifest(
        manifest_path=manifest_path,
        config=_load_manifest_config(manifest_path),
    )
    _emit(result.to_payload(), args)
    return result.exit_code


def cmd_functions_contract_infer(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    contract = InferredFunctionContract(
        function=args.name,
        args=tuple(_parse_literal(value) for value in (args.arg or [])),
        kwargs=_parse_kwargs(args.kw or []),
        expect=_parse_literal(args.expect),
        manifest=args.manifest,
    )
    fmt = resolve_output_format(args)
    if args.dry_run:
        if fmt == OutputFormat.json:
            write_payload(contract.to_file_payload(), fmt=fmt)
        else:
            write_text(contract.to_yaml())
        return 0

    target = (
        Path(args.output_file) if args.output_file else default_contract_path(args.name)
    )
    written = contract.write(
        repo_root=ctx.repo_root, path=target, overwrite=args.overwrite
    )
    if fmt == OutputFormat.json:
        write_payload({"status": "created", "path": str(written)}, fmt=fmt)
    else:
        write_text(f"Created {written}\n")
    return 0


def cmd_functions_package_list(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    packages = group_functions(runtime.list_functions())
    return _emit(
        {
            "packages": [package.to_payload() for package in packages],
            "summary": {"packages": len(packages)},
        },
        args,
    )


def cmd_functions_package_doctor(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    issues: list[dict[str, Any]] = []
    for item in runtime.list_functions():
        if item.source == "repo" and item.package == "default":
            issues.append(
                {
                    "code": "unnamespaced_repo_function",
                    "severity": "warning",
                    "function": item.name,
                    "message": (
                        f"Repo-local function {item.name!r} is not namespaced. "
                        "Prefer package-style names such as `platform.slug`."
                    ),
                    "source_path": str(item.source_path) if item.source_path else None,
                }
            )
    if getattr(args, "strict", False):
        for issue in StrictFunctionDoctor(
            repo_root=ctx.repo_root,
            paths=ctx.settings.functions.paths,
        ).scan():
            payload = dict(issue.to_payload())
            payload["severity"] = "error"
            issues.append(payload)
    payload = {
        "status": (
            "failed"
            if any(issue.get("severity") == "error" for issue in issues)
            else "ok"
        ),
        "packages": [
            package.to_payload()
            for package in group_functions(runtime.list_functions())
        ],
        "issues": issues,
        "summary": {"issues": len(issues)},
    }
    _emit(payload, args)
    return 1 if payload["status"] == "failed" else 0


def cmd_functions_package_docs_generate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    packages = {
        package.name: package for package in group_functions(runtime.list_functions())
    }
    if args.name not in packages:
        available = ", ".join(sorted(packages)) or "(none)"
        raise ConnectCtlError(
            f"Function package {args.name!r} not found. Available packages: {available}"
        )
    markdown = _package_docs_markdown(packages[args.name])
    target = Path(args.output_file)
    if not target.is_absolute():
        target = ctx.repo_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    write_text(f"Generated {target}\n")
    return 0


def cmd_functions_package_lock(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    service = FunctionLockService(ctx.settings)
    lock_path = Path(args.lock_file)
    if args.write and args.check:
        raise ConnectCtlError("Use only one of --write or --check.")
    if args.write:
        written = service.write_lock(lock_path)
        payload = {"status": "written", "path": _display_path(ctx.repo_root, written)}
        return _emit_lock_payload(payload, args)
    if args.check:
        result = service.check_lock(lock_path=lock_path)
        _emit_lock_payload(result.to_payload(), args)
        return 1 if result.status == "failed" else 0
    return _emit_lock_payload(service.build_lock_payload(), args)


def cmd_functions_package_diff(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    result = FunctionLockService(ctx.settings).diff(lock_path=Path(args.lock_file))
    _emit_lock_payload(result.to_payload(), args)
    return 0


def cmd_functions_package_check(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    impact_artifact = Path(args.impact_artifact) if args.impact_artifact else None
    result = FunctionLockService(ctx.settings).gate(
        lock_path=Path(args.lock_file),
        impact_artifact=impact_artifact,
    )
    _emit_lock_payload(result.to_payload(), args)
    return 1 if result.status == "failed" else 0


def cmd_functions_used_by(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    matches = inventory.used_by_function(args.name)
    return _emit(
        {
            "query": {"kind": "function", "name": args.name},
            "summary": {"matches": len(matches)},
            "matches": [item.to_payload() for item in matches],
        },
        args,
    )


def cmd_functions_impact(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    descriptor = runtime.registry.get(args.name)
    report = TemplateImpactService(ctx.settings).function_impact(
        args.name,
        with_render_diff=bool(args.with_render_diff),
        metadata={"function": descriptor.to_payload()},
    )
    return _emit(report.to_payload(), args)


def cmd_functions_lint(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    issues = []
    if getattr(args, "unused", False):
        used = inventory.used_functions
        for item in runtime.list_functions():
            if item.source == "repo" and item.name not in used:
                issues.append(
                    {
                        "code": "unused_function",
                        "name": item.name,
                        "message": (
                            f"Function {item.name!r} is declared but not used by any manifest"
                        ),
                        "source_path": (
                            str(item.source_path) if item.source_path else None
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


def cmd_functions_rename(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = FunctionRefactorPlanner(ctx.settings).rename(
        args.old_name,
        args.new_name,
        dry_run=bool(args.dry_run),
    )
    return _emit(payload, args)


def cmd_functions_deprecate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = FunctionRefactorPlanner(ctx.settings).deprecate(
        args.name,
        replacement=args.replacement,
        remove_after=args.remove_after,
        dry_run=bool(args.dry_run),
    )
    return _emit(payload, args)


def cmd_functions_catalog_generate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = FunctionCatalogService(ctx.settings).generate(
        output_file=Path(args.output_file)
    )
    return _emit(payload, args)


def cmd_functions_docs_generate(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    runtime = TemplateRuntime.from_settings(ctx.settings)
    inventory = TemplateInventoryScanner(ctx.settings).scan()
    markdown = TemplateDocsGenerator().functions_markdown(
        runtime=runtime,
        inventory=inventory,
    )
    target = Path(args.output_file)
    if not target.is_absolute():
        target = ctx.repo_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    write_text(f"Generated {target}\n")
    return 0


def cmd_functions_scaffold(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    service = FunctionScaffoldService(ctx.repo_root)
    plan = service.plan(
        name=args.name,
        function_path=Path(args.path),
        with_fixture=bool(args.with_fixture),
        contract_path=Path(args.contract_path) if args.contract_path else None,
        fixture_path=Path(args.fixture_path) if args.fixture_path else None,
        template_test_path=(
            Path(args.template_test_path) if args.template_test_path else None
        ),
        status="planned" if args.dry_run else "created",
    )
    fmt = resolve_output_format(args)
    if args.dry_run:
        if fmt in (OutputFormat.json, OutputFormat.yaml):
            write_payload(plan.to_payload(repo_root=ctx.repo_root), fmt=fmt)
        else:
            write_text(_render_scaffold_text(plan, repo_root=ctx.repo_root))
        return 0

    service.write(plan, overwrite=bool(args.overwrite))
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload(plan.to_payload(repo_root=ctx.repo_root), fmt=fmt)
    else:
        write_text(_render_scaffold_text(plan, repo_root=ctx.repo_root))
    return 0


def cmd_functions_review(
    args: argparse.Namespace, *, ctx: CliContext, logger=None
) -> int:
    payload = FunctionReviewService(ctx.settings).review(
        args.name,
        with_render_diff=bool(args.with_render_diff),
        contract_pattern=args.pattern,
        lock_file=Path(args.lock_file) if args.lock_file else None,
    )
    _emit(payload, args)
    return 1 if payload.get("status") == "failed" else 0


def _function_context_from_manifest(
    ctx: CliContext, manifest: str | None
) -> FunctionContext:
    if not manifest:
        return FunctionContext.from_flat_context({}, repo_root=ctx.repo_root)
    path = Path(manifest)
    if not path.is_absolute():
        path = ctx.repo_root / path
    rr = build_renderer(ctx.settings).render(path)
    return FunctionContext.from_flat_context(
        rr.placeholder_context,
        sources=rr.placeholder_sources,
        repo_root=ctx.repo_root,
        manifest_path=path,
    )


def _parse_kwargs(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ConnectCtlError("--kw expects key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ConnectCtlError("--kw key must not be empty")
        out[key] = _parse_literal(value.strip())
    return out


def _parse_literal(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value


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


def _load_manifest_config(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as e:
        raise ConnectCtlError(f"Failed to read manifest: {path}") from e
    if not isinstance(raw, dict):
        raise ConnectCtlError(f"{path}: manifest must be a mapping")
    config = raw.get("config", {}) or {}
    if not isinstance(config, dict):
        raise ConnectCtlError(f"{path}: `config` must be a mapping")
    return config


def _render_scaffold_text(plan, *, repo_root: Path) -> str:
    lines = [
        f"Function scaffold {plan.status}:",
    ]
    for item in plan.files:
        lines.append(f"- {item.kind}: {_display_path(repo_root, item.path)}")
    return "\n".join(lines) + "\n"


def _package_docs_markdown(package) -> str:
    lines = [
        f"# BKKT Function Package `{package.name}`",
        "",
        "Autogenerated reference for one BKKT function namespace package.",
        "",
        "| Function | Source | Capabilities | Description |",
        "|---|---|---|---|",
    ]
    for item in package.functions:
        source = str(item.source_path) if item.source_path else item.source
        capabilities = ", ".join(item.capabilities) or "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{item.name}`",
                    source.replace("|", "\\|"),
                    capabilities.replace("|", "\\|"),
                    (item.description.strip() or "-").replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.extend(["", "Generated by `bkkt functions package docs generate`.", ""])
    return "\n".join(lines)


def _emit_lock_payload(payload: dict[str, Any], args: argparse.Namespace) -> int:
    fmt = resolve_output_format(args)
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload(payload, fmt=fmt)
    else:
        status = payload.get("status", "ok")
        write_text(f"status: {status}\n")
        summary = payload.get("summary")
        if isinstance(summary, dict):
            write_text(
                "summary: "
                + ", ".join(f"{key}={value}" for key, value in summary.items())
                + "\n"
            )
        path = payload.get("path")
        if path:
            write_text(f"path: {path}\n")
        for issue in payload.get("issues", []) or []:
            write_text(f"- [{issue.get('code')}] {issue.get('message')}\n")
        for change in payload.get("changes", []) or []:
            write_text(
                f"- [{change.get('kind')}] {change.get('function')} "
                f"{change.get('before_fingerprint') or '-'} -> "
                f"{change.get('after_fingerprint') or '-'}\n"
            )
    return 0


def _display_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _emit(payload: Any, args: argparse.Namespace) -> int:
    fmt = resolve_output_format(args)
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload(payload, fmt=fmt)
    else:
        if isinstance(payload, list):
            for item in payload:
                write_text(
                    f"{item['name']}\t{item['source']}\t{item.get('description') or ''}\n"
                )
        else:
            write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0
