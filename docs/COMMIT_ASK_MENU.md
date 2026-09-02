# `--commit-ask` Interactive Menu

`--commit-ask` walks the same dirty repos the report showed (respecting `--limit`,
newest first) and shows an arrow-key menu per repo. This documents every menu entry.
For the flag itself and its requirements, see
[COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md).

Needs an interactive terminal and a non-empty `commit_command` in settings (see
[SETTINGS.md](SETTINGS.md)); the submenu's *Open in file explorer* additionally needs
`file_explorer` and *Rename repo* needs `rename_prefix`, both optional — without them
every other entry still works.
Currently-muted repos, and repos already settled within the `min_visit_age` window (1 hour
by default), are dropped **before** the scan: they cost no git call and are reported as a
single `Skipped N repo(s) without scanning` line at the end (`--debug` names each one).
Repos changed more recently than the optional `min_modified_age` setting allows are still
scanned and listed, labelled `[changed 12 minutes ago]`. None of them count against
`--limit`.

Navigate with the arrow keys and confirm with Enter; Ctrl-C leaves the tool. There are no
letter keys to type — the menus are rendered by [`pick`](https://github.com/wong2/pick)
(see `menu.py`, the only module that imports it).

Each menu takes the whole screen and hands it back afterwards, which is why an entry that
prints something waits for Enter first — otherwise the next menu would cover the output
before it could be read.

`menu.py` drives `pick` on its **blessed** backend rather than the default curses one.
On Windows, a child process that inherits the console (`git pull`, the commit command)
permanently stops curses translating the arrow keys: they still arrive, but as raw
`ESC [ A` sequences that `pick` ignores, so the next menu draws and then accepts nothing.
blessed decodes those sequences itself, so the subprocesses keep the console and their
live output. The unit tests replace the menu helper, so a real menu is only exercised by
`tools\menu_smoke.bat` — run it by hand after touching `menu.py`.

## Top menu

```
<repo path>  -  <N> uncommitted

 > Commit
   More actions...
   Skip
   Abort
```

| Entry | Action |
|-------|--------|
| Commit | Run the configured `commit_command` in this repo's directory (output streams live). Then move to the next repo. |
| More actions... | Open the **more** submenu (below). |
| Skip | Skip this repo; move to the next. |
| Abort | Abort the loop. No further repos are touched. |

**Being shown** a repo's menu records a visit, so `min_visit_age` holds that repo back on
the next run. The visit is written *before* the menu is drawn, so Commit, Skip, Mute, a
submenu action, *Abort* and Ctrl-C all count — you were shown the repo either way, and
otherwise the one you keep bailing out of would greet you on every single run. Repos further
down the list that the loop never reached are not recorded.

A repo the scan found **nothing to commit** in is recorded the same way, during the walk
itself. There is nothing left to ask about it, so re-scanning it on every run is pure cost —
this is what makes an interrupted run still shorten the next one. A repo with changes is
never recorded by the walk: it is settled only once its menu comes up.

## More submenu

```
<repo path>  -  more actions

 > Age of changed files
   List changed files
   Remote url
   Pull
   Open in file explorer
   Rename repo
   Stash changes
   Mute repo
   Back
```

Entries that print something wait for Enter before the next menu repaints the screen.

| Entry | Action |
|-------|--------|
| Age of changed files | Show the modification date of each changed file. When every changed file shares the same date, it collapses to one line (e.g. `All 5 files: 22.08.2026`); otherwise each file is listed with its date. Returns to the submenu. |
| List changed files | List the changed files in this repo — the same set that was counted (see [SCANNING.md](SCANNING.md)). Returns to the submenu. |
| Remote url | Show this repo's remotes — name and fetch URL, one line each (`git remote -v`, push duplicates dropped). Prints `(no remote)` when the repo has none. Returns to the submenu. |
| Pull | Run `git pull --no-edit` in this repo (live output; `--no-edit` keeps a merge commit out of the git editor). Use it to fast-forward before committing. A plain pull — if it can't proceed (e.g. local changes conflict) it fails loudly and nothing else is touched. Returns to the submenu. The same `repo_actions.run_pull` [`--pull-ask`](PULL_ASK.md) uses, so both behave identically. |
| Open in file explorer | Open this repo in the configured file manager (`file_explorer` in settings). Launched detached, so the prompt comes straight back — the file manager stays open as long as you want it. Without `file_explorer` set it just says so and changes nothing. Returns to the submenu. |
| Rename repo | Rename this repo's folder to `<rename_prefix><name>` (e.g. `project` -> `_old_project`). Point `rename_prefix` at one of your `ignore_prefixes` and the folder drops out of the next scan. Refuses (and returns to the submenu) when `rename_prefix` is unset, the name already starts with it, the target exists, or the rename fails. On success the repo is consumed — the loop moves to the next one. |
| Stash changes | Stash this repo's changes: `git stash push -u -m "<YYYY_MM_DD> GIT REPO STATUS TOOL"`. `-u` includes untracked files, so the repo is fully clean afterwards and does not come back dirty in the next scan. The message is fixed (today's date + the tool marker) — not configurable. On success the repo is consumed — nothing is left to commit, so the loop moves to the next one. A failed stash returns to the submenu. Restore with `git stash pop` in that repo. |
| Mute repo | Mute this repo, then pick a timeframe from a menu: 1 day / 1 week / 1 month, or *Custom duration...* which asks for typed input like `4h` / `3d` / `2w`. The repo is listed but not prompted for in future `--commit-ask` runs until the mute expires (`1m` = 30 days). Returns to the loop (moves to the next repo). |
| Back | Back to the top menu for this repo. |

The read-only entries (age, list, url, pull, explorer) act and re-show the submenu — they
never consume the repo, and neither does a refused rename or a failed stash. Only *Commit* (top menu) commits; only
*Mute repo* mutes; only a successful rename renames; only a successful stash stashes.

## See also

- [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md) — all flags, including `--list-muted`.
- [PULL_ASK.md](PULL_ASK.md) — `--pull-ask`, which finds repos behind their remote rather
  than repos with local changes, and keeps its own mutes.
- [SETTINGS.md](SETTINGS.md) — the `commit_command`, `file_explorer`, `rename_prefix`
  and `min_modified_age` keys.
- [CODEX.md](CODEX.md) — commit-with-Codex `commit_command` examples.
