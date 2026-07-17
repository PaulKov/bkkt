from __future__ import annotations

from dataclasses import dataclass

from .models import FailureRemediation


@dataclass(frozen=True)
class FailureBundleReadmeRenderer:
    def render(
        self,
        *,
        command: str,
        env: str,
        stage: str,
        created_at_iso: str,
        error: BaseException,
        remediation: FailureRemediation,
    ) -> str:
        lines = [
            f"# BKKT Failure Bundle: {command}",
            "",
            f"- Created at: `{created_at_iso}`",
            f"- Env: `{env}`",
            f"- Stage: `{stage}`",
            f"- Error: `{error.__class__.__name__}: {str(error)}`",
            "",
            "Files:",
            "- `bundle.json`: metadata, error, routing summary and file pointers",
            "- `prepared_manifest.json`: final manifest after routing/prune, if available",
            "- `routing.json`: routing target and raw routing debug, if available",
            "",
            "Suggested Remediation:",
            f"- Category: `{remediation.category}`",
            f"- Summary: {remediation.summary}",
        ]
        if remediation.actions:
            lines.extend(
                [
                    "",
                    "Action items:",
                    *[f"- {action}" for action in remediation.actions],
                ]
            )
        if remediation.commands:
            lines.extend(
                [
                    "",
                    "Suggested next commands:",
                    "```bash",
                    *remediation.commands,
                    "```",
                ]
            )
        if remediation.references:
            lines.extend(
                [
                    "",
                    "References:",
                    *[f"- `{reference}`" for reference in remediation.references],
                ]
            )
        lines.extend(
            [
                "",
                "Useful next steps:",
                "- inspect `prepared_manifest.json` to see the exact config sent to the target cluster",
                "- inspect `routing.json` to confirm target cluster and prune policy",
                "- rerun the failing command with the same manifest after fixing the underlying issue",
                "",
            ]
        )
        return "\n".join(lines)
