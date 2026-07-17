# Security Policy

BKKT works with Kafka Connect, Schema Registry, Kafka Admin APIs, credentials,
and production-adjacent operational metadata. Please handle security reports
privately.

## Supported versions

Security fixes target the latest published alpha/pre-release and the latest
stable release once one exists.

## Reporting a vulnerability

Do **not** open a public GitHub issue for vulnerabilities, leaked secrets, or
private infrastructure details.

Use [GitHub private vulnerability reporting](https://github.com/PaulKov/bkkt/security/advisories/new)
for `PaulKov/bkkt`.

Include:

- affected BKKT version;
- whether the issue affects CLI, generated manifests, or bundled demo assets;
- minimal reproduction steps;
- impact and any known workaround;
- whether any credentials, internal hosts, or customer data may be exposed.

## Handling secrets

- Never commit real credentials, tokens, private keys, JAAS strings, cloud
  account identifiers, or production host lists.
- Use placeholders such as `${secretManager:...}` in examples.
- Prefer sanitized demo assets under `connectctl/assets/demo`.
- Run `bkkt oss hygiene --scope repository` before public release work.

## Disclosure

Maintainers will acknowledge confirmed reports, coordinate a fix, and publish a
release note when the fix is available.
