from __future__ import annotations

import logging
import pathlib
from collections.abc import Mapping

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


def _quote_i3_arg(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def move_workspace_to_output(
        workspace: Workspace | str,
        output: str,
        i3_conn: i3ipc.Connection | None = None) -> bool:
    if isinstance(workspace, Workspace):
        workspace = workspace.name
    i3_conn = i3_conn or i3ipc.Connection()
    logger = logging.getLogger("i3.utils.move_workspace_to_output")
    workspaces = i3_conn.get_workspaces()
    target = next((ws for ws in workspaces if ws.name == workspace), None)
    if target is None:
        logger.debug(f"workspace does not exist, skipping: {workspace}")
        return True
    if target.output == output:
        logger.debug(f"workspace already on output: {workspace} -> {output}")
        return True
    logger.debug(f"moving workspace to output: {workspace} -> {output}")
    return (
        run_command(f"workspace {_quote_i3_arg(workspace)}", i3_conn)
        and run_command(f"move workspace to output {_quote_i3_arg(output)}", i3_conn)
    )


def move_workspaces_to_default_monitor(
        defaults: Mapping[str, str],
        i3_conn: i3ipc.Connection | None = None) -> bool:
    i3_conn = i3_conn or i3ipc.Connection()
    workspaces = i3_conn.get_workspaces()
    focused = next((ws for ws in workspaces if ws.focused), None)
    success = True
    for workspace, output in defaults.items():
        success = move_workspace_to_output(workspace, output, i3_conn) and success
    if focused is not None:
        success = run_command(f"workspace {_quote_i3_arg(focused.name)}", i3_conn) and success
    return success
