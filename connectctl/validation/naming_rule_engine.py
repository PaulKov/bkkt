from __future__ import annotations

import re
from typing import Dict, Optional, Sequence, Tuple

from ..config_models import NamingRule
from ..models import ConnectorManifest
from .naming_vars import build_template_vars


def rule_applies(rule: NamingRule, vars: Dict[str, Optional[str]]) -> bool:
    if not rule.applies_to:
        return True
    for k, allowed in rule.applies_to.items():
        val = vars.get(k)
        if val is None:
            return False
        if not allowed:
            continue
        if "*" in allowed:
            continue
        if str(val) not in allowed:
            return False
    return True


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template_example(template: str, vars: Dict[str, Optional[str]]) -> str:
    """Render a user-friendly suggested name from a template.

    Missing variables become `<var>`, and `{index}` becomes `<index>`
    when it cannot be inferred.
    """

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key == "index":
            v = vars.get("index")
            return str(v) if v and str(v).isdigit() else "<index>"
        v = vars.get(key)
        return str(v) if v is not None and str(v) != "" else f"<{key}>"

    return _PLACEHOLDER_RE.sub(repl, template)


def evaluate_first_applicable_rule(
    manifest: ConnectorManifest,
    rules: Sequence[NamingRule],
) -> Tuple[Optional[NamingRule], bool, Optional[str], Optional[str], Optional[str]]:
    """Pick the first applicable naming rule and evaluate it.

    Returns:
      (rule, ok, expected_pattern, expected_template, suggested_name)
    """

    name = manifest.name or ""
    vars = build_template_vars(manifest)

    applicable = [r for r in rules if rule_applies(r, vars)]
    if not applicable:
        return None, False, None, None, None

    rule = applicable[0]
    if rule.template:
        expected_template = rule.template
        expected_pattern = template_to_regex(rule.template, vars)
        suggested = render_template_example(rule.template, vars)
        ok = bool(name) and re.compile(expected_pattern).match(name) is not None
        return rule, ok, expected_pattern, expected_template, suggested

    if rule.regex:
        try:
            expected_pattern = render_regex_template(rule.regex, vars)
        except Exception:
            expected_pattern = rule.regex
        ok = bool(name) and re.compile(expected_pattern).match(name) is not None
        return rule, ok, expected_pattern, None, None

    return rule, False, None, None, None


def template_to_regex(template: str, vars: Dict[str, Optional[str]]) -> str:
    """Convert a template like '{env}.{domain}.{dataset}.{type}.{system}.{index}' to a regex.

    Rules:
      - literal text is regex-escaped
      - {index} becomes '\\d+'
      - known vars become escaped exact matches
      - missing vars become '[^.]+' (any non-dot segment)
    """

    out: list[str] = ["^"]
    pos = 0
    for m in _PLACEHOLDER_RE.finditer(template):
        out.append(re.escape(template[pos : m.start()]))
        key = m.group(1)
        if key == "index":
            out.append(r"\d+")
        else:
            val = vars.get(key)
            if val is None:
                out.append(r"[^.]+")
            else:
                out.append(re.escape(str(val)))
        pos = m.end()

    out.append(re.escape(template[pos:]))
    out.append("$")
    rx = "".join(out)

    # Allow optional extra dot-segments before the final index segment.
    needle = r"\.\d+$"
    if rx.endswith(needle):
        rx = rx[: -len(needle)] + r"(?:\.[^.]+)*" + needle
    return rx


def render_regex_template(regex_tpl: str, vars: Dict[str, Optional[str]]) -> str:
    """Render a regex template with placeholders using escaped known vars."""

    fmt: Dict[str, str] = {}
    for k, v in vars.items():
        if v is None:
            continue
        fmt[k] = re.escape(str(v))
    fmt.setdefault("index", r"\d+")
    return regex_tpl.format(**fmt)


def validate_against_rules(
    manifest: ConnectorManifest,
    rules: Sequence[NamingRule],
) -> Tuple[Optional[NamingRule], Optional[str]]:
    """Validate connector name against the first applicable naming rule.

    Returns (rule, error_message) where error_message is None if ok.
    """

    name = manifest.name
    vars = build_template_vars(manifest)

    applicable = [r for r in rules if rule_applies(r, vars)]
    if not applicable:
        return (
            None,
            "no naming rule matched this connector (check naming.rules applies_to in connectctl.yaml)",
        )

    rule = applicable[0]

    if rule.template:
        rx_str = template_to_regex(rule.template, vars)
        rx = re.compile(rx_str)
        if not rx.match(name):
            suggested = render_template_example(rule.template, vars)
            return rule, (
                f"name does not match naming.template rule '{rule.id}': expected /{rx_str}/ (name={name!r}). "
                f"Suggested: {suggested!r}"
            )
        return rule, None

    if rule.regex:
        try:
            rx_str = render_regex_template(rule.regex, vars)
        except KeyError as e:
            return (
                rule,
                f"invalid naming.regex rule '{rule.id}': missing placeholder {e}",
            )
        rx = re.compile(rx_str)
        if not rx.match(name):
            return rule, (
                f"name does not match naming.regex rule '{rule.id}': expected /{rx_str}/ (name={name!r})"
            )
        return rule, None

    return (
        rule,
        f"invalid naming rule '{rule.id}': must define either template or regex",
    )
