# Kafka Admin guide

BKKT wraps common Kafka Admin operations for operators who already manage
Connect manifests in the same workspace.

```bash
bkkt kafka topics list --env dev --cluster local
bkkt kafka topics describe TOPIC --env dev --cluster local
bkkt kafka groups list --env dev --cluster local
bkkt kafka brokers list --env dev --cluster local
```

## Safety

Topic create/delete/alter paths require explicit selection and confirmation
gates. Prefer dry-run output in CI and human review for production clusters.

Bootstrap servers and security settings come from `connectctl.yaml` cluster
definitions or environment-specific admin endpoints.
