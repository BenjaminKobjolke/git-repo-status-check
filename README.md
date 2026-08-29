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
  "min_modified_age": "1h"
}
```

Only `folders` is required. `commit_command` powers `--commit-ask`, `file_explorer` is the
file manager its `e` action opens a repo in (`[[REPO_PATH]]` is replaced with the repo path),
`ignore_prefixes` prunes folders by name prefix while scanning, `rename_prefix` is the
prefix its `r` action renames a repo folder with (archiving it out of the next scan), and
`min_modified_age` holds `--commit-ask` back from repos touched within that window
(someone is probably still working there) — see [docs/SETTINGS.md](docs/SETTINGS.md).

Each entry of `folders` is a root folder. The scanner walks each root recursively, stops descending
once it finds a git repo, and (if a repo has a `.gitmodules`) also checks each submodule.

## Usage

```bat
start.bat
```

or directly:

```bat
uv run python main.py [--settings PATH] [--limit N] [--commit-ask] [--list-muted] [--debug]
```

- `--settings PATH` — use a settings file other than `settings.json` in the project root
  (also overridable via the `GIT_REPO_STATUS_SETTINGS` environment variable).
- `--limit N` — show at most `N` repos (newest changes first); summary still reports the true total.
  With `--commit-ask`, `N` counts only repos that are actually prompted for.
- `--commit-ask` — after the report, prompt `[c]ommit / [m]ore / [s]kip / [a]bort`
  per dirty repo and run the `commit_command` from settings in that repo's directory on `c`.
  `m` opens a submenu (age of files / list files / pull / explorer / rename / mute).
  `rename` prefixes the repo folder with `rename_prefix` so it drops out of the next scan.
  Muting takes a timeframe (`1d`/`1w`/`1m` or custom like `4h`/`3d`/`2w`). Muted repos are
  not prompted for until the mute expires, nor are repos changed more recently than the optional
  `min_modified_age` setting allows; both stay in the report with a `[muted for 2 days]` /
  `[changed 12 minutes ago]` label and do not count against `--limit`.
  Requires a non-empty `commit_command` (aborts before scanning if unset)
  and an interactive terminal.
- `--list-muted` — list repos currently muted and the date each is muted until, then exit.
- `--debug` — enable diagnostic logging.

See [docs/COMMAND_LINE_ARGUMENTS.md](docs/COMMAND_LINE_ARGUMENTS.md),
[docs/COMMIT_ASK_MENU.md](docs/COMMIT_ASK_MENU.md) (the `--commit-ask` menu),
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

If a repo still looks wrong, check it by hand — `git -C <repo> diff --name-only --ignore-cr-at-eol`
lists only the genuinely edited files. See [docs/SCANNING.md](docs/SCANNING.md) for the exact rule.

**A repo is missing from the report.** Check `ignore_prefixes` in your settings, and that the repo
is not nested inside another repo (the walk stops at the first `.git` it finds) or under a pruned
folder like `node_modules`.

## Tests

```bat
tools\run_tests.bat              REM unit tests
tools\run_integration_tests.bat  REM integration tests (creates real temp git repos)
```

## Dependencies

Runtime: `SQLAlchemy` (stores `--commit-ask` mutes in a SQLite `mutes.db`). Everything else
is the Python standard library. Dev tooling: `ruff`, `mypy`, `pytest`.
