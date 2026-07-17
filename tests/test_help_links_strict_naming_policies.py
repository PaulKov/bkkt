from __future__ import annotations

import pytest

from connectctl.cli_parser import build_parser


@pytest.mark.parametrize(
    "cmd",
    [
        "apply",
        "diff",
        "sync",
        "validate",
        "validate-connect",
    ],
)
def test_help_mentions_naming_docs(
    capsys: pytest.CaptureFixture[str], cmd: str
) -> None:
    """UX guard: strict naming флаги должны вести к docs/NAMING.md.

    Если текст help меняется — обновите docs/CLI_REFERENCE.md через:
      bkkt docs generate-cli-reference
    """

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([cmd, "--help"])

    out = capsys.readouterr().out
    assert "docs/NAMING.md" in out


@pytest.mark.parametrize(
    "cmd",
    [
        "apply",
        "diff",
        "sync",
    ],
)
def test_help_mentions_policies_docs(
    capsys: pytest.CaptureFixture[str], cmd: str
) -> None:
    """UX guard: policy-flags должны вести к docs/POLICIES.md."""

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([cmd, "--help"])

    out = capsys.readouterr().out
    assert "docs/POLICIES.md" in out
