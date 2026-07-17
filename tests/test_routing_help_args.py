from __future__ import annotations

import pytest

from connectctl.cli_parser import build_parser


@pytest.mark.parametrize(
    "cmd, expected_flags",
    [
        ("diff", ["--cluster", "--suppress-tag-conflicts"]),
        ("sync", ["--cluster", "--suppress-tag-conflicts"]),
        ("validate-connect", ["--cluster", "--suppress-tag-conflicts"]),
    ],
)
def test_help_contains_routing_flags(
    capsys: pytest.CaptureFixture[str],
    cmd: str,
    expected_flags: list[str],
) -> None:
    """Защитный тест: команды должны документировать routing-флаги в --help.

    Это помогает ловить регрессии в CLI и синхронизировать docs/CLI_REFERENCE.md.
    """

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([cmd, "--help"])  # prints help + exits(0)

    out = capsys.readouterr().out
    for flag in expected_flags:
        assert flag in out
