# Release process

Public alpha releases use GitHub Actions + PyPI Trusted Publishing (OIDC).
Long-lived `PYPI_API_TOKEN` values are **not** stored in the repository.

## Versioning

- PEP 440 prerelease: `0.1.0a1`
- Git tag: `v0.1.0a1`
- Package name: `bkkt`

## Preconditions

1. `master` CI is green (lint, mypy, pytest, hygiene, build, wheel smoke).
2. `bkkt oss readiness` passes.
3. PyPI Trusted Publisher is configured for:
   - owner: `PaulKov`
   - repository: `bkkt`
   - workflow: `release.yml`
   - environment: `pypi`

## Publish

```bash
git checkout master
git pull
git tag -a v0.1.0a1 -m "bkkt 0.1.0a1"
git push origin v0.1.0a1
```

The release workflow rebuilds artifacts, verifies version/tag match, creates a
GitHub prerelease, and publishes to PyPI via OIDC.

## Verify from outside

```bash
pip install --pre bkkt==0.1.0a1
bkkt --version
bkkt --help
bkkt demo init /tmp/bkkt-demo && (cd /tmp/bkkt-demo && bkkt demo smoke)
```
