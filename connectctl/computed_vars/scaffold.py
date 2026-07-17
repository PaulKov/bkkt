from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..exceptions import ConnectCtlError


@dataclass(frozen=True)
class ComputedVarScaffold:
    """Creates a repo-local computed variable plus its contract-test skeleton."""

    name: str
    function_path: Path
    test_path: Path

    def write(self, *, repo_root: Path) -> None:
        function_target = _safe_repo_path(repo_root, self.function_path, "--path")
        test_target = _safe_repo_path(repo_root, self.test_path, "--test-path")
        _write_new_file(function_target, self.function_template())
        _write_new_file(test_target, self.test_template())

    def preview_payload(self, *, repo_root: Path) -> dict[str, str]:
        function_target = _safe_repo_path(repo_root, self.function_path, "--path")
        test_target = _safe_repo_path(repo_root, self.test_path, "--test-path")
        return {
            "name": self.name,
            "function_path": str(function_target),
            "test_path": str(test_target),
            "function_template": self.function_template(),
            "test_template": self.test_template(),
        }

    def function_template(self) -> str:
        fn_name = _python_identifier(self.name)
        return f'''from __future__ import annotations

from connectctl.plugins import ComputedVarContext, bkkt_computed_var


@bkkt_computed_var(name="{self.name}", description="TODO")
def {fn_name}(*, ctx: ComputedVarContext) -> str:
    """Return a deterministic computed variable value."""

    return ""
'''

    def test_template(self) -> str:
        return f"""cases:
  - name: {self.name} default case
    variable: {self.name}
    expect: ""
"""


def default_test_path(name: str) -> Path:
    return Path("bkkt/computed_vars/tests") / f"{_file_stem(name)}.yaml"


def _safe_repo_path(repo_root: Path, raw_path: Path, option: str) -> Path:
    target = raw_path if raw_path.is_absolute() else repo_root / raw_path
    target = target.resolve()
    try:
        target.relative_to(repo_root.resolve())
    except ValueError as e:
        raise ConnectCtlError(f"{option} must stay inside repo root") from e
    return target


def _write_new_file(path: Path, content: str) -> None:
    if path.exists():
        raise ConnectCtlError(f"Scaffold target already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _python_identifier(name: str) -> str:
    candidate = re.sub(r"\W+", "_", name).strip("_").lower()
    if not candidate:
        return "computed_value"
    if candidate[0].isdigit():
        return f"computed_{candidate}"
    return candidate


def _file_stem(name: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_.-").lower()
    return candidate or "computed_var"
