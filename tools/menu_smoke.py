"""Manual smoke test for menu.py -- the one thing the unit tests cannot cover.

The unit tests replace ``menu.choose``, so nothing else drives a real menu. This walks the
sequence that broke once: a menu, then a subprocess inheriting the console, then another
menu. Under the curses backend the second menu drew but ignored every key -- if all three
menus here respond to the arrow keys, the blessed backend still holds.

Needs a real terminal window -- run ``tools\\menu_smoke.bat`` (or the line below) from a
console. Started anywhere that captures output instead of giving a console, the run is
refused rather than left hanging on a key that can never arrive.

    uv run python tools/menu_smoke.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from git_repo_status_check import menu

ITEMS = (("Continue", "go"), ("Quit", "quit"))


def main() -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("menu_smoke needs a real terminal; run tools\\menu_smoke.bat from a console.")
        return 1

    if menu.choose(ITEMS, "1/3  Arrow keys + Enter. Pick Continue.") == "quit":
        return 1

    # A subprocess inheriting the console, as the pull / commit / stash actions do.
    subprocess.run([sys.executable, "-c", "print('  subprocess output')"], check=False)
    print("  printed output")
    menu.pause()

    if menu.choose(ITEMS, "2/3  Still responsive after a subprocess? Pick Continue.") == "quit":
        return 1

    typed = menu.ask_text("  Type anything and press Enter: ")
    print(f"  got: {typed!r}")
    menu.pause()

    menu.choose(ITEMS, "3/3  Still responsive after typed input? Pick either.")
    print("\nOK: every menu responded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
