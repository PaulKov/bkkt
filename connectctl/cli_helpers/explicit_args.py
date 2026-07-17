from __future__ import annotations

import argparse
import sys
from typing import Iterable, Iterator, Sequence, TypeVar, cast, overload


_N = TypeVar("_N")


def was_explicit(args: object, dest: str) -> bool:
    return dest in set(getattr(args, "_explicit_dests", ()) or ())


def explicit_dests(args: object) -> frozenset[str]:
    return frozenset(getattr(args, "_explicit_dests", ()) or ())


class ExplicitTrackingArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that annotates parsed namespaces with explicit CLI options."""

    @overload
    def parse_args(
        self,
        args: Sequence[str] | None = None,
        namespace: None = None,
    ) -> argparse.Namespace: ...

    @overload
    def parse_args(
        self,
        args: Sequence[str] | None,
        namespace: _N,
    ) -> _N: ...

    @overload
    def parse_args(
        self,
        *,
        namespace: _N,
    ) -> _N: ...

    def parse_args(
        self,
        args: Sequence[str] | None = None,
        namespace: _N | None = None,
    ) -> argparse.Namespace | _N:
        parsed = super().parse_args(args=args, namespace=namespace)
        annotate_namespace_with_explicit_args(
            self, cast(argparse.Namespace, parsed), argv=args
        )
        return parsed


def annotate_namespace_with_explicit_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    *,
    argv: Sequence[str] | None,
) -> None:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    option_map = _build_option_map(parser)
    explicit_options = tuple(_iter_explicit_options(raw_argv, option_map))
    explicit = frozenset(
        option_map[option] for option in explicit_options if option in option_map
    )
    setattr(args, "_raw_argv", tuple(raw_argv))
    setattr(args, "_explicit_options", tuple(explicit_options))
    setattr(args, "_explicit_dests", explicit)


def _build_option_map(parser: argparse.ArgumentParser) -> dict[str, str]:
    out: dict[str, str] = {}
    for action in _iter_parser_actions(parser):
        for option in getattr(action, "option_strings", ()) or ():
            out[option] = action.dest
    return out


def _iter_parser_actions(parser: argparse.ArgumentParser) -> Iterator[argparse.Action]:
    for action in parser._actions:
        yield action
        if isinstance(action, argparse._SubParsersAction):
            for subparser in action.choices.values():
                yield from _iter_parser_actions(subparser)


def _iter_explicit_options(
    argv: Sequence[str], option_map: dict[str, str]
) -> Iterable[str]:
    for token in argv:
        if token == "--":
            break
        if token.startswith("--") and token != "--":
            option = token.split("=", 1)[0]
            if option in option_map:
                yield option
            continue
        if not token.startswith("-") or token == "-":
            continue
        if token in option_map:
            yield token
            continue
        for short in _split_short_options(token, option_map):
            yield short


def _split_short_options(token: str, option_map: dict[str, str]) -> Iterable[str]:
    if not token.startswith("-") or token.startswith("--"):
        return ()
    options: list[str] = []
    for char in token[1:]:
        option = f"-{char}"
        if option in option_map:
            options.append(option)
    return tuple(options)


__all__ = [
    "ExplicitTrackingArgumentParser",
    "annotate_namespace_with_explicit_args",
    "explicit_dests",
    "was_explicit",
]
