# `--sync-ask` — pull, commit and push in one run

`--pull-ask`, `--commit-ask` and `--push-ask` each answer one question. Bringing a folder
full of repos fully in sync means asking all three, in that order. This mode does exactly
that: the three existing modes, back to back, in one command.

```bat
start_sync-ask.bat
```

or directly:

```bat
uv run python main.py --sync-ask [--all] [--limit N] [--settings PATH] [--debug]
```

## What it does

Three stages, each announced with a banner, each *the existing mode unchanged*:

```
=== Pull (--pull-ask) ===
...
=== Commit (--commit-ask) ===
...
=== Push (--push-ask) ===
...
```

1. **Pull** — [`--pull-ask`](PULL_ASK.md): fetch every repo, ask about each one behind its
   upstream.
2. **Commit** — [`--commit-ask`](COMMAND_LINE_ARGUMENTS.md#--commit-ask): the normal report,
   then a menu per dirty repo ([COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md)).
3. **Push** — [`--push-ask`](PUSH_ASK.md): ask about each repo with commits its remote does
   not have — which now includes whatever the commit stage just committed.

Pull first so a commit lands on top of the remote's latest; push last so the new commits go
out. Each stage's menus, mutes and visits are exactly the standalone mode's: what you mute
or skip in one stage is that stage's business only, and `--list-muted` still shows the three
sections it always did.

## Abort ends the run

*Abort* in any stage's menu ends the whole run — not just that stage. The stage prints
`Aborted.` and the remaining stages do not start. *Skip* is still per repo, and Ctrl-C leaves
the tool as it always did.

## Flags

- `--all` — ignore mutes and visits in every stage (and `min_modified_age` in the commit
  stage), exactly as it does for each mode on its own.
- `--limit N` — applies to the commit stage only, the same way it does for `--commit-ask`;
  the pull and push stages never took a limit.
- `--settings PATH`, `--debug` — as everywhere.

## Requirements

- A non-empty `commit_command` in settings (see [SETTINGS.md](SETTINGS.md)). Checked
  **before** the pull stage starts: a pull walk is minutes, so a run that could not honour
  its commit stage fails immediately instead.
- An interactive terminal (each stage prints its notice and does nothing otherwise).

## Credentials

`--pull-ask` switches `GIT_TERMINAL_PROMPT` off so an unattended fetch cannot hang on a
console prompt (see [PULL_ASK.md](PULL_ASK.md#credentials)). Here that setting is restored as
soon as the pull stage ends, so the push stage can still ask you for credentials the way
[`--push-ask`](PUSH_ASK.md) on its own does.

## See also

- [PULL_ASK.md](PULL_ASK.md), [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md),
  [PUSH_ASK.md](PUSH_ASK.md) — the three stages.
- [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md) — every flag.
