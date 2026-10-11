"""Constants used only by typed commits, split out to keep constants.py below its length cap."""

GIT_ADD_ALL: tuple[str, ...] = ("add", "-A")
GIT_COMMIT_MESSAGE: tuple[str, ...] = ("commit", "-m")
COMMIT_MESSAGE_PROMPT = "  Commit message: "
COMMIT_MESSAGE_EMPTY = "  Empty commit message; nothing committed."
COMMIT_NO_PUSH_TARGET = "  Committed, not pushed: no remote or no branch to push."
