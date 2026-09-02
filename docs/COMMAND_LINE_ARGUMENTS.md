# Command Line Arguments

`main.py` (or `start.bat`) accepts the following arguments. All are optional.

```
uv run python main.py [--settings PATH] [--limit N] [--commit-ask] [--pull-ask] [--all]
                      [--fix-line-endings] [--list-muted] [--debug]
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

The file is a JSON object with a required `folders` list of root paths to scan, plus the
optional `commit_command`, `file_explorer`, `rename_prefix`, `ignore_prefixes` and
`min_modified_age` keys (see [SETTINGS.md](SETTINGS.md)):

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
- With `--commit-ask`, `N` counts only repos that will actually be prompted for. Repos
  below `min_modified_age` are still listed (labelled, see below) but do not use up a
  slot, so `--limit 10` always yields 10 repos to act on. Muted and already-settled repos
  are not scanned at all, so they never reach this listing:

  ```
  D:\GIT\sps-station-client  -  15 uncommitted files  [changed 12 minutes ago]
  D:\GIT\some\repo  -  4 uncommitted files
  ```

```bat
uv run python main.py --limit 10
```

## `--commit-ask`

After the report, walk the same dirty repos it showed (respecting `--limit`, newest first)
and show an arrow-key menu for each: **Commit / More actions... / Skip / Abort**. Navigate
with the arrow keys, confirm with Enter, leave with Ctrl-C — nothing is typed.

- **Commit** — run the configured `commit_command` in that repo's directory (output streams live).
- **More actions...** — open a submenu: age of changed files / list changed files / remote
  url / pull / open in file explorer / rename repo / stash changes / mute repo / back.
  - *Age of changed files* — show the modification date of each changed file. When every changed file shares
    the same date, it collapses to one line (e.g. `All 5 files: 22.08.2026`); otherwise each
    file is listed with its date.
  - *List changed files* — list the changed files in this repo — the same set that was counted, so
    line-ending-only changes are absent — then show the submenu again.
  - *Pull* — run `git pull --no-edit` in this repo (live output), then show the submenu again.
    Use it to fast-forward before committing. A plain pull — if it can't proceed (e.g. local
    changes conflict) it fails loudly and nothing else is touched. `--no-edit` keeps a merge
    commit from opening the git editor over the menu.
  - *Open in file explorer* — open this repo in the file manager configured as `file_explorer`, launched
    detached so the prompt returns right away, then show the submenu again.
  - *Rename repo* — rename this repo's folder to `<rename_prefix><name>` (e.g. `_old_project`), so
    a matching `ignore_prefixes` entry keeps it out of the next scan. The repo is
    consumed; a refused rename returns to the submenu.
  - *Stash changes* — `git stash push -u` this repo's changes (untracked included) under the message
    `<YYYY_MM_DD> GIT REPO STATUS TOOL`. The repo is consumed — it is clean afterwards, so
    there is nothing left to commit; a failed stash returns to the submenu.
  - *Mute repo* — mute this repo, then pick a timeframe from a menu (1 day / 1 week / 1 month, or
    *Custom duration...* which asks for typed input like `4h` / `3d` / `2w`). The repo is still listed but no longer prompted for in
    future `--commit-ask` runs until the mute expires (`1m` = 30 days).
  - *Back* — back to the top menu.
- **Skip** — skip this repo.
- **Abort** — abort the loop; no further repos are touched.

See [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) for the full menu reference.

Requires a non-empty `commit_command` in settings.json (see
[SETTINGS.md](SETTINGS.md)); without one the tool prints an error and exits 1 **before
scanning**. The submenu's *Open in file explorer* additionally needs `file_explorer` and *Rename repo*
needs `rename_prefix`, but both settings are optional — without them only those actions are
unavailable. Needs an interactive terminal — with piped/redirected stdin it prints a
notice and does nothing. For Codex usage examples, see [CODEX.md](CODEX.md).

Muted repos, and repos already settled within `min_visit_age` (you answered their menu, or
a previous scan found nothing to commit), are dropped **before** the scan: they cost no git
call and are reported as a single `Skipped N repo(s) without scanning` line (`--debug` names
each one). Repos whose newest changed file is younger than the optional `min_modified_age`
setting are still scanned and listed with a `[changed 12 minutes ago]` label, just not
prompted for, and do not count against `--limit`. Pass `--all` to prompt for all of them
anyway. See [SETTINGS.md](SETTINGS.md).

Mutes and visits are stored in a `mutes.db` SQLite file in the project root (gitignored,
machine-local).

```bat
uv run python main.py --commit-ask
```

## `--pull-ask`

Fetch every repo under the configured folders and show a menu — **Pull / Stash changes and
pull / Rename repo / Skip / Mute repo / Abort** — for each one that is *behind* its upstream, as the walk
finds it. Repos with no tracking branch (detached HEAD, unpushed branch, no remote) are
skipped silently.

This is the opposite question from the rest of the tool: `--commit-ask` is about local
changes you have not pushed, `--pull-ask` is about remote changes you have not pulled. It
does its own walk because it has to fetch, and it needs no `commit_command`.

Repos it should not re-check are dropped **before** the fetch, not after: muted ones, and
ones already settled within `min_visit_age` (default `1h`) — either because you answered
their menu, or because a previous fetch found nothing to pull. Those cost no network
at all and are reported as a single `Skipped N repo(s) without fetching` line — which is what
makes a re-run take seconds instead of minutes. `--debug` names each skipped repo.

Its mutes and visits are stored separately from `--commit-ask`'s, so muting or answering for
a repo here does not silence it there. Needs an interactive terminal.

**See [PULL_ASK.md](PULL_ASK.md) for the full description of the mode and its menu.**

```bat
uv run python main.py --pull-ask
```

```
D:\GIT\some\repo  -  4 commit(s) behind origin/main  -  3 uncommitted

 > Pull
   Stash changes and pull
   Rename repo
   Skip
   Mute repo
   Abort
