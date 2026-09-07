"""The Settings tab: a form over ``SettingsDocument``, saved and validated in place.

Validation is shown where the input is (a line under the Save button), never in a dialog,
and comes from ``Settings.load`` -- the one validator -- run on the file just written.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..settings_file import SettingsDocument, validate
from . import labels, palette, stylesheet
from .i18n import TK, t

_PREFIX_SEPARATOR = ","


class SettingsPage(QWidget):
    """Edits every key of ``settings.json`` at ``path``."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            palette.SPACE_XL, palette.SPACE_XL, palette.SPACE_XL, palette.SPACE_XL
        )
        layout.setSpacing(palette.SPACE_M)
        layout.addWidget(labels.heading(t(TK.SETTINGS_HEADING)))
        layout.addWidget(labels.subheading(t(TK.SETTINGS_SUBHEADING, path=str(path))))
        layout.addSpacing(palette.SPACE_S)

        self._folders = self._folder_list(layout)
        self._commit_command = self._field(
            layout, TK.SETTINGS_LABEL_COMMIT_COMMAND, TK.SETTINGS_HINT_COMMIT_COMMAND
        )
        self._file_explorer = self._field(
            layout, TK.SETTINGS_LABEL_FILE_EXPLORER, TK.SETTINGS_HINT_FILE_EXPLORER
        )
        self._rename_prefix = self._field(
            layout, TK.SETTINGS_LABEL_RENAME_PREFIX, TK.SETTINGS_HINT_RENAME_PREFIX
        )
        self._ignore_prefixes = self._field(
            layout, TK.SETTINGS_LABEL_IGNORE_PREFIXES, TK.SETTINGS_HINT_IGNORE_PREFIXES
        )
        self._min_modified_age = self._field(
            layout, TK.SETTINGS_LABEL_MIN_MODIFIED_AGE, TK.SETTINGS_HINT_MIN_MODIFIED_AGE
        )
        self._min_visit_age = self._field(
            layout, TK.SETTINGS_LABEL_MIN_VISIT_AGE, TK.SETTINGS_HINT_MIN_VISIT_AGE
        )
        self._visit_age_off = QCheckBox(t(TK.SETTINGS_OPTION_VISIT_AGE_OFF))
        self._visit_age_off.toggled.connect(self._min_visit_age.setDisabled)
        layout.addWidget(self._visit_age_off)

        layout.addSpacing(palette.SPACE_S)
        actions = QHBoxLayout()
        self._save = QPushButton(t(TK.SETTINGS_ACTION_SAVE))
        self._save.setObjectName(stylesheet.PRIMARY)
        self._save.clicked.connect(self.save)
        actions.addWidget(self._save)
        actions.addStretch()
        layout.addLayout(actions)
        self._message = QLabel()
        self._message.setWordWrap(True)
        layout.addWidget(self._message)
        layout.addStretch()

        self.load()

    # -- document <-> widgets -----------------------------------------------------------

    def load(self) -> None:
        doc = SettingsDocument.read(self._path)
        self._folders.clear()
        self._folders.addItems(doc.folders)
        self._commit_command.setText(doc.commit_command)
        self._file_explorer.setText(doc.file_explorer)
        self._rename_prefix.setText(doc.rename_prefix)
        self._ignore_prefixes.setText(f"{_PREFIX_SEPARATOR} ".join(doc.ignore_prefixes))
        self._min_modified_age.setText(doc.min_modified_age)
        self._visit_age_off.setChecked(doc.min_visit_age is None)
        self._min_visit_age.setText(doc.min_visit_age or "")

    def document(self) -> SettingsDocument:
        """What the form holds right now, in the shape the file is written from."""
        prefixes = [
            part.strip()
            for part in self._ignore_prefixes.text().split(_PREFIX_SEPARATOR)
            if part.strip()
        ]
        return SettingsDocument(
            folders=[self._folders.item(i).text() for i in range(self._folders.count())],
            commit_command=self._commit_command.text(),
            file_explorer=self._file_explorer.text(),
            rename_prefix=self._rename_prefix.text(),
            ignore_prefixes=prefixes,
            min_modified_age=self._min_modified_age.text(),
            min_visit_age=None if self._visit_age_off.isChecked() else self._min_visit_age.text(),
        )

    def save(self) -> None:
        self.document().write(self._path)
        error = validate(self._path)
        if error is None:
            self._show_message(t(TK.SETTINGS_SAVED), error=False)
        else:
            self._show_message(t(TK.SETTINGS_INVALID, error=error), error=True)

    def message(self) -> str:
        return self._message.text()

    # -- building blocks ------------------------------------------------------------------

    def _folder_list(self, layout: QVBoxLayout) -> QListWidget:
        layout.addWidget(labels.menu_title(t(TK.SETTINGS_LABEL_FOLDERS)))
        layout.addWidget(labels.hint(t(TK.SETTINGS_HINT_FOLDERS)))
        folders = QListWidget()
        layout.addWidget(folders)
        row = QHBoxLayout()
        add = QPushButton(t(TK.SETTINGS_ACTION_ADD_FOLDER))
        add.clicked.connect(self._add_folder)
        remove = QPushButton(t(TK.SETTINGS_ACTION_REMOVE_FOLDER))
        remove.clicked.connect(self._remove_folder)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)
        layout.addSpacing(palette.SPACE_S)
        return folders

    def _field(self, layout: QVBoxLayout, label_key: str, hint_key: str) -> QLineEdit:
        layout.addWidget(labels.menu_title(t(label_key)))
        layout.addWidget(labels.hint(t(hint_key)))
        edit = QLineEdit()
        layout.addWidget(edit)
        return edit

    def _add_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, t(TK.SETTINGS_PICK_FOLDER))
        if chosen:
            self.add_folder(chosen)

    def add_folder(self, folder: str) -> None:
        self._folders.addItem(str(Path(folder)))

    def _remove_folder(self) -> None:
        for item in self._folders.selectedItems():
            self._folders.takeItem(self._folders.row(item))

    def _show_message(self, text: str, *, error: bool) -> None:
        self._message.setObjectName(stylesheet.MESSAGE_ERROR if error else "")
        # The object name changed after styling: re-polish so the new selector applies.
        self._message.style().unpolish(self._message)
        self._message.style().polish(self._message)
        self._message.setText(text)
