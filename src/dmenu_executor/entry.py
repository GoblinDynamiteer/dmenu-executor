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


class EntryError(Entry):
    def execute(self) -> None:
        pass


class EntryStartApplication(Entry):
    def __init__(self, app: Path | str, use_terminal: bool = False, args: list[str] | None = None):
        self._app = app
        self._args = args
        self._use_terminal = use_terminal
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug(f"{app=}, {use_terminal=}, {args=}")
        Entry.__init__(self, f"[app] {self._app}")

    def _cmd_with_args(self) -> str:
        if not self._args:
            return str(self._app)
        return f"{self._app} {' '.join(self._args)}"

    def execute(self) -> None:
        if isinstance(self._app, Path):
            assert self._app.exists(follow_symlinks=True), \
                f"{self._app} does not exist!"
        _cmd = self._cmd_with_args()
        if self._use_terminal:
            _cmd = f"{self.settings.terminal_shell_start_cmd} {_cmd}"
        run_exec(_cmd)


def create_entry_from_dict(data: dict[str, any]) -> EntryStartApplication:
    _type = data.get("type")
    if not _type:
        raise TypeError(f"cannot create Entry from data: {data}, missing 'type'")
    if _type == "start_app":
        _app = data.get("executable")
        if not _app:
            raise TypeError(f"cannot create Entry from data: {data}, missing 'executable'")
        use_terminal = data.get("use_terminal", False)
        args = data.get("executable_args", None)
        return EntryStartApplication(_app, use_terminal=use_terminal, args=args)
    raise TypeError(f"cannot create Entry from data: {data}, unknown type: {_type}")
