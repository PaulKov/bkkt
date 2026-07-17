from pathlib import Path

from connectctl.models import RepoConfig
from connectctl.validation import lint_connector_dir_pattern, format_repo_layout_issues


def test_connector_dir_lint_detects_domain_mismatch_and_dataset_charset(tmp_path: Path):
    # Minimal repo layout
    (tmp_path / "orders" / "source" / "postgres" / "connector_orders__payments").mkdir(
        parents=True
    )
    (tmp_path / "orders" / "source" / "postgres" / "connector_wrong__payments").mkdir(
        parents=True
    )
    (tmp_path / "orders" / "sink" / "iceberg" / "connector_orders__bad-dataset").mkdir(
        parents=True
    )
    # Special dirs must be ignored
    (tmp_path / "orders" / "sink" / "iceberg" / "types").mkdir(parents=True)
    (tmp_path / "orders" / "sink" / "iceberg" / "modes").mkdir(parents=True)
    (tmp_path / "orders" / "sink" / "iceberg" / "sql" / "stage").mkdir(parents=True)

    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)
    issues = lint_connector_dir_pattern(cfg)

    # One issue for domain mismatch + one for dataset charset
    assert len(issues) == 2
    paths = sorted(i.path for i in issues)
    assert "orders/source/postgres/connector_wrong__payments" in paths
    assert "orders/sink/iceberg/connector_orders__bad-dataset" in paths


def test_connector_dir_lint_can_skip_dataset_charset_check(tmp_path: Path):
    (tmp_path / "orders" / "sink" / "iceberg" / "connector_orders__bad-dataset").mkdir(
        parents=True
    )
    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)

    issues = lint_connector_dir_pattern(cfg, check_dataset_charset=False)
    # With charset check disabled, this name is considered structurally ok.
    assert issues == []


def test_connector_dir_lint_can_be_scoped_to_specific_dirs(tmp_path: Path):
    (tmp_path / "orders" / "source" / "postgres" / "connector_orders__payments").mkdir(
        parents=True
    )
    (tmp_path / "orders" / "source" / "postgres" / "connector_wrong__payments").mkdir(
        parents=True
    )
    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)

    # Scope to the *valid* directory only -> no issues.
    issues_ok = lint_connector_dir_pattern(
        cfg, limit_to_paths=[Path("orders/source/postgres/connector_orders__payments")]
    )
    assert issues_ok == []

    # Scope to the *invalid* directory only -> single issue.
    issues_bad = lint_connector_dir_pattern(
        cfg, limit_to_paths=[Path("orders/source/postgres/connector_wrong__payments")]
    )
    assert len(issues_bad) == 1
    assert issues_bad[0].path == "orders/source/postgres/connector_wrong__payments"


def test_format_repo_layout_issues_truncates_output(tmp_path: Path):
    # Build a couple of issues by creating invalid directories.
    (tmp_path / "orders" / "source" / "postgres" / "connector_wrong__a").mkdir(
        parents=True
    )
    (tmp_path / "orders" / "source" / "postgres" / "connector_wrong__b").mkdir(
        parents=True
    )
    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)
    issues = lint_connector_dir_pattern(cfg)
    assert len(issues) == 2

    txt = format_repo_layout_issues(issues, max_items=1)
    assert "… и ещё" in txt


def test_connector_dir_lint_ignores_shared_sql_system_dir(tmp_path: Path):
    (tmp_path / "acme" / "sink" / "clickhouse" / "sql" / "stage").mkdir(parents=True)
    (tmp_path / "acme" / "sink" / "clickhouse" / "connector_acme__events").mkdir(
        parents=True
    )
    cfg = RepoConfig(root=tmp_path, connectors_root=tmp_path)

    issues = lint_connector_dir_pattern(cfg)

    assert issues == []
