from types import SimpleNamespace

import pytest

from dmenu_executor.i3.utils import (
    floating_window_command,
    move_workspaces_to_default_monitor,
    resolve_floating_size,
    window_matches,
)


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


def test_resolve_floating_size_handles_percentages_and_pixels():
    assert resolve_floating_size("60%x70%", 1920, 1080) == (1152, 756)
    assert resolve_floating_size("1200x800", 1920, 1080) == (1200, 800)
    assert resolve_floating_size("50%x800px", 1920, 1080) == (960, 800)
    assert resolve_floating_size([1000, 600], 1920, 1080) == (1000, 600)
    assert resolve_floating_size(None, 1920, 1080) == (1152, 756)


def test_resolve_floating_size_rejects_malformed_spec():
    with pytest.raises(ValueError):
        resolve_floating_size("1200", 1920, 1080)


def test_floating_window_command():
    assert floating_window_command(1152, 756) == (
        "floating enable, resize set 1152 px 756 px, move position center"
    )
    assert "move position 100 200" in floating_window_command(800, 600, "100 200")


def test_window_matches():
    nautilus = SimpleNamespace(window_class="Org.gnome.Nautilus",
                               window_instance="org.gnome.Nautilus",
                               app_id=None)
    assert window_matches(nautilus, "nautilus")
    assert window_matches(nautilus, "")
    assert not window_matches(nautilus, "firefox")
    # i3 does not always know the class yet, float it anyway
    assert window_matches(SimpleNamespace(window_class=None,
                                          window_instance=None,
                                          app_id=None), "nautilus")
