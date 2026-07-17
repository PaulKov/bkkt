from __future__ import annotations

from typing import List

from ...output import OutputFormat, write_payload, write_text
from .models import SearchExplainMode, SearchResultItem, SearchRunResult, SearchView


def emit_search_output(
    result: SearchRunResult, *, fmt: OutputFormat, view: SearchView
) -> None:
    if fmt == OutputFormat.text:
        if view == SearchView.long:
            write_text(_render_long_text(result))
        else:
            write_text(_render_short_text(result))
        return
    write_payload(result.to_dict(), fmt=fmt)


def _render_short_text(result: SearchRunResult) -> str:
    lines: List[str] = []
    lines.append(
        "Search: source={source} env={env} cluster={cluster} explain={explain} count={count}\n".format(
            source=result.query.source.value,
            env=",".join(result.query.envs),
            cluster=result.query.cluster_filter or "all",
            explain=result.query.explain.value,
            count=len(result.results),
        )
    )
    if result.query.explain == SearchExplainMode.stats:
        lines.extend(_render_stats_lines(result))
    for item in result.results:
        facts = item.facts
        hit_summary = _render_hit_summary(item)
        lines.append(
            "[{origin}] env={env} cluster={cluster} {name} domain={domain} dataset={dataset} type={ctype} system={system}{hit}\n".format(
                origin=facts.origin,
                env=",".join(facts.envs) or "?",
                cluster=",".join(facts.clusters) or "?",
                name=facts.name,
                domain=facts.domain or "?",
                dataset=facts.dataset or "?",
                ctype=facts.connector_type or "?",
                system=facts.system or "?",
                hit=f" hit={hit_summary}" if hit_summary else "",
            )
        )
    if result.warnings:
        lines.append("\nWarnings:\n")
        for warning in result.warnings:
            lines.append(f"- {warning}\n")
    return "".join(lines)


def _render_long_text(result: SearchRunResult) -> str:
    lines: List[str] = []
    lines.append(
        "Search: source={source} env={env} cluster={cluster} explain={explain} count={count}\n\n".format(
            source=result.query.source.value,
            env=",".join(result.query.envs),
            cluster=result.query.cluster_filter or "all",
            explain=result.query.explain.value,
            count=len(result.results),
        )
    )
    if result.query.explain == SearchExplainMode.stats:
        lines.extend(_render_stats_lines(result))
        lines.append("\n")

    for item in result.results:
        facts = item.facts
        lines.append(f"- Connector: {facts.name}\n")
        lines.append(f"  origin: {facts.origin}\n")
        lines.append(f"  env: {', '.join(facts.envs) or '?'}\n")
        lines.append(f"  cluster: {', '.join(facts.clusters) or '?'}\n")
        if facts.path:
            lines.append(f"  path: {facts.path}\n")
        if facts.alias_scopes:
            lines.append("  alias scopes:\n")
            for alias in facts.alias_scopes:
                urls = ", ".join(alias.urls)
                lines.append(f"    - {alias.cluster}/{alias.env} urls=[{urls}]\n")
        lines.append(
            "  meta: domain={domain} dataset={dataset} type={ctype} system={system} layer={layer} mode={mode} kind={kind}\n".format(
                domain=facts.domain or "?",
                dataset=facts.dataset or "?",
                ctype=facts.connector_type or "?",
                system=facts.system or "?",
                layer=facts.layer or "-",
                mode=facts.mode or "-",
                kind=facts.kind or "-",
            )
        )
        if facts.source_tables:
            lines.append(f"  source tables: {', '.join(facts.source_tables)}\n")
        if facts.sink_tables:
            lines.append(f"  sink tables: {', '.join(facts.sink_tables)}\n")
        if facts.consumed_topics:
            lines.append(f"  consumed topics: {', '.join(facts.consumed_topics)}\n")
        if facts.produced_topics:
            lines.append(f"  produced topics: {', '.join(facts.produced_topics)}\n")
        if facts.produced_pattern:
            lines.append(f"  produced pattern: {facts.produced_pattern}\n")
        topic_patterns = facts.topic_patterns()
        if topic_patterns:
            lines.append(f"  topic patterns: {', '.join(topic_patterns)}\n")
        if (
            facts.db_hosts
            or facts.db_ports
            or facts.db_names
            or facts.db_schemas
            or facts.db_servers
        ):
            lines.append(
                "  db: host={host} port={port} name={name} schema={schema} server={server}\n".format(
                    host=", ".join(facts.db_hosts) or "-",
                    port=", ".join(facts.db_ports) or "-",
                    name=", ".join(facts.db_names) or "-",
                    schema=", ".join(facts.db_schemas) or "-",
                    server=", ".join(facts.db_servers) or "-",
                )
            )
        if facts.sink_database or facts.sink_warehouse:
            lines.append(
                "  sink: database={database} warehouse={warehouse}\n".format(
                    database=facts.sink_database or "-",
                    warehouse=facts.sink_warehouse or "-",
                )
            )
        if item.matched:
            lines.append("  matched:\n")
            for match in item.matched:
                matched_values = (
                    ", ".join(match.matched_values) if match.matched_values else "-"
                )
                query_value = (
                    match.query_value if match.query_value is not None else "-"
                )
                lines.append(
                    f"    - field={match.field} op={match.operator} query={query_value} values={matched_values}\n"
                )
                if result.query.explain == SearchExplainMode.long and match.sources:
                    lines.append(f"      via: {', '.join(match.sources)}\n")
                if result.query.explain == SearchExplainMode.long and match.occurrences:
                    lines.append("      also found:\n")
                    for occurrence in match.occurrences:
                        sources = ", ".join(occurrence.sources) or "-"
                        lines.append(
                            f"        - field={occurrence.field} value={occurrence.value} via={sources}\n"
                        )
        lines.append("\n")

    if result.warnings:
        lines.append("Warnings:\n")
        for warning in result.warnings:
            lines.append(f"- {warning}\n")
    return "".join(lines)


def _render_hit_summary(item: SearchResultItem) -> str:
    if not item.matched:
        return ""
    chunks = []
    for match in item.matched[:3]:
        values = ",".join(match.matched_values[:2]) if match.matched_values else "-"
        chunks.append(
            f"{match.field}{match.operator}{match.query_value or ''}->{values}"
        )
    more = len(item.matched) - len(chunks)
    if more > 0:
        chunks.append(f"+{more} more")
    return "; ".join(chunks)


def _render_stats_lines(result: SearchRunResult) -> List[str]:
    stats = result.stats_to_dict()
    lines: List[str] = ["Stats:\n"]
    sections = (
        ("by env/cluster", stats["by_env_cluster"]),
        ("by matched field", stats["by_field"]),
        ("by config source", stats["by_config_source"]),
    )
    for title, values in sections:
        lines.append(f"  {title}:\n")
        if not values:
            lines.append("    - none\n")
            continue
        for key, count in values.items():
            lines.append(f"    - {key}: {count}\n")
    return lines


__all__ = ["emit_search_output"]
