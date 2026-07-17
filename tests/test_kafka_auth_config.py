from pathlib import Path

from connectctl.models import Environment
from connectctl.settings import Settings


def test_kafka_auth_iam_sets_oauthbearer(tmp_path: Path) -> None:
    cfg = tmp_path / "connectctl.yaml"
    cfg.write_text(
        """
version: 1
connectors_root: "."
clusters:
  dev:
    connect:
      hosts: ["127.0.0.1"]
      port: 8083
    kafka:
      bootstrap_servers: ["b-1:9098"]
      auth:
        type: iam
        region: eu-central-1
""".lstrip(),
        encoding="utf-8",
    )

    s = Settings.load(cfg, repo_root=tmp_path)
    k = s.clusters[Environment.dev].kafka
    assert k is not None
    assert k.sasl_mechanism == "OAUTHBEARER"
    assert k.iam_region == "eu-central-1"


def test_kafka_auth_maps_aws_msk_iam_to_oauthbearer(tmp_path: Path) -> None:
    cfg = tmp_path / "connectctl.yaml"
    cfg.write_text(
        """
version: 1
connectors_root: "."
clusters:
  dev:
    connect:
      hosts: ["127.0.0.1"]
      port: 8083
    kafka:
      bootstrap_servers: ["b-1:9098"]
      security_protocol: SASL_SSL
      sasl_mechanism: AWS_MSK_IAM
      iam_region: eu-central-1
""".lstrip(),
        encoding="utf-8",
    )

    s = Settings.load(cfg, repo_root=tmp_path)
    k = s.clusters[Environment.dev].kafka
    assert k is not None
    assert k.sasl_mechanism == "OAUTHBEARER"
    assert k.iam_region == "eu-central-1"
