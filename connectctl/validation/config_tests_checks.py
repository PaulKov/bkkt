from __future__ import annotations

from typing import Any, Dict, List

from ..exceptions import ValidationError
from ..models import ConnectorManifest

from .config_tests_common import ConfigTestIssue, _ALLOWED_SEVERITIES


def check_iceberg_table_id_columns(
    *,
    rid: str,
    check: Dict[str, Any],
    cfg: Dict[str, Any],
    manifest: ConnectorManifest,
) -> List[ConfigTestIssue]:
    """Validate per-table id-columns for Iceberg sinks.

    For each topic in `topics`, infers table id (e.g. db.table -> db__table) and checks:
      - if iceberg.table.<db_name>.<table>.id-columns exists -> OK
      - else if iceberg.tables.default-id-columns exists -> WARNING (default used)
      - else -> ERROR
    """

    sev_missing = str(check.get("severity", "error"))
    sev_default_used = str(check.get("default_used_severity", "warning")).lower()
    if sev_default_used not in _ALLOWED_SEVERITIES:
        raise ValidationError(
            f"config_tests: rule {rid!r} iceberg_table_id_columns default_used_severity must be 'warning' or 'error'"
        )

    topics_key = str(check.get("topics_key", "topics"))
    topics_regex_key = str(check.get("topics_regex_key", "topics.regex"))
    db_key = str(check.get("db_name_key", "transforms.setTableName.db.name"))
    default_key = str(
        check.get("default_id_columns_key", "iceberg.tables.default-id-columns")
    )
    tmpl = str(
        check.get(
            "per_table_id_columns_template", "iceberg.table.{db}.{table}.id-columns"
        )
    )

    issues: List[ConfigTestIssue] = []

    db_name = cfg.get(db_key)
    if not isinstance(db_name, str) or not db_name:
        issues.append(
            ConfigTestIssue(
                severity=sev_missing,
                rule_id=rid,
                message=f"missing/empty {db_key!r} (cannot validate per-table id-columns)",
                key=db_key,
            )
        )
        return issues

    topics_val = cfg.get(topics_key)
    topics_regex_val = cfg.get(topics_regex_key)
    if isinstance(topics_val, str) and topics_val.strip():
        topics = [t.strip() for t in topics_val.split(",") if t.strip()]
    elif isinstance(topics_regex_val, str) and topics_regex_val.strip():
        # Cannot enumerate tables from regex reliably.
        if default_key not in cfg:
            issues.append(
                ConfigTestIssue(
                    severity=sev_missing,
                    rule_id=rid,
                    message=(
                        f"{topics_key!r} is not set, {topics_regex_key!r} is used; cannot infer per-table keys, "
                        f"and {default_key!r} is missing"
                    ),
                    key=default_key,
                )
            )
        else:
            issues.append(
                ConfigTestIssue(
                    severity=sev_default_used,
                    rule_id=rid,
                    message=(
                        f"{topics_regex_key!r} is used; cannot infer per-table id-columns keys. "
                        f"Connector will rely on default {default_key!r}"
                    ),
                    key=default_key,
                )
            )
        return issues
    else:
        issues.append(
            ConfigTestIssue(
                severity=sev_missing,
                rule_id=rid,
                message=f"missing {topics_key!r} (cannot infer tables)",
                key=topics_key,
            )
        )
        return issues

    has_default = (
        default_key in cfg
        and isinstance(cfg.get(default_key), str)
        and str(cfg.get(default_key)).strip() != ""
    )

    inferred_tables: List[str] = []
    for t in topics:
        parts = t.split(".")
        if len(parts) < 2:
            continue

        tail = None
        if parts[0] == "cdc" and len(parts) >= 6:
            tail = parts[4:]
        else:
            tail = parts[-3:] if len(parts) >= 3 else parts[-2:]

        if tail and tail[-1].isdigit():
            tail = tail[:-1]

        if not tail:
            continue

        table_id = "__".join(tail)
        inferred_tables.append(table_id)

    if not inferred_tables:
        issues.append(
            ConfigTestIssue(
                severity=sev_missing,
                rule_id=rid,
                message=f"failed to infer tables from {topics_key!r}",
                key=topics_key,
            )
        )
        return issues

    for table_id in sorted(set(inferred_tables)):
        per_key = tmpl.format(db=db_name, table=table_id)
        if (
            per_key in cfg
            and isinstance(cfg.get(per_key), str)
            and str(cfg.get(per_key)).strip() != ""
        ):
            continue

        if has_default:
            issues.append(
                ConfigTestIssue(
                    severity=sev_default_used,
                    rule_id=rid,
                    message=(
                        f"table {table_id!r} does not define {per_key!r}; "
                        f"default {default_key!r} will be used"
                    ),
                    key=per_key,
                )
            )
        else:
            issues.append(
                ConfigTestIssue(
                    severity=sev_missing,
                    rule_id=rid,
                    message=(
                        f"table {table_id!r} is missing id-columns: neither {per_key!r} nor default {default_key!r} is set"
                    ),
                    key=per_key,
                )
            )

    return issues
