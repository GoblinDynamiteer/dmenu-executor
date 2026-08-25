from types import SimpleNamespace

from dmenu_executor.i3.utils import move_workspaces_to_default_monitor


class FakeI3Connection:
    def __init__(self):
        self.commands = []

    def get_workspaces(self):
        return [
            SimpleNamespace(name="1", output="DP-1", focused=True),
            SimpleNamespace(name="2", output="HDMI-A-1", focused=False),
            SimpleNamespace(name="3", output="DP-1", focused=False),
        ]

    def command(self, command):
        self.commands.append(command)
        return [SimpleNamespace(success=True)]


def test_move_workspaces_to_default_monitor_moves_only_needed_workspaces():
    conn = FakeI3Connection()

    assert move_workspaces_to_default_monitor(
        {
            "1": "DP-1",
            "2": "DP-1",
            "missing": "DP-1",
        },
        i3_conn=conn,
    )

    assert conn.commands == [
        'workspace "2"',
        'move workspace to output "DP-1"',
        'workspace "1"',
    ]
