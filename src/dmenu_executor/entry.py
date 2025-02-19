from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
import time

import concurrent.futures
from typing import Union

from i3man.utils import move_workspaces_to_default_monitor

from dmenu_executor.i3.utils import run_exec, select_workspace
from dmenu_executor.settings import Settings

WS_LEN = 200


class EntryType(StrEnum):
    I3Command = "i3_command"
    OpenPdf = "open_pdf"
    OpenUrl = "open_web"
    StartApplication = "start_app"


class Key(StrEnum):
    Command = "command"
    Data = "data"
    EntryType = "type"
    Executable = "executable"
    ExecutableArguments = "executable_args"
    Label = "entry_label"
    LabelSuffixUrl = "include_url_in_label"
    SearchPaths = "search_paths"
    UseTerminal = "use_terminal"
    WebBrowserName = "browser"
    Workspace = "workspace"
    WorkspaceInLabel = "include_workspace_in_label"


class I3Command(StrEnum):
    MoveWorkspaces = "move_workspaces"


class Entry(ABC):
    def __init__(self, text, workspace: str = "", add_workspace_to_label: bool = False):
        if add_workspace_to_label and workspace:
            _suffix = f" | ws: {workspace}"
            self.text = f"{text}".ljust(WS_LEN, " ") + _suffix
        else:
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
                 add_workspace_to_label: bool = False,
                 workspace: str = ""):
        self._app = app
        self._args = args
        self._use_terminal = use_terminal
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug(f"{app=}, {use_terminal=}, {args=}")
        Entry.__init__(self,
                       f"[app] {label or self._app}",
                       workspace=workspace,
                       add_workspace_to_label=add_workspace_to_label
                       )

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
                   add_workspace_to_label=data.get(Key.WorkspaceInLabel, False),
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
            _cmd = f"{self.settings.terminal_shell_start_cmd} \"{_cmd}\""
        self.select_workspace()
        run_exec(_cmd)


class EntryOpenUrl(Entry):
    def __init__(self,
                 url: str,
                 include_url_in_label: bool = False,
                 add_workspace_to_label: bool = False,
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
        Entry.__init__(self,
                       f"[web] {_label}",
                       workspace=workspace,
                       add_workspace_to_label=add_workspace_to_label)

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
            add_workspace_to_label=data.get(Key.WorkspaceInLabel, False),
            include_url_in_label=data.get(Key.LabelSuffixUrl, False),
            workspace=data.get(Key.Workspace, "")
        )


class EntryOpenPdf(Entry):
    def __init__(self,
                 pdf_path: Path,
                 executable: str,
                 workspace: str = "",
                 add_workspace_to_label: bool = False,
                 nfo: str = ""):

        _loc = pdf_path.parent.relative_to(Path.home())
        if nfo:
            _label = f"{pdf_path.name} | {_loc} ({nfo})"
        else:
            _label = f"{pdf_path.name} | {_loc}"
        self._path = pdf_path
        self._executable = executable
        Entry.__init__(self,
                       _label,
                       workspace=workspace,
                       add_workspace_to_label=add_workspace_to_label)

    def execute(self) -> None:
        self.select_workspace()
        run_exec(f"{self._executable} {self._path}")

    @classmethod
    def build_entries(cls,
                      paths: list[str],
                      workspace: str,
                      executable: str
                      ) -> list[EntryOpenPdf]:
        logger = logging.getLogger("_pdf_build_entries")
        entries: list[EntryOpenPdf] = []
        start = time.time()
        for _path in paths:
            logger.debug(f"globbing {_path}...")
            items: list[Path] = list(Path(_path).rglob("*.pdf"))
            logger.debug(f"found {len(items)} matches")
            for item in items:
                nfo_file = item.with_suffix(".nfo")
                if nfo_file.is_file():
                    logger.debug(f"reading: {nfo_file.name}")
                    text = nfo_file.read_text()
                    nfo = text.strip("\n")
                else:
                    nfo = ""
                entry = EntryOpenPdf(pdf_path=item,
                                     nfo=nfo,
                                     executable=executable,
                                     workspace=workspace)
                entries.append(entry)
        logger.debug(f"operation took {time.time() - start} s")
        return entries


class I3CommandEntry(Entry):
    def __init__(self,
                 command: I3Command,
                 data: dict | None = None,
                 label: str = ""
                 ):
        if label:
            _label = label
        else:
            _label = command

        if command == I3Command.MoveWorkspaces:
            if not data:
                raise ValueError(f"Need data set for {command=}")
            for k, v in data.items():
                assert isinstance(k, str), f"malformed data, expected key {k} to be str"
                assert isinstance(v, str), f"malformed data, expected val {v} to be str"

        self._data = data
        self._command = command

        Entry.__init__(self, text=f"[i3] {_label}")

    def execute(self) -> None:
        if self._command == I3Command.MoveWorkspaces:
            move_workspaces_to_default_monitor(defaults=self._data)
            return
        raise ValueError(f"cannot process command: {self._command}")

    @classmethod
    def from_dict(cls, data: dict) -> I3CommandEntry:
        assert data.get(Key.EntryType, None) == EntryType.I3Command
        _command = data.get(Key.Command, "")
        if not _command:
            raise ValueError(f"command missing from entry: {data}")
        _command = I3Command(_command)
        return cls(
            command=_command,
            label=data.get(Key.Label, ""),
            data=data.get(Key.Data, None)
        )


class EntryOpenPdfSubMenu(Entry):
    def __init__(self,
                 search_paths: list[str],
                 executable: str,
                 label: str = "",
                 workspace: str = ""):
        self._executable: str = executable
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug(f"{search_paths=}")
        if label:
            _label = label
        else:
            _label = ", ".join(search_paths)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            self._future = executor.submit(EntryOpenPdf.build_entries,
                                           search_paths,
                                           workspace,
                                           executable)
        Entry.__init__(self, f"[pdf] {_label}")

    def execute(self) -> None:
        from dmenu_executor import Dmenu

        dmenu = Dmenu()
        dmenu.settings.prompt = f"Open in ({self._executable})"
        entries: list[EntryOpenPdf] = self._future.result()
        for entry in entries:
            dmenu.add_entry(entry)
        dmenu.execute()

    @classmethod
    def from_dict(cls, data: dict) -> EntryOpenPdfSubMenu:
        assert data.get(Key.EntryType, None) == EntryType.OpenPdf
        return cls(
            label=data.get(Key.Label, ""),
            search_paths=data.get(Key.SearchPaths, []),
            workspace=data.get(Key.Workspace, ""),
            executable=data.get(Key.Executable, "")
        )

EntriesType = Union[EntryStartApplication, EntryOpenUrl, EntryOpenPdfSubMenu, I3CommandEntry]

def create_entry_from_dict(data: dict[str, any]) -> EntriesType:
    _type = data.get(Key.EntryType)
    if not _type:
        raise TypeError(f"cannot create Entry from data: {data}, missing 'type'")
    if _type == EntryType.StartApplication:
        return EntryStartApplication.from_dict(data)
    if _type == EntryType.OpenUrl:
        return EntryOpenUrl.from_dict(data)
    if _type == EntryType.OpenPdf:
        return EntryOpenPdfSubMenu.from_dict(data)
    if _type == EntryType.I3Command:
        return I3CommandEntry.from_dict(data)
    raise TypeError(f"cannot create Entry from data: {data}, unknown type: {_type}")
