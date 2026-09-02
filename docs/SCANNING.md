# Scanning

How the tool finds git repositories and decides which ones are "dirty".

## What gets scanned

For each root folder listed in `settings.json` (see [SETTINGS.md](SETTINGS.md)), the tool walks
the directory tree looking for git repositories.

### Repo discovery

- The walk is **recursive** from each root.
- A directory is a git repo when it contains a `.git` entry (folder or file). A `.git` that is
  present but broken (a dead worktree/gitlink pointer, or an empty `.git` dir) is still picked
  up here, then skipped with a clear warning once git reports it is not a valid repo (see
  [Requirements](#requirements)).
- Once a repo is found, the walk **stops descending into it** — nested folders inside a repo
  are not re-scanned as separate repos (except submodules, see below).
- Certain noise directories are **never descended into** for speed:
  `node_modules`, `.venv`, `venv`, `__pycache__`, `.mypy_cache`, `.ruff_cache`.
- Folders whose name starts with any configured `ignore_prefixes` (see
  [SETTINGS.md](SETTINGS.md)) are also pruned from the walk. Matching is case-sensitive; a
  root listed in `folders` is never filtered this way, only subfolders found while walking.
  The `--commit-ask` `r` action renames a repo folder with the configured `rename_prefix`
  (see [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md)), which is how a repo is archived out of
  this walk — point `rename_prefix` at one of the `ignore_prefixes`.

So a layout like `D:\GIT\<org>\<repo>` is handled: the walk passes through `<org>` and reports
each `<repo>`.

### Repos the walk holds back

The two ask-modes (`--commit-ask`, `--pull-ask`) filter the walk itself. A repo is dropped
**before** it is announced on the progress line and before any git command runs, when either
rule holds:

- it is **muted** and the mute has not expired, or
- it was **already settled** within `min_visit_age` (see [SETTINGS.md](SETTINGS.md)).

A repo counts as settled two ways. Either its menu was shown to you — the visit is recorded
before the menu is drawn, so *Abort* and Ctrl-C count too — or the walk found nothing to ask
about it: no uncommitted changes for `--commit-ask`, nothing to pull for `--pull-ask`. Repos
further down the walk that you never reached are not recorded.

Held-back repos are not listed one by one; you get a single line at the end:

```
Skipped 243 repo(s) without fetching (muted, or seen within min_visit_age). Pass --all to check them anyway.
```

`--debug` names each one. `--all` ignores both rules for that run — what the walk *records*
is unaffected.

The filter lives inside the walk rather than being applied to its result on purpose: it is
what makes a re-run cheap, and announcing a repo the tool is about to drop would make an idle
re-run look exactly like a full scan. Plain report mode (no ask-mode flag) never filters and
never records — it is a passive listing, not a decision about any repo.

## What counts as "uncommitted"

A repo is reported as dirty when `git status --porcelain` returns any entries. The file count is
the number of porcelain lines, which includes:

- **Modified** tracked files (staged or unstaged)
- **Staged** additions/deletions/renames
- **Untracked** files (anything git would show as `??`)

Ignored files (per `.gitignore`) are **not** counted — porcelain does not list them by default.

A clean repo (no porcelain output) is not printed; it only contributes to the total scanned
but not to the dirty summary.

### Line-ending-only changes are excluded

A modified tracked file whose **only** difference is a CR at end of line does not count.

Why: with `core.autocrlf` off, a file committed with LF endings but sitting in the worktree with
CRLF endings is "modified" as far as git is concerned, even though nobody edited it. On Windows
this silently marks whole repos dirty — one repo in a real scan showed 130 such files and zero
actual edits.

How: after the porcelain listing, entries with a modification code (` M`, `M `, `MM`) are checked
against `git diff --name-only --ignore-cr-at-eol` (worktree and staged). A path that no longer
appears there is line-ending noise and is dropped. Nothing is written — no repo's `core.autocrlf`
or `.gitattributes` is touched — so the rule works the same in either direction (LF worktree over
CRLF blobs too).

The filter is deliberately narrow and fails safe:

- Untracked (`??`), added, deleted and renamed entries are never filtered.
- Every listing is read with `-z`, so both sides name a file identically: raw, unquoted,
  NUL-terminated. The line-based formats quote spaces and non-ASCII differently on each side,
  which used to leave those paths unmatchable and therefore unfiltered.
- If either diff command fails, nothing is filtered.
- A repo left with zero real changes drops out of the report entirely. Run with `--debug` to see
  a line naming how many entries were ignored per repo, or `--fix-line-endings` to repair
  those repos (see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)).

Because the count and the `--commit-ask` `[l]ist files` view come from the same filtered list,
the two always agree.

## Submodules

If a repo contains a `.gitmodules` file, its submodules are checked **individually**:

- Submodule paths are read directly from the `.gitmodules` file (the `path =` entries).
  This is tolerant of a `.gitmodules` that is inconsistent with the index — a case where
  `git submodule status` would abort with "no submodule mapping found in .gitmodules".
- A declared submodule that is not initialized/checked out (no `.git` in its folder) is
  skipped.
- Each initialized submodule is scanned with the same `git status --porcelain` rule.
- A dirty submodule is reported as its own row, tagged as a submodule and indented under the
  report, e.g.:

  ```
  D:\GIT\some\repo  -  3 uncommitted files
    submodule D:\GIT\some\repo\vendor  -  1 uncommitted file
  ```

Uninitialized submodules (no working tree checked out) contribute nothing.

## Ordering

Dirty repos are sorted **newest change first**. "Newest" is the most recent modification time
(`mtime`) among the repo's uncommitted files. The repo you touched most recently appears at the
top. Deleted files have no mtime and do not affect the ordering.

Use `--limit N` to show only the `N` most recently changed repos (see
[COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)).

This ordering covers the dirty report and `--commit-ask`. `--pull-ask` has no ordering: it
puts each repo to you the moment the fetch finds it behind, so there is never a complete list
to sort (see [PULL_ASK.md](PULL_ASK.md)).

## Requirements

- `git` must be on your `PATH`. If git is missing or a git command fails in a given repo, that
  repo is treated as having 0 uncommitted files and a warning is logged (visible with
  `--debug`); the scan continues.
- If a folder has a `.git` entry but git reports it is **not a valid git repository** (a broken
  gitlink/worktree pointer or an empty `.git`), the scan skips it with a concise warning —
  `<path>: .git present but not a valid git repository — skipping` — instead of dumping git's
  raw `fatal:` line.
