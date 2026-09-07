# `--push-ask` — push repos with commits their remote does not have

`--commit-ask` finds uncommitted changes and `--pull-ask` finds repos behind their remote.
Neither notices a repo whose work is committed but never pushed. This mode does.

```bat
start_push-ask.bat
```

or directly:

```bat
uv run python main.py --push-ask [--all] [--settings PATH] [--debug]
```

## What it does

It walks the same configured `folders` as every other mode (same `ignore_prefixes`, same
"stop descending once a repo is found" rule — see [SCANNING.md](SCANNING.md)). Repos that
are muted or already settled within `min_visit_age` are dropped **before** anything else
happens (see below). For each repo that survives that:

1. `git rev-parse --abbrev-ref --symbolic-full-name @{u}` — the tracking branch's name.
2. With a tracking branch: `git rev-list --left-right --count @{u}...HEAD` — how many
   commits you have that the upstream does not. Only a non-zero *ahead* count is reported.
3. Without one: `git symbolic-ref --short HEAD` (the branch — a detached HEAD is skipped),
   `git remote` (the remote to push to; no remote means nothing to push to, skipped) and
   `git rev-list --count HEAD` (every commit on a never-pushed branch is unpushed). Reported
   when there is at least one commit.

**No fetch.** "Ahead" is measured against the *local* tracking ref, so the walk costs no
network and is as fast as the plain scan. The trade-off: if the remote moved on since your
last fetch, the push is rejected — the menu then comes back for the same repo, and *Pull* is
one entry away.

A repo found ahead is put to you **immediately**, mid-walk:

```
D:\GIT\some\repo  -  2 commit(s) ahead of origin/main
D:\GIT\fresh\repo  -  5 commit(s) on main, no upstream
```

A `3 uncommitted` suffix is a **warning, not a filter** — pushing only sends commits, so
local changes do not stop it.

## The menu

```
D:\GIT\some\repo  -  2 commit(s) ahead of origin/main

 > Push
   Pull
   Skip
   Mute repo
   Abort
```

On a branch with no upstream the first entry names what it will run and *Pull* is left out
(there is no tracking branch to pull from):

```
 > Push -u origin main
   Skip
   Mute repo
   Abort
```

| Entry | Action |
|-------|--------|
| Push | `git push` (or `git push -u <remote> <branch>` on a branch without upstream), output streaming live, then wait for Enter and move to the next repo. A rejected push shows the **menu again for this repo**. |
| Pull | `git pull --no-edit` — the same pull as the other modes — then the menu again. For when the push was rejected because the remote moved on. |
| Skip | Skip this repo; move to the next. Also how you leave a repo whose push just failed. |
| Mute repo | Mute this repo, then pick a timeframe (1 day / 1 week / 1 month, or *Custom duration...* for typed input like `4h` / `3d` / `2w`). |
| Abort | Abort the loop. No further repos are touched. |

Arrow keys to move, Enter to confirm, Ctrl-C to leave — nothing is typed. Same `pick`
wrapper as every other menu in the tool ([COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) explains
why it runs on the blessed backend).

`GIT_TERMINAL_PROMPT` is **not** switched off here, unlike `--pull-ask`: nothing runs
unattended, and a push may legitimately have to ask you for credentials.

## Repos it does not re-check

Same two rules as `--pull-ask`, applied before the git calls; you get one summary line:

```
Skipped 34 repo(s) without checking (muted, or seen within min_visit_age). Pass --all to check them anyway.
```

**Muted** — you chose *Mute repo* and the timeframe has not expired.

**Already settled** — checked within `min_visit_age` (default `1h`, `null` to switch off;
see [SETTINGS.md](SETTINGS.md)): its menu was shown to you (recorded before the menu is
drawn, so *Abort* and Ctrl-C count), or the walk found nothing to push (up to date, no
remote, detached HEAD).

Both are stored per repo path in `mutes.db`, in `push_mutes` and `push_visits` — tables of
their own. Muting or visiting a repo here does **not** silence it in `--commit-ask` or
`--pull-ask`, and vice versa. `--list-muted` prints all three modes' mutes.

`--all` ignores both rules for this run without clearing them.

## Requirements

- An interactive terminal (with piped or redirected stdin it prints a notice and does
  nothing).
- No `commit_command` needed.

## See also

- [COMMAND_LINE_ARGUMENTS.md](COMMAND_LINE_ARGUMENTS.md) — every flag.
- [PULL_ASK.md](PULL_ASK.md) — the opposite direction, which shares this mode's walk and
  menu loop.
- [COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) — the uncommitted-changes menu.
