import logging
from abc import ABC, abstractmethod
from pathlib import Path

from dmenu_executor.i3.utils import run_exec, run_command
from dmenu_executor.settings import Settings


class Entry(ABC):
    def __init__(self, text):
        self.text = text
        self.settings: Settings | None = None

    @abstractmethod
    def execute(self) -> None:
        raise NotImplemented("execute is not implemented")


class EntryStartApplication(Entry):
    def __init__(self, app: Path | str, use_terminal: bool = False):
        self._app = app
        self._use_terminal = use_terminal
        self._logger = logging.getLogger(self.__class__.__name__)
        Entry.__init__(self, f"[app] {self._app}")

    def execute(self) -> None:
        if isinstance(self._app, Path):
            assert self._app.exists(follow_symlinks=True), \
                f"{self._app} does not exist!"
        if self._use_terminal:
            _cmd = f"{self.settings.terminal_shell_start_cmd} {self._app}"
        else:
            _cmd = self._app
        run_exec(_cmd)


def create_entry_from_dict(data: dict[str, any]) -> EntryStartApplication:
    _type = data.get("type")
    if not _type:
        raise TypeError(f"cannot create Entry from data: {data}, missing 'type'")
    if _type == "start_app":
        _app = data.get("executable")
        if not _app:
            raise TypeError(f"cannot create Entry from data: {data}, missing 'executable'")
        return EntryStartApplication(_app, use_terminal=data.get("use_terminal", False))
    raise TypeError(f"cannot create Entry from data: {data}, unknown type: {_type}")
