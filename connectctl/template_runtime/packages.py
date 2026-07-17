from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import FunctionDescriptor


@dataclass(frozen=True)
class FunctionPackage:
    name: str
    functions: tuple[FunctionDescriptor, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "functions": [item.name for item in self.functions],
            "count": len(self.functions),
            "source_paths": sorted(
                {
                    str(item.source_path)
                    for item in self.functions
                    if item.source_path is not None
                }
            ),
        }


def group_functions(
    functions: Iterable[FunctionDescriptor],
) -> tuple[FunctionPackage, ...]:
    grouped: dict[str, list[FunctionDescriptor]] = {}
    for function in functions:
        grouped.setdefault(function.package, []).append(function)
    return tuple(
        FunctionPackage(
            name=name,
            functions=tuple(sorted(items, key=lambda item: item.name)),
        )
        for name, items in sorted(grouped.items())
    )
