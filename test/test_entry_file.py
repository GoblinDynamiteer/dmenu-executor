import shlex
from pathlib import Path

import pytest

from dmenu_executor.entry import (
    EntryClaude,
    EntryCopilot,
    EntryOpenPdf,
    EntryOpenUrl,
    EntryOpenUrlSubMenu,
    EntryStartApplication,
    InputCheck,
    create_entry_from_dict,
    resolve_input,
    substitute_input,
)
from dmenu_executor.menu import Dmenu
from dmenu_executor.settings import Settings


def test_example_entry_file_loads_without_i3man_dependency():
    menu = Dmenu.create_from_entry_file(Path("examples/entries.json"))

    assert sorted(entry.text for entry in menu._entries) == [
        "[app] claude | app",
        "[app] claude | app + listing",
        "[app] code | open directory ...",
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

    assert commands == ["gnome-terminal -- bash -c 'cd /tmp/project && env FOO=bar claude'"]


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
        "gnome-terminal -- bash -c 'cd /tmp/project && claude'",
        {"below": "gnome-terminal -- bash -c 'cd /tmp/project && exec zsh'",
         "height": "",
         "match_class": ""},
    )]


def test_terminal_below_object_sets_command_cwd_and_height(monkeypatch):
    monkeypatch.setenv("HOME", "/home/user")
    calls = _record_terminal_below(monkeypatch)
    entry = EntryCopilot.from_dict(
        {"type": "copilot", "cwd": "/tmp/project", "workspace": "",
         "terminal_below": {"command": "make test", "cwd": "~/web", "height": "35%"}}
    )
    entry.settings = Settings()

    entry.execute()

    [(_, kwargs)] = calls
    assert kwargs["below"] == "gnome-terminal -- bash -c 'cd /home/user/web && make test'"
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

    assert commands == ["gnome-terminal -- bash -c 'cd /tmp/project && claude'"]


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


def test_cwd_is_used_without_terminal(monkeypatch):
    monkeypatch.setenv("HOME", "/home/user")
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "make", "executable_args": ["run"],
         "cwd": "~/project"}
    )
    entry.settings = Settings()

    entry.execute()

    assert commands == ["cd /home/user/project && make run"]


@pytest.fixture
def opened_urls(monkeypatch):
    opened = []
    monkeypatch.setattr("dmenu_executor.web.utils.subprocess.Popen",
                        lambda args: opened.append(("command", args)))
    monkeypatch.setattr("dmenu_executor.web.utils.webbrowser.open_new_tab",
                        lambda url: opened.append(("default", url)))
    monkeypatch.setattr("dmenu_executor.web.utils.select_workspace",
                        lambda workspace: opened.append(("workspace", workspace)))
    return opened


@pytest.mark.parametrize(
    "browser, expected",
    [
        (None, ("default", "https://example.com/")),
        ("firefox", ("command", ["firefox", "--new-tab", "https://example.com/"])),
        ("chromium --new-window",
         ("command", ["chromium", "--new-window", "https://example.com/"])),
    ],
)
def test_open_web_browser(opened_urls, browser, expected):
    data = {"type": "open_web", "url": "https://example.com/", "workspace": "web"}
    if browser is not None:
        data["browser"] = browser

    EntryOpenUrl.from_dict(data).execute()

    assert opened_urls == [expected, ("workspace", "web")]


def test_web_list_without_browser_uses_default_browser(opened_urls):
    menu = EntryOpenUrlSubMenu.from_dict(
        {"type": "web_list", "urls": [{"url": "https://example.com/"}]}
    )

    [entry] = menu._entries
    entry.execute()

    assert opened_urls == [("default", "https://example.com/")]


def test_open_web_rejects_non_string_browser():
    with pytest.raises(TypeError):
        EntryOpenUrl.from_dict({"type": "open_web", "url": "https://example.com/",
                                "browser": ["firefox"]})


def test_pdf_label_outside_home_uses_absolute_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    pdf = tmp_path / "manuals" / "guide.pdf"

    entry = EntryOpenPdf(pdf_path=pdf, executable="okular")

    assert entry.text == f"guide.pdf | {tmp_path / 'manuals'}"