```

*Stash changes and pull* is offered only on a repo with local changes: it runs the same
`git stash push -u` as the `--commit-ask` submenu, then pulls. A failed stash cancels the
pull. *Rename repo* is offered only when `rename_prefix` is configured: same rename as that
submenu (`<rename_prefix><name>`), and the renamed repo is not pulled.

A failed pull (or a failed stash) shows this same menu again for the same repo instead of
moving on — the usual cause is local changes in the way, and *Stash changes and pull* is the
answer to it. *Skip* leaves the repo alone.

## `--all`

Ignore every skip filter for this run: `--commit-ask` scans and prompts for all repos,
including muted ones, ones settled within `min_visit_age`, and ones changed within
`min_modified_age`. Repos it checks are still recorded — `--all` changes what is *honored*,
not what is written. Nothing is un-muted — the stored mutes are simply not honored this run,
so the next run without `--all` skips them again.

With `--pull-ask` it likewise ignores that mode's own mutes and visits, so every repo is
fetched again.

Only meaningful together with `--commit-ask` or `--pull-ask`; on its own the report already
lists every repo.
With `--limit N`, `N` now counts all repos, since none are held back.

```bat
uv run python main.py --commit-ask --all
```

## `--fix-line-endings`

Walk the configured folders and offer to repair every repo whose *only* uncommitted changes
are line-ending noise. Such repos never appear in the normal report (the filter empties
them), so this mode does its own walk. Needs an interactive terminal.

Per repo it prints the path and the number of phantom changes, then shows a menu:
**Fix line endings / Skip / Abort**. Choosing *Fix line endings* sets the repo's **local** `core.autocrlf` to
whichever value makes git agree with the index again, and refreshes the index's stale stat
data with `git add` on exactly those paths. Nothing is committed, no file on disk is
rewritten, and no `.gitattributes` is touched.

Which value is right depends on the repo, so both are tried and verified against real git
output. `git add` only ever runs once the diff confirms there is no content left to stage. If
no value works — a `.gitattributes` `text` rule outranks `core.autocrlf`, for instance — the
previous local setting is restored and the repo is reported as not auto-fixable.

```bat
uv run python main.py --fix-line-endings
```

```
D:\GIT\some\repo  -  12 line-ending-only change(s)

 > Fix line endings
   Skip
   Abort

  OK: core.autocrlf=true — 12 phantom change(s) gone.
```

## `--list-muted`

List repos currently muted (via either ask-mode's *Mute repo* action) and the date each is
muted until, soonest expiry first, then exit. Does not scan and does not need a
`commit_command`. Expired mutes are not shown. Prints `No muted repos.` when none are
active anywhere.

The two modes keep separate mutes, so both are listed under a heading each.

```bat
uv run python main.py --list-muted
```

```
Commit mutes (--commit-ask):
  D:\GIT\some\repo  -  muted until 2026-08-31 08:41
Pull mutes (--pull-ask):
  No muted repos.
```

## `--debug`

Enable diagnostic logging (scan progress, git errors) via `AppLogger`, printed to stderr.
Without it, only warnings and errors are logged. Does not affect the report output.

```bat
uv run python main.py --debug
```

This is also how you see which entries were dropped as line-ending noise
(see [SCANNING.md](SCANNING.md)):

```
DEBUG git_repo_status_check: D:\GIT\some\repo: ignored 48 line-ending-only change(s)
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
