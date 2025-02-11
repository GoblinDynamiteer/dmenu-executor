from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
import time

from dmenu_executor.i3.utils import run_exec, select_workspace
from dmenu_executor.settings import Settings


class EntryType(StrEnum):
    StartApplication = "start_app"
    OpenUrl = "open_web"


class Key(StrEnum):
    EntryType = "type"
    Executable = "executable"
    ExecutableArguments = "executable_args"
    Label = "entry_label"
    LabelSuffixUrl = "include_url_in_label"
    UseTerminal = "use_terminal"
    WebBrowserName = "browser"
    Workspace = "workspace"


class Entry(ABC):
    def __init__(self, text, workspace: str = ""):
        self.text = text
        self.settings: Settings | None = None
        self._workspace = workspace

    @abstractmethod
    def execute(self) -> None:
        raise NotImplemented("execute is not implemented")

    def select_workspace(self) -> None:
        if not self._workspace:
            return
        select_workspace(self._workspace)
        time.sleep(0.1)


class EntryError(Entry):
    def execute(self) -> None:
        pass


class EntryStartApplication(Entry):
    def __init__(self,
                 app: Path | str,
                 use_terminal: bool = False,
                 args: list[str] | None = None,
                 label: str = "",
                 workspace: str = ""):
        self._app = app
        self._args = args
        self._use_terminal = use_terminal
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug(f"{app=}, {use_terminal=}, {args=}")
        Entry.__init__(self, f"[app] {label or self._app}",
                       workspace=workspace)

    @classmethod
    def from_dict(cls, data: dict) -> EntryStartApplication:
        assert data.get(Key.EntryType, None) == EntryType.StartApplication
        _app = data.get(Key.Executable)
        if not _app:
            raise TypeError(f"cannot create Entry from data: {data}, "
                            "missing 'executable'")
        use_terminal = data.get(Key.UseTerminal, False)
        args = data.get(Key.ExecutableArguments, None)
        label = data.get(Key.Label, "")
        workspace = data.get(Key.Workspace, "")
        return cls(_app,
                   use_terminal=use_terminal,
                   args=args,
                   label=label,
                   workspace=workspace)

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


class EntryOpenUrl(Entry):
    def __init__(self,
                 url: str,
                 include_url_in_label: bool = False,
                 use_browser_name: str = "",
                 label: str = "",
                 workspace: str = ""):
        self._url = url
        if use_browser_name != "firefox":
            raise ValueError("Can currently only handle browser 'firefox'")
        self._browser: str = use_browser_name
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug(f"{url=}")
        if include_url_in_label and label:
            _label = f"{label} | {url}"
        elif label:
            _label = label
        else:
            _label = url
        Entry.__init__(self, f"[web] {_label}", workspace=workspace)

    def execute(self) -> None:
        if self._browser == "firefox":
            from dmenu_executor.web.utils import open_url_in_firefox_browser

            open_url_in_firefox_browser(self._url, workspace=self._workspace)

        else:
            from dmenu_executor.web.utils import open_url_in_browser

            open_url_in_browser(self._url, workspace=self._workspace)

    @classmethod
    def from_dict(cls, data: dict) -> EntryOpenUrl:
        assert data.get(Key.EntryType, None) == EntryType.OpenUrl
        if not (_url := data.get("url")):
            raise TypeError(f"cannot create Entry from data: {data}, "
                            "missing 'url'")
        return cls(
            url=_url,
            use_browser_name=data.get(Key.WebBrowserName, ""),
            label=data.get(Key.Label, ""),
            include_url_in_label=data.get(Key.LabelSuffixUrl, False),
            workspace=data.get(Key.Workspace, "")
        )


def create_entry_from_dict(data: dict[str, any]) -> EntryStartApplication | EntryOpenUrl:
    _type = data.get(Key.EntryType)
    if not _type:
        raise TypeError(f"cannot create Entry from data: {data}, missing 'type'")
    if _type == EntryType.StartApplication:
        return EntryStartApplication.from_dict(data)
    if _type == EntryType.OpenUrl:
        return EntryOpenUrl.from_dict(data)
    raise TypeError(f"cannot create Entry from data: {data}, unknown type: {_type}")
