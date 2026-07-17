from __future__ import annotations

import argparse
import logging
from types import SimpleNamespace

from connectctl.services.completion.service import CompletionService


def _ctx():
    # CompletionService использует только ctx.logger, поэтому достаточно простого объекта.
    return SimpleNamespace(logger=logging.getLogger("bkkt-test"))


def test_completion_install_dry_run_does_not_create_file(tmp_path):
    rc_file = tmp_path / "bashrc"
    assert not rc_file.exists()

    svc = CompletionService(ctx=_ctx())
    args = argparse.Namespace(
        shell="bash",
        program="bkkt",
        no_comments=False,
        install=True,
        dry_run=True,
        system=False,
        yes=True,
        rc_file=str(rc_file),
    )

    assert svc.run(args) == 0
    # В dry-run ничего не должно создаваться на диске.
    assert not rc_file.exists()


def test_completion_install_dry_run_does_not_modify_existing_file(tmp_path):
    rc_file = tmp_path / "bashrc"
    rc_file.write_text("# test rc\n", encoding="utf-8")
    before = rc_file.read_text(encoding="utf-8")

    svc = CompletionService(ctx=_ctx())
    args = argparse.Namespace(
        shell="bash",
        program="bkkt",
        no_comments=False,
        install=True,
        dry_run=True,
        system=False,
        yes=True,
        rc_file=str(rc_file),
    )

    assert svc.run(args) == 0
    after = rc_file.read_text(encoding="utf-8")
    assert after == before
