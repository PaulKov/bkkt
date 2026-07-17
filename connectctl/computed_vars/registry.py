from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from ..exceptions import ConnectCtlError
from .models import ComputedVarDescriptor


class ComputedVarRegistry:
    """Deterministic registry for repo-local computed variables."""

    def __init__(self) -> None:
        self._items: OrderedDict[str, ComputedVarDescriptor] = OrderedDict()

    def register(self, descriptor: ComputedVarDescriptor) -> None:
        name = descriptor.name.strip()
        if not name:
            raise ConnectCtlError("BKKT computed var name must not be empty")
        if name in self._items:
            existing = self._items[name]
            raise ConnectCtlError(
                "BKKT computed var name collision: "
                f"{name!r} from {descriptor.source_path or descriptor.source} "
                f"conflicts with {existing.source_path or existing.source}."
            )
        self._items[name] = descriptor

    def get(self, name: str) -> ComputedVarDescriptor:
        try:
            return self._items[name]
        except KeyError as e:
            available = ", ".join(sorted(self._items)) or "(none)"
            raise ConnectCtlError(
                f"Computed variable {name!r} is not registered. "
                f"Available computed variables: {available}"
            ) from e

    def list(self) -> list[ComputedVarDescriptor]:
        return [self._items[key] for key in sorted(self._items)]

    def names(self) -> Iterable[str]:
        return self._items.keys()
