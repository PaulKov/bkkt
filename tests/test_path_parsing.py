from pathlib import Path


from connectctl.models import Environment, ConnectorType, RepoConfig
from connectctl.repo import ConnectorRepo


def test_parse_connector_path_sample_repo():
    repo_root = Path(__file__).resolve().parents[1]
    cfg = RepoConfig(root=repo_root, connectors_root=repo_root)
    repo = ConnectorRepo(cfg)

    p = (
        repo_root
        / "acme/source/mysql/connector_acme__orders/prod_source_acme__orders__common_tables.json"
    )
    info = repo.parse_connector_path(p)

    assert info.domain == "acme"
    assert info.connector_type == ConnectorType.source
    assert info.system == "mysql"
    assert info.connector_dir == "connector_acme__orders"
    assert info.env == Environment.prod
    assert info.remainder.startswith("source_acme__orders__common_tables")
