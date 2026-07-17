from __future__ import annotations

from connectctl.cli_helpers.explicit_args import explicit_dests, was_explicit
from connectctl.cli_parser import build_parser


def test_root_parser_tracks_explicit_options_across_subparsers() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "search",
            "--source",
            "live",
            "--topic",
            "payments.events",
        ]
    )

    assert was_explicit(args, "source") is True
    assert was_explicit(args, "topic") is True
    assert was_explicit(args, "env") is False
    assert was_explicit(args, "cluster") is False
    assert {"source", "topic"} <= explicit_dests(args)
