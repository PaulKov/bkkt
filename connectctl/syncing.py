"""Sync primitives.

This module is a small facade that keeps backward-compatible imports:

  - compute_sync_plan
  - run_sync
  - build_desired_manifests
  - SyncPlan

Implementation lives in the dedicated syncing_* modules.
"""

from __future__ import annotations

from .syncing_desired import build_desired_manifests
from .syncing_models import PrunePolicy, SyncPlan
from .syncing_plan import _expand_env_placeholders, compute_sync_plan
from .syncing_runner import run_sync

__all__ = [
    "SyncPlan",
    "PrunePolicy",
    "build_desired_manifests",
    "compute_sync_plan",
    "run_sync",
    "_expand_env_placeholders",
]
