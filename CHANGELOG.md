# Changelog

All notable changes to the public BKKT distribution are documented here.

## 0.1.0a1 — 2026-07-17

### Added

- First public alpha of the `bkkt` CLI on PyPI.
- Portable GitOps workflows: render, validate, compare, drift, plan, apply,
  export, sync, reconcile.
- Runtime helpers for Kafka Connect, Kafka Admin, and Schema Registry.
- Local Docker demo (`bkkt demo`).
- Repository-wide OSS hygiene / readiness gates (`bkkt oss`).

### Alpha limitations

- Not production-stable; expect CLI and packaging changes before 0.1.0.
- Internal Python package `connectctl` is **not** a stable public API.
- Enterprise families (GitLab MR automation, fleet/assurance/reliability
  centers, UI/service API, heal/rollout/incident/monitor) are out of scope.
- No long-lived PyPI tokens in CI — releases use GitHub OIDC Trusted Publishing.
