from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


UsageKind = Literal["placeholder", "fn_arg", "renders", "provides", "depends_on"]


@dataclass(frozen=True, order=True)
class TemplateUsage:
    """One repo-wide function/variable usage in a connector manifest."""

    manifest: str
    config_key: str
    kind: UsageKind
    via_function: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        return {
            "manifest": self.manifest,
            "config_key": self.config_key,
            "kind": self.kind,
            "via_function": self.via_function,
        }


@dataclass(frozen=True)
class TemplateInventory:
    """Pre-render inventory of placeholders found in connector configs."""

    variable_usages: dict[str, tuple[TemplateUsage, ...]]
    function_usages: dict[str, tuple[TemplateUsage, ...]]

    def used_by_variable(self, name: str) -> tuple[TemplateUsage, ...]:
        return self.variable_usages.get(name, ())

    def used_by_function(self, name: str) -> tuple[TemplateUsage, ...]:
        return self.function_usages.get(name, ())

    @property
    def used_variables(self) -> set[str]:
        return set(self.variable_usages)

    @property
    def used_functions(self) -> set[str]:
        return set(self.function_usages)
