from __future__ import annotations

from pathlib import Path
from typing import Any

from ..rendering.renderer_models import RenderResult
from ..utils import flatten_dict
from .loader import VarsProfileLoader
from .models import VarsProfileChange, VarsProfileDiff


class VarsProfileService:
    """Read-only operations for named runtime variable profiles."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.loader = VarsProfileLoader(self.repo_root)

    def list_payload(self) -> dict[str, Any]:
        profiles = self.loader.list()
        return {
            "profiles": [profile.to_payload() for profile in profiles],
            "summary": {"profiles": len(profiles)},
        }

    def explain_payload(self, name: str) -> dict[str, Any]:
        return self.loader.get(name).to_payload()

    def diff(
        self, name: str, *, manifest: str, render_result: RenderResult
    ) -> VarsProfileDiff:
        profile = self.loader.get(name)
        current = render_result.placeholder_context
        profile_flat = flatten_dict(profile.values)
        changes = []
        for key, after in sorted(profile_flat.items()):
            before = current.get(key)
            if before == after:
                continue
            changes.append(
                VarsProfileChange(
                    key=key,
                    before=before,
                    after=after,
                    source=f"vars_profile:{profile.name}",
                )
            )
        return VarsProfileDiff(
            profile=profile,
            manifest=manifest,
            changes=tuple(changes),
        )
