from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import ValidationError
from ..models import ConnectorManifest

from .config_tests_checks import check_iceberg_table_id_columns
from .config_tests_common import ConfigTestIssue, _as_list, _ensure_str
from .config_tests_loader import _extract_rules, _load_yaml_file, _normalize_rule
from .config_tests_selectors import _applies_to


class ConfigTestRunner:
    """Runs configurable validations over rendered connector configs."""

    def __init__(self, *, enabled: bool, rules: List[Dict[str, Any]]):
        self.enabled = enabled
        self.rules = rules

    @classmethod
    def from_settings(
        cls, *, repo_root: Path, config_tests: Optional[Dict[str, Any]] = None
    ) -> "ConfigTestRunner":
        config_tests = config_tests or {}
        enabled = bool(config_tests.get("enabled", True))

        rules: List[Dict[str, Any]] = []
        has_explicit_sources = "rules" in config_tests or "files" in config_tests
        discover_convention = bool(
            config_tests.get("discover", not has_explicit_sources)
        )

        if discover_convention:
            for p in _discover_convention_files(repo_root):
                loaded = _load_yaml_file(p)
                rules.extend(_with_source(_extract_rules(loaded), p, repo_root))

        # Inline rules
        rules.extend(
            _with_source(
                _extract_rules(config_tests.get("rules", [])),
                "connectctl.yaml:config_tests.rules",
                repo_root,
            )
        )

        # External rule files
        for fp in _as_list(config_tests.get("files")):
            if not fp:
                continue
            p = Path(str(fp))
            if not p.is_absolute():
                p = repo_root / p
            loaded = _load_yaml_file(p)
            rules.extend(_with_source(_extract_rules(loaded), p, repo_root))

        norm_rules = [_normalize_rule(r) for r in rules]
        return cls(enabled=enabled, rules=norm_rules)

    def validate(
        self,
        manifest: ConnectorManifest,
        *,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[ConfigTestIssue]:
        if not self.enabled or not self.rules:
            return []

        issues: List[ConfigTestIssue] = []
        cfg = manifest.config

        for rule in self.rules:
            if not _applies_to(manifest, rule.get("applies_to") or {}, context=context):
                continue

            rid = rule["id"]
            for check in rule["checks"]:
                issues.extend(self._run_check(rid, check, cfg, manifest))

        return issues

    def _run_check(
        self,
        rid: str,
        check: Dict[str, Any],
        cfg: Dict[str, Any],
        manifest: ConnectorManifest,
    ) -> List[ConfigTestIssue]:
        ckind = str(check.get("check"))
        sev = str(check.get("severity", "error"))
        msg_prefix = check.get("message")

        def issue(
            message: str, *, key: Optional[str] = None, severity: Optional[str] = None
        ) -> ConfigTestIssue:
            return ConfigTestIssue(
                severity=severity or sev,
                rule_id=rid,
                message=message if not msg_prefix else f"{msg_prefix}: {message}",
                key=key,
            )

        # --- Generic checks ---
        if ckind == "require_keys":
            keys = [str(x) for x in _as_list(check.get("keys"))]
            missing = [k for k in keys if k not in cfg]
            return [issue(f"missing required config key {k!r}", key=k) for k in missing]

        if ckind == "require_any":
            keys = [str(x) for x in _as_list(check.get("keys"))]
            if keys and not any(k in cfg for k in keys):
                return [issue(f"expected at least one of keys: {keys}")]
            return []

        if ckind == "forbid_keys":
            keys = [str(x) for x in _as_list(check.get("keys"))]
            present = [k for k in keys if k in cfg]
            return [issue(f"forbidden key present {k!r}", key=k) for k in present]

        if ckind == "require_key_patterns":
            patterns = [str(x) for x in _as_list(check.get("patterns"))]
            issues: List[ConfigTestIssue] = []
            for pattern in patterns:
                if not any(fnmatch.fnmatchcase(key, pattern) for key in cfg):
                    issues.append(
                        issue(
                            f"missing required config key pattern {pattern!r}",
                            key=pattern,
                        )
                    )
            return issues

        if ckind == "forbid_key_patterns":
            patterns = [str(x) for x in _as_list(check.get("patterns"))]
            present = [
                key
                for key in cfg
                if any(fnmatch.fnmatchcase(key, pattern) for pattern in patterns)
            ]
            return [issue(f"forbidden key present {k!r}", key=k) for k in present]

        if ckind in {"equals", "not_equals", "match", "in", "not_in", "compare"}:
            key = check.get("key")
            if not isinstance(key, str) or not key:
                raise ValidationError(
                    f"config_tests: rule {rid!r} {ckind} requires string 'key'"
                )
            if key not in cfg:
                return [issue(f"key {key!r} is missing", key=key)]

            val = cfg.get(key)
            if not isinstance(val, str):
                return [
                    issue(
                        f"key {key!r} must be string, got {type(val).__name__}", key=key
                    )
                ]

            if ckind == "equals":
                expected = _ensure_str(
                    check.get("value"), key=f"rules[{rid}].equals.value"
                )
                if val != expected:
                    return [
                        issue(f"expected {key!r} == {expected!r}, got {val!r}", key=key)
                    ]
                return []

            if ckind == "not_equals":
                expected = _ensure_str(
                    check.get("value"), key=f"rules[{rid}].not_equals.value"
                )
                if val == expected:
                    return [issue(f"expected {key!r} != {expected!r}", key=key)]
                return []

            if ckind == "match":
                import re

                pattern = _ensure_str(
                    check.get("pattern"), key=f"rules[{rid}].match.pattern"
                )
                mode = str(check.get("mode", "fullmatch"))
                flags_val = check.get("flags", "")
                flags = 0
                if isinstance(flags_val, str) and "i" in flags_val.lower():
                    flags |= re.IGNORECASE
                try:
                    rx = re.compile(pattern, flags=flags)
                except re.error as e:
                    raise ValidationError(
                        f"config_tests: rule {rid!r} invalid regex {pattern!r}: {e}"
                    )

                ok = (
                    rx.search(val) is not None
                    if mode == "search"
                    else rx.fullmatch(val) is not None
                )
                if not ok:
                    return [
                        issue(
                            f"value for {key!r} does not match /{pattern}/ (got {val!r})",
                            key=key,
                        )
                    ]
                return []

            if ckind == "in":
                values = [str(x) for x in _as_list(check.get("values"))]
                if values and val not in values:
                    return [
                        issue(f"expected {key!r} in {values!r}, got {val!r}", key=key)
                    ]
                return []

            if ckind == "not_in":
                values = [str(x) for x in _as_list(check.get("values"))]
                if values and val in values:
                    return [
                        issue(
                            f"expected {key!r} not in {values!r}, got {val!r}", key=key
                        )
                    ]
                return []

            if ckind == "compare":
                op = str(check.get("op"))
                expected_raw = check.get("value")
                try:
                    expected_num = float(str(expected_raw))
                    actual_num = float(val)
                except Exception:
                    return [
                        issue(
                            f"cannot compare non-numeric value for {key!r}: {val!r}",
                            key=key,
                        )
                    ]

                cmp: dict[str, bool] = {
                    "gt": actual_num > expected_num,
                    "gte": actual_num >= expected_num,
                    "lt": actual_num < expected_num,
                    "lte": actual_num <= expected_num,
                }
                cmp_ok: bool | None = cmp.get(op)
                if cmp_ok is None:
                    raise ValidationError(
                        f"config_tests: rule {rid!r} compare.op must be one of gt/gte/lt/lte"
                    )
                if not cmp_ok:
                    return [
                        issue(
                            f"expected {key!r} {op} {expected_num}, got {actual_num}",
                            key=key,
                        )
                    ]
                return []

        # --- Custom checks ---
        if ckind == "iceberg_table_id_columns":
            return check_iceberg_table_id_columns(
                rid=rid, check=check, cfg=cfg, manifest=manifest
            )

        raise ValidationError(
            f"config_tests: rule {rid!r} unknown check kind {ckind!r}"
        )


def _discover_convention_files(repo_root: Path) -> List[Path]:
    """Return repo-local config test files using the default convention."""

    root = repo_root / "config_tests"
    if not root.is_dir():
        return []
    return sorted(
        [
            *root.rglob("*.yaml"),
            *root.rglob("*.yml"),
        ],
        key=lambda p: p.relative_to(repo_root).as_posix(),
    )


def _with_source(
    rules: List[Dict[str, Any]], source: Path | str, repo_root: Path
) -> List[Dict[str, Any]]:
    if isinstance(source, Path):
        try:
            label = source.relative_to(repo_root).as_posix()
        except ValueError:
            label = str(source)
    else:
        label = source

    tagged: List[Dict[str, Any]] = []
    for rule in rules:
        copy = dict(rule)
        copy.setdefault("_source", label)
        tagged.append(copy)
    return tagged
