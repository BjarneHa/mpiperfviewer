

from enum import Enum

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QHBoxLayout
)
import qtawesome as qta

FILE_EXTENSION = "mpipcproj"

class PathSelector(QGroupBox):
    confirmed: Signal = Signal(str)
    _line_edit: QLineEdit
    _file_button: QPushButton
    _confirm_button: QPushButton
    _file_types: str | None
    _dialog_title: str

    def __init__(self, box_title: str, dialog_title: str, button_text: str, file_types: str | None = None, parent: QWidget | None = None):
        super().__init__(parent, title=box_title)
        self._file_types = file_types
        self._dialog_title = dialog_title
        layout = QVBoxLayout(self)
        path_layout = QHBoxLayout()
        layout.addLayout(path_layout)
        self._line_edit = QLineEdit(self, readOnly=True)
        _ = self._line_edit.textChanged.connect(self._path_changed)
        self._file_button = QPushButton(self)
        self._file_button.setIcon(qta.icon("mdi6.folder-open"))
        _ = self._file_button.clicked.connect(self._open_dialog)
        path_layout.addWidget(self._line_edit)
        path_layout.addWidget(self._file_button)
        path_layout.setStretch(0, 1)
        path_layout.setStretch(1, 0)
        self._confirm_button = QPushButton(button_text, self)
        self._confirm_button.setEnabled(False)
        _ = self._confirm_button.clicked.connect(self._confirm_clicked)
        layout.addWidget(self._confirm_button)

    @Slot()
    def _path_changed(self, text: str):
        self._confirm_button.setEnabled(text != "")

    @Slot()
    def _confirm_clicked(self):
        self.confirmed.emit(self._line_edit.text())

    @Slot()
    def _open_dialog(self):
        if self._file_types is None:
            path = QFileDialog.getExistingDirectory(self, self._dialog_title)
        else:
            path, _ = QFileDialog.getOpenFileName(self, self._dialog_title, filter=self._file_types)
        if len(path) > 0:
            self._line_edit.setText(path)


class StartDialog(QDialog):
    class Choice(Enum):
        NEW_PROJECT = 0
        OPEN_PROJECT = 1

    _choice: "StartDialog.Choice | None"
    _result_path: str | None
    _new_selector: PathSelector
    _existing_selector: PathSelector

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._choice = None
        self._result_path = None
        layout = QVBoxLayout(self)
        title_font = QFont()
        # title_font.setPixelSize(24)
        title_font.setWeight(QFont.Weight.Bold)
        title = QLabel("Welcome to mpiperfviewer.", parent=self)
        title.setFont(title_font)
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self._new_selector = PathSelector(
            box_title = "New Project",
            dialog_title = "Select directory containing input data.",
            button_text = "Create",
            file_types = None, # Directory
            parent = self,
        )
        _ = self._new_selector.confirmed.connect(self._new_project)
        layout.addWidget(self._new_selector)
        self._existing_selector = PathSelector(
            box_title = "Existing Project",
            dialog_title = "Select project file.",
            button_text = "Open",
            file_types = f"mpiperfviewer Project (*.{FILE_EXTENSION});;All files (*)",
            parent = self,
        )
        _ = self._existing_selector.confirmed.connect(self._open_existing_project)
        layout.addWidget(self._existing_selector)

    @Slot()
    def _new_project(self, path: str):
        self._choice = StartDialog.Choice.NEW_PROJECT
        self._result_path = path
        _ = self.close()

    @Slot()
    def _open_existing_project(self, path: str):
        self._choice = StartDialog.Choice.OPEN_PROJECT
        self._result_path = path
        _ = self.close()

    @staticmethod
    def get_choice(parent: QWidget):
        self = StartDialog(parent)
        _ = self.exec()
        if self._result_path is None:
            raise Exception("Unexpected: No result from StartDialog.")
        return self._choice, self._result_path
