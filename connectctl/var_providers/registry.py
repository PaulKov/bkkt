from __future__ import annotations

from collections import OrderedDict

from ..exceptions import ConnectCtlError
from .models import VarProviderDescriptor


class VarProviderRegistry:
    """Deterministic registry for repo-local variable providers."""

    def __init__(self) -> None:
        self._providers: OrderedDict[str, VarProviderDescriptor] = OrderedDict()

    def register(self, descriptor: VarProviderDescriptor) -> None:
        name = descriptor.name.strip()
        if not name:
            raise ConnectCtlError("BKKT variable provider name must not be empty")
        if name in self._providers:
            existing = self._providers[name]
            raise ConnectCtlError(
                "BKKT variable provider name collision: "
                f"{name!r} from {descriptor.source_path} conflicts with "
                f"{existing.source_path}."
            )
        self._providers[name] = descriptor

    def get(self, name: str) -> VarProviderDescriptor:
        try:
            return self._providers[name]
        except KeyError as e:
            available = ", ".join(sorted(self._providers)) or "(none)"
            raise ConnectCtlError(
                f"Variable provider {name!r} is not registered. "
                f"Available providers: {available}"
            ) from e

    def list(self) -> list[VarProviderDescriptor]:
        return [self._providers[name] for name in sorted(self._providers)]
