# Command Line Arguments

`main.py` (or `start.bat`) accepts the following arguments. All are optional.

```
uv run python main.py [--settings PATH] [--limit N] [--commit-ask] [--list-muted] [--debug]
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

## `--commit-ask`

After the report, walk the same dirty repos it showed (respecting `--limit`, newest first)
and prompt for each: `[c]ommit / [m]ore / [s]kip / [a]bort`.

- `c` — run the configured `commit_command` in that repo's directory (output streams live).
- `m` — open a submenu of secondary actions:
  `[a]ge of files / [l]ist files / [p]ull / [m]ute / [b]ack`.
  - `a` — show the modification date of each changed file. When every changed file shares
    the same date, it collapses to one line (e.g. `All 5 files: 22.08.2026`); otherwise each
    file is listed with its date.
  - `l` — list the changed files in this repo (`git status --short`), then prompt again.
  - `p` — run `git pull` in this repo (live output), then prompt again. Use it to
    fast-forward before committing. A plain pull — if it can't proceed (e.g. local
    changes conflict) it fails loudly and nothing else is touched.
  - `m` — mute this repo, then pick a timeframe (`1d` / `1w` / `1m` or a custom value like
    `3d` / `2w`). The repo is silently skipped in future `--commit-ask` runs until the mute
    expires (`1m` = 30 days).
  - `b` — back to the top prompt.
- `s` — skip this repo.
- `a` — abort the loop; no further repos are touched.

See [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) for the full menu reference.

Requires a non-empty `commit_command` in settings.json (see
[SETTINGS.md](SETTINGS.md)); without it the tool prints an error and exits 1 **before
scanning**. Needs an interactive terminal — with piped/redirected stdin it prints a notice
and does nothing. For Codex usage examples, see [CODEX.md](CODEX.md).

Mutes are stored in a `mutes.db` SQLite file in the project root (gitignored, machine-local).

```bat
uv run python main.py --commit-ask
```

## `--list-muted`

List repos currently muted (via the `--commit-ask` `m` choice) and the date each is muted
until, soonest expiry first, then exit. Does not scan and does not need a `commit_command`.
Expired mutes are not shown. Prints `No muted repos.` when none are active.

```bat
uv run python main.py --list-muted
```

```
D:\GIT\some\repo  -  muted until 2026-08-31 08:41
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
