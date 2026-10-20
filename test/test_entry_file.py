import shlex
from pathlib import Path

import pytest

from dmenu_executor.entry import EntryClaude, EntryCopilot, EntryStartApplication
from dmenu_executor.menu import Dmenu
from dmenu_executor.settings import Settings


def test_example_entry_file_loads_without_i3man_dependency():
    menu = Dmenu.create_from_entry_file(Path("examples/entries.json"))

    assert sorted(entry.text for entry in menu._entries) == [
        "[app] claude | app",
        "[app] claude | app + listing",
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


def _record_terminal_below(monkeypatch):
    calls = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec",
                        lambda *args, **kwargs: pytest.fail("terminal below expected"))
    monkeypatch.setattr("dmenu_executor.entry.run_exec_with_terminal_below",
                        lambda cmd, **kwargs: calls.append((cmd, kwargs)))
    return calls


def test_terminal_below_true_opens_interactive_shell_in_entry_cwd(monkeypatch):
    calls = _record_terminal_below(monkeypatch)
    entry = EntryClaude.from_dict(
        {"type": "claude", "cwd": "/tmp/project", "workspace": "", "terminal_below": True}
    )
    entry.settings = Settings(interactive_shell="zsh")

    entry.execute()

    assert calls == [(
        'gnome-terminal -- bash -c "cd /tmp/project && claude"',
        {"below": "gnome-terminal -- bash -c 'cd /tmp/project && exec zsh'",
         "height": "",
         "match_class": ""},
    )]


def test_terminal_below_object_sets_command_cwd_and_height(monkeypatch):
    calls = _record_terminal_below(monkeypatch)
    entry = EntryCopilot.from_dict(
        {"type": "copilot", "cwd": "/tmp/project", "workspace": "",
         "terminal_below": {"command": "make test", "cwd": "~/web", "height": "35%"}}
    )
    entry.settings = Settings()

    entry.execute()

    [(_, kwargs)] = calls
    assert kwargs["below"] == "gnome-terminal -- bash -c 'cd ~/web && make test'"
    assert kwargs["height"] == "35%"


def test_terminal_below_command_with_quotes_is_quoted(monkeypatch):
    calls = _record_terminal_below(monkeypatch)
    command = """sh -c 'echo "hi"'"""
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "okular", "terminal_below": {"command": command}}
    )
    entry.settings = Settings()

    entry.execute()

    [(cmd, kwargs)] = calls
    assert cmd == "okular"
    # no cwd anywhere: no 'cd'
    assert shlex.split(kwargs["below"]) == ["gnome-terminal", "--", "bash", "-c", command]


def test_entry_without_terminal_below_runs_single_terminal(monkeypatch):
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    monkeypatch.setattr("dmenu_executor.entry.run_exec_with_terminal_below",
                        lambda *args, **kwargs: pytest.fail("no terminal below expected"))
    entry = EntryClaude.from_dict(
        {"type": "claude", "cwd": "/tmp/project", "workspace": "", "terminal_below": False}
    )
    entry.settings = Settings()

    entry.execute()

    assert commands == ['gnome-terminal -- bash -c "cd /tmp/project && claude"']


@pytest.mark.parametrize(
    "extra, error",
    [
        ({"terminal_below": True, "floating": True}, ValueError),
        ({"terminal_below": {"commnd": "ls"}}, ValueError),
        ({"terminal_below": {"height": "big"}}, ValueError),
        ({"terminal_below": {"height": "100%"}}, ValueError),
        ({"terminal_below": {"height": 35}}, TypeError),
        ({"terminal_below": {"command": ["ls"]}}, TypeError),
        ({"terminal_below": "ls"}, TypeError),
    ],
)
def test_malformed_terminal_below_is_rejected(extra, error):
    with pytest.raises(error):
        EntryClaude.from_dict({"type": "claude", "cwd": "/tmp/project", **extra})
