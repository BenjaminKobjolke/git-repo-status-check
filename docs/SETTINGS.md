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

A JSON object with a single key, `folders`: a non-empty list of root folder paths to scan.

```json
{
  "folders": [
    "D:\\GIT",
    "C:\\Users\\me\\projects"
  ]
}
```

### `folders`

- Type: list of strings (each a directory path). Required, must be non-empty.
- Each entry is a **root** folder; the tool scans it recursively for git repos (see
  [SCANNING.md](SCANNING.md)).
- On Windows, escape backslashes in JSON: `"D:\\GIT"`. Forward slashes also work:
  `"D:/GIT"`.

## Validation

Settings are validated on load; the tool fails fast with a clear message when:

- the file is not valid JSON,
- there is no `folders` key, or it is not a non-empty list,
- a `folders` entry is not a string,
- **none** of the listed folders exist.

A listed folder that does not exist is **skipped with a warning** (visible with `--debug`), as
long as at least one folder is valid. This lets one shared settings file cover multiple machines
where some roots are absent.

## Example: per-machine settings via environment variable

```bat
set GIT_REPO_STATUS_SETTINGS=C:\configs\git-roots.json
uv run python main.py
```
