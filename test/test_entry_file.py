from pathlib import Path

import pytest

from dmenu_executor.entry import EntryClaude, EntryStartApplication
from dmenu_executor.menu import Dmenu
from dmenu_executor.settings import Settings


def test_example_entry_file_loads_without_i3man_dependency():
    menu = Dmenu.create_from_entry_file(Path("examples/entries.json"))

    assert sorted(entry.text for entry in menu._entries) == [
        "[app] nautilus | files | Downloads (floating)",
        "[app] okular",
        "[web] Links",
        "[web] https://github.com/",
    ]


def test_floating_entry_keeps_floating_settings():
    entry = EntryStartApplication.from_dict(
        {
            "type": "start_app",
            "executable": "nautilus",
            "floating": True,
            "floating_size": "50%x900",
            "floating_position": "center",
            "window_class": "nautilus",
        }
    )

    assert entry._floating
    assert entry._floating_size == "50%x900"
    assert entry._floating_position == "center"
    assert entry._window_class == "nautilus"


def test_non_floating_entry_defaults_to_tiled():
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "okular"}
    )

    assert not entry._floating


def test_entry_env_is_prefixed_to_command():
    entry = EntryStartApplication.from_dict(
        {
            "type": "start_app",
            "executable": "/usr/bin/app",
            "executable_args": ["--flag"],
            "env": {"QT_SCALE_FACTOR": 1.5, "GREETING": "hello world"},
        }
    )

    assert entry._cmd_with_args() == \
        "env QT_SCALE_FACTOR=1.5 'GREETING=hello world' /usr/bin/app --flag"


def test_entry_without_env_runs_command_as_is():
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "okular", "executable_args": ["a.pdf"]}
    )

    assert entry._cmd_with_args() == "okular a.pdf"


def test_terminal_entry_sets_env_inside_the_terminal(monkeypatch):
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    entry = EntryClaude.from_dict(
        {"type": "claude", "cwd": "/tmp/project", "workspace": "", "env": {"FOO": "bar"}}
    )
    entry.settings = Settings()

    entry.execute()

    assert commands == ['gnome-terminal -- bash -c "cd /tmp/project && env FOO=bar claude"']


@pytest.mark.parametrize(
    "env, error",
    [
        (["FOO=bar"], TypeError),
        ({"FOO": True}, TypeError),
        ({"FOO": ["bar"]}, TypeError),
        ({"1FOO": "bar"}, ValueError),
        ({"FOO=X": "bar"}, ValueError),
    ],
)
def test_malformed_env_is_rejected(env, error):
    with pytest.raises(error):
        EntryStartApplication.from_dict(
            {"type": "start_app", "executable": "okular", "env": env}
        )
