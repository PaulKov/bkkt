from __future__ import annotations

from pathlib import Path

from connectctl import cli


def test_repo_bootstrap_runs_without_connectctl_yaml(tmp_path: Path) -> None:
    rc = cli.main(["--repo-root", str(tmp_path), "repo", "bootstrap", "--dry-run"])
    assert rc == 0


def test_help_runs_without_connectctl_yaml() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rc = cli.main(["--repo-root", str(repo_root), "help", "--list"])
    assert rc == 0


def test_help_list_falls_back_to_argparse_when_examples_doc_is_missing(
    tmp_path: Path,
) -> None:
    rc = cli.main(["--repo-root", str(tmp_path), "help", "--list"])
    assert rc == 0


def test_help_topic_falls_back_to_argparse_when_examples_doc_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    rc = cli.main(["--repo-root", str(tmp_path), "help", "apply"])
    assert rc == 0

    captured = capsys.readouterr()
    assert "usage:" in captured.out
    assert "apply" in captured.out


def test_search_list_vars_runs_without_connectctl_yaml(tmp_path: Path) -> None:
    rc = cli.main(["--repo-root", str(tmp_path), "search", "--list-vars"])
    assert rc == 0
