import subprocess
import webbrowser

from dmenu_executor.i3.utils import select_workspace


def open_url_in_browser(
        url: str,
        use_webbrowser_lib: bool = True,
        workspace: str = "",
        subprocess_command: str = ""):
    if use_webbrowser_lib:
        webbrowser.open_new_tab(url)
    elif subprocess_command:
        subprocess.call(f"{subprocess_command} {url}".split())
    else:
        raise ValueError(f"Need either arg {use_webbrowser_lib=} or {subprocess_command=}")
    if workspace:
        select_workspace(workspace)


def open_url_in_firefox_browser(url: str, workspace: str = ""):
    open_url_in_browser(url,
                        use_webbrowser_lib=False,
                        subprocess_command="firefox --new-tab",
                        workspace=workspace)
