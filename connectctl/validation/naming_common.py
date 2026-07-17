from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple


_SINK_FILENAME_RE = re.compile(
    r"^(dev|stage|prod)_sink_(?P<layer>[^_]+)_.+\.json$", re.IGNORECASE
)
_SINK_FILENAME_DOT_RE = re.compile(
    r"^(dev|stage|prod)\..*?\.sink\.(?P<layer>[^.]+)\..+\.json$", re.IGNORECASE
)


@dataclass(frozen=True)
class NamingPatterns:
    """Regex templates for connector names.

    Placeholders:
      - {env}    -> env name (dev|stage|prod)
      - {domain} -> domain dir name
      - {system} -> system dir name (postgres/mariadb/iceberg/...)

    The templates are treated as python regex.
    """

    source: str = r"^{env}\.{domain}\.[^.]+\.source\.{system}\.\d+$"
    sink: str = r"^{env}\.{domain}\.[^.]+\.sink\.[^.]+\.{system}\.\d+$"


@dataclass(frozen=True)
class NamingLintIssue:
    """A structured naming lint issue.

    This is meant for MR comments and CI logs (human-readable), while
    strict validation is meant to hard-fail the pipeline.

    For template-based naming rules we try to compute a suggested name.
    For regex-based rules we provide a rendered regex pattern.
    """

    relpath: str
    actual_name: str
    connector_type: str
    domain: str
    system: str
    rule_id: Optional[str] = None
    expected_template: Optional[str] = None
    expected_pattern: Optional[str] = None
    suggested_name: Optional[str] = None
    errors: Tuple[str, ...] = ()
    vars: Dict[str, Optional[str]] = field(default_factory=dict)


def compile_pattern(
    template: str, *, env: str, domain: str, system: str
) -> re.Pattern[str]:
    """Compile a naming regex template using escaped env/domain/system."""

    def esc(x: str) -> str:
        return re.escape(x)

    pattern = template.format(env=esc(env), domain=esc(domain), system=esc(system))
    return re.compile(pattern)


def matches_any_allowed_pattern(
    name: str,
    patterns: Sequence[str],
    *,
    env: str,
    domain: str,
    system: str,
) -> bool:
    """Return True if name matches any of allowed naming pattern templates."""
    for tpl in patterns:
        try:
            if compile_pattern(tpl, env=env, domain=domain, system=system).match(name):
                return True
        except Exception:
            continue
    return False


def extract_layer_from_filename(filename: str) -> Optional[str]:
    """Best-effort extraction of sink layer from a manifest filename."""
    m = _SINK_FILENAME_RE.match(filename) or _SINK_FILENAME_DOT_RE.match(filename)
    if not m:
        return None
    return m.group("layer")
