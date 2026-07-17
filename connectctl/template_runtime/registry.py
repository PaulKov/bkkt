from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from ..exceptions import ConnectCtlError
from .builtins import BUILTIN_FUNCTIONS
from .models import FunctionDescriptor


class FunctionRegistry:
    """Deterministic registry for builtin and repo-local functions."""

    def __init__(self) -> None:
        self._functions: OrderedDict[str, FunctionDescriptor] = OrderedDict()

    @classmethod
    def with_builtins(cls) -> "FunctionRegistry":
        registry = cls()
        for name, (fn, description) in BUILTIN_FUNCTIONS.items():
            registry.register(
                FunctionDescriptor(
                    name=name,
                    fn=fn,
                    description=description,
                    source="builtin",
                )
            )
        return registry

    def register(self, descriptor: FunctionDescriptor) -> None:
        name = descriptor.name.strip()
        if not name:
            raise ConnectCtlError("BKKT function name must not be empty")
        if name in self._functions:
            existing = self._functions[name]
            raise ConnectCtlError(
                "BKKT function name collision: "
                f"{name!r} from {descriptor.source_path or descriptor.source} "
                f"conflicts with {existing.source_path or existing.source}. "
                "Rename the repo function; overriding builtins is not allowed."
            )
        self._functions[name] = descriptor

    def get(self, name: str) -> FunctionDescriptor:
        try:
            return self._functions[name]
        except KeyError as e:
            available = ", ".join(sorted(self._functions)) or "(none)"
            raise ConnectCtlError(
                f"Function {name!r} is not registered. Available functions: {available}"
            ) from e

    def list(self) -> list[FunctionDescriptor]:
        return [self._functions[k] for k in sorted(self._functions)]

    def names(self) -> Iterable[str]:
        return self._functions.keys()
