from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
import json

import dmenu

from dmenu_executor.entry import Entry, create_entry_from_dict, EntryError
from dmenu_executor.settings import Settings



class Dmenu:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self._dmenu = dmenu
        self._entries: set[Entry] = set()

    def add_entry(self, entry: Entry) -> None:
        entry.settings = self.settings
        self._entries.add(entry)

    def set_prompt(self, prompt_text: str) -> None:
        self.settings.prompt = prompt_text

    def execute(self) -> None:
        if not self._entries:
            raise ValueError("no entries added")
        ret = self._dmenu.show(sorted({e.text for e in self._entries}),
                               case_insensitive=self.settings.case_insensitive,
                               background=self.settings.color_bar_background,
                               foreground=self.settings.color_selected_foreground,
                               background_selected=self.settings.color_selected_background,
                               foreground_selected=self.settings.color_selected_foreground,
                               lines=self.settings.lines,
                               prompt=self.settings.prompt)
        if not ret:
            return
        for e in self._entries:
            if e.text == ret:
                e.execute()
                return
        raise RuntimeError(f"could not find entry for execution: {ret}")

    @classmethod
    def create_menu_with_errors(cls, errors: list[str] | str) -> Dmenu:
        menu = cls(Settings(prompt=f"Errors:",
                            color_selected_foreground="black",
                            color_selected_background="red",
                            color_bar_background="red"))
        if isinstance(errors, str):
            errors = [errors]
        for error in errors:
            menu.add_entry(EntryError(error))
        return menu

    @classmethod
    def create_from_entry_file(cls, file_path: Path) -> Dmenu:
        if not file_path.is_file():
            return Dmenu.create_menu_with_errors(f"file does not exist: {file_path}")
        try:
            data = json.loads(file_path.read_text())
        except JSONDecodeError as json_error:
            return Dmenu.create_menu_with_errors(
                f"Failed to decode {file_path}: {json_error}")
        if "settings" in data:
            menu = cls(Settings.from_dict(data["settings"]))
        else:
            menu = cls()
        for entry in data["entries"]:
            try:
                menu.add_entry(create_entry_from_dict(entry))
            except (ValueError, TypeError, AssertionError) as error:
                return Dmenu.create_menu_with_errors(
                    f"could not generate entries: {error}")
        return menu