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
optional `commit_command` key used by `--commit-ask`, and an optional `ignore_prefixes` key
that skips folders by name prefix during scanning.

```json
{
  "folders": [
    "D:\\GIT",
    "C:\\Users\\me\\projects"
  ],
  "commit_command": "codex --yolo \"git commit and push\"",
  "ignore_prefixes": ["_old_"]
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
- The command run in each repo's directory when you answer `c` at the `--commit-ask` prompt
  (see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)).
- Run via the shell with the working directory set to the repo, so the command needs no repo
  path of its own. Output streams live to the console.
- If present it must be a non-empty string, or settings validation fails.

```json
{
  "folders": ["D:\\GIT"],
  "commit_command": "codex --yolo \"git commit and push using those guidelines D:\\GIT\\...\\commit-fast.md\""
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

## Validation

Settings are validated on load; the tool fails fast with a clear message when:

- the file is not valid JSON,
- there is no `folders` key, or it is not a non-empty list,
- a `folders` entry is not a string,
- **none** of the listed folders exist,
- `ignore_prefixes` is present but is not a list of non-empty strings.

A listed folder that does not exist is **skipped with a warning** (visible with `--debug`), as
long as at least one folder is valid. This lets one shared settings file cover multiple machines
where some roots are absent.

## Example: per-machine settings via environment variable

```bat
set GIT_REPO_STATUS_SETTINGS=C:\configs\git-roots.json
uv run python main.py
```
