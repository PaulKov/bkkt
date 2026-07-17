"""Repository-wide OSS hygiene and secret/internal-reference scanning.

Public alpha releases must stay free of credentials, private keys, and
organization-specific infrastructure references. This module powers:

* ``bkkt oss hygiene`` — public-asset or repository-wide scan
* ``bkkt oss readiness`` — required-file checklist plus hygiene gates

Hard-deny rules cover credential filenames, cloud/API token shapes, private
keys, and known internal hosts/registries/buckets/account IDs. Synthetic
RFC1918 fixtures under ``tests/`` are intentionally allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable, Pattern, Sequence

from ..output import OutputFormat, resolve_output_format, write_payload, write_text


DEFAULT_PUBLIC_ASSET_GLOBS: tuple[str, ...] = (
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/*.md",
    "docs/**/*.md",
    "connectctl/assets/repo_defaults/connectctl.yaml",
    "connectctl/assets/repo_defaults/**/*.json",
    "connectctl/assets/demo/**/*",
)


REQUIRED_OSS_FILES: tuple[str, ...] = (
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "connectctl/assets/demo/README.md",
    "connectctl/assets/demo/connectctl.yaml",
    "connectctl/assets/demo/docker-compose.yml",
    "connectctl/assets/demo/schemas/demo-orders-value.avsc",
)


FORBIDDEN_FILENAMES: frozenset[str] = frozenset(
    {
        "prod-aws-credentials.toml",
        "*.credentials.toml",
        ".env",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)


REPO_WIDE_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".cache",
        "__pycache__",
        "dist",
        "build",
        "htmlcov",
        "node_modules",
        ".superpowers",
    }
)


SCANNABLE_SUFFIXES: frozenset[str] = frozenset(
    {
        "",
        ".md",
        ".py",
        ".toml",
        ".yml",
        ".yaml",
        ".json",
        ".txt",
        ".ini",
        ".cfg",
        ".sh",
        ".avsc",
        ".env",
        ".example",
        ".lock",
    }
)


# Paths that intentionally embed synthetic secret/internal samples for tests.
SYNTHETIC_ALLOWLIST_PATHS: frozenset[str] = frozenset(
    {
        "tests/test_oss_hygiene.py",
        ".gitleaks.toml",
        "connectctl/services/oss_hygiene.py",
    }
)


@dataclass(frozen=True)
class OssHygieneRule:
    id: str
    description: str
    pattern: Pattern[str]
    # When True, rule applies in repository-wide scans (hard deny).
    hard_deny: bool = True
    # Relative path prefixes where this rule is ignored (synthetic fixtures).
    allow_path_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OssHygieneFinding:
    path: str
    rule_id: str
    line: int
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rule_id": self.rule_id,
            "line": self.line,
            "excerpt": self.excerpt,
        }


@dataclass(frozen=True)
class OssHygieneReport:
    root: str
    files_scanned: int
    findings: tuple[OssHygieneFinding, ...]
    skipped_files: tuple[str, ...] = ()
    scope: str = "public"

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "scope": self.scope,
            "files_scanned": self.files_scanned,
            "finding_count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
            "skipped_files": list(self.skipped_files),
        }


@dataclass(frozen=True)
class OssReadinessCheck:
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
class OssReadinessReport:
    root: str
    checks: tuple[OssReadinessCheck, ...]
    hygiene: OssHygieneReport

    @property
    def ok(self) -> bool:
        return all(check.status == "pass" for check in self.checks) and self.hygiene.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "checks": [check.to_dict() for check in self.checks],
            "hygiene": self.hygiene.to_dict(),
        }


# Soft hygiene for public docs/assets (RFC1918 still flagged here).
PUBLIC_RULES: tuple[OssHygieneRule, ...] = (
    OssHygieneRule(
        id="internal_ip",
        description="Internal RFC1918 host reference",
        pattern=re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        hard_deny=False,
    ),
    OssHygieneRule(
        id="internal_cluster_names",
        description="Company-specific Kafka Connect cluster alias",
        pattern=re.compile(r"\b(?:corp|internal)[_-]{1,2}(?:main|source|external)\b"),
    ),
    OssHygieneRule(
        id="internal_registry",
        description="Internal container registry reference",
        pattern=re.compile(r"(?:registry|artifactory)\.internal\b"),
    ),
    OssHygieneRule(
        id="internal_gitlab",
        description="Internal GitLab host reference",
        pattern=re.compile(r"git(?:lab)?\.internal\b"),
    ),
    OssHygieneRule(
        id="internal_bucket",
        description="Internal S3 bucket reference",
        pattern=re.compile(r"(?:prod|stage)-internal-data"),
    ),
    OssHygieneRule(
        id="internal_msk",
        description="Internal MSK/bootstrap host reference",
        pattern=re.compile(r"(?:prod|stage)-msk\.internal"),
    ),
)


# Hard-deny rules for repository-wide alpha gates.
HARD_DENY_RULES: tuple[OssHygieneRule, ...] = (
    OssHygieneRule(
        id="aws_access_key_id",
        description="AWS access key id pattern",
        pattern=re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    OssHygieneRule(
        id="github_token",
        description="GitHub personal access token pattern",
        pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ),
    OssHygieneRule(
        id="gitlab_token",
        description="GitLab personal access token pattern",
        pattern=re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b"),
    ),
    OssHygieneRule(
        id="pypi_token",
        description="PyPI API token pattern",
        pattern=re.compile(r"\bpypi-[A-Za-z0-9_\-]{20,}\b"),
    ),
    OssHygieneRule(
        id="private_key",
        description="PEM/OpenSSH private key block",
        pattern=re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    ),
    OssHygieneRule(
        id="internal_gitlab_rip",
        description="Private GitLab host reference",
        pattern=re.compile(r"\bgitlab\.rip\b"),
    ),
    OssHygieneRule(
        id="internal_artifactory",
        description="Private Artifactory/registry host",
        pattern=re.compile(
            r"\b(?:artifactory|registry)\.(?:rip|internal|corp)\b",
            re.IGNORECASE,
        ),
    ),
    OssHygieneRule(
        id="company_domain_marker",
        description="Company-specific domain marker blocked in alpha exports",
        # Constructed to avoid self-matching this source file when allowlist is off.
        pattern=re.compile("1" + "win"),
    ),
    OssHygieneRule(
        id="aws_account_id",
        description="Hard-coded 12-digit AWS account id",
        pattern=re.compile(r"\barn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:"),
    ),
    OssHygieneRule(
        id="internal_bucket_dp_prod",
        description="Internal production data bucket",
        pattern=re.compile(r"\bs3://dp-prod-data\b"),
    ),
)


# Backward-compatible alias used by older imports/tests.
DEFAULT_RULES: tuple[OssHygieneRule, ...] = PUBLIC_RULES


class OssHygieneService:
    """Scan public assets or the full repository before OSS release."""

    def __init__(
        self,
        *,
        rules: Sequence[OssHygieneRule] = PUBLIC_RULES,
        hard_deny_rules: Sequence[OssHygieneRule] = HARD_DENY_RULES,
        public_asset_globs: Sequence[str] = DEFAULT_PUBLIC_ASSET_GLOBS,
        required_files: Sequence[str] = REQUIRED_OSS_FILES,
        forbidden_filenames: Sequence[str] = tuple(sorted(FORBIDDEN_FILENAMES)),
    ) -> None:
        self._rules = tuple(rules)
        self._hard_deny_rules = tuple(hard_deny_rules)
        self._public_asset_globs = tuple(public_asset_globs)
        self._required_files = tuple(required_files)
        self._forbidden_filenames = tuple(forbidden_filenames)

    def scan(
        self, *, root: Path, globs: Sequence[str] | None = None
    ) -> OssHygieneReport:
        """Scan public/docs assets with soft + hard hygiene rules."""
        root = root.resolve()
        files = _discover_files(root=root, globs=globs or self._public_asset_globs)
        return self._scan_files(
            root=root,
            files=files,
            rules=self._rules + self._hard_deny_rules,
            scope="public",
            check_filenames=True,
        )

    def scan_repository(self, *, root: Path) -> OssHygieneReport:
        """Scan the full repository with hard-deny secret/internal rules."""
        root = root.resolve()
        files = _discover_repository_files(root=root)
        return self._scan_files(
            root=root,
            files=files,
            rules=self._hard_deny_rules,
            scope="repository",
            check_filenames=True,
        )

    def readiness(self, *, root: Path) -> OssReadinessReport:
        root = root.resolve()
        checks: list[OssReadinessCheck] = []

        missing = [
            relative
            for relative in self._required_files
            if not (root / relative).is_file()
        ]
        checks.append(
            OssReadinessCheck(
                id="required-files",
                status="pass" if not missing else "fail",
                message=(
                    "All required OSS governance/demo files are present."
                    if not missing
                    else "Missing required files: " + ", ".join(missing)
                ),
            )
        )

        empty = [
            relative
            for relative in self._required_files
            if (root / relative).is_file()
            and not (root / relative).read_text(encoding="utf-8").strip()
        ]
        checks.append(
            OssReadinessCheck(
                id="non-empty-files",
                status="pass" if not empty else "fail",
                message=(
                    "Required OSS files are non-empty."
                    if not empty
                    else "Empty required files: " + ", ".join(empty)
                ),
            )
        )

        public_hygiene = self.scan(root=root)
        checks.append(
            OssReadinessCheck(
                id="oss-hygiene",
                status="pass" if public_hygiene.ok else "fail",
                message=(
                    "Public assets contain no banned internal references."
                    if public_hygiene.ok
                    else f"Public assets contain {len(public_hygiene.findings)} finding(s)."
                ),
            )
        )

        repo_hygiene = self.scan_repository(root=root)
        checks.append(
            OssReadinessCheck(
                id="repository-hygiene",
                status="pass" if repo_hygiene.ok else "fail",
                message=(
                    "Repository contains no credential/secret/internal hard-deny hits."
                    if repo_hygiene.ok
                    else f"Repository scan found {len(repo_hygiene.findings)} finding(s)."
                ),
            )
        )

        # Surface the stricter report for readiness consumers.
        hygiene = repo_hygiene if not repo_hygiene.ok else public_hygiene
        return OssReadinessReport(
            root=str(root),
            checks=tuple(checks),
            hygiene=hygiene,
        )

    def run_hygiene(self, args: Any) -> int:
        root = _arg_root(args)
        scope = str(getattr(args, "scope", "public") or "public")
        if scope == "repository":
            report = self.scan_repository(root=root)
        else:
            report = self.scan(root=root)
        _write_hygiene_report(
            report, resolve_output_format(args, default=OutputFormat.text)
        )
        return 0 if report.ok else 1

    def run_readiness(self, args: Any) -> int:
        report = self.readiness(root=_arg_root(args))
        _write_readiness_report(
            report, resolve_output_format(args, default=OutputFormat.text)
        )
        return 0 if report.ok else 1

    def _scan_files(
        self,
        *,
        root: Path,
        files: Sequence[Path],
        rules: Sequence[OssHygieneRule],
        scope: str,
        check_filenames: bool,
    ) -> OssHygieneReport:
        findings: list[OssHygieneFinding] = []
        skipped: list[str] = []

        for path in files:
            relative = _relative(path, root=root)
            if check_filenames:
                findings.extend(self._filename_findings(relative))
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                skipped.append(relative)
                continue
            findings.extend(
                self._scan_text(
                    root=root,
                    path=path,
                    text=text,
                    rules=rules,
                )
            )

        # Also catch forbidden filenames that may not be text-scannable.
        if check_filenames and scope == "repository":
            for path in _discover_repository_files(root=root, suffixes=None):
                relative = _relative(path, root=root)
                findings.extend(self._filename_findings(relative))

        # Deduplicate findings from dual filename passes.
        unique: dict[tuple[str, str, int, str], OssHygieneFinding] = {
            (f.path, f.rule_id, f.line, f.excerpt): f for f in findings
        }

        return OssHygieneReport(
            root=str(root),
            files_scanned=len(files) - len(skipped),
            findings=tuple(
                sorted(unique.values(), key=lambda f: (f.path, f.line, f.rule_id))
            ),
            skipped_files=tuple(skipped),
            scope=scope,
        )

    def _filename_findings(self, relative: str) -> list[OssHygieneFinding]:
        name = Path(relative).name
        hits: list[OssHygieneFinding] = []
        for pattern in self._forbidden_filenames:
            if pattern.startswith("*") and name.endswith(pattern[1:]):
                matched = True
            else:
                matched = name == pattern
            if matched:
                hits.append(
                    OssHygieneFinding(
                        path=relative,
                        rule_id="forbidden_filename",
                        line=0,
                        excerpt=f"forbidden filename: {name}",
                    )
                )
        return hits

    def _scan_text(
        self,
        *,
        root: Path,
        path: Path,
        text: str,
        rules: Sequence[OssHygieneRule],
    ) -> Iterable[OssHygieneFinding]:
        relative = _relative(path, root=root)
        if relative in SYNTHETIC_ALLOWLIST_PATHS:
            return
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule in rules:
                if any(
                    relative.startswith(prefix) for prefix in rule.allow_path_prefixes
                ):
                    continue
                if rule.pattern.search(line):
                    yield OssHygieneFinding(
                        path=relative,
                        rule_id=rule.id,
                        line=line_number,
                        excerpt=line.strip()[:200],
                    )


def _discover_files(*, root: Path, globs: Sequence[str]) -> tuple[Path, ...]:
    files: set[Path] = set()
    for pattern in globs:
        files.update(path for path in root.glob(pattern) if _is_scannable_file(path))
    return tuple(sorted(files, key=lambda p: p.as_posix()))


def _discover_repository_files(
    *, root: Path, suffixes: frozenset[str] | None = SCANNABLE_SUFFIXES
) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in REPO_WIDE_SKIP_DIR_NAMES for part in path.parts):
            continue
        if (
            suffixes is not None
            and path.suffix not in suffixes
            and path.name not in FORBIDDEN_FILENAMES
        ):
            # Still include extensionless forbidden names and common config names.
            if path.name not in {
                "Makefile",
                "Dockerfile",
                "LICENSE",
            } and not path.name.startswith(".env"):
                continue
        files.append(path)
    return tuple(sorted(files, key=lambda p: p.as_posix()))


def _is_scannable_file(path: Path) -> bool:
    return (
        path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def _relative(path: Path, *, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _arg_root(args: Any) -> Path:
    return Path(str(getattr(args, "root", "."))).expanduser()


def _write_hygiene_report(report: OssHygieneReport, fmt: OutputFormat) -> None:
    if fmt != OutputFormat.text:
        write_payload(report.to_dict(), fmt=fmt)
        return

    lines = [
        "# OSS hygiene",
        "",
        f"Root: `{report.root}`",
        f"Scope: `{report.scope}`",
        f"Files scanned: {report.files_scanned}",
        f"Status: {'PASS' if report.ok else 'FAIL'}",
    ]
    if report.findings:
        lines.extend(["", "## Findings"])
        lines.extend(
            f"- `{finding.path}:{finding.line}` {finding.rule_id}: {finding.excerpt}"
            for finding in report.findings
        )
    if report.skipped_files:
        lines.extend(["", "## Skipped binary/non-UTF8 files"])
        lines.extend(f"- `{path}`" for path in report.skipped_files)
    lines.append("")
    write_text("\n".join(lines))


def _write_readiness_report(report: OssReadinessReport, fmt: OutputFormat) -> None:
    if fmt != OutputFormat.text:
        write_payload(report.to_dict(), fmt=fmt)
        return

    lines = [
        "# OSS alpha readiness",
        "",
        f"Root: `{report.root}`",
        f"Status: {'PASS' if report.ok else 'FAIL'}",
        "",
        "## Checks",
    ]
    lines.extend(
        f"- {check.status.upper()} `{check.id}`: {check.message}"
        for check in report.checks
    )
    if report.hygiene.findings:
        lines.extend(["", "## Hygiene findings"])
        lines.extend(
            f"- `{finding.path}:{finding.line}` {finding.rule_id}: {finding.excerpt}"
            for finding in report.hygiene.findings
        )
    lines.append("")
    write_text("\n".join(lines))


__all__ = [
    "DEFAULT_PUBLIC_ASSET_GLOBS",
    "DEFAULT_RULES",
    "FORBIDDEN_FILENAMES",
    "HARD_DENY_RULES",
    "PUBLIC_RULES",
    "REPO_WIDE_SKIP_DIR_NAMES",
    "REQUIRED_OSS_FILES",
    "SYNTHETIC_ALLOWLIST_PATHS",
    "OssHygieneFinding",
    "OssHygieneReport",
    "OssHygieneRule",
    "OssHygieneService",
    "OssReadinessCheck",
    "OssReadinessReport",
]
