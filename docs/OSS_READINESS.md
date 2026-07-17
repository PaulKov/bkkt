# OSS readiness checklist

Run before every public tag:

```bash
uv sync --all-extras
uv run pre-commit run -a
uv run mypy --no-incremental connectctl
uv run pytest -q
uv run bkkt oss hygiene --scope public
uv run bkkt oss hygiene --scope repository
uv run bkkt oss readiness
uv build
uv run twine check dist/*
```

## Must be true

- [ ] No `prod-aws-credentials.toml` or `*.credentials.toml`
- [ ] No private keys / cloud API tokens
- [ ] No private GitLab / internal registry hosts
- [ ] No company domain markers in tracked files
- [ ] Public CLI contract tests pass
- [ ] Demo smoke works from a clean wheel install
