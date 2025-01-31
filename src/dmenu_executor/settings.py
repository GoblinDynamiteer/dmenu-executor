from dataclasses import dataclass
from typing import Self, Any

import logging

@dataclass
class Settings:
    case_insensitive: bool = True
    color_selected_foreground: str = "white"
    color_selected_background: str = "#042C44"
    color_bar_background: str = "black"
    lines: int = 40
    terminal: str = "gnome-terminal"
    shell: str = "bash"
    shell_command_arg: str = "-c"

    @property
    def terminal_shell_start_cmd(self) -> str:
        return f"{self.terminal} -- {self.shell} {self.shell_command_arg}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        _default = Settings()
        _ret = Settings(
            case_insensitive=data.get("dmenu_case_insensitive", _default.case_insensitive),
            color_selected_foreground=data.get("dmenu_color_selected_foreground", _default.color_selected_foreground),
            color_selected_background=data.get("dmenu_color_selected_background", _default.color_selected_background),
            color_bar_background=data.get("dmenu_color_bar_background", _default.color_bar_background),
            lines=data.get("dmenu_lines", _default.lines),
            shell=data.get("shell", _default.shell),
            shell_command_arg=data.get("shell_command_arg", _default.shell_command_arg),
        )
        logging.getLogger(f"{cls.__class__.__name__}.from_dict").debug(
            f"created: {_ret}"
        )
        return _ret
