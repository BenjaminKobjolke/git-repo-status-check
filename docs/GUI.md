# Desktop GUI

`gui.py` (or `start_gui.bat`) opens a PySide6 window with two tabs:

- **Run** — one button per mode (Scan, Commit ask, Pull ask, Push ask, Sync ask, Fix line
  endings, List muted), the `--all` and `--limit` switches, a log panel, and a prompt panel.
  Every menu the terminal would draw appears there as a row of buttons with the same labels;
  the custom mute duration is a text field. *Stop* ends the run at its next question.
- **Settings** — a form over every `settings.json` key (folders with a browse dialog,
  commit command, file explorer, rename prefix, ignore prefixes, the two age thresholds).
  *Save* writes the file, then loads it through the same validator the CLI uses and shows
  the result in a line under the button.

```bat
start_gui.bat [--settings PATH] [--debug]
```

`--settings` and `--debug` mean what they mean for `main.py` (see
[COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)). The bat runs `pythonw`, so no
console window opens; diagnostics go to the log panel instead.

## How it reuses the CLI

The modes are not reimplemented. They talk to the user through one small port,
`frontend.Frontend` (`src/git_repo_status_check/frontend.py`), with two implementations:

| Seam | Terminal (`menu.TerminalFrontend`) | Window (`gui/qt_frontend.py`) |
|---|---|---|
| menu | `pick`, blessed backend | a signal; the Run tab renders buttons; the click is queued back |
| typed answer | `input()` | a text field |
| pause | Enter to continue | no-op (the log keeps everything on screen) |
| live child process | inherits the console | captured line by line into the log, stdin closed, no console window |
| progress | one overwritten stderr line | the status bar |

A mode runs on a worker thread (`gui/worker.py`). When it calls `menu.choose`, the Qt
frontend emits what to show and blocks on a queue; the main thread shows the buttons, the
user clicks, the answer goes on the queue and the mode resumes. *Stop* (and closing the
window) put a cancel sentinel on that queue, so a blocked question raises `RunCancelled`
and the run ends with `Aborted.` — a run inside `git` finishes that command first.

`print()` and `AppLogger` output reach the log because the app installs `gui/log_stream.py`
as `sys.stdout` and `sys.stderr` before anything else starts. The orchestration itself
(`runner.py`: which mode, which stores, the sync stage order) is shared with `main.py`.

Because the child's stdin is closed, a remote that asks for credentials fails with git's
own message instead of hanging — configure a credential helper for such remotes.

## No console flashes

Under `pythonw` there is no console for a child to inherit, so Windows would give every
`git` call (and the `cmd.exe` behind the file-explorer launch) a console window of its own —
one flash per call, several per repo during a scan. Every child is therefore started with
`CREATE_NO_WINDOW` (`SUBPROCESS_NO_WINDOW` in `constants.py`, `0` off Windows): the captured
`scanner.run_git`, the explorer launch in `repo_actions.py`, and the window's `run_live`.
Only the terminal frontend's `run_live` (`menu.py`) inherits the console, on purpose — that
is where live output and credential prompts belong. `tests/unit/test_no_console_window.py`
pins the flag on the two captured paths.

## Localization

Every label goes through `gui/i18n.py` (`TK` key constants, `t()`), backed by
[python-localization](https://github.com/BenjaminKobjolke/python-localization) and the
JSON files in `lang/`. The language is the saved preference, else the OS language, else
English. To add one: copy `lang/en.json` to `lang/<code>.json` and translate the values —
a test checks every language file has exactly the English key set.

CLI wording (`constants.py`) is not localized; the GUI shows the modes' output verbatim.

## Theme

`gui/palette.py` holds every colour and spacing token; `gui/stylesheet.py` builds the one
application stylesheet from them (tests pin: no `min-width`/`min-height`, a `:focus` rule on
every focusable control, no colour literal outside the palette). Each tab sits in a
`QScrollArea`, so the window can be dragged to any size. On Windows the caption bar and
frame are themed through DWM (`gui/window_chrome.py`); elsewhere that call is a no-op.

## Tests

`tests/integration/test_gui_offscreen.py` renders the window with `QT_QPA_PLATFORM=offscreen`
(no display, no focus stealing): it shrinks the window to 200×200, saves both tabs as PNGs,
runs a real Scan over a temp repo through the worker, and drives Commit ask with a pre-fed
*Skip* to check the menu labels. Unit tests cover the frontend port, the queue hand-off,
the settings document and the theme rules.
