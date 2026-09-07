"""GUI strings: every translation key as a constant, and the one ``t()`` widgets call.

Raw strings never appear at a call site (CODING_RULES "Localize From the Start"); a key
that is missing from ``lang/<code>.json`` renders as the key itself so the gap is visible on
screen instead of as an empty label. Translations live in ``lang/`` at the project root.
"""

from __future__ import annotations

from pathlib import Path

from python_localization import Localization

# src/git_repo_status_check/gui/i18n.py -> the checkout root, where lang/ lives.
LANG_DIR = Path(__file__).resolve().parents[3] / "lang"
FALLBACK_LANGUAGE = "en"
# Persists the chosen language per app (python-localization's PreferenceStore).
APP_NAME = "git-repo-status-check"


class TK:
    """Translation keys. Dot paths into ``lang/en.json``."""

    WINDOW_TITLE = "window.title"
    TAB_RUN = "tab.run"
    TAB_SETTINGS = "tab.settings"

    RUN_HEADING = "run.heading"
    RUN_SUBHEADING = "run.subheading"
    RUN_EMPTY = "run.empty"
    RUN_STARTED = "run.started"
    RUN_FINISHED = "run.finished"
    RUN_ACTION_SCAN = "run.action.scan"
    RUN_ACTION_COMMIT_ASK = "run.action.commit_ask"
    RUN_ACTION_PULL_ASK = "run.action.pull_ask"
    RUN_ACTION_PUSH_ASK = "run.action.push_ask"
    RUN_ACTION_SYNC_ASK = "run.action.sync_ask"
    RUN_ACTION_FIX_LINE_ENDINGS = "run.action.fix_line_endings"
    RUN_ACTION_LIST_MUTED = "run.action.list_muted"
    RUN_ACTION_STOP = "run.action.stop"
    RUN_OPTION_ALL = "run.option.all"
    RUN_OPTION_LIMIT = "run.option.limit"
    RUN_OPTION_LIMIT_NONE = "run.option.limit_none"

    PROMPT_OK = "prompt.ok"

    STATUS_IDLE = "status.idle"
    STATUS_RUNNING = "status.running"
    STATUS_SCANNING = "status.scanning"
    STATUS_STOPPING = "status.stopping"

    SETTINGS_HEADING = "settings.heading"
    SETTINGS_SUBHEADING = "settings.subheading"
    SETTINGS_SAVED = "settings.saved"
    SETTINGS_INVALID = "settings.invalid"
    SETTINGS_PICK_FOLDER = "settings.pick_folder"
    SETTINGS_LABEL_FOLDERS = "settings.label.folders"
    SETTINGS_LABEL_COMMIT_COMMAND = "settings.label.commit_command"
    SETTINGS_LABEL_FILE_EXPLORER = "settings.label.file_explorer"
    SETTINGS_LABEL_RENAME_PREFIX = "settings.label.rename_prefix"
    SETTINGS_LABEL_IGNORE_PREFIXES = "settings.label.ignore_prefixes"
    SETTINGS_LABEL_MIN_MODIFIED_AGE = "settings.label.min_modified_age"
    SETTINGS_LABEL_MIN_VISIT_AGE = "settings.label.min_visit_age"
    SETTINGS_HINT_FOLDERS = "settings.hint.folders"
    SETTINGS_HINT_COMMIT_COMMAND = "settings.hint.commit_command"
    SETTINGS_HINT_FILE_EXPLORER = "settings.hint.file_explorer"
    SETTINGS_HINT_RENAME_PREFIX = "settings.hint.rename_prefix"
    SETTINGS_HINT_IGNORE_PREFIXES = "settings.hint.ignore_prefixes"
    SETTINGS_HINT_MIN_MODIFIED_AGE = "settings.hint.min_modified_age"
    SETTINGS_HINT_MIN_VISIT_AGE = "settings.hint.min_visit_age"
    SETTINGS_OPTION_VISIT_AGE_OFF = "settings.option.visit_age_off"
    SETTINGS_ACTION_ADD_FOLDER = "settings.action.add_folder"
    SETTINGS_ACTION_REMOVE_FOLDER = "settings.action.remove_folder"
    SETTINGS_ACTION_SAVE = "settings.action.save"

    @classmethod
    def all_keys(cls) -> list[str]:
        """Every key, for the test that checks each language file covers them all."""
        return [
            value for name, value in vars(cls).items() if name.isupper() and isinstance(value, str)
        ]


_localization: Localization | None = None


def configure(lang_dir: Path = LANG_DIR, language: str | None = None) -> Localization:
    """Build the translator once. ``language`` None = saved preference, then the OS language."""
    global _localization
    _localization = Localization(
        driver="json",
        lang_dir=str(lang_dir),
        default_lang=language,
        fallback_lang=FALLBACK_LANGUAGE,
        app_name=APP_NAME,
        fallback_to_key=True,
    )
    return _localization


def t(key: str, **params: object) -> str:
    """The translation for ``key`` with ``{name}`` placeholders filled from ``params``."""
    localization = _localization if _localization is not None else configure()
    value = localization.t(key, **params)
    # A key that names a section comes back as a dict; a label wants a string either way.
    return value if isinstance(value, str) else key
