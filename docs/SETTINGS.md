# Settings

Configuration lives in a JSON file, by default `settings.json` in the project root.

## Location

The settings path is resolved in this order (see
[COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)):

1. `--settings PATH` command-line argument
2. `GIT_REPO_STATUS_SETTINGS` environment variable
3. `settings.json` next to `main.py` (default)

`settings.json` is git-ignored — it holds your machine-specific folder paths. A committed
`settings.example.json` documents the format.

## First run

If no settings file exists at the resolved path, the tool writes a `settings.example.json`
template next to it and exits with a message. Copy it to `settings.json` and edit.

```bat
copy settings.example.json settings.json
```

## Format

A JSON object with a required `folders` key (a non-empty list of root folder paths), an
optional `commit_command` key used by `--commit-ask`, an optional `file_explorer` key
for its `e` menu action, an optional `rename_prefix` key for its `r` menu action, an
optional `ignore_prefixes` key that skips folders by name prefix during scanning, and an
optional `min_modified_age` key that holds `--commit-ask` back from freshly-touched repos,
and an optional `min_visit_age` key that stops either ask-mode re-checking a repo it just
settled.

```json
{
  "folders": [
    "D:\\GIT",
    "C:\\Users\\me\\projects"
  ],
  "commit_command": "codex --yolo \"git commit and push\"",
  "file_explorer": "explorer \"[[REPO_PATH]]\"",
  "rename_prefix": "_old_",
  "ignore_prefixes": ["_old_"],
  "min_modified_age": "1h",
  "min_visit_age": "1h"
}
```

### `folders`

- Type: list of strings (each a directory path). Required, must be non-empty.
- Each entry is a **root** folder; the tool scans it recursively for git repos (see
  [SCANNING.md](SCANNING.md)).
- On Windows, escape backslashes in JSON: `"D:\\GIT"`. Forward slashes also work:
  `"D:/GIT"`.

### `commit_command`

- Type: string. Optional; omit it if you don't use `--commit-ask`.
- The command run in each repo's directory when you choose *Commit* in the `--commit-ask` menu
  (see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)).
- Run via the shell with the working directory set to the repo, so the command needs no repo
  path of its own. Output streams live to the console.
- The `[[REPO_PATH]]` placeholder is `file_explorer`-only; it is **not** substituted here.
- If present it must be a non-empty string, or settings validation fails.

```json
{
  "folders": ["D:\\GIT"],
  "commit_command": "codex --yolo \"git commit and push using those guidelines D:\\GIT\\...\\commit-fast.md\""
}
```

### `file_explorer`

- Type: string. Optional; omit it if you don't use the `--commit-ask` `e` action.
- The command run when you choose *Open in file explorer* in the `--commit-ask` **more** submenu (see
  [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md)) to open the current repo in a file manager.
- `[[REPO_PATH]]` in the string is replaced with the repo's path. **Quote it yourself** —
  paths contain spaces: `"fman \"[[REPO_PATH]]\""`.
- Without `[[REPO_PATH]]`, the quoted repo path is appended, so a bare `"explorer"` works.
- Launched **detached** — the menu comes back immediately rather than waiting for the file
  manager to close. Nothing is reported about how it exits.
- If present it must be a non-empty string, or settings validation fails. If it is absent
  and you choose *Open in file explorer*, the tool says so and the loop carries on.

```json
{
  "folders": ["D:\\GIT"],
  "file_explorer": "fman \"[[REPO_PATH]]\""
}
```

### `rename_prefix`

- Type: string. Optional; omit it if you don't use the *Rename repo* action.
- The prefix prepended to a repo's **folder name** when you choose *Rename repo* — in the
  `--commit-ask` **more** submenu (see [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md)) or on the
  `--pull-ask` menu (see [PULL_ASK.md](PULL_ASK.md)):
  `D:\GIT\project` becomes `D:\GIT\_old_project`.
- `--pull-ask` hides the entry entirely when this is unset, since there would be nothing to
  rename to.
- Set it to one of your `ignore_prefixes` entries and the renamed folder is pruned from the
  next scan — that is the point of the action: archive a repo you no longer want prompted for.
- Only the folder is renamed; nothing inside the repo is touched, and the rename is undone by
  renaming the folder back.
- Refused (with a message, back to the submenu) when the name already starts with the prefix,
  when the target name already exists, or when the OS rejects the rename (e.g. a file in the
  repo is open). Nothing is overwritten.
