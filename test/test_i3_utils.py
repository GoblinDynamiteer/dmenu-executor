from types import SimpleNamespace

import pytest

from dmenu_executor.i3.utils import (
    floating_window_command,
    focus_window_command,
    move_workspaces_to_default_monitor,
    resolve_floating_size,
    run_exec,
    run_exec_with_terminal_below,
    split_below_command,
    terminal_below_resize_command,
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


def test_run_exec_quotes_the_command():
    conn = FakeI3Connection()

    assert run_exec('env \'X=a,b;c\' app "file name"', conn)

    assert conn.commands == ['exec "env \'X=a,b;c\' app \\"file name\\""']


class FakeWindow(SimpleNamespace):
    def command(self, command):
        self.commands.append(command)
        return [SimpleNamespace(success=True)]


class FakeEventConnection(FakeI3Connection):
    """Opens a window (WINDOW_NEW event) of the next class in `window_classes` per exec."""

    def __init__(self, window_classes=("Gnome-terminal", "Gnome-terminal")):
        super().__init__()
        self.window_classes = list(window_classes)
        self.created = 0
        self.handlers = []
        self.pending = []
        self.window_commands = []
        self.running = False

    def on(self, event, handler):
        self.handlers.append(handler)

    def off(self, handler):
        self.handlers.remove(handler)

    def command(self, command):
        if command.startswith("exec ") and self.window_classes:
            container = FakeWindow(id=100 + self.created,
                                   window_class=self.window_classes.pop(0),
                                   window_instance=None, app_id=None,
                                   commands=self.window_commands)
            self.created += 1
            self.pending.append(SimpleNamespace(container=container))
        return super().command(command)

    def main(self):
        self.running = True
        while self.running and self.pending:
            event = self.pending.pop(0)
            for handler in list(self.handlers):
                handler(self, event)

    def main_quit(self):
        self.running = False


def test_terminal_below_commands():
    assert split_below_command(7) == "[con_id=7] split vertical"
    assert focus_window_command(7) == "[con_id=7] focus"
    assert terminal_below_resize_command("35%") == "resize set height 35 ppt"
    assert terminal_below_resize_command("400") == "resize set height 400 px"
    assert terminal_below_resize_command("400px") == "resize set height 400 px"


@pytest.mark.parametrize("height", ["", "big", "0", "100%", "-5%"])
def test_terminal_below_resize_command_rejects_malformed_height(height):
    with pytest.raises(ValueError):
        terminal_below_resize_command(height)


def test_run_exec_with_terminal_below_splits_resizes_and_refocuses():
    conn = FakeEventConnection()

    assert run_exec_with_terminal_below("top", "bottom", height="35%", i3_conn=conn)

    assert conn.commands == [
        'exec "top"',
        "[con_id=100] split vertical",
        'exec "bottom"',
        "[con_id=100] focus",
    ]
    assert conn.window_commands == ["resize set height 35 ppt"]
    assert not conn.handlers


def test_run_exec_with_terminal_below_without_height_keeps_split_size():
    conn = FakeEventConnection()

    assert run_exec_with_terminal_below("top", "bottom", i3_conn=conn)

    assert conn.window_commands == []


def test_run_exec_with_terminal_below_fails_when_lower_window_is_missing():
    conn = FakeEventConnection(window_classes=["Gnome-terminal"])

    assert not run_exec_with_terminal_below("top", "bottom", timeout_s=0.01, i3_conn=conn)

    assert conn.commands[-1] == 'exec "bottom"'
    assert not conn.handlers


def test_run_exec_with_terminal_below_matches_class_on_first_window_only():
    conn = FakeEventConnection(window_classes=["okular", "Gnome-terminal"])

    assert run_exec_with_terminal_below("okular", "terminal", height="30%",
                                        match_class="okular", i3_conn=conn)

    assert conn.commands == [
        'exec "okular"',
        "[con_id=100] split vertical",
        'exec "terminal"',
        "[con_id=100] focus",
    ]
    assert conn.window_commands == ["resize set height 30 ppt"]


def test_run_exec_with_terminal_below_skips_other_windows_before_the_app():
    conn = FakeEventConnection(window_classes=["okular", "Gnome-terminal"])
    splash = SimpleNamespace(container=FakeWindow(id=50, window_class="splash",
                                                  window_instance=None, app_id=None,
                                                  commands=conn.window_commands))
    conn.pending.append(splash)

    assert run_exec_with_terminal_below("okular", "terminal",
                                        match_class="okular", i3_conn=conn)

    assert "[con_id=100] split vertical" in conn.commands
    assert "[con_id=50] split vertical" not in conn.commands
