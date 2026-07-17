from __future__ import annotations

from typing import Optional, Sequence

from ..config_models import NamingConfig
from ..models import ConnectorManifest, ConnectorType
from .naming_common import (
    NamingLintIssue,
    NamingPatterns,
    compile_pattern,
    extract_layer_from_filename,
    matches_any_allowed_pattern,
)
from .naming_rule_engine import evaluate_first_applicable_rule
from .naming_vars import build_template_vars


def lint_strict_naming(
    manifest: ConnectorManifest,
    *,
    naming: Optional[NamingConfig] = None,
    patterns: Optional[NamingPatterns] = None,
    extra_allowed_name_patterns: Sequence[str] = (),
) -> Optional[NamingLintIssue]:
    """Return a NamingLintIssue instead of raising.

    This is used to build MR comments with actionable hints (expected template,
    suggested name). If there are no issues, returns None.
    """

    patterns = patterns or NamingPatterns()
    naming = naming or NamingConfig()

    info = manifest.info
    env = info.env.value
    domain = info.domain
    system = info.system
    ctype = info.connector_type
    name = manifest.name or ""

    vars = build_template_vars(manifest)

    errors: list[str] = []

    # 1) Basic invariants
    if not name:
        errors.append("name is empty")
    else:
        parts = name.split(".")
        if len(parts) < 4:
            errors.append(
                f"name must have at least 4 dot-separated parts, got: {name!r}"
            )
        if parts and parts[0] != env:
            errors.append(f"name must start with env '{env}.' (got {parts[0]!r})")
        if len(parts) >= 2 and parts[1] != domain:
            errors.append(f"2nd segment must be domain '{domain}' (got {parts[1]!r})")
        if parts and not parts[-1].isdigit():
            errors.append(f"last segment must be numeric index (got {parts[-1]!r})")
        if ctype.value not in parts:
            errors.append(f"name must contain connector type segment '{ctype.value}'")
        if system not in parts:
            errors.append(f"name must contain system segment '{system}'")

    # 2) Enforce config["name"] consistency if present
    cfg_name = manifest.config.get("name")
    if cfg_name is not None and str(cfg_name) != name:
        errors.append(
            f"config.name must equal manifest name (config.name={cfg_name!r}, manifest.name={name!r})"
        )

    # 3) Sink layer convention from filename
    if ctype == ConnectorType.sink:
        layer = extract_layer_from_filename(info.path.name)
        if layer and name and f"sink.{layer}." not in name:
            errors.append(
                f"sink filename indicates layer '{layer}', but connector name does not contain 'sink.{layer}.'"
            )

    # 4) Rules / fallback patterns
    allowed_patterns = tuple(naming.extra_allowed_patterns) + tuple(
        extra_allowed_name_patterns
    )
    rule_id: Optional[str] = None
    expected_template: Optional[str] = None
    expected_pattern: Optional[str] = None
    suggested_name: Optional[str] = None

    if naming.enabled and naming.rules:
        rule, rule_ok, rx_str, tmpl, example = evaluate_first_applicable_rule(
            manifest, naming.rules
        )
        if rule is not None:
            rule_id = rule.id
        expected_template = tmpl
        expected_pattern = rx_str
        suggested_name = example

        if not rule_ok:
            if name and matches_any_allowed_pattern(
                name, allowed_patterns, env=env, domain=domain, system=system
            ):
                # Legacy/escape hatch: explicitly allowed pattern.
                pass
            else:
                if tmpl:
                    errors.append(
                        f"name does not match naming.template rule '{rule_id}': expected '{example}'"
                    )
                elif rx_str:
                    errors.append(
                        f"name does not match naming.regex rule '{rule_id}': expected /{rx_str}/"
                    )
                else:
                    errors.append(
                        "no naming rule matched this connector (check naming.rules applies_to in connectctl.yaml)"
                    )
    else:
        template = patterns.source if ctype == ConnectorType.source else patterns.sink
        rx = compile_pattern(template, env=env, domain=domain, system=system)
        expected_pattern = rx.pattern
        if name and not rx.match(name):
            if not matches_any_allowed_pattern(
                name, allowed_patterns, env=env, domain=domain, system=system
            ):
                errors.append(
                    f"name does not match strict pattern for {ctype.value}: expected /{rx.pattern}/"
                )

    if not errors:
        return None

    return NamingLintIssue(
        relpath=str(info.relpath),
        actual_name=name,
        connector_type=ctype.value,
        domain=domain,
        system=system,
        rule_id=rule_id,
        expected_template=expected_template,
        expected_pattern=expected_pattern,
        suggested_name=suggested_name,
        errors=tuple(errors),
        vars=vars,
    )
