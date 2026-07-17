from __future__ import annotations

import argparse
from collections import defaultdict

from connectctl.cli_parser import build_parser


def test_duplicate_store_action_destinations_do_not_shadow_defaults_with_none() -> None:
    """Guard against DATAPLAT-3491-style argparse alias regressions.

    The bug was caused by two optional arguments sharing the same ``dest``:
    the alias action stored ``None`` and shadowed the canonical action default.
    Boolean pairs such as ``--foo`` / ``--no-foo`` are fine; this test only
    checks value-storing actions where a ``None`` default can later crash
    service-layer ``float(...)`` / ``int(...)`` parsing.
    """

    failures: list[str] = []
    for command_path, actions in _walk_duplicate_optional_actions(build_parser()):
        store_actions = [
            action for action in actions if type(action).__name__ == "_StoreAction"
        ]
        if len(store_actions) < 2:
            continue
        has_none_default = any(action.default is None for action in store_actions)
        has_real_default = any(
            action.default not in {None, argparse.SUPPRESS} for action in store_actions
        )
        if has_none_default and has_real_default:
            rendered = ", ".join(
                f"{'/'.join(action.option_strings)} default={action.default!r}"
                for action in store_actions
            )
            failures.append(f"{' '.join(command_path)}: {rendered}")

    assert not failures, "\n".join(failures)


def test_apply_timeout_alias_keeps_canonical_default() -> None:
    parser = build_parser()

    apply_args = parser.parse_args(
        [
            "apply",
            "--env",
            "prod",
            "--dry-run",
            "connectors/demo/prod.json",
        ]
    )
    assert apply_args.timeout_seconds == 300


def _walk_duplicate_optional_actions(
    parser: argparse.ArgumentParser,
    *,
    command_path: tuple[str, ...] = (),
) -> list[tuple[tuple[str, ...], list[argparse.Action]]]:
    duplicates: list[tuple[tuple[str, ...], list[argparse.Action]]] = []
    by_dest: dict[str, list[argparse.Action]] = defaultdict(list)
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                duplicates.extend(
                    _walk_duplicate_optional_actions(
                        child,
                        command_path=(*command_path, str(name)),
                    )
                )
            continue
        if action.option_strings and action.dest != "help":
            by_dest[action.dest].append(action)

    for actions in by_dest.values():
        if len(actions) > 1:
            duplicates.append((command_path, actions))
    return duplicates
