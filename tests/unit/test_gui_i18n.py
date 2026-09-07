"""Unit tests for the GUI translations: every key resolves, every language is complete."""

from __future__ import annotations

import json

import pytest

from git_repo_status_check.gui import i18n
from git_repo_status_check.gui.i18n import TK


def _flatten(tree: dict[str, object], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for name, value in tree.items():
        key = f"{prefix}{name}"
        if isinstance(value, dict):
            keys |= _flatten(value, f"{key}.")
        else:
            keys.add(key)
    return keys


def _keys_of(language: str) -> set[str]:
    return _flatten(json.loads((i18n.LANG_DIR / f"{language}.json").read_text(encoding="utf-8")))


@pytest.fixture(autouse=True)
def _english(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin English so the tests do not depend on the developer's OS language."""
    monkeypatch.setattr(i18n, "_localization", None)
    i18n.configure(language=i18n.FALLBACK_LANGUAGE)


def test_every_tk_constant_exists_in_english() -> None:
    missing = sorted(set(TK.all_keys()) - _keys_of("en"))
    assert missing == []


def test_every_language_has_the_same_keys_as_english() -> None:
    english = _keys_of("en")
    for path in i18n.LANG_DIR.glob("*.json"):
        assert _keys_of(path.stem) == english, path.name


def test_t_fills_placeholders() -> None:
    assert i18n.t(TK.RUN_FINISHED, code=0) == "Finished (exit 0)."


def test_missing_key_renders_as_the_key() -> None:
    assert i18n.t("nope.missing") == "nope.missing"
