from pathlib import Path

from dmenu_executor.entry import EntryStartApplication
from dmenu_executor.menu import Dmenu


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
