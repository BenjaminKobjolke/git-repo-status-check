"""Entry point for the desktop window: edit settings.json and run every mode natively."""

from __future__ import annotations

from pathlib import Path

from git_repo_status_check.gui.app import main

if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parent))
