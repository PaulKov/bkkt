# Architecture

BKKT is a portable GitOps control plane for Kafka Connect.

## Layers

```text
┌──────────────────────────────────────────────┐
│ CLI (bkkt)                                   │
│ argparse parsers → command handlers          │
├──────────────────────────────────────────────┤
│ Services                                     │
│ render / validate / compare / apply / sync   │
│ search / lineage / drift / reconcile         │
├──────────────────────────────────────────────┤
│ Ports & clients                              │
│ Connect REST · Kafka Admin · Schema Registry │
├──────────────────────────────────────────────┤
│ Workspace                                    │
│ connectctl.yaml · manifests · schemas        │
└──────────────────────────────────────────────┘
```

## Design principles

- **GitOps first** — desired state lives in JSON/YAML manifests.
- **Dry-run by default for mutations** — plan before apply.
- **Explicit selection** — env/cluster/path selectors reduce blast radius.
- **Portable core** — no private CI, GitLab, or fleet centers in alpha.
- **Internal package is unstable** — distribute as `bkkt`; import `connectctl`
  only at your own risk.

## Manifest flow

1. Load `connectctl.yaml` cluster inventory and vars.
2. Resolve placeholders / functions.
3. Render effective connector configs.
4. Validate locally (and optionally against Connect plugin validation).
5. Compare against live REST state.
6. Apply create/update/delete with confirmation gates.

## Runtime clients

| Client | Used by |
|--------|---------|
| Kafka Connect REST | `connect`, `apply`, `compare`, `drift`, `sync` |
| Kafka Admin | `kafka` topic/group/broker helpers |
| Schema Registry | `schema` subjects/compatibility |

## OSS hygiene

`bkkt oss hygiene --scope repository` hard-denies credentials, token shapes,
private keys, and private infrastructure references before release.
