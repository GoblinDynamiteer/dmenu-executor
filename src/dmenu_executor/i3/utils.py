from __future__ import annotations

import logging
import pathlib

import i3ipc

from dmenu_executor.i3.workspace import Workspace


def is_reply_success(reply: i3ipc.CommandReply | list[i3ipc.CommandReply]) -> bool:
    if isinstance(reply, i3ipc.CommandReply):
        reply = [reply]
    return all([re.success for re in reply])


def run_command(command: str, i3_conn: i3ipc.Connection | None = None) -> bool:
    if not i3_conn:
        i3_conn = i3ipc.Connection()
    logger = logging.getLogger("i3.utils.run_command")
    logger.debug(f"running: {command}")
    if is_reply_success(i3_conn.command(command)):
        return True
    logger.error(f"{command} failed!")
    return False

def run_exec(executable: str | pathlib.Path, i3_conn: i3ipc.Connection | None = None) -> bool:
    logger = logging.getLogger("i3.utils.run_exec")
    logger.debug(f"starting: {executable}")
    return run_command(f"exec {executable}", i3_conn)


def select_workspace(
        workspace: Workspace | str,
        i3_conn: i3ipc.Connection | None = None) -> bool:
    if isinstance(workspace, Workspace):
        workspace = workspace.name
    if not i3_conn:
        i3_conn = i3ipc.Connection()
    return run_command(f"workspace {workspace}", i3_conn)
