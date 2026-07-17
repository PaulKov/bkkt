from __future__ import annotations

import re
from pathlib import Path

import yaml

from ..exceptions import ConnectCtlError
from .models import FunctionScaffoldPlan, ScaffoldFile, ScaffoldStatus


class FunctionScaffoldService:
    """Build and write repo-local function authoring fixtures."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    def plan(
        self,
        *,
        name: str,
        function_path: Path,
        with_fixture: bool,
        contract_path: Path | None = None,
        fixture_path: Path | None = None,
        template_test_path: Path | None = None,
        status: str = "planned",
    ) -> FunctionScaffoldPlan:
        normalized_name = _normalize_function_name(name)
        function_target = self._resolve_inside_repo(function_path)
        files = [
            ScaffoldFile(
                kind="function",
                path=function_target,
                content=_function_template(normalized_name),
            )
        ]
        if with_fixture:
            contract_target = self._resolve_inside_repo(
                contract_path
                or Path("bkkt/functions/tests") / f"{normalized_name}.yaml"
            )
            fixture_target = self._resolve_inside_repo(
                fixture_path
                or Path("bkkt/templates/fixtures") / f"{normalized_name}.json"
            )
            template_test_target = self._resolve_inside_repo(
                template_test_path
                or Path("bkkt/templates/tests") / f"{normalized_name}.yaml"
            )
            files.extend(
                [
                    ScaffoldFile(
                        kind="function_contract",
                        path=contract_target,
                        content=_function_contract_template(normalized_name),
                    ),
                    ScaffoldFile(
                        kind="render_fixture",
                        path=fixture_target,
                        content=_render_fixture_template(normalized_name),
                    ),
                    ScaffoldFile(
                        kind="template_test",
                        path=template_test_target,
                        content=_template_test_template(
                            normalized_name,
                            fixture_path=_relative(self.repo_root, fixture_target),
                        ),
                    ),
                ]
            )
        if status not in {"planned", "created"}:
            raise ValueError(f"Unsupported scaffold status: {status}")
        scaffold_status: ScaffoldStatus = (
            "planned" if status == "planned" else "created"
        )
        return FunctionScaffoldPlan(status=scaffold_status, files=tuple(files))

    def write(self, plan: FunctionScaffoldPlan, *, overwrite: bool = False) -> None:
        existing = [item.path for item in plan.files if item.path.exists()]
        if existing and not overwrite:
            paths = ", ".join(_relative(self.repo_root, path) for path in existing)
            raise ConnectCtlError(
                f"Function scaffold target already exists: {paths}. "
                "Use --overwrite explicitly to replace generated files."
            )
        for item in plan.files:
            item.path.parent.mkdir(parents=True, exist_ok=True)
            item.path.write_text(item.content, encoding="utf-8")

    def _resolve_inside_repo(self, path: Path) -> Path:
        target = path if path.is_absolute() else self.repo_root / path
        resolved = target.resolve()
        try:
            resolved.relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError("Scaffold paths must stay inside repo root") from e
        return resolved


def _normalize_function_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise ConnectCtlError("Function name must not be empty")
    return value


def _python_identifier(function_name: str) -> str:
    raw = function_name.rsplit(".", 1)[-1]
    value = re.sub(r"\W+", "_", raw).strip("_") or "custom_function"
    if value[0].isdigit():
        value = f"_{value}"
    return value


def _function_template(name: str) -> str:
    py_name = _python_identifier(name)
    return f'''from __future__ import annotations

from connectctl.plugins import FunctionContext, bkkt_function


@bkkt_function(name="{name}", description="Describe what this function does")
def {py_name}(value: str, *, ctx: FunctionContext) -> str:
    """Return a deterministic render-time value."""

    return str(value)
'''


def _function_contract_template(name: str) -> str:
    payload = {
        "cases": [
            {
                "name": f"{name} keeps a string value",
                "function": name,
                "args": ["example"],
                "expect": "example",
            }
        ]
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _render_fixture_template(name: str) -> str:
    return (
        "{\n"
        f'  "name": "bkkt.functions.{name}.fixture",\n'
        '  "config": {\n'
        f'    "function.result": "${{fn:{name}(\'example\')}}"\n'
        "  }\n"
        "}\n"
    )


def _template_test_template(name: str, *, fixture_path: str) -> str:
    payload = {
        "cases": [
            {
                "name": f"{name} render fixture",
                "manifest": fixture_path,
                "expect": {"config": {"function.result": "example"}},
            }
        ]
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)
