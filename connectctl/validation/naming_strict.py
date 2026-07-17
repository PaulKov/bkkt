from __future__ import annotations

from typing import Optional, Sequence

from ..exceptions import ValidationError
from ..config_models import NamingConfig
from ..models import ConnectorManifest, ConnectorType
from ..naming.hints import format_deployable_name_hints
from .naming_common import (
    NamingPatterns,
    compile_pattern,
    extract_layer_from_filename,
    matches_any_allowed_pattern,
)
from .naming_rule_engine import validate_against_rules
from .naming_vars import build_template_vars


def validate_strict_naming(
    manifest: ConnectorManifest,
    *,
    naming: Optional[NamingConfig] = None,
    patterns: Optional[NamingPatterns] = None,
    extra_allowed_name_patterns: Sequence[str] = (),
) -> None:
    """Validate connector naming conventions (strict mode).

    The goal is to catch wrongly placed manifests and wrong connector names early in CI,
    before anything is deployed.
    """

    patterns = patterns or NamingPatterns()
    naming = naming or NamingConfig()

    info = manifest.info
    env = info.env.value
    domain = info.domain
    system = info.system
    ctype = info.connector_type
    name = manifest.name

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

    # 3) File-name-derived sink layer convention: <env>_sink_<layer>_... or dot-style equivalent
    if ctype == ConnectorType.sink:
        layer = extract_layer_from_filename(info.path.name)
        if layer and name and f"sink.{layer}." not in name:
            errors.append(
                f"sink filename indicates layer '{layer}', but connector name does not contain 'sink.{layer}.'"
            )

    # 4) Configurable rules (regex/template) from connectctl.yaml.
    allowed_patterns = tuple(naming.extra_allowed_patterns) + tuple(
        extra_allowed_name_patterns
    )

    if naming.enabled and naming.rules:
        _rule, rule_err = validate_against_rules(manifest, naming.rules)
        if rule_err:
            if not matches_any_allowed_pattern(
                name, allowed_patterns, env=env, domain=domain, system=system
            ):
                errors.append(rule_err)
    else:
        template = patterns.source if ctype == ConnectorType.source else patterns.sink
        rx = compile_pattern(template, env=env, domain=domain, system=system)
        if name and not rx.match(name):
            if not matches_any_allowed_pattern(
                name, allowed_patterns, env=env, domain=domain, system=system
            ):
                errors.append(
                    f"name does not match strict pattern for {ctype.value}: {rx.pattern!r} (name={name!r})"
                )

    if errors:
        rel = str(info.relpath)
        # Add user-friendly templates/examples.
        vars = build_template_vars(manifest)
        dataset = vars.get("dataset")
        ds_src = vars.get("dataset_source")

        layer_hint = (
            extract_layer_from_filename(info.path.name)
            if ctype == ConnectorType.sink
            else None
        )
        hint = format_deployable_name_hints(
            connector_type=ctype,
            domain=domain,
            system=system,
            dataset=dataset,
            layer=layer_hint,
        )

        # Add transparency about dataset inference for naming.rules.
        if dataset and ds_src:
            extra: list[str] = [
                "",
                "Dataset для naming rules:",
                f"  - dataset = {dataset!r}",
                f"  - источник = {ds_src}",
            ]
            if ds_src == "database.dbname":
                extra.append(
                    f"  - database.dbname = {manifest.config.get('database.dbname')!r}"
                )
            if ds_src == "connector_dir":
                extra.append(f"  - connector_dir = {info.connector_dir!r}")
            hint = hint + "\n" + "\n".join(extra)

        raise ValidationError(
            "Strict naming validation failed for %s:\n- %s\n\n%s"
            % (rel, "\n- ".join(errors), hint)
        )
