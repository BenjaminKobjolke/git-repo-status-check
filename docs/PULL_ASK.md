# `--pull-ask` — pull repos that are behind their remote

The default report answers one question: *which repos have uncommitted changes?* This mode
answers the other one: *which repos are behind their remote?* A repo can be perfectly clean
and still five commits stale, and nothing else in the tool would ever mention it.

```bat
start_pull-ask.bat
```

or directly:

```bat
uv run python main.py --pull-ask [--all] [--settings PATH] [--debug]
```

## What it does

It walks the same configured `folders` as every other mode (same `ignore_prefixes`, same
"stop descending once a repo is found" rule — see [SCANNING.md](SCANNING.md)). Repos that
are muted or that you already saw within `min_visit_age` are dropped **before** anything
else happens (see below). For each repo that survives that:

1. `git fetch --quiet` — updates the remote refs. This is the slow part; a live
   `Scanning: <path>` line on stderr says where it is.
2. `git rev-parse --abbrev-ref --symbolic-full-name @{u}` — the tracking branch's name.
   Repos with no upstream (a detached HEAD, a branch nobody pushed, no remote at all) are
   **skipped silently** — that is normal across a folder full of repos, not a problem.
   Run with `--debug` to see them.
3. `git rev-list --left-right --count @{u}...HEAD` — how many commits the upstream has that
   you do not. Only repos with a non-zero *behind* count are reported.

Repos that are only *ahead* are not reported: there is nothing to pull.

Then it prints the list, most stale first, and shows a menu per repo.

```
D:\GIT\some\repo  -  4 commit(s) behind origin/main
D:\GIT\other\repo  -  1 commit(s) behind origin/master  -  3 uncommitted
```

The `3 uncommitted` note is a **warning, not a filter** — repos with local changes are still
prompted for. A plain `git pull` usually succeeds anyway and fails loudly when it cannot.

## The menu

```
D:\GIT\some\repo  -  4 commit(s) behind origin/main

 > Pull
   Skip
   Mute repo
   Abort
```

Arrow keys to move, Enter to confirm, Ctrl-C to leave — nothing is typed. Same `pick`
wrapper as every other menu in the tool ([COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) explains
why it runs on the blessed backend).

| Entry | Action |
|-------|--------|
| Pull | Run `git pull` in this repo, output streaming live, then wait for Enter and move to the next repo. A plain pull — no rebase, no autostash. If it cannot proceed it fails loudly and nothing else is touched. |
| Skip | Skip this repo; move to the next. |
| Mute repo | Mute this repo, then pick a timeframe (1 day / 1 week / 1 month, or *Custom duration...* for typed input like `4h` / `3d` / `2w`). Muted repos are listed but not prompted for until the mute expires. |
| Abort | Abort the loop. No further repos are touched. |

## Repos it does not re-check

The fetch is the entire cost of this mode (~1.5 s per repo, serially), so both hold-back
rules are applied **before** the network call rather than after. A held-back repo is not
fetched, not measured, and not listed — it costs nothing. You get one summary line instead:

```
Skipped 34 repo(s) without fetching (muted, or seen within min_visit_age). Pass --all to check them anyway.
```

Run with `--debug` for a line naming each one and why.

Two rules hold a repo back:

**Muted** — you chose *Mute repo* and the timeframe has not expired.

**Recently seen** — you already had this repo's menu up within `min_visit_age` (default
`1h`, `null` to switch off; see [SETTINGS.md](SETTINGS.md)). A visit is recorded when you
leave a repo's menu by **any route except Abort** — Pull, Skip and Mute all count as "you
decided about this one". Abort records nothing, since you did not decide.

That is what makes a re-run cheap: the second run only fetches the repos you have not
already dealt with.

Both are stored per repo path in `mutes.db`, in `pull_mutes` and `pull_visits` — tables of
their own, separate from `--commit-ask`'s `mutes` and `visits`. Muting or visiting a repo
here does **not** silence it there, and vice versa: the two modes ask about different
things.

`--list-muted` prints both modes' mutes, under a heading each.

`--all` ignores both rules for this run without clearing them, so every repo is fetched
again — exactly as it does for `--commit-ask`.

## Credentials

`GIT_TERMINAL_PROMPT=0` is set for the process before the walk starts. Without it, a single
repo whose remote wants a username would block its `git fetch` on a console prompt and hang
the whole scan. With it, that repo's fetch fails fast and is skipped; the walk goes on.

Repos using an SSH agent or a credential helper are unaffected — nothing about this changes
stored credentials.

## Requirements

- An interactive terminal (with piped or redirected stdin it prints a notice and does
  nothing).
- No `commit_command` needed — that is `--commit-ask`'s requirement, not this one.

## See also

- [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md) — every flag.
- [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) — the uncommitted-changes menu, whose *Pull*
  submenu entry runs the same pull as this mode.
- [SCANNING.md](SCANNING.md) — how repos are found.
