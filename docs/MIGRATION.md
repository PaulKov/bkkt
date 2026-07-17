# Migration notes

## From an internal BKKT / connectctl fork

1. Install the public alpha: `pip install --pre bkkt==0.1.0a1`.
2. Keep using `connectctl.yaml` and existing connector manifests when they are
   already portable.
3. Remove enterprise-only commands from scripts/CI:
   `mr`, `report`, `fleet`, `assurance`, `reliability`, `health`, `heal`,
   `rollout`, `incident`, `monitor`, `service`, `ui`, continuous-deployment.
4. Replace company hosts/buckets/account IDs with environment-specific local
   config that is **not** committed.
5. Run `bkkt oss hygiene --scope repository` on any repository you intend to
   publish.

## Python imports

The distribution name is `bkkt`, but the importable package remains
`connectctl`. Treat `connectctl` as an unstable implementation detail in alpha.

## Credentials

Never copy `prod-aws-credentials.toml`, `.env` files, or private keys into a
public fork. Use your local secret manager / AWS profile outside Git.
