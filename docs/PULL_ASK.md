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
are muted or that were already settled within `min_visit_age` are dropped **before** anything
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

A repo found behind is put to you **immediately**, mid-walk, before the rest are fetched:

```
D:\GIT\some\repo  -  4 commit(s) behind origin/main
```

That is deliberate. Fetching a few hundred repos takes minutes, so collecting them all
before the first question meant an interrupted run decided nothing at all. The cost is
ordering: repos arrive in walk order, not most-behind-first, because sorting needs the whole
walk finished.

The `3 uncommitted` note is a **warning, not a filter** — repos with local changes are still
prompted for. A plain `git pull` usually succeeds anyway and fails loudly when it cannot;
when it cannot, the **menu comes back for the same repo** so *Stash changes and pull* is
still one keystroke away.

## The menu

```
D:\GIT\some\repo  -  4 commit(s) behind origin/main  -  3 uncommitted

 > Pull
   Stash changes and pull
   Rename repo
   Skip
   Mute repo
   Abort
```

*Stash changes and pull* appears **only on a repo with local changes** — on a clean one
there would be nothing to stash. *Rename repo* appears **only when `rename_prefix` is
configured** — without one there is nothing to rename to. Either way the entry is left out
rather than shown and failing.

Arrow keys to move, Enter to confirm, Ctrl-C to leave — nothing is typed. Same `pick`
wrapper as every other menu in the tool ([COMMIT_ASK_MENU.md](COMMIT_ASK_MENU.md) explains
why it runs on the blessed backend).

| Entry | Action |
|-------|--------|
| Pull | Run `git pull --no-edit` in this repo, output streaming live, then wait for Enter and move to the next repo. A plain pull — no rebase, no autostash. `--no-edit` keeps a merge commit from dropping you into the git editor on top of the menu. If the pull fails, nothing is touched and the **menu is shown again for this repo** — the usual cause is local changes, and *Stash changes and pull* is right there. |
| Stash changes and pull | Only shown when the repo has local changes. Runs `git stash push -u -m "<YYYY_MM_DD> GIT REPO STATUS TOOL"` — the same stash as the `--commit-ask` submenu, including untracked files — and then pulls. If the stash fails, the pull is **not** attempted (the dirty tree is exactly what would trip it up) and the menu is shown again — *Skip* to leave the repo alone. Recover your work with `git stash pop`. |
| Rename repo | Only shown when `rename_prefix` is set. Renames the repo folder to `<rename_prefix><name>` (e.g. `_old_project`) — the same rename as the `--commit-ask` submenu — so a matching `ignore_prefixes` entry keeps it out of the next scan. Nothing is pulled: the repo is no longer at that path. A refused rename (no prefix, already prefixed, target exists) shows the menu again. |
| Skip | Skip this repo; move to the next. Also how you leave a repo whose pull just failed. |
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

**Already settled** — this repo was checked within `min_visit_age` (default `1h`, `null`
to switch off; see [SETTINGS.md](SETTINGS.md)). A repo is settled two ways:

- **Its menu was shown to you.** The visit is recorded *before* the menu is drawn, so Pull,
  Skip, Mute, *Abort* and Ctrl-C all leave it recorded — you were shown the repo either way.
  Repos further down the walk that you never reached stay untouched.
- **The fetch found nothing to pull.** Up to date, no tracking branch, detached HEAD, an
  unreachable remote — no menu is ever shown for those, so the walk settles them itself.

That is what makes a re-run cheap, and it is why the same repo does not greet you on every
run: bail out of it once and the next run moves on to the one behind it. The flip side —
a repo you looked at and ignored stays behind its upstream, quietly, until the window
expires.

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
