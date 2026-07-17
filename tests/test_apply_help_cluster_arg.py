from __future__ import annotations

import pytest

from connectctl.cli_parser import build_parser


def test_apply_help_contains_cluster_arg(capsys: pytest.CaptureFixture[str]) -> None:
    """Защитный тест: apply должен поддерживать --cluster.

    Это критично для multi-cluster деплоя и должно ловиться в CI при регрессии.
    """

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["apply", "--help"])  # prints help + exits(0)

    out = capsys.readouterr().out
    assert "--cluster" in out