def test_pdf_search_path_expands_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.pdf").touch()
    (tmp_path / "docs" / "guide.nfo").write_text("user guide\n")

    entries = EntryOpenPdf.build_entries(["~/docs"], workspace="", executable="okular")

    assert [entry.text for entry in entries] == ["guide.pdf | docs (user guide)"]


def test_each_executable_arg_is_one_argument(monkeypatch):
    monkeypatch.setenv("HOME", "/home/user")
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    args = ["--title", "it's a \"test\"", "~/Downloads", "--path=~/x", "$HOME", "*.txt", 8080]
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "~/bin/app", "executable_args": args,
         "cwd": "~/my project", "use_terminal": True}
    )
    entry.settings = Settings()

    entry.execute()

    # i3 runs the command with a shell, the terminal with another one: parse both levels
    [command] = commands
    *terminal, inner = shlex.split(command)
    assert terminal == ["gnome-terminal", "--", "bash", "-c"]
    assert shlex.split(inner) == [
        "cd", "/home/user/my project", "&&",
        "/home/user/bin/app", "--title", "it's a \"test\"", "/home/user/Downloads",
        "--path=~/x", "$HOME", "*.txt", "8080",
    ]


def test_executable_with_safe_words_is_not_quoted():
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "nautilus",
         "executable_args": ["--new-window", "/tmp"]}
    )

    assert entry._cmd_with_args() == "nautilus --new-window /tmp"


@pytest.mark.parametrize("args", ["--flag", {"a": "b"}, [True], [["--flag"]]])
def test_malformed_executable_args_are_rejected(args):
    with pytest.raises(TypeError):
        EntryStartApplication.from_dict(
            {"type": "start_app", "executable": "okular", "executable_args": args}
        )


def _input_entry(**extra):
    data = {"type": "start_app", "executable": "pycharm",
            "executable_args": ["nosplash", "{input}"],
            "input": {"prompt": "Directory:", "check": "dir"}}
    data.update(extra)
    return EntryStartApplication.from_dict(data)


def test_input_is_parsed():
    entry = _input_entry(input={"prompt": "Dir:", "check": "file", "items": ["~/a", "~/b"]})

    assert entry._input.prompt == "Dir:"
    assert entry._input.check == InputCheck.File
    assert entry._input.items == ["~/a", "~/b"]


def test_input_defaults():
    entry = _input_entry(input={})

    assert entry._input.prompt == "Input:"
    assert entry._input.check == InputCheck.NoCheck
    assert entry._input.items == []


def test_input_placeholder_in_cwd_only_is_accepted():
    entry = _input_entry(executable_args=[], cwd="~/projects/{input}")

    assert entry._input is not None


@pytest.mark.parametrize(
    "extra, error",
    [
        ({"input": "Directory:"}, TypeError),
        ({"input": {"check": "folder"}}, ValueError),
        ({"input": {"check": ["dir"]}}, ValueError),
        ({"input": {"promt": "Directory:"}}, ValueError),
        ({"input": {"prompt": 1}}, TypeError),
        ({"input": {"items": "~/a"}}, TypeError),
        ({"input": {"items": ["~/a", 1]}}, TypeError),
        ({"executable_args": ["nosplash"]}, ValueError),
        ({"executable_args": ["{inptu}"], "cwd": "~/projects"}, ValueError),
    ],
)
def test_malformed_input_is_rejected(extra, error):
    with pytest.raises(error):
        _input_entry(**extra)


@pytest.mark.parametrize("entry_type", ["claude", "copilot"])
def test_input_is_rejected_for_claude_and_copilot(entry_type):
    with pytest.raises(ValueError):
        create_entry_from_dict({"type": entry_type, "cwd": "/tmp/{input}", "input": {}})


def test_resolve_input_without_check_keeps_the_text():
    assert resolve_input("~/a b", InputCheck.NoCheck, "/tmp") == "~/a b"


def test_resolve_input_expands_home_and_relative_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "projects" / "app").mkdir(parents=True)
    (tmp_path / "notes.txt").touch()

    assert resolve_input("~/projects/app", InputCheck.Dir) == str(tmp_path / "projects" / "app")
    assert resolve_input("projects/app/", InputCheck.Dir) == str(tmp_path / "projects" / "app")
    assert resolve_input("app", InputCheck.Dir, "~/projects") == str(tmp_path / "projects" / "app")
    assert resolve_input("../notes.txt", InputCheck.File, "~/projects") == \
        str(tmp_path / "notes.txt")
    assert resolve_input(str(tmp_path / "notes.txt"), InputCheck.Exists, "/somewhere") == \
        str(tmp_path / "notes.txt")


