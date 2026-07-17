from __future__ import annotations

from argparse import Namespace

from connectctl.services.sync_service import _requires_multi_cluster_confirmation


def test_sync_requires_confirmation_for_multi_cluster_apply_without_override() -> None:
    args = Namespace(dry_run=False)
    assert (
        _requires_multi_cluster_confirmation(
            args,
            cli_cluster=None,
            selected_clusters=None,
        )
        is True
    )


def test_sync_skips_confirmation_for_dry_run_or_explicit_single_cluster() -> None:
    dry_run_args = Namespace(dry_run=True)
    assert (
        _requires_multi_cluster_confirmation(
            dry_run_args,
            cli_cluster=None,
            selected_clusters=["acme-main"],
        )
        is False
    )

    single_cluster_args = Namespace(dry_run=False)
    assert (
        _requires_multi_cluster_confirmation(
            single_cluster_args,
            cli_cluster="acme-main",
            selected_clusters=None,
        )
        is False
    )
