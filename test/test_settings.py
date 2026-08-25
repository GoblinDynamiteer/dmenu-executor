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
