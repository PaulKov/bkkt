# Engineering Metrics

This document tracks BKKT code metrics that are generated from the current source tree.

- Command: `bkkt docs update-dev-metrics`
- Check mode: `bkkt docs update-dev-metrics --check`
- Scope:
  - repository-wide Python metrics
  - repository-wide Python metrics excluding tests
  - `connectctl` package metrics
  - internal dependency graph coupling/cohesion for `connectctl.*`

Definitions used in this document:

- `LOC` — all physical lines in Python files
- `SLOC` — source lines of code only (blank/comment-only lines excluded)
- `excluding tests` — excludes `tests/**`, `*/tests/**`, `conftest.py`, and `test_*.py`

<!-- BKKT_DEV_METRICS_START -->
_The section below is generated automatically by `bkkt docs update-dev-metrics`._

### Repository Python footprint

**All Python files (`**/*.py`)**

- Files: **715**
- LOC: **81699**
- SLOC: **65887**
- LOC/SLOC ratio: **1.24**
- Smallest file by LOC: **0** (`connectctl/adapters/__init__.py`)
- Largest file by LOC: **1406** (`connectctl/commands/vars_cmd.py`)
- Average LOC/file: **114.26**
- Median LOC/file: **73**

**Python files excluding tests**

- Files: **607**
- LOC: **63381**
- SLOC: **51544**
- LOC/SLOC ratio: **1.23**

### `connectctl` package footprint

- Files: **605**
- LOC: **63221**
- SLOC: **51424**
- LOC/SLOC ratio: **1.23**
- Average LOC/file: **104.50**
- Median LOC/file: **69**
- Average SLOC/file: **85.00**
- Median SLOC/file: **51**

**Top 15 largest `connectctl` modules**

| Module | LOC | SLOC |
|---|---:|---:|
| `connectctl/commands/vars_cmd.py` | 1406 | 1221 |
| `connectctl/commands/functions_cmd.py` | 1075 | 944 |
| `connectctl/commands/registry.py` | 1046 | 1007 |
| `connectctl/services/validate_connect_service.py` | 720 | 631 |
| `connectctl/services/init/template_engine.py` | 661 | 533 |
| `connectctl/services/oss_hygiene.py` | 648 | 551 |
| `connectctl/kafka/admin.py` | 626 | 542 |
| `connectctl/services/search/query.py` | 591 | 528 |
| `connectctl/services/connector_facts.py` | 558 | 483 |
| `connectctl/services/repo_bootstrap/service.py` | 555 | 484 |
| `connectctl/commands/connect/restart_cmd.py` | 493 | 437 |
| `connectctl/services/apply_service.py` | 464 | 395 |
| `connectctl/connect/client_base.py` | 458 | 374 |
| `connectctl/services/connect_delete_safety.py` | 447 | 379 |
| `connectctl/services/init/template_overrides.py` | 434 | 329 |

### Coupling / cohesion (`connectctl.*` internal imports)

- Modules: **605**
- Internal import edges: **1766**
- Average Ce (fan-out): **2.92**
- Median Ce: **2**
- P90 Ce: **7**
- P95 Ce: **9**
- Max Ce: **30** (`connectctl.commands.registry`)
- Max Ca (fan-in): **150** (`connectctl.exceptions`)
- Largest connected component ratio: **0.931**
- Average clustering coefficient: **0.255**
- Cohesion ratio: **0.302**

**Heuristic interpretation**

- Average Ce = **2.92** → **OK**
- P90 Ce = **7** → **OK**
- Average clustering = **0.255** → **ALERT**

**Top 15 modules by fan-out (Ce)**

- `connectctl.commands.registry`: **30**
- `connectctl.services.apply_service`: **26**
- `connectctl.commands.vars_cmd`: **20**
- `connectctl.services.diff.service`: **20**
- `connectctl.rendering.renderer_impl`: **17**
- `connectctl.services.sync_service`: **17**
- `connectctl.services.validate_connect_service`: **17**
- `connectctl.services.validate_service`: **16**
- `connectctl.services.drift.service`: **15**
- `connectctl.commands.functions_cmd`: **13**
- `connectctl.services.compare.service`: **13**
- `connectctl.services.config.hosts_service`: **13**
- `connectctl.commands.connect.patch_cmd`: **12**
- `connectctl.services.config.clusters_service`: **12**
- `connectctl.services.config.render_service`: **12**

**Top 15 modules by fan-in (Ca)**

- `connectctl.exceptions`: **150**
- `connectctl.models`: **131**
- `connectctl.logging_utils`: **92**
- `connectctl.app.context`: **59**
- `connectctl.ports`: **41**
- `connectctl.output`: **40**
- `connectctl.repo`: **31**
- `connectctl.settings_models`: **29**
- `connectctl.cli_helpers.output_args`: **28**
- `connectctl.utils`: **25**
- `connectctl.rendering.factory`: **22**
- `connectctl.commands.connect.common`: **16**
- `connectctl.template_runtime`: **15**
- `connectctl.cli_helpers.concurrency_args`: **12**
- `connectctl.rendering.runtime_vars`: **12**
<!-- BKKT_DEV_METRICS_END -->