@pytest.mark.parametrize(
    "value, check, message",
    [
        ("notes.txt", InputCheck.Dir, "not a directory: "),
        ("projects", InputCheck.File, "not a file: "),
        ("missing", InputCheck.Exists, "does not exist: "),
        ("missing", InputCheck.Dir, "not a directory: "),
    ],
)
def test_resolve_input_rejects_wrong_paths(tmp_path, monkeypatch, value, check, message):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "projects").mkdir()
    (tmp_path / "notes.txt").touch()

    with pytest.raises(ValueError, match=f"^{message}{tmp_path / value}$"):
        resolve_input(value, check)


def test_substitute_input_returns_copies():
    args = ["--project={input}", "x"]

    assert substitute_input(args, "~/{input}", "app") == (["--project=app", "x"], "~/app")
    assert args == ["--project={input}", "x"]


@pytest.fixture
def fake_dmenu(monkeypatch):
    """Answers each dmenu call from `answers`; `calls` records (prompt, items)."""
    class FakeDmenu:
        answers: list[str | None] = []
        calls: list[tuple[str, list[str]]] = []

        def show(self, items, prompt=None, **kwargs):
            self.calls.append((prompt, list(items)))
            return self.answers.pop(0)

    fake = FakeDmenu()
    monkeypatch.setattr("dmenu.show", fake.show)
    return fake


def test_input_value_is_quoted_into_the_command(tmp_path, monkeypatch, fake_dmenu):
    project = tmp_path / "my project"
    project.mkdir()
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    fake_dmenu.answers = [str(project)]
    entry = _input_entry(input={"prompt": "Directory:", "check": "dir", "items": ["~/a"]})
    entry.settings = Settings()

    entry.execute()

    assert fake_dmenu.calls == [("Directory: (ctrl+y to paste)", ["~/a"])]
    assert commands == [f"pycharm nosplash {shlex.quote(str(project))}"]
    # the entry still has the placeholder, the next run asks again
    assert entry._args == ["nosplash", "{input}"]


def test_input_is_substituted_into_cwd(tmp_path, monkeypatch, fake_dmenu):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "projects" / "app").mkdir(parents=True)
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    fake_dmenu.answers = ["projects/app"]
    entry = _input_entry(executable="make", executable_args=["test"], cwd="{input}")
    entry.settings = Settings()

    entry.execute()

    assert commands == [f"cd {tmp_path}/projects/app && make test"]


def test_cancelled_input_runs_nothing(monkeypatch, fake_dmenu):
    monkeypatch.setattr("dmenu_executor.entry.run_exec",
                        lambda *args: pytest.fail("nothing should run"))
    fake_dmenu.answers = [None]
    entry = _input_entry()
    entry.settings = Settings()

    entry.execute()

    assert fake_dmenu.calls == [("Directory: (ctrl+y to paste)", [])]


def test_failed_input_check_shows_error_menu(tmp_path, monkeypatch, fake_dmenu):
    monkeypatch.setattr("dmenu_executor.entry.run_exec",
                        lambda *args: pytest.fail("nothing should run"))
    fake_dmenu.answers = [str(tmp_path / "missing"), None]
    entry = _input_entry()
    entry.settings = Settings()

    entry.execute()

    assert fake_dmenu.calls == [
        ("Directory: (ctrl+y to paste)", []),
        ("Errors:", [f"not a directory: {tmp_path / 'missing'}"]),
    ]


def test_entry_without_input_does_not_ask(monkeypatch, fake_dmenu):
    commands = []
    monkeypatch.setattr("dmenu_executor.entry.run_exec", commands.append)
    entry = EntryStartApplication.from_dict(
        {"type": "start_app", "executable": "okular", "executable_args": ["{input}"]}
    )
    entry.settings = Settings()

    entry.execute()

    assert fake_dmenu.calls == []
    assert commands == ["okular '{input}'"]
