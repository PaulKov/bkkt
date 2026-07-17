from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Iterable

from ...output import OutputFormat, resolve_output_format, write_payload, write_text


@dataclass(frozen=True)
class DemoFileResult:
    path: str
    action: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "action": self.action}


@dataclass(frozen=True)
class DemoInitResult:
    output_dir: str
    dry_run: bool
    files: tuple[DemoFileResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": self.output_dir,
            "dry_run": self.dry_run,
            "files": [item.to_dict() for item in self.files],
            "next_commands": next_commands(self.output_dir),
        }


class DemoScaffoldService:
    """Copy the bundled local demo stack into an operator-owned directory."""

    def run_init(self, args: Any) -> int:
        output_dir = Path(str(getattr(args, "output_dir", "bkkt-demo"))).expanduser()
        result = self.init(
            output_dir=output_dir,
            force=bool(getattr(args, "force", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
        fmt = resolve_output_format(args, default=OutputFormat.text)
        if fmt == OutputFormat.text:
            write_text(format_text(result))
        else:
            write_payload(result.to_dict(), fmt=fmt)
        return 0

    def init(
        self, *, output_dir: Path, force: bool = False, dry_run: bool = False
    ) -> DemoInitResult:
        target_root = output_dir.resolve()
        source_root = resources.files("connectctl.assets.demo")
        files: list[DemoFileResult] = []

        for relative, content in _iter_asset_files(source_root):
            target = target_root / relative
            action = _plan_action(target=target, force=force, dry_run=dry_run)
            files.append(
                DemoFileResult(path=str(target.relative_to(target_root)), action=action)
            )
            if dry_run or action == "skipped":
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        return DemoInitResult(
            output_dir=str(target_root),
            dry_run=dry_run,
            files=tuple(files),
        )


def _iter_asset_files(source_root: Any) -> Iterable[tuple[Path, bytes]]:
    yield from _walk_assets(source_root, base=Path())


def _walk_assets(node: Any, *, base: Path) -> Iterable[tuple[Path, bytes]]:
    for item in sorted(node.iterdir(), key=lambda path: str(path)):
        relative = base / str(item.name)
        if item.is_dir():
            if "__pycache__" in relative.parts:
                continue
            yield from _walk_assets(item, base=relative)
            continue
        if _is_internal_asset_file(relative):
            continue
        yield relative, item.read_bytes()


def _is_internal_asset_file(relative: Path) -> bool:
    parts = set(relative.parts)
    return (
        "__pycache__" in parts
        or relative.name == "__init__.py"
        or relative.suffix == ".pyc"
    )


def _plan_action(*, target: Path, force: bool, dry_run: bool) -> str:
    if not target.exists():
        return "would_create" if dry_run else "created"
    if not force:
        return "skipped"
    return "would_overwrite" if dry_run else "overwritten"


def next_commands(output_dir: str) -> list[str]:
    return [
        f"cd {output_dir}",
        "docker compose up -d",
        "bkkt --config connectctl.yaml config clusters --env dev",
        "bkkt --config connectctl.yaml kafka topics plan --env dev --cluster local --file kafka/topics/dev/demo.yaml",
        "bkkt --config connectctl.yaml kafka topics apply --env dev --cluster local --file kafka/topics/dev/demo.yaml --dry-run",
        "bkkt --config connectctl.yaml schema subjects list --env dev --cluster local",
    ]


def format_text(result: DemoInitResult) -> str:
    lines = [
        "# BKKT demo scaffold",
        "",
        f"Output dir: `{result.output_dir}`",
        f"Mode: {'dry-run' if result.dry_run else 'write'}",
        "",
        "## Files",
    ]
    lines.extend(f"- `{item.path}`: {item.action}" for item in result.files)
    lines.extend(["", "## Next commands"])
    lines.extend(f"- `{command}`" for command in next_commands(result.output_dir))
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "DemoInitResult",
    "DemoScaffoldService",
    "format_text",
    "next_commands",
]
