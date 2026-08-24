# Command Line Arguments

`main.py` (or `start.bat`) accepts the following arguments. All are optional.

```
uv run python main.py [--settings PATH] [--limit N] [--debug]
```

## `--settings PATH`

Path to the settings file to use instead of `settings.json` in the project root.

- Default: `settings.json` next to `main.py`.
- Also overridable via the `GIT_REPO_STATUS_SETTINGS` environment variable.
- Precedence: `--settings` > `GIT_REPO_STATUS_SETTINGS` > project-root `settings.json`.
- If the file does not exist, a `settings.example.json` template is written next to the
  expected path and the program exits with an error telling you to fill it in.

```bat
uv run python main.py --settings C:\configs\my-git-roots.json
```

The file is a JSON object with a `folders` list of root paths to scan:

```json
{
  "folders": [
    "D:\\GIT"
  ]
}
```

## `--limit N`

Show at most `N` repositories. Results are sorted newest-change-first, so `--limit` keeps
the `N` most recently changed repos.

- Default: no limit (all dirty repos printed).
- The summary line still reports the true total and notes the truncation:
  `Summary: 61 dirty repo(s) (showing 10)`.
- `N` larger than the number of dirty repos prints all of them with no `(showing …)` note.

```bat
uv run python main.py --limit 10
```

## `--debug`

Enable diagnostic logging (scan progress, git errors) via `AppLogger`, printed to stderr.
Without it, only warnings and errors are logged. Does not affect the report output.

```bat
uv run python main.py --debug
```

## `--help`

Standard argparse help, listing all arguments.

```bat
uv run python main.py --help
```

## Notes

- While scanning, a live `Scanning: <path>` line is shown on stderr and overwritten in
  place. It only appears when stderr is a terminal, so redirecting or piping output keeps it
  clean:

  ```bat
  uv run python main.py > dirty-repos.txt
  ```

- "Uncommitted" counts every `git status --porcelain` entry: modified, staged, and untracked
  files. Submodules of a repo (when it has a `.gitmodules`) are checked and reported
  individually.
