from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from ..exceptions import ValidationError

from .config_tests_common import _ALLOWED_SEVERITIES


def _load_yaml_file(path: Path) -> Any:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValidationError(f"config_tests: file not found: {path}")
    except Exception as e:
        raise ValidationError(f"config_tests: failed to read YAML file {path}: {e}")
    return data


def _extract_rules(obj: Any) -> List[Dict[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, dict):
        rules = obj.get("rules")
        if rules is None:
            # allow {id:..., ...} single rule
            if "id" in obj:
                return [obj]
            return []
        if isinstance(rules, list):
            return list(rules)
        raise ValidationError("config_tests: 'rules' must be a list")
    if isinstance(obj, list):
        return list(obj)
    raise ValidationError("config_tests: YAML root must be a dict or a list")


def _normalize_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rule, dict):
        raise ValidationError("config_tests: each rule must be a mapping")
    rid = rule.get("id")
    if not rid or not isinstance(rid, str):
        raise ValidationError("config_tests: each rule must have string 'id'")

    severity = str(rule.get("severity", "error")).lower()
    if severity not in _ALLOWED_SEVERITIES:
        raise ValidationError(
            f"config_tests: rule {rid!r} has invalid severity {severity!r} (allowed: {sorted(_ALLOWED_SEVERITIES)})"
        )

    applies_to = rule.get("applies_to") or {}
    if applies_to and not isinstance(applies_to, dict):
        raise ValidationError(
            f"config_tests: rule {rid!r} applies_to must be a mapping"
        )

    checks = rule.get("checks")
    if checks is None:
        # allow single-check shorthand
        if "check" in rule:
            checks = [
                {
                    k: v
                    for k, v in rule.items()
                    if k
                    not in {
                        "id",
                        "description",
                        "severity",
                        "applies_to",
                    }
                }
            ]
        else:
            raise ValidationError(
                f"config_tests: rule {rid!r} must define 'checks' (list) or 'check' (single)"
            )

    if not isinstance(checks, list) or not checks:
        raise ValidationError(
            f"config_tests: rule {rid!r} checks must be a non-empty list"
        )

    norm_checks: List[Dict[str, Any]] = []
    for c in checks:
        if not isinstance(c, dict):
            raise ValidationError(
                f"config_tests: rule {rid!r} each check must be a mapping"
            )
        ckind = c.get("check")
        if not ckind:
            raise ValidationError(
                f"config_tests: rule {rid!r} each check must define 'check'"
            )
        csev = str(c.get("severity", severity)).lower()
        if csev not in _ALLOWED_SEVERITIES:
            raise ValidationError(
                f"config_tests: rule {rid!r} check has invalid severity {csev!r} (allowed: {sorted(_ALLOWED_SEVERITIES)})"
            )
        norm = dict(c)
        norm["severity"] = csev
        norm_checks.append(norm)

    return {
        "id": rid,
        "description": rule.get("description"),
        "severity": severity,
        "_source": rule.get("_source"),
        "applies_to": applies_to,
        "checks": norm_checks,
    }
