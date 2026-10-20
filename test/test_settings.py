from dmenu_executor.settings import Settings


def test_settings_from_dict_loads_prompt_and_terminal():
    settings = Settings.from_dict(
        {
            "prompt": "launch:",
            "terminal": "alacritty",
        }
    )

    assert settings.prompt == "launch:"
    assert settings.terminal == "alacritty"


def test_settings_interactive_shell_defaults_to_login_shell(monkeypatch):
    monkeypatch.setenv("SHELL", "/usr/bin/zsh")
    assert Settings().interactive_shell_cmd == "/usr/bin/zsh"
    monkeypatch.delenv("SHELL")
    assert Settings().interactive_shell_cmd == "bash"
    assert Settings.from_dict({"interactive_shell": "zsh"}).interactive_shell_cmd == "zsh"
