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

## What counts as "uncommitted"

A repo is reported as dirty when `git status --porcelain` returns any entries. The file count is
the number of porcelain lines, which includes:

- **Modified** tracked files (staged or unstaged)
- **Staged** additions/deletions/renames
- **Untracked** files (anything git would show as `??`)

Ignored files (per `.gitignore`) are **not** counted — porcelain does not list them by default.

A clean repo (no porcelain output) is not printed; it only contributes to the total scanned
but not to the dirty summary.

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

## Requirements

- `git` must be on your `PATH`. If git is missing or a git command fails in a given repo, that
  repo is treated as having 0 uncommitted files and a warning is logged (visible with
  `--debug`); the scan continues.
- If a folder has a `.git` entry but git reports it is **not a valid git repository** (a broken
  gitlink/worktree pointer or an empty `.git`), the scan skips it with a concise warning —
  `<path>: .git present but not a valid git repository — skipping` — instead of dumping git's
  raw `fatal:` line.
