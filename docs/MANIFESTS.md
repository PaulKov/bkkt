# Manifests and layering

BKKT expects a connector repository with:

```text
connectctl.yaml          # cluster inventory, vars, defaults
schemas/                 # optional JSON Schema contracts
<source|sink>/.../*.json # connector manifests
```

## `connectctl.yaml`

Minimal local example:

```yaml
clusters:
  dev:
    local:
      hosts: ["http://localhost:8083"]
vars:
  env: dev
```

Use RFC1918 or localhost hosts in examples. Never commit production credentials.

## Connector manifests

Each connector is a JSON document with at least:

```json
{
  "name": "dev.acme.orders.sink.raw.iceberg.0",
  "config": {
    "connector.class": "org.apache.kafka.connect.file.FileStreamSinkConnector",
    "topics": "acme.orders.events",
    "file": "/tmp/orders.out"
  }
}
```

Placeholders such as `${env}` or `${secretManager:...}` are resolved during
render. Secret values must never be committed in plaintext.

## Layering order

1. Global defaults (`connectctl/assets/repo_defaults` when bootstrapping)
2. Repository `connectctl.yaml` vars
3. Per-connector manifest fields
4. Runtime overrides from CLI flags

## Validation

```bash
bkkt render --env dev --cluster local
bkkt validate --env dev --cluster local
bkkt validate-connect --env dev --cluster local
```
