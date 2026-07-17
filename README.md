# BKKT

**BKKT** is a portable GitOps CLI for Kafka Connect.

Manage connector manifests as code: render, validate, compare, plan, apply, and
operate Connect / Kafka Admin / Schema Registry from one workflow-friendly tool.

> Alpha software (`0.1.0a1`). The CLI command surface is the supported contract.
> The internal Python package (`connectctl`) is **not** a stable public API.

## Install

```bash
pip install --pre bkkt==0.1.0a1
# or
uv pip install --pre bkkt==0.1.0a1
```

Requirements: Python 3.11 or 3.12.

## 10-minute local demo

```bash
bkkt demo init --output-dir ./bkkt-demo
cd ./bkkt-demo
bkkt demo up          # starts Redpanda + Kafka Connect via Docker Compose
bkkt demo smoke       # render/validate/apply dry-run against the demo stack
bkkt demo down
```

The demo assets ship inside the package (`connectctl/assets/demo`) and use only
localhost / synthetic `acme` / `orders` fixtures.

## Safe live workflow

BKKT keeps mutation safety gates on by default:

1. Prefer `--dry-run` first.
2. Scope work with explicit `--env`, `--cluster`, path, or selector flags.
3. Confirm broad fan-out interactively, or pass `--yes` in automation.

```bash
# Render + validate from manifests
bkkt render --env dev --cluster local
bkkt validate --env dev --cluster local

# Inspect drift without changing the cluster
bkkt compare --env dev --cluster local --dry-run
bkkt drift --env dev --cluster local

# Apply only after review
bkkt plan --env dev --cluster local
bkkt apply --env dev --cluster local --dry-run
bkkt apply --env dev --cluster local --yes
```

## Portable CLI scope (alpha)

| Family | Purpose |
|--------|---------|
| `config` / `repo` | Local workspace and cluster config |
| `render` / `validate` / `validate-connect` / `inspect` | Manifest quality gates |
| `search` / `find` / `lineage` | Discovery across repo and live clusters |
| `compare` / `diff` / `drift` / `plan` / `apply` | Desired vs live workflows |
| `export` / `sync` / `reconcile` | Capture and converge state |
| `connect` / `kafka` / `schema` | Runtime Connect / Admin / SR operations |
| `functions` / `vars` | Placeholder helpers |
| `demo` / `oss` / `docs` / `completion` | Self-service DX |

Enterprise-only families (GitLab MR automation, fleet/assurance/reliability
centers, UI/service API, heal/rollout/incident/monitor) are **not** part of the
public alpha.

## Search examples (neutral fixtures)

```bash
bkkt search --source repo --env prod \
  --table 'prod__dbt__acme__orders__raw.exchange_rates__events'

bkkt find --source repo --env prod \
  --database 'prod__cdc__users__acme_common__ods' \
  --table 'acme__ma_users'

bkkt search --source live --env stage --cluster all \
  --topic 'stage__cdc__users__acme_common__ods.acme_3__ma_users' \
  --yes
```

## OSS hygiene gates

Before publishing or contributing large changes:

```bash
bkkt oss hygiene --scope public
bkkt oss hygiene --scope repository
bkkt oss readiness
```

Repository scope hard-denies credential filenames, cloud/API token shapes,
private keys, and private infrastructure hosts.

## Documentation

| Doc | Audience |
|-----|----------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How BKKT layers manifests and runtime clients |
| [docs/CLI.md](docs/CLI.md) | Full alpha command contract |
| [docs/MANIFESTS.md](docs/MANIFESTS.md) | Manifest layout and layering |
| [docs/CONNECT.md](docs/CONNECT.md) | Kafka Connect operations |
| [docs/KAFKA.md](docs/KAFKA.md) | Kafka Admin helpers |
| [docs/SCHEMA_REGISTRY.md](docs/SCHEMA_REGISTRY.md) | Schema Registry helpers |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common failures |
| [docs/RELEASE.md](docs/RELEASE.md) | Tagging and PyPI Trusted Publishing |
| [docs/MIGRATION.md](docs/MIGRATION.md) | Moving from internal forks to public BKKT |
| [CHANGELOG.md](CHANGELOG.md) | Alpha notes and limitations |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup and PR expectations |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |

## License

Apache License 2.0. See [LICENSE](LICENSE).
