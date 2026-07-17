from __future__ import annotations

from argparse import Namespace

from ...app.context import CliContext
from ..state.path import resolve_state_db_path
from ..state.store import StateStore
from .session import AuditSession


def audit_session_from_args(
    *,
    command: str,
    args: Namespace,
    ctx: CliContext,
    plan_hash: str | None = None,
) -> AuditSession:
    if bool(getattr(args, "no_audit", False)):
        return AuditSession(command=command, args=args, store=None, plan_hash=plan_hash)
    state_db = resolve_state_db_path(
        repo_root=ctx.repo_root,
        explicit_path=getattr(args, "state_db", None),
    )
    return AuditSession(
        command=command,
        args=args,
        store=StateStore(state_db),
        plan_hash=plan_hash,
    )
