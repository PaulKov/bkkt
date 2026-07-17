from __future__ import annotations

import pytest

import connectctl
from connectctl.cli_parser import build_parser


def test_top_level_version_flag(capsys) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"bkkt {connectctl.__version__}"
