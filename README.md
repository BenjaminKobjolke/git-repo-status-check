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
  ]
}
```

Each entry is a root folder. The scanner walks each root recursively, stops descending
once it finds a git repo, and (if a repo has a `.gitmodules`) also checks each submodule.

## Usage

```bat
start.bat
```

or directly:

```bat
uv run python main.py [--settings PATH] [--debug]
```

- `--settings PATH` — use a settings file other than `settings.json` in the project root
  (also overridable via the `GIT_REPO_STATUS_SETTINGS` environment variable).
- `--debug` — enable diagnostic logging.

Output lists each dirty repo with its uncommitted file count, then a summary:

```
D:\GIT\some\repo  —  3 uncommitted files
  submodule D:\GIT\some\repo\vendor  —  1 uncommitted file

Summary: 1 dirty repo(s)
```

"Uncommitted" counts every `git status --porcelain` entry: modified, staged, and
untracked files.

## Tests

```bat
tools\run_tests.bat              REM unit tests
tools\run_integration_tests.bat  REM integration tests (creates real temp git repos)
```

## Dependencies

Runtime uses the Python standard library only. Dev tooling: `ruff`, `mypy`, `pytest`.
