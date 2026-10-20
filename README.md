# dmenu-executor

A launcher for [i3](https://i3wm.org/): `dmenu-exec` reads a JSON file of entries, shows them
in [dmenu](https://tools.suckless.org/dmenu/) and runs the one you pick. You can start
applications, open them in a terminal, put them on a given workspace, float them, open URLs or
PDFs, and run i3 commands.

```
[app] claude | my-project
[app] htop
[apps] morning setup
[pdf] Manuals
[web] Links
[i3] move workspaces to default monitors
```

## Requirements

- Linux with i3. Commands are run through i3 IPC (`i3ipc`).
- The `dmenu` binary.
- Python 3.13 or newer.
- Optional, depending on the entries you use: a terminal (default `gnome-terminal`), a PDF
  viewer (`open_pdf`).

## Installation

```sh
pip install git+https://github.com/GoblinDynamiteer/dmenu-executor.git
# or, from a clone, editable so changes are live:
pip install -e .
```

This installs the `dmenu-exec` command.

## Usage

```sh
dmenu-exec path/to/entries.json [--log-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}]
```

Bind it to a key in your i3 config:

```
bindsym $mod+d exec --no-startup-id dmenu-exec ~/.config/dmenu-executor/entries.json
```

If the entry file is missing, is not valid JSON or has an invalid entry, dmenu shows a red
error menu with the reason instead of the entries.

## Entry file

```json
{
    "settings": {
        "terminal": "gnome-terminal",
        "dmenu_lines": 20
    },
    "entries": [
        {"type": "start_app", "executable": "htop", "use_terminal": true},
        {"type": "open_web", "url": "https://github.com/"}
    ]
}
```

`settings` is optional. [`examples/entries.json`](examples/entries.json) has more examples.

### Settings

| key                               | default          | meaning                                                  |
|-----------------------------------|------------------|----------------------------------------------------------|
| `prompt`                          | none             | dmenu prompt                                             |
| `dmenu_lines`                     | `40`             | number of lines dmenu shows                              |
| `dmenu_case_insensitive`          | `true`           | case-insensitive matching                                |
| `dmenu_color_bar_background`      | `"black"`        | background color                                         |
| `dmenu_color_selected_background` | `"#042C44"`      | background of the selected line                          |
| `dmenu_color_selected_foreground` | `"white"`        | text color                                               |
| `terminal`                        | `"gnome-terminal"` | terminal for `use_terminal`, `claude`, `copilot`, `terminal_below` |
| `shell`                           | `"bash"`         | shell that runs commands inside the terminal              |
| `shell_command_arg`               | `"-c"`           | argument that passes the command to `shell`              |
| `interactive_shell`               | `$SHELL`         | shell started by `"terminal_below": true`; empty means `$SHELL`, then `shell` |

A terminal command is started as `<terminal> -- <shell> <shell_command_arg> '<command>'`.

`executable`, each item of `executable_args`, and `cwd` are passed exactly as written: one
item is one argument, spaces and quotes included. A leading `~` is expanded to your home
directory; other shell syntax (`$VAR`, globs, `;`) is not interpreted. Only
`terminal_below.command` is a shell command line.

### Common entry keys

| key                          | meaning                                                         |
|------------------------------|-----------------------------------------------------------------|
| `type`                       | entry type (required), see below                                |
| `entry_label`                | text shown in dmenu (each type has a default)                   |
| `active`                     | `false` hides the entry                                         |
| `workspace`                  | i3 workspace to switch to before starting                       |
| `include_workspace_in_label` | append `ws: <workspace>` to the label                           |

### `start_app`

Starts an application.

| key                 | meaning                                                                      |
|---------------------|------------------------------------------------------------------------------|
| `executable`        | program to run (required), without arguments                                 |
| `executable_args`   | list of arguments, one item per argument: `["--port", "8080", "my file.txt"]` |
| `use_terminal`      | run the command inside `terminal`                                            |
| `cwd`               | directory to `cd` to first                                                   |
| `env`               | environment variables, e.g. `{"QT_SCALE_FACTOR": "1.5"}`                     |
| `id`                | name used by `start_apps`                                                    |
| `floating`          | float the new window                                                         |
| `floating_size`     | `"<width>x<height>"`, each in pixels or percent of the workspace (default `"60%x70%"`) |
| `floating_position` | i3 `move position` argument (default `"center"`)                             |
| `window_class`      | only handle a new window whose class/instance contains this (case-insensitive) |
| `terminal_below`    | open a second terminal below the window, see below                          |

#### `terminal_below`

Opens a second terminal under the application's window (i3 vertical split), then gives the
focus back to the application. Use `true` for an interactive shell in the entry's `cwd`, or an
object where every key is optional:

| key       | default                    | meaning                                    |
|-----------|----------------------------|--------------------------------------------|
| `command` | interactive shell          | command run in the lower terminal          |
| `cwd`     | the entry's `cwd`          | directory the command starts in            |
| `height`  | i3's 50/50 split           | `"35%"` or pixels (`"400"`, `"400px"`)       |

```json
{"type": "claude", "cwd": "~/projects/app", "terminal_below": true}
{"type": "claude", "cwd": "~/projects/app",
 "terminal_below": {"command": "make watch", "height": "30%"}}
```

The terminal closes when `command` exits. To keep a shell open afterwards, end with one, e.g.
`"command": "git status; exec $SHELL"`. `terminal_below` cannot be combined with `floating`.
Applications that only raise an already-running instance open no new window, so nothing is
split.

### `claude` / `copilot`

Starts [Claude Code](https://claude.com/claude-code) (`claude`) or GitHub Copilot CLI
(`copilot`) in a terminal in a project directory, on its own workspace.

| key      | meaning                                                                 |
|----------|-------------------------------------------------------------------------|
| `cwd`    | project directory (required)                                            |
| `resume` | session to resume (`--resume=<session>`)                                |

The label defaults to `claude | <dir>` and the workspace to `claude [<dir>]` (`copilot` the
same). `env`, `id`, `floating*`, `window_class` and `terminal_below` work as for `start_app`.

### `start_apps`

Starts several `start_app`/`claude`/`copilot` entries, 2 seconds apart.

| key       | meaning                              |
|-----------|--------------------------------------|
| `entries` | list of entry `id`s (required)       |

### `open_web`

Opens a URL.

| key                    | meaning                                  |
|------------------------|------------------------------------------|
| `url`                  | the URL (required)                       |
| `browser`              | omitted: the system's default browser; `"firefox"`: a new Firefox tab (`firefox --new-tab`); anything else: a command line the URL is appended to, e.g. `"chromium --new-window"` |
| `include_url_in_label` | show the URL after `entry_label`         |

### `web_list`

A sub-menu of URLs. `browser`, `workspace`, `include_url_in_label` and
`include_workspace_in_label` apply to all of them.

| key    | meaning                                                                           |
|--------|-----------------------------------------------------------------------------------|
| `urls` | list of `{"url": ..., "label": ..., "subgroup": ...}`; `label` and `subgroup` are optional, URLs with the same `subgroup` get their own sub-menu |

### `open_pdf`

A sub-menu of all PDFs found (recursively) under the search paths. If a `.nfo` file with the
same name sits next to a PDF, its text is shown in the label. Folders inside your home directory
are shown relative to it, others with their full path.

| key            | meaning                                |
|----------------|----------------------------------------|
| `search_paths` | list of directories (`~` is expanded)  |
| `executable`   | PDF viewer, e.g. `"okular"`            |

### `i3_command`

| key       | meaning                                                                    |
|-----------|----------------------------------------------------------------------------|
| `command` | `"move_workspaces"`: move workspaces to outputs, then return to the current workspace |
| `data`    | `{"<workspace>": "<output>"}`, e.g. `{"1": "DP-1", "2": "HDMI-A-1"}`       |

## Development

```sh
uv run --extra dev pytest
```

The tests mock i3, so they run without it. Window handling (floating, `terminal_below`) is
checked by hand in i3.
