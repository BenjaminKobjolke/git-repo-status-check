# `--commit-ask` Interactive Menu

`--commit-ask` walks the same dirty repos the report showed (respecting `--limit`,
newest first) and prompts per repo. This documents every menu choice. For the flag
itself and its requirements, see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md).

Needs an interactive terminal and a non-empty `commit_command` in settings (see
[SETTINGS.md](SETTINGS.md)); the `e` submenu key additionally needs `file_explorer` and `r`
needs `rename_prefix`, both optional — without them every other key still works.
Currently-muted repos are not prompted for, and neither are repos changed more recently than
the optional `min_modified_age` setting allows. Both are still listed in the report with a
`[muted for 2 days]` / `[changed 12 minutes ago]` label, and neither counts against
`--limit`.

## Top prompt

```
<repo path>  -  <N> uncommitted
  [c]ommit / [m]ore / [s]kip / [a]bort?
```

| Key | Action |
|-----|--------|
| `c` | Run the configured `commit_command` in this repo's directory (output streams live). Then move to the next repo. |
| `m` | Open the **more** submenu (below). |
| `s` | Skip this repo; move to the next. |
| `a` | Abort the loop. No further repos are touched. |

## More submenu

```
  [a]ge of files / [l]ist files / [p]ull / [e]xplorer / [r]ename / [m]ute / [b]ack?
```

| Key | Action |
|-----|--------|
| `a` | Show the modification date of each changed file. When every changed file shares the same date, it collapses to one line (e.g. `All 5 files: 22.08.2026`); otherwise each file is listed with its date. Re-prompts. |
| `l` | List the changed files in this repo — the same set that was counted (see [SCANNING.md](SCANNING.md)). Re-prompts. |
| `p` | Run `git pull` in this repo (live output). Use it to fast-forward before committing. A plain pull — if it can't proceed (e.g. local changes conflict) it fails loudly and nothing else is touched. Re-prompts. |
| `e` | Open this repo in the configured file manager (`file_explorer` in settings). Launched detached, so the prompt comes straight back — the file manager stays open as long as you want it. Without `file_explorer` set it just says so and changes nothing. Re-prompts. |
| `r` | Rename this repo's folder to `<rename_prefix><name>` (e.g. `project` -> `_old_project`). Point `rename_prefix` at one of your `ignore_prefixes` and the folder drops out of the next scan. Refuses (and re-prompts) when `rename_prefix` is unset, the name already starts with it, the target exists, or the rename fails. On success the repo is consumed — the loop moves to the next one. |
| `m` | Mute this repo, then pick a timeframe (`1d` / `1w` / `1m`, or custom like `4h` / `3d` / `2w`). The repo is listed but not prompted for in future `--commit-ask` runs until the mute expires (`1m` = 30 days). Returns to the loop (moves to the next repo). |
| `b` | Back to the top prompt for this repo. |

`a`, `l`, `p`, and `e` act and re-show the submenu — they never consume the repo, and
neither does a refused `r`. Only `c` (top prompt) commits; only `m` mutes; only a
successful `r` renames.

## See also

- [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md) — all flags, including `--list-muted`.
- [SETTINGS.md](SETTINGS.md) — the `commit_command`, `file_explorer`, `rename_prefix`
  and `min_modified_age` keys.
- [CODEX.md](CODEX.md) — commit-with-Codex `commit_command` examples.
