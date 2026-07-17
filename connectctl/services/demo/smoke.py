from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

import yaml

from ...output import OutputFormat, resolve_output_format, write_payload, write_text
from ..oss_hygiene import OssHygieneService
from .scaffold import DemoFileResult, DemoScaffoldService


REQUIRED_DEMO_FILES: tuple[str, ...] = (
    "README.md",
    "connectctl.yaml",
    "docker-compose.yml",
    "redpanda-console.yaml",
    "kafka/topics/dev/demo.yaml",
    "schemas/demo-orders-value.avsc",
)


@dataclass(frozen=True)
class DemoSmokeCheck:
    id: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class DemoSmokeResult:
    output_dir: str
    kept: bool
    files: tuple[DemoFileResult, ...]
    checks: tuple[DemoSmokeCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.status == "pass" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output_dir": self.output_dir,
            "kept": self.kept,
            "files": [item.to_dict() for item in self.files],
            "checks": [check.to_dict() for check in self.checks],
        }


class DemoSmokeService:
    """Offline demo smoke validation that does not require Docker-in-Docker."""

    def __init__(
        self,
        *,
        scaffold_service: DemoScaffoldService | None = None,
        hygiene_service: OssHygieneService | None = None,
    ) -> None:
        self._scaffold_service = scaffold_service or DemoScaffoldService()
        self._hygiene_service = hygiene_service or OssHygieneService()

    def run(self, args: Any) -> int:
        result = self.smoke(
            output_dir=(
                Path(str(args.output_dir)).expanduser()
                if getattr(args, "output_dir", None)
                else None
            ),
            keep=bool(getattr(args, "keep", False)),
        )
        fmt = resolve_output_format(args, default=OutputFormat.text)
        if fmt == OutputFormat.text:
            write_text(format_demo_smoke_text(result))
        else:
            write_payload(result.to_dict(), fmt=fmt)
        return 0 if result.ok else 1

    def smoke(
        self, *, output_dir: Path | None = None, keep: bool = False
    ) -> DemoSmokeResult:
        if output_dir is not None:
            target = output_dir.resolve()
            result = self._run_smoke(target=target, keep=True)
            return result

        with tempfile.TemporaryDirectory(prefix="bkkt-demo-smoke-") as tmp:
            result = self._run_smoke(target=Path(tmp), keep=keep)
            if keep:
                # The temporary directory would be removed by the context manager, so
                # keep mode needs an explicit user-owned output directory.
                result = _replace_keep_message(result)
            return result

    def _run_smoke(self, *, target: Path, keep: bool) -> DemoSmokeResult:
        init = self._scaffold_service.init(output_dir=target, force=True)
        checks: list[DemoSmokeCheck] = []
        checks.append(_required_files_check(target))
        checks.extend(_parse_checks(target))
        checks.append(_hygiene_check(self._hygiene_service, target))

        return DemoSmokeResult(
            output_dir=str(target),
            kept=keep,
            files=init.files,
            checks=tuple(checks),
        )


def _required_files_check(root: Path) -> DemoSmokeCheck:
    missing = [
        relative for relative in REQUIRED_DEMO_FILES if not (root / relative).is_file()
    ]
    return DemoSmokeCheck(
        id="required-demo-files",
        status="pass" if not missing else "fail",
        message=(
            "All required demo files were generated."
            if not missing
            else "Missing demo files: " + ", ".join(missing)
        ),
    )


def _parse_checks(root: Path) -> tuple[DemoSmokeCheck, ...]:
    checks: list[DemoSmokeCheck] = []
    yaml_files = (
        "connectctl.yaml",
        "docker-compose.yml",
        "redpanda-console.yaml",
        "kafka/topics/dev/demo.yaml",
    )
    for relative in yaml_files:
        checks.append(_parse_yaml_check(root / relative, relative))
    checks.append(
        _parse_json_check(
            root / "schemas/demo-orders-value.avsc", "schemas/demo-orders-value.avsc"
        )
    )
    return tuple(checks)


def _parse_yaml_check(path: Path, relative: str) -> DemoSmokeCheck:
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive error formatting
        return DemoSmokeCheck(
            id=f"parse-yaml:{relative}",
            status="fail",
            message=f"{relative} is not valid YAML: {exc}",
        )
    return DemoSmokeCheck(
        id=f"parse-yaml:{relative}",
        status="pass",
        message=f"{relative} is valid YAML.",
    )


def _parse_json_check(path: Path, relative: str) -> DemoSmokeCheck:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive error formatting
        return DemoSmokeCheck(
            id=f"parse-json:{relative}",
            status="fail",
            message=f"{relative} is not valid JSON: {exc}",
        )
    return DemoSmokeCheck(
        id=f"parse-json:{relative}",
        status="pass",
        message=f"{relative} is valid JSON.",
    )


def _hygiene_check(service: OssHygieneService, root: Path) -> DemoSmokeCheck:
    report = service.scan(root=root, globs=("**/*",))
    return DemoSmokeCheck(
        id="oss-hygiene",
        status="pass" if report.ok else "fail",
        message=(
            "Generated demo files contain no banned internal references."
            if report.ok
            else f"Generated demo files contain {len(report.findings)} hygiene finding(s)."
        ),
    )


def _replace_keep_message(result: DemoSmokeResult) -> DemoSmokeResult:
    checks = list(result.checks)
    checks.append(
        DemoSmokeCheck(
            id="keep-output-dir",
            status="fail",
            message="Use --output-dir together with --keep to preserve smoke files.",
        )
    )
    return DemoSmokeResult(
        output_dir=result.output_dir,
        kept=False,
        files=result.files,
        checks=tuple(checks),
    )


def format_demo_smoke_text(result: DemoSmokeResult) -> str:
    lines = [
        "# BKKT demo smoke",
        "",
        f"Output dir: `{result.output_dir}`",
        f"Status: {'PASS' if result.ok else 'FAIL'}",
        f"Files generated: {len(result.files)}",
        "",
        "## Checks",
    ]
    lines.extend(
        f"- {check.status.upper()} `{check.id}`: {check.message}"
        for check in result.checks
    )
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "DemoSmokeCheck",
    "DemoSmokeResult",
    "DemoSmokeService",
    "REQUIRED_DEMO_FILES",
    "format_demo_smoke_text",
]
