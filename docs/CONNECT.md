# Kafka Connect guide

## Status and inventory

```bash
bkkt connect status --env dev --cluster local
bkkt connect list --env dev --cluster local
bkkt get-connector NAME --env dev --cluster local
```

## Safe mutations

```bash
bkkt connect pause NAME --env dev --cluster local --dry-run
bkkt connect resume NAME --env dev --cluster local --yes
bkkt connect restart NAME --env dev --cluster local --yes
bkkt connect delete NAME --env dev --cluster local --dry-run
```

Prefer `plan` / `apply` for GitOps changes instead of ad-hoc PATCH loops.

## Apply workflow

```bash
bkkt compare --env dev --cluster local
bkkt plan --env dev --cluster local
bkkt apply --env dev --cluster local --dry-run
bkkt apply --env dev --cluster local --yes
```

## Tips

- Use `--cluster all` only with confirmation/`--yes`.
- Capture live state with `bkkt export` before large reconciles.
- Failed tasks: inspect with `bkkt connect status` then restart a single task
  when safe.
