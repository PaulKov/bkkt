from __future__ import annotations

import argparse

from .connect.create_cmd import register_parser as register_create
from .connect.delete_cmd import register_parser as register_delete
from .connect.endpoints_cmd import register_parser as register_endpoints
from .connect.offsets_cmd import register_parser as register_offsets
from .connect.patch_cmd import register_parser as register_patch
from .connect.pause_cmd import register_parser as register_pause
from .connect.resume_cmd import register_parser as register_resume
from .connect.restart_cmd import register_parser as register_restart
from .connect.stop_cmd import register_parser as register_stop
from .connect.status_cmd import register_parser as register_status
from .connect.update_cmd import register_parser as register_update


def register_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Kafka Connect REST client helpers (connectctl connect ...)."""

    p_connect = subparsers.add_parser(
        "connect",
        help="Kafka Connect REST клиент: status/restart/pause/resume/stop/delete/create/update/patch/endpoints/offsets",
    )
    connect_sub = p_connect.add_subparsers(dest="connect_cmd", required=True)

    # Keep subcommand order stable for predictable help output.
    register_status(connect_sub)
    register_endpoints(connect_sub)
    register_offsets(connect_sub)
    register_restart(connect_sub)
    register_pause(connect_sub)
    register_resume(connect_sub)
    register_stop(connect_sub)
    register_delete(connect_sub)
    register_create(connect_sub)
    register_update(connect_sub)
    register_patch(connect_sub)

    return p_connect
