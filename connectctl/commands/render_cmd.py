from __future__ import annotations

import argparse
from pathlib import Path

from ..app.context import CliContext
from ..exceptions import ConnectCtlError
from ..logging_utils import get_logger
from ..output import OutputFormat, resolve_output_format, write_payload, write_text
from ..rendering.factory import build_renderer
from ..rendering.runtime_vars import load_runtime_vars_with_sources
from ..services.render_service import RenderService
from ..template_graph import TemplateExecutionGraphBuilder
from ..template_trace import TemplateTracer, TraceContractEnricher
from ..vars_contracts import VarsRedactor, VarsSchemaLoader
from .render.parser import register_parser as _register_render_parser


def cmd_render(
    args: argparse.Namespace, *, ctx: CliContext | None = None, logger=None
) -> int:
    if ctx is None:
        ctx = CliContext.from_args(args, logger=get_logger(logger))
    if getattr(args, "path", None) == "trace":
        return cmd_render_trace(args, ctx=ctx, logger=logger)
    if not getattr(args, "path", None):
        raise ConnectCtlError("render requires a manifest path")
    if getattr(args, "trace_path", None):
        raise ConnectCtlError(
            "Unexpected extra positional argument. Use `bkkt render trace <manifest>` "
            "or `bkkt render <manifest>`."
        )
    svc = RenderService(ctx=ctx, logger=logger)
    return int(svc.run(args))


def cmd_render_trace(args: argparse.Namespace, *, ctx: CliContext, logger=None) -> int:
    manifest_arg = getattr(args, "trace_path", None)
    if not manifest_arg:
        raise ConnectCtlError("Usage: bkkt render trace <manifest> --config-key <key>")
    config_key = getattr(args, "config_key", None)
    if not config_key:
        raise ConnectCtlError("`bkkt render trace` requires --config-key")

    repo_root = ctx.repo_root
    env_file = (repo_root / str(manifest_arg)).resolve()
    runtime_vars, runtime_sources = load_runtime_vars_with_sources(args, repo_root)
    renderer = build_renderer(
        ctx.settings,
        fs=ctx.fs,
        routing_cli_cluster=getattr(args, "cluster", None),
        routing_suppress_tag_conflicts=bool(
            getattr(args, "suppress_tag_conflicts", False)
        ),
    )
    rr = renderer.render(
        env_file,
        runtime_vars=runtime_vars,
        runtime_var_sources=runtime_sources,
        reuse_overrides=bool(getattr(args, "reuse_overrides", True)),
        reuse_from=[Path(p) for p in (getattr(args, "reuse_from", None) or [])] or None,
    )
    graph = TemplateExecutionGraphBuilder(ctx.settings).build(rr)
    report = TemplateTracer(repo_root=repo_root).trace_config_key(
        rr,
        graph,
        config_key=str(config_key),
    )
    payload = report.to_payload()
    schema = VarsSchemaLoader(ctx.repo_root).load()
    if getattr(args, "include_contracts", False):
        payload = TraceContractEnricher(schema).enrich_payload(payload)
    else:
        payload["steps"] = _redact_trace_steps(
            payload.get("steps", []),
            VarsRedactor(schema),
        )
    return _emit_trace(payload, args)


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    return _register_render_parser(subparsers, handler=cmd_render)


def _emit_trace(payload: dict, args: argparse.Namespace) -> int:
    fmt = resolve_output_format(args)
    if fmt in (OutputFormat.json, OutputFormat.yaml):
        write_payload(payload, fmt=fmt)
    else:
        write_text(
            f"{payload['config_key']} = {payload['final_value']}\n"
            f"manifest: {payload['manifest']}\n"
        )
        for step in payload["steps"]:
            write_text(
                f"- {step['kind']}: {step['name']} "
                f"value={step.get('value')} source={step.get('source')}\n"
            )
    return 0


def _redact_trace_steps(
    steps: list[dict],
    redactor: VarsRedactor,
) -> list[dict]:
    redacted: list[dict] = []
    for step in steps:
        item = dict(step)
        if "value" in item:
            item["value"] = redactor.redact_value(str(item.get("name")), item["value"])
        redacted.append(item)
    return redacted
