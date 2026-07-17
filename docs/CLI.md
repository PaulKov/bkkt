# CLI contract (alpha)

The public alpha supports the following top-level families.

| Command | Notes |
|---------|-------|
| `config` | Inspect/edit local BKKT config helpers |
| `repo` | Bootstrap/migrate connector repositories |
| `render` | Render manifests to effective configs |
| `validate` | Local schema/policy validation |
| `validate-connect` | Live Connect plugin validation |
| `inspect` | Human-friendly connector inspection |
| `search` / `find` | Query repo or live connectors |
| `lineage` | Topic/table lineage views |
| `compare` / `diff` / `drift` | Desired vs live |
| `plan` / `apply` | Change planning and mutation |
| `export` / `sync` / `reconcile` | Capture and converge |
| `get-connector` | Fetch one connector payload |
| `connect` | Runtime Connect operations |
| `kafka` | Kafka Admin helpers |
| `schema` | Schema Registry helpers |
| `functions` / `vars` | Placeholder helpers |
| `demo` | Local Docker demo |
| `oss` | Hygiene/readiness gates |
| `docs` | Generate/check CLI reference |
| `completion` | Shell completion |
| `help` / `init` | UX aliases |

## Excluded from alpha

These families are intentionally absent:

`mr`, `report`, `release`, `continuous-deployment`, `service`, `ui`, `fleet`,
`assurance`, `reliability`, `health`, `dq`, `heal`, `rollout`, `incident`,
`monitor`, `freshness`, `state`, `templates`, `put-config`, `lint`, `doctor`
(top-level), `policies`, `explain` (top-level).

## Safety semantics

Mutating commands keep:

- `--dry-run` where mutation is possible;
- explicit selectors (`--env`, `--cluster`, path, regexp);
- confirmation or `--yes` for broad fan-out.

## Versioning

- Distribution name: `bkkt`
- Alpha version: `0.1.0a1`
- Internal module: `connectctl` (unstable)
