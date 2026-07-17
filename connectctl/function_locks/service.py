from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import ConnectCtlError
from ..settings_models import Settings
from ..template_impact import TemplateImpactService
from .fingerprint import FunctionFingerprinter
from .lockfile import FunctionLockfile, LOCKFILE_VERSION
from .models import (
    FunctionLockChange,
    FunctionLockCheckResult,
    FunctionLockDocument,
    FunctionLockIssue,
    LockedFunction,
    LockedPackage,
)


class FunctionLockService:
    """High-level function lock, diff, and impact gate operations."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo_root = settings.repo.root.resolve()

    def build_document(self) -> FunctionLockDocument:
        from ..template_runtime import TemplateRuntime

        runtime = TemplateRuntime.from_settings(self.settings)
        fingerprinter = FunctionFingerprinter(self.repo_root)
        functions = tuple(
            sorted(
                (
                    fingerprinter.lock_function(item)
                    for item in runtime.list_functions()
                    if item.source == "repo"
                ),
                key=lambda item: item.name,
            )
        )
        packages: dict[str, list[LockedFunction]] = {}
        for function in functions:
            packages.setdefault(function.package, []).append(function)
        return FunctionLockDocument(
            version=LOCKFILE_VERSION,
            packages=tuple(
                LockedPackage(name=name, functions=tuple(items))
                for name, items in sorted(packages.items())
            ),
        )

    def build_lock_payload(self) -> dict[str, Any]:
        return self.build_document().to_payload()

    def write_lock(self, path: Path | None = None) -> Path:
        return FunctionLockfile(self.repo_root, path=path).write(self.build_document())

    def diff(self, lock_path: Path | None = None) -> FunctionLockCheckResult:
        expected = FunctionLockfile(self.repo_root, path=lock_path).load()
        current = self.build_document()
        changes = self._diff_documents(expected=expected, current=current)
        return FunctionLockCheckResult(
            status="failed" if changes else "ok",
            changes=changes,
        )

    def check_lock(self, lock_path: Path | None = None) -> FunctionLockCheckResult:
        diff = self.diff(lock_path=lock_path)
        issues = tuple(self._issue_for_change(change) for change in diff.changes)
        return FunctionLockCheckResult(
            status="failed" if issues else "ok",
            changes=diff.changes,
            issues=issues,
        )

    def gate(
        self,
        lock_path: Path | None = None,
        impact_artifact: Path | None = None,
    ) -> FunctionLockCheckResult:
        diff = self.diff(lock_path=lock_path)
        acknowledged = self._acknowledged_functions(impact_artifact)
        gate_issues: list[FunctionLockIssue] = []
        impact = TemplateImpactService(self.settings)
        for change in diff.changes:
            if change.function in acknowledged:
                continue
            gate_issues.append(self._issue_for_change(change))
            if change.kind != "changed":
                continue
            for usage in impact.inventory.used_by_function(change.function):
                gate_issues.append(
                    FunctionLockIssue(
                        code="missing_function_impact_artifact",
                        function=change.function,
                        manifest=usage.manifest,
                        config_key=usage.config_key,
                        message=(
                            f"Function {change.function!r} changed and is used by "
                            f"{usage.manifest}:{usage.config_key}. Provide an impact "
                            "artifact with `--impact-artifact`."
                        ),
                    )
                )
        return FunctionLockCheckResult(
            status="failed" if gate_issues else "ok",
            changes=diff.changes,
            issues=tuple(sorted(gate_issues)),
        )

    @staticmethod
    def _diff_documents(
        *,
        expected: FunctionLockDocument,
        current: FunctionLockDocument,
    ) -> tuple[FunctionLockChange, ...]:
        before = expected.functions_by_name
        after = current.functions_by_name
        changes: list[FunctionLockChange] = []
        for name in sorted(set(before) | set(after)):
            before_item = before.get(name)
            after_item = after.get(name)
            if before_item is None and after_item is not None:
                changes.append(
                    FunctionLockChange(
                        kind="added",
                        function=name,
                        package=after_item.package,
                        after_fingerprint=after_item.fingerprint,
                        after_source_path=after_item.source_path,
                    )
                )
            elif before_item is not None and after_item is None:
                changes.append(
                    FunctionLockChange(
                        kind="removed",
                        function=name,
                        package=before_item.package,
                        before_fingerprint=before_item.fingerprint,
                        before_source_path=before_item.source_path,
                    )
                )
            elif (
                before_item is not None
                and after_item is not None
                and before_item.fingerprint != after_item.fingerprint
            ):
                changes.append(
                    FunctionLockChange(
                        kind="changed",
                        function=name,
                        package=after_item.package,
                        before_fingerprint=before_item.fingerprint,
                        after_fingerprint=after_item.fingerprint,
                        before_source_path=before_item.source_path,
                        after_source_path=after_item.source_path,
                    )
                )
        return tuple(sorted(changes))

    @staticmethod
    def _issue_for_change(change: FunctionLockChange) -> FunctionLockIssue:
        code = {
            "added": "function_added",
            "removed": "function_removed",
            "changed": "function_fingerprint_changed",
        }[change.kind]
        return FunctionLockIssue(
            code=code,
            function=change.function,
            message=(
                f"Function {change.function!r} is {change.kind}; "
                "update `bkkt/functions.lock.yaml` intentionally."
            ),
        )

    def _acknowledged_functions(self, impact_artifact: Path | None) -> set[str]:
        if impact_artifact is None:
            return set()
        path = impact_artifact
        if not path.is_absolute():
            path = self.repo_root / path
        try:
            path.resolve().relative_to(self.repo_root)
        except ValueError as e:
            raise ConnectCtlError(
                "Impact artifact path must stay inside repo root"
            ) from e
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConnectCtlError("Impact artifact must be a YAML/JSON mapping")
        names: set[str] = set()
        for key in ("function", "name"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                names.add(value.strip())
        functions = raw.get("functions")
        if isinstance(functions, list):
            names.update(str(item).strip() for item in functions if str(item).strip())
        return names
