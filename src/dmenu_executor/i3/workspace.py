import dataclasses
import logging

import i3ipc
from i3ipc import WorkspaceReply


@dataclasses.dataclass
class Workspace:
    name: str
    current_monitor: str
    is_focused: bool
    is_visible: bool

    def __str__(self) -> str:
        return self.name

    # def is_on_monitor(self, monitor: str | MonitorPos) -> bool:
    #     if monitor in MonitorPos:
    #         monitor = getattr(MonitorList(), monitor)
    #     return monitor == self.current_monitor

    @classmethod
    def from_workspace_reply(cls, wsr: WorkspaceReply):
        """
        WorkspaceReply:
            ('num', int),
            ('name', str),
            ('visible', bool),
            ('focused', bool),
            ('urgent', bool),
            ('rect', Rect),
            ('output', str),
        """

        expected_attrs = (
            "name", "output", "visible", "focused"
        )
        for attr in expected_attrs:
            assert hasattr(wsr, attr), f"missing attribute in WorkspaceReply: {attr}"

        return cls(
            wsr.name,
            wsr.output,
            wsr.focused,
            wsr.visible
        )


class WorkspaceList:
    def __init__(self, i3_conn: i3ipc.Connection | None = None) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._conn = i3_conn or i3ipc.Connection()
        self._list: list[Workspace] = []

    def get(self) -> list[Workspace]:
        self._refresh()
        return self._list

    def _refresh(self):
        self._list.clear()
        for ws in self._conn.get_workspaces():
            self._list.append(Workspace.from_workspace_reply(ws))