- If present it must be a non-empty string, or settings validation fails. If it is absent and
  you choose *Rename repo* in the `--commit-ask` submenu, the tool says so and the loop carries on.

```json
{
  "folders": ["D:\\GIT"],
  "rename_prefix": "_old_",
  "ignore_prefixes": ["_old_"]
}
```

### `ignore_prefixes`

- Type: list of non-empty strings. Optional; defaults to none (no folders skipped).
- Any directory whose name **starts with** one of these prefixes is pruned from the scan
  walk — not descended into, not reported. Handy for archived trees like `_old_project`.
- Matching is **case-sensitive** and applies to the discovery walk only. A configured **root**
  in `folders` is chosen explicitly and is never filtered by a prefix; only subfolders
  encountered while walking are pruned.
- If present it must be a list of non-empty strings, or settings validation fails.

```json
{
  "folders": ["D:\\GIT"],
  "ignore_prefixes": ["_old_", "archive_"]
}
```

### `min_modified_age`

- Type: string duration. Optional; defaults to none (every dirty repo is prompted).
- Accepted forms: a positive integer plus a unit -- `h` (hours), `d` (days), `w` (weeks),
  `m` = 30 days. Examples: `"1h"`, `"4h"`, `"3d"`, `"2w"`. Note `m` means **months, not
  minutes**, matching the mute timeframes.
- When set, `--commit-ask` does not prompt for any repo whose **newest** changed file was
  modified less than this long ago -- someone is probably still working there, and a
  commit-and-push would land mid-edit.
- Affects `--commit-ask` only. The repo still appears in the report, labelled
  `[changed 12 minutes ago]`, and it does not count against `--limit`.
- A repo where no changed file has a readable modification time (e.g. only deletions) is
  still prompted.
- If present it must parse as a duration, or settings validation fails.

```json
{
  "folders": ["D:\\GIT"],
  "commit_command": "...",
  "min_modified_age": "1h"
}
```

### `min_visit_age`

- Type: string duration, or `null`. Optional; **defaults to `"1h"`** — unlike every other
  optional key, this one is on unless you turn it off.
- Same accepted forms as `min_modified_age`: a positive integer plus `h` / `d` / `w` /
  `m` (= 30 days). Examples: `"30m"` is *30 months*, not 30 minutes — there is no minute unit.
- A repo is recorded as *settled* two ways. Either its menu was shown to you (the visit is
  written before the menu is drawn, so *Abort* and Ctrl-C count too; repos further down the
  walk that you never reached do not), or the walk found nothing to ask about it: no uncommitted changes for `--commit-ask`, nothing to pull for
  `--pull-ask`. For this long afterwards that repo is left alone, so re-running the tool a
  few minutes later only covers what you have not already dealt with.
- **Affects `--commit-ask` and `--pull-ask` the same way**: a settled repo is dropped
  **before** the git call, so it is not listed at all. You get one
  `Skipped N repo(s) without scanning` / `without fetching` line instead, and `--debug`
  names each skipped repo. That is where the runtime of a re-run goes, in both modes.
- Set it to `null` to switch the behaviour off and be prompted for every repo every run.
  `"0h"` is **not** accepted (durations must be positive) — `null` is the off switch.
- Visits are stored per repo path in `mutes.db` next to `main.py`, in tables separate from
  the mutes: they never show up in `--list-muted`, and an explicit mute always wins the
  reason. Each mode has its own visit table, so answering for a repo in one does not silence
  it in the other.
- If present it must parse as a duration or be `null`, or settings validation fails.

```json
{
  "folders": ["D:\GIT"],
  "commit_command": "...",
  "min_visit_age": "1h"
}
```

## Validation

Settings are validated on load; the tool fails fast with a clear message when:

- the file is not valid JSON,
- there is no `folders` key, or it is not a non-empty list,
- a `folders` entry is not a string,
- **none** of the listed folders exist,
- `commit_command`, `file_explorer` or `rename_prefix` is present but is not a non-empty
  string,
- `ignore_prefixes` is present but is not a list of non-empty strings,
- `min_modified_age` or `min_visit_age` is present but is neither a parsable duration
  string (e.g. `"1h"`) nor `null`.

A listed folder that does not exist is **skipped with a warning** (visible with `--debug`), as
long as at least one folder is valid. This lets one shared settings file cover multiple machines
where some roots are absent.

## Example: per-machine settings via environment variable

```bat
set GIT_REPO_STATUS_SETTINGS=C:\configs\git-roots.json
uv run python main.py
```
