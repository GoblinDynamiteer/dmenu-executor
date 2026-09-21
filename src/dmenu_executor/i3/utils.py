from __future__ import annotations

import logging
import pathlib
import threading
from collections.abc import Mapping, Sequence

import i3ipc

from dmenu_executor.i3.workspace import Workspace

DEFAULT_FLOATING_SIZE = "60%x70%"
DEFAULT_FLOATING_POSITION = "center"
DEFAULT_FLOATING_TIMEOUT_S = 5.0


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


def _resolve_dimension(value: str, total: int) -> int:
    value = str(value).strip().lower().removesuffix("px").strip()
    if value.endswith("%"):
        return max(1, round(total * float(value.removesuffix("%")) / 100))
    return max(1, int(float(value)))


def resolve_floating_size(
        size: str | Sequence[str | int] | None,
        width: int,
        height: int) -> tuple[int, int]:
    """Resolve a '<width>x<height>' size spec into pixels.

    Both parts are either absolute pixels ('1200') or a percentage of the
    workspace ('60%'), e.g. '60%x70%', '1200x800' or '60%x800'.
    """
    if isinstance(size, Sequence) and not isinstance(size, str):
        parts = [str(part) for part in size]
    else:
        # drop the optional 'px' units first, they contain the separator
        parts = str(size or DEFAULT_FLOATING_SIZE).lower().replace("px", "").split("x")
    if len(parts) != 2:
        raise ValueError(f"malformed floating size: {size!r}, "
                         "expected '<width>x<height>'")
    return _resolve_dimension(parts[0], width), _resolve_dimension(parts[1], height)


def floating_window_command(
        width: int,
        height: int,
        position: str = DEFAULT_FLOATING_POSITION) -> str:
    return (f"floating enable, resize set {width} px {height} px, "
            f"move position {position or DEFAULT_FLOATING_POSITION}")


def window_matches(window, match: str) -> bool:
    if not match:
        return True
    _match = match.lower()
    _values = [getattr(window, attr, None)
               for attr in ("window_class", "window_instance", "app_id")]
    if not any(_values):
        # i3 does not always know the class when the window is mapped,
        # accept it rather than leaving the window tiled.
        return True
    return any(value and _match in value.lower() for value in _values)


def focused_workspace_size(i3_conn: i3ipc.Connection) -> tuple[int, int]:
    focused = next((ws for ws in i3_conn.get_workspaces() if ws.focused), None)
    if focused is None:
        raise RuntimeError("no focused workspace found")
    return focused.rect.width, focused.rect.height


def run_exec_floating(
        executable: str | pathlib.Path,
        size: str | Sequence[str | int] | None = DEFAULT_FLOATING_SIZE,
        position: str = DEFAULT_FLOATING_POSITION,
        match_class: str = "",
        timeout_s: float = DEFAULT_FLOATING_TIMEOUT_S,
        i3_conn: i3ipc.Connection | None = None) -> bool:
    """Start `executable` and float/resize the window it opens.

    The window is left on the workspace it appears on (the focused one unless
    i3 is configured otherwise), so this keeps the window in the current
    workspace.
    """
    logger = logging.getLogger("i3.utils.run_exec_floating")
    i3_conn = i3_conn or i3ipc.Connection()
    width, height = resolve_floating_size(size, *focused_workspace_size(i3_conn))
    command = floating_window_command(width, height, position)
    handled = False

    def _on_window_new(conn: i3ipc.Connection, event) -> None:
        nonlocal handled
        window = event.container
        if not window_matches(window, match_class):
            logger.debug(f"ignoring new window: {window.window_class}")
            return
        logger.debug(f"floating window {window.window_class}: {command}")
        handled = is_reply_success(window.command(command))
        conn.main_quit()

    i3_conn.on(i3ipc.Event.WINDOW_NEW, _on_window_new)
    try:
        if not run_exec(executable, i3_conn):
            return False
        timer = threading.Timer(timeout_s, i3_conn.main_quit)
        timer.start()
        try:
            i3_conn.main()
        finally:
            timer.cancel()
    finally:
        i3_conn.off(_on_window_new)
    if not handled:
        logger.error(f"no window to float appeared within {timeout_s} s: "
                     f"{match_class or executable}")
    return handled
