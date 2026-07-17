# Troubleshooting

## `bkkt` not found after install

```bash
python -m pip show bkkt
which bkkt
python -c "import connectctl; print(connectctl.__version__)"
```

Ensure the virtualenv that received `pip install` is active.

## Connect HTTP errors

- Verify `connectctl.yaml` hosts are reachable.
- Check TLS/basic-auth settings for the target env.
- Prefer `bkkt connect status` before broader compare/apply.

## Placeholder / secret resolution failures

- Confirm vars exist in `connectctl.yaml`.
- Secret manager placeholders must resolve in the runtime environment; BKKT
  does not store plaintext secrets in Git.

## Drift noise

Worker config transformers can rewrite live configs. Compare with
`bkkt compare` / `bkkt drift` and normalize known volatile keys before apply.

## OSS hygiene failures

```bash
bkkt oss hygiene --scope repository --output text
```

Remove credentials, private keys, private GitLab/registry hosts, and
company-specific domain markers before opening a PR.
