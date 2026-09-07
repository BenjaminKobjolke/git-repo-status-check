"""Constants only the ``--fix-line-endings`` repair (``line_endings.py``) uses.

Split out of ``constants.py`` to keep that module under the file-length cap; everything
shared with the scanner (the noise rule, the pull-time reset) stays there.
"""

from __future__ import annotations

# --fix-line-endings writes only the repo's local core.autocrlf. `--default ""` makes an unset
# key an empty answer instead of exit code 1, so "unset" and "set to something" read the same way.
GIT_CONFIG_GET_LOCAL_AUTOCRLF: tuple[str, ...] = (
    "config",
    "--local",
    "--get",
    "--default",
    "",
    "core.autocrlf",
)
GIT_CONFIG_SET_AUTOCRLF: tuple[str, ...] = ("config", "core.autocrlf")
GIT_CONFIG_UNSET_AUTOCRLF: tuple[str, ...] = ("config", "--unset", "core.autocrlf")

# Every path with a real content difference left, once the conversion above has been applied.
# Whole worktree, no path arguments: `git diff` has no --pathspec-from-file, and a list of
# hundreds of paths overflows the Windows command line. The caller intersects the output
# with the noisy paths; a noisy path absent from it agrees with its blob, and only the
# index's cached stat data is stale.
GIT_DIFF_WORKTREE_NAMES: tuple[str, ...] = ("diff", "--name-only", "-z")

# Refreshes that stale stat data. Only ever run on paths the diff above just reported as
# content-identical, so it can never stage an actual change. Paths arrive on stdin,
# NUL-separated (same as `GIT_CHECKOUT_HEAD_STDIN_PATHS` in constants.py).
GIT_ADD_STDIN_PATHS: tuple[str, ...] = ("add", "--pathspec-from-file=-", "--pathspec-file-nul")

# Values tried, in order. Which one clears the phantom changes depends on whether the blobs
# hold CRLF or LF, so the repair tries and verifies instead of guessing. "true" comes first
# because LF blobs in a CRLF worktree is the common Windows case.
AUTOCRLF_CANDIDATES: tuple[str, ...] = ("true", "false")

# Prompts and results.
FIX_NEEDS_TTY = "--fix-line-endings needs an interactive terminal; nothing to do."
FIX_NONE_FOUND = "No repos with line-ending-only changes."
FIX_HEADER = "{repo}  -  {count} line-ending-only change(s)"
FIX_MENU = (
    ("Fix line endings", "y"),
    ("Skip", "n"),
    ("Abort", "a"),
)
FIX_APPLIED = "  OK: core.autocrlf={value} — {count} phantom change(s) gone."
FIX_FAILED = "  FAILED: no core.autocrlf value made it clean (a .gitattributes rule likely wins)."
