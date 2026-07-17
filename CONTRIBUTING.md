# Contributing to BKKT

Thanks for helping improve BKKT. Keep the core portable, provider-agnostic, and
safe for self-hosted operators.

## Principles

- Keep the OSS core free of company-specific hosts, secrets, buckets, registry
  URLs, private incident details, and production manifests.
- Prefer GitOps-first workflows and dry-run/plan output for mutating operations.
- Treat the CLI surface as the public contract; `connectctl` Python imports are
  unstable in alpha.
- Write tests for behavior changes and update docs for user-visible changes.
- Prefer small modules, explicit services, and dependency injection.

## Local development

```bash
uv sync --extra dev
uv run pytest -q
uv run mypy --no-incremental connectctl
uv run pre-commit run -a
uv run bkkt oss hygiene --scope repository
uv run bkkt oss readiness
```

If the project exposes generated docs commands:

```bash
uv run bkkt docs generate-cli-reference --check
```

## Pull request checklist

- Describe the problem, user impact, and chosen solution.
- Include validation commands and notable test results.
- Call out any public CLI contract changes.
- Avoid bundling unrelated refactors with feature or bug-fix work.
- Run repository-wide OSS hygiene before opening the PR.

## Open-core boundary

See [docs/OSS_READINESS.md](docs/OSS_READINESS.md) and [docs/CLI.md](docs/CLI.md).
