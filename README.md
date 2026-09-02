# git-repo-status-check

CLI that scans configured root folders (e.g. `D:\GIT`) for git repositories with
uncommitted changes and reports which repos are dirty and how many files are uncommitted
in each. Submodules are checked individually.

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- `git` on your PATH

## Setup

```bat
install.bat
```

Copy `settings.example.json` to `settings.json` and set your folders:

```json
{
  "folders": [
    "D:\\GIT"
  ],
  "commit_command": "codex --yolo \"git commit and push\"",
  "file_explorer": "explorer \"[[REPO_PATH]]\"",
  "ignore_prefixes": ["_old_"],
  "rename_prefix": "_old_",
  "min_modified_age": "1h",
  "min_visit_age": "1h"
}
```

Only `folders` is required. `commit_command` powers `--commit-ask`, `file_explorer` is the
file manager its `e` action opens a repo in (`[[REPO_PATH]]` is replaced with the repo path),
`ignore_prefixes` prunes folders by name prefix while scanning, `rename_prefix` is the
prefix its `r` action renames a repo folder with (archiving it out of the next scan), and
`min_modified_age` holds `--commit-ask` back from repos touched within that window
(someone is probably still working there), and `min_visit_age` (default `1h`, `null` to
disable) stops `--commit-ask` re-prompting for a repo whose menu you already saw — see
[docs/SETTINGS.md](docs/SETTINGS.md).

Each entry of `folders` is a root folder. The scanner walks each root recursively, stops descending
once it finds a git repo, and (if a repo has a `.gitmodules`) also checks each submodule.

## Usage

```bat
start.bat
```

Shortcuts for the interactive menus (all forward extra arguments, e.g. `--limit 10`):

```bat
start_commit-ask.bat
start_commit-ask_all.bat
start_pull-ask.bat
```

or directly:

```bat
uv run python main.py [--settings PATH] [--limit N] [--commit-ask] [--pull-ask] [--all]
                      [--fix-line-endings] [--list-muted] [--debug]
```

- `--settings PATH` — use a settings file other than `settings.json` in the project root
  (also overridable via the `GIT_REPO_STATUS_SETTINGS` environment variable).
- `--limit N` — show at most `N` repos (newest changes first); summary still reports the true total.
  With `--commit-ask`, `N` counts only repos that are actually prompted for.
- `--commit-ask` — after the report, show an arrow-key menu per dirty repo
  (**Commit / More actions... / Skip / Abort**): arrow keys to move, Enter to confirm,
  Ctrl-C to leave. *Commit* runs the `commit_command` from settings in that repo's directory.
  *More actions...* opens a submenu (age of changed files / list changed files / remote url /
  pull / open in file explorer / rename repo / stash changes / mute repo / back).
  *Rename repo* prefixes the repo folder with `rename_prefix` so it drops out of the next scan;
  *Stash changes* runs `git stash push -u` with a `<YYYY_MM_DD> GIT REPO STATUS TOOL` message.
  Muting picks a timeframe (1 day / 1 week / 1 month, or a typed custom value like
  `4h` / `3d` / `2w`). Muted repos are not prompted for until the mute expires; neither are
  repos whose menu you already left by any route but *Abort* within `min_visit_age`
  (default 1 hour, so a quick re-run only asks about what is left), nor
  repos changed more recently than the optional
  `min_modified_age` setting allows; all three stay in the report with a `[muted for 2 days]` /
  `[seen 10 minutes ago]` / `[changed 12 minutes ago]` label and do not count against `--limit`.
  Requires a non-empty `commit_command` (aborts before scanning if unset)
  and an interactive terminal.
- `--pull-ask` — the other direction: fetch every repo and show a menu
  (**Pull / Skip / Mute repo / Abort**) for each one that is *behind* its upstream, most
  stale first. Repos with no tracking branch are skipped silently. Muted repos, and ones
  whose menu you already saw within `min_visit_age`, are dropped *before* the fetch — so a
  re-run only checks what you have not dealt with yet. Its mutes and visits are separate
  from `--commit-ask`'s. See [docs/PULL_ASK.md](docs/PULL_ASK.md).
- `--all` — with `--commit-ask` or `--pull-ask`, prompt for every repo, ignoring mutes,
  `min_visit_age` and `min_modified_age`. Mutes are kept, just not honored for this run.
- `--fix-line-endings` — offer to repair each repo whose only changes are line-ending
  noise, by setting its local `core.autocrlf`. Nothing is committed or rewritten on disk.
- `--list-muted` — list repos currently muted (commit mutes and pull mutes, in separate
  sections) and the date each is muted until, then exit.
- `--debug` — enable diagnostic logging.

See [docs/COMMAND_LINE_ARGUMENTS.md](docs/COMMAND_LINE_ARGUMENTS.md),
[docs/COMMIT_ASK_MENU.md](docs/COMMIT_ASK_MENU.md) (the `--commit-ask` menu),
[docs/PULL_ASK.md](docs/PULL_ASK.md) (the `--pull-ask` mode),
[docs/SETTINGS.md](docs/SETTINGS.md), and [docs/CODEX.md](docs/CODEX.md) (commit-with-Codex
examples) for details.

Output lists each dirty repo with its uncommitted file count, then a summary:

```
D:\GIT\some\repo  —  3 uncommitted files
  submodule D:\GIT\some\repo\vendor  —  1 uncommitted file

Summary: 1 dirty repo(s)
```

"Uncommitted" counts every `git status --porcelain` entry: modified, staged, and
untracked files — except changes that are only a CR at end of line, which are dropped as
CRLF/LF noise (see [docs/SCANNING.md](docs/SCANNING.md)).

## Troubleshooting

**A repo is reported dirty but `git diff` shows nothing meaningful.** Almost always CRLF/LF
noise: the file was committed with LF endings and an editor rewrote it with CRLF, so git calls it
modified. Those entries are filtered out of the count — run with `--debug` to see how many were
ignored per repo:

```
DEBUG git_repo_status_check: D:\GIT\some\repo: ignored 48 line-ending-only change(s)
```

To stop git itself from reporting them, run `--fix-line-endings`: it offers to set each such
repo's local `core.autocrlf` to a value that makes git agree with the index again, without
committing or rewriting anything.

If a repo still looks wrong, check it by hand — `git -C <repo> diff --name-only --ignore-cr-at-eol`
lists only the genuinely edited files. See [docs/SCANNING.md](docs/SCANNING.md) for the exact rule.

**A repo is missing from the report.** Check `ignore_prefixes` in your settings, and that the repo
is not nested inside another repo (the walk stops at the first `.git` it finds) or under a pruned
folder like `node_modules`.

## Tests

```bat
tools\run_tests.bat              REM unit tests
tools\run_integration_tests.bat  REM integration tests (creates real temp git repos)
tools\menu_smoke.bat             REM manual: the arrow-key menus in a real terminal
```

`menu_smoke.bat` is not part of the automated suites — the unit tests replace the menu
helper, so nothing else drives a real menu. Run it by hand after touching
`src/git_repo_status_check/menu.py`.

## Dependencies

Runtime: `SQLAlchemy` (stores `--commit-ask` and `--pull-ask` mutes in a SQLite `mutes.db`) and
`pick[blessed]` (the arrow-key menus). Everything else is the Python standard
library. Dev tooling: `ruff`, `mypy`, `pytest`.
