from pathlib import Path

from dmenu_executor.menu import Dmenu


def test_example_entry_file_loads_without_i3man_dependency():
    menu = Dmenu.create_from_entry_file(Path("examples/entries.json"))

    assert sorted(entry.text for entry in menu._entries) == [
        "[app] okular",
        "[web] Links",
        "[web] https://github.com/",
    ]
