# Using with Codex

`--commit-ask` runs whatever you put in the `commit_command` setting once per dirty repo, with
the working directory set to that repo (see [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md)
and [SETTINGS.md](SETTINGS.md)). [Codex](https://github.com/openai/codex) is a natural fit: it
can read a commit-guidelines file and do the commit + push for you.

## Setup

Add a `commit_command` to `settings.json`:

```json
{
  "folders": ["D:\\GIT"],
  "commit_command": "codex --yolo \"git commit and push using those guidelines D:\\GIT\\BenjaminKobjolke\\claude-code\\commands\\git\\commit-fast.md\""
}
```

The command needs no repo path of its own — it runs *inside* the repo's directory, so `codex`
acts on the current repo.

## Run it

```bat
uv run python main.py --commit-ask
```

For each dirty repo you get `[c]ommit / [m]ore / [s]kip / [a]bort`:

- `c` — run the `commit_command` in that repo (Codex's output streams live to your terminal).
- `m` — secondary actions (file ages, file list, pull, open in your file manager, mute);
  see [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md).
- `s` — skip this repo.
- `a` — stop; no further repos are touched.

Combine with `--limit` to only walk the most recently changed repos:

```bat
uv run python main.py --commit-ask --limit 10
```

## `codex --yolo` vs `codex exec`

Two Codex modes, and they behave differently here:

| Command | Behavior | Use when |
|---------|----------|----------|
| `codex --yolo "<prompt>"` | Interactive TUI. You **see** everything Codex does. Skips approval prompts. | You want to watch the commit happen (default). |
| `codex exec --dangerously-bypass-approvals-and-sandbox "<prompt>"` | Non-interactive. Runs the prompt and exits — less to look at. | Fully headless, no watching. |

Note on `--yolo`: because it opens an interactive session, it may not return to the `--commit-ask`
prompt on its own after the commit — you may have to close/exit the Codex session to move to the
next repo. `codex exec` returns automatically but shows less. Pick per your preference.

`--yolo` is a Codex convenience alias for "skip approvals"; it is not a flag of `codex exec`. For
the non-interactive form use `--dangerously-bypass-approvals-and-sandbox` as shown above.

## Example prompts

Point Codex at a guidelines file (recommended — keeps commit style consistent):

```
codex --yolo "git commit and push using those guidelines D:\GIT\...\commit-fast.md"
```

Or inline instructions, no file:

```
codex --yolo "stage all changes, write a concise conventional-commit message, commit and push"
```

## Not just Codex

`commit_command` is any shell command. Anything that commits in the current directory works —
your own script, an alias, or a plain git one-liner:

```json
{ "commit_command": "git add -A && git commit -m \"wip\" && git push" }
```
