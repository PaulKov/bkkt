from __future__ import annotations

import argparse

import pytest

from connectctl.cli_parser import build_parser


PUBLIC_COMMAND_FAMILIES = {
    "apply",
    "compare",
    "completion",
    "config",
    "connect",
    "demo",
    "diff",
    "docs",
    "drift",
    "export",
    "find",
    "functions",
    "get-connector",
    "help",
    "init",
    "inspect",
    "kafka",
    "lineage",
    "oss",
    "plan",
    "reconcile",
    "render",
    "repo",
    "schema",
    "search",
    "sync",
    "validate",
    "validate-connect",
    "vars",
}

EXCLUDED_COMMAND_FAMILIES = {
    "assurance",
    "connectors",
    "continuous-deployment",
    "doctor",
    "dq",
    "explain",
    "fleet",
    "freshness",
    "get_connector",
    "heal",
    "health",
    "incident",
    "lint",
    "monitor",
    "mr",
    "policies",
    "put-config",
    "release",
    "reliability",
    "render-changed",
    "report",
    "rollout",
    "service",
    "state",
    "templates",
    "ui",
}


def _top_level_choices(parser: argparse.ArgumentParser) -> set[str]:
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return set(subparsers.choices)


def test_public_cli_exposes_only_approved_command_families() -> None:
    assert _top_level_choices(build_parser()) == PUBLIC_COMMAND_FAMILIES


@pytest.mark.parametrize("command", sorted(EXCLUDED_COMMAND_FAMILIES))
def test_excluded_command_family_cannot_parse(command: str, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args([command])

    assert exc_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
