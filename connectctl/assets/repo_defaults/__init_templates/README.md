# __init_templates

This directory contains repository-local init templates for `bkkt init`.

How it works:

- BKKT always has built-in templates.
- If a manifests repository also contains `__init_templates/`, BKKT will look for more
  specific template fragments here and layer them on top of the built-ins.

Important:

- Files in `__init_templates/` affect only `bkkt init`.
- They do not participate in render/apply of existing manifests.
- Runtime render uses layered overrides from `__global/` and domain-specific layers.

Typical flow:

1. Run `bkkt repo bootstrap`
2. Edit the template fragment you want to customize
3. Re-run `bkkt init` and inspect the generated manifests
