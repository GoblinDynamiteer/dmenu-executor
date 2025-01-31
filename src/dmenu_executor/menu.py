from pathlib import Path
from typing import Self
import json

import dmenu

from dmenu_executor.entry import Entry, create_entry_from_dict
from dmenu_executor.settings import Settings


class Dmenu:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._dmenu = dmenu
        self._entries: set[Entry] = set()

    def add_entry(self, entry: Entry) -> None:
        entry.settings = self.settings
        self._entries.add(entry)

    def execute(self) -> None:
        if not self._entries:
            raise ValueError("no entries added")
        ret = self._dmenu.show({e.text for e in self._entries}, lines=30)
        if not ret:
            return
        for e in self._entries:
            if e.text == ret:
                e.execute()
                return
        raise RuntimeError(f"could not find entry for execution: {ret}")

    @classmethod
    def create_from_entry_file(cls, file_path: Path) -> Self:
        assert file_path.is_file(), f"file does not exist: {file_path}"
        data = json.loads(file_path.read_text())
        if "settings" in data:
            menu = cls(Settings.from_dict(data["settings"]))
        else:
            menu = cls()
        for entry in data["entries"]:
            menu.add_entry(create_entry_from_dict(entry))
        return menu