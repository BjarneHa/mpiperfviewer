from typing import Dict
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QLabel, QLineEdit, QWidget

FILTERS = ["size", "count", "tags"]

class FilterView(QGroupBox):
    def __init__(self, parent: QWidget | None=None):
        super().__init__("Filter", parent)
        layout = QGridLayout(self)
        self._range_filters: Dict[str, FilterView.RangeFilter] = dict()
        for (i, filter) in enumerate(FILTERS):
            self._range_filters[filter] = FilterView.RangeFilter(filter, i, layout, self)
        self.setLayout(layout)

    class RangeFilter(QObject):
        def __init__(self, filter: str, i: int, layout: QGridLayout, parent=None):
            super().__init__(parent)
            self.checkbox = QCheckBox(filter, parent)
            self.checkbox.checkStateChanged.connect(self.check_changed)
            layout.addWidget(self.checkbox, i*2, 0, 1, 3)
            self.min_edit = QLineEdit(parent, placeholderText="-∞")
            self.min_edit.setDisabled(True)
            self.min_edit.setValidator(QRegularExpressionValidator(r"\d+", self))
            self.max_edit = QLineEdit(parent, placeholderText="∞")
            self.max_edit.setDisabled(True)
            self.max_edit.setValidator(QRegularExpressionValidator(r"\d+", self))
            layout.addWidget(self.min_edit, i*2+1, 0, 1, 1)
            layout.addWidget(QLabel(f"≤ {filter} ≤"), i*2+1, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.max_edit, i*2+1, 2, 1, 1)

        @Slot()
        def check_changed(self, value: Qt.CheckState):
            checked = value == Qt.CheckState.Checked
            self.min_edit.setDisabled(not checked)
            self.max_edit.setDisabled(not checked)
