from __future__ import annotations

import inspect
from typing import Callable

from ..template_runtime import FunctionContext, TemplateRuntime
from .models import FunctionContractCase, FunctionContractResult, FunctionContractSuite


ContextFactory = Callable[[str | None], FunctionContext]


class FunctionContractRunner:
    """Runs repo-local function contract cases against TemplateRuntime."""

    def __init__(
        self,
        runtime: TemplateRuntime,
        *,
        context_factory: ContextFactory,
    ) -> None:
        self.runtime = runtime
        self.context_factory = context_factory

    def run(self, cases: tuple[FunctionContractCase, ...]) -> FunctionContractSuite:
        return FunctionContractSuite(tuple(self._run_one(case) for case in cases))

    def _run_one(self, case: FunctionContractCase) -> FunctionContractResult:
        try:
            descriptor = self.runtime.registry.get(case.function)
            kwargs = dict(case.kwargs or {})
            sig = inspect.signature(descriptor.fn)
            if "ctx" in sig.parameters and "ctx" not in kwargs:
                kwargs["ctx"] = self.context_factory(case.manifest)
            actual = descriptor.fn(*case.args, **kwargs)
            if str(actual) == str(case.expect):
                return FunctionContractResult(
                    case=case, status="passed", actual=str(actual)
                )
            return FunctionContractResult(
                case=case, status="failed", actual=str(actual)
            )
        except Exception as e:
            return FunctionContractResult(case=case, status="failed", error=str(e))
