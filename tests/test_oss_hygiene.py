"""OSS hygiene and repository-wide secret/internal-reference guardrails."""

from __future__ import annotations

from pathlib import Path

from connectctl.cli_parser import build_parser
from connectctl.services.oss_hygiene import (
    FORBIDDEN_FILENAMES,
    OssHygieneService,
    REPO_WIDE_SKIP_DIR_NAMES,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_user_facing_docs_and_bootstrap_assets_are_oss_safe() -> None:
    report = OssHygieneService().scan(root=REPO_ROOT)

    assert report.ok, "Found project-specific references:\n" + "\n".join(
        f"{finding.path}:{finding.line} -> {finding.rule_id}"
        for finding in report.findings
    )


def test_repository_wide_scan_is_clean_for_alpha_export() -> None:
    report = OssHygieneService().scan_repository(root=REPO_ROOT)

    assert report.ok, "Repository-wide hygiene failed:\n" + "\n".join(
        f"{finding.path}:{finding.line} -> {finding.rule_id}: {finding.excerpt}"
        for finding in report.findings
    )
    assert report.files_scanned > 50
    assert "prod-aws-credentials.toml" not in {
        Path(path).name for path in _tracked_names(REPO_ROOT)
    }


def test_oss_hygiene_detects_internal_references(tmp_path: Path) -> None:
    public_doc = tmp_path / "README.md"
    public_doc.write_text(
        "private endpoint: https://git.internal/example\n", encoding="utf-8"
    )

    report = OssHygieneService().scan(root=tmp_path, globs=("README.md",))

    assert report.ok is False
    assert report.findings[0].rule_id == "internal_gitlab"
    assert report.findings[0].path == "README.md"


def test_repository_wide_scan_hard_denies_credential_filename(tmp_path: Path) -> None:
    (tmp_path / "prod-aws-credentials.toml").write_text(
        "access_key_id = 'example'\n", encoding="utf-8"
    )

    report = OssHygieneService().scan_repository(root=tmp_path)

    assert report.ok is False
    assert any(finding.rule_id == "forbidden_filename" for finding in report.findings)


def test_repository_wide_scan_hard_denies_aws_access_key(tmp_path: Path) -> None:
    sample = tmp_path / "notes.md"
    sample.write_text("key=AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")

    report = OssHygieneService().scan_repository(root=tmp_path)

    assert report.ok is False
    assert any(finding.rule_id == "aws_access_key_id" for finding in report.findings)


def test_repository_wide_scan_hard_denies_private_key_block(tmp_path: Path) -> None:
    sample = tmp_path / "id_rsa"
    sample.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )

    report = OssHygieneService().scan_repository(root=tmp_path)

    assert report.ok is False
    assert any(finding.rule_id == "private_key" for finding in report.findings)


def test_repository_wide_scan_hard_denies_gitlab_rip(tmp_path: Path) -> None:
    sample = tmp_path / "config.yaml"
    sample.write_text("url: https://gitlab.rip/group/project\n", encoding="utf-8")

    report = OssHygieneService().scan_repository(root=tmp_path)

    assert report.ok is False
    assert any(finding.rule_id == "internal_gitlab_rip" for finding in report.findings)


def test_repository_wide_scan_allows_rfc1918_in_tests(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_hosts.py").write_text(
        'hosts = ["10.0.0.1", "192.168.1.10"]\n', encoding="utf-8"
    )

    report = OssHygieneService().scan_repository(root=tmp_path)

    assert report.ok is True


def test_repository_wide_scan_skips_venv_and_git_dirs(tmp_path: Path) -> None:
    forbidden = tmp_path / ".venv" / "lib"
    forbidden.mkdir(parents=True)
    (forbidden / "leak.txt").write_text("https://gitlab.rip/secret\n", encoding="utf-8")
    assert ".venv" in REPO_WIDE_SKIP_DIR_NAMES

    report = OssHygieneService().scan_repository(root=tmp_path)

    assert report.ok is True
    assert report.files_scanned == 0


def test_forbidden_filename_allowlist_covers_credentials_toml() -> None:
    assert "prod-aws-credentials.toml" in FORBIDDEN_FILENAMES
    assert "*.credentials.toml" in FORBIDDEN_FILENAMES


def test_cli_parser_exposes_oss_commands_without_config_requirement() -> None:
    parser = build_parser()

    hygiene = parser.parse_args(["oss", "hygiene", "--output", "json"])
    readiness = parser.parse_args(["oss", "readiness", "--root", "."])
    repo = parser.parse_args(
        ["oss", "hygiene", "--scope", "repository", "--output", "json"]
    )

    assert hygiene.cmd == "oss"
    assert hygiene.oss_cmd == "hygiene"
    assert hygiene.requires_config is False
    assert readiness.oss_cmd == "readiness"
    assert readiness.requires_config is False
    assert repo.scope == "repository"


def test_public_cli_contract_still_rejects_enterprise_families() -> None:
    parser = build_parser()
    with __import__("pytest").raises(SystemExit):
        parser.parse_args(["fleet", "--help"])


def _tracked_names(root: Path) -> set[str]:
    return {path.name for path in root.rglob("*") if path.is_file()}
