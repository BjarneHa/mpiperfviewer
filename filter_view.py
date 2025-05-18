from abc import ABC, abstractmethod
from typing import override

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

FILTERS = ["size", "count", "tags"]


class RangeFilterWidget(QObject):
    _checkbox: QCheckBox
    _min_edit: QLineEdit
    _max_edit: QLineEdit

    def __init__(
        self, filter: str, i: int, layout: QGridLayout, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self._checkbox = QCheckBox(filter, parent)
        _ = self._checkbox.checkStateChanged.connect(self._check_changed)
        layout.addWidget(self._checkbox, i * 2, 0, 1, 3)
        self._min_edit = QLineEdit(parent, placeholderText="-∞")
        self._min_edit.setDisabled(True)
        self._min_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        self._max_edit = QLineEdit(parent, placeholderText="∞")
        self._max_edit.setDisabled(True)
        self._max_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        layout.addWidget(self._min_edit, i * 2 + 1, 0)
        filter_label = QLabel(f"≤ {filter} ≤")
        layout.addWidget(filter_label, i * 2 + 1, 1)
        layout.addWidget(self._max_edit, i * 2 + 1, 2)

    @Slot()
    def _check_changed(self, value: Qt.CheckState):
        checked = value == Qt.CheckState.Checked
        self._min_edit.setDisabled(not checked)
        self._max_edit.setDisabled(not checked)

    def state(self):
        if not self._checkbox.isChecked():
            return UNFILTERED
        min = None
        max = None
        try:
            min = int(self._min_edit.text())
        except ValueError:
            pass
        try:
            max = int(self._max_edit.text())
        except ValueError:
            pass
        return RangeFilter(min, max)


class Filter(ABC):
    @abstractmethod
    def test(self, x: int) -> bool:
        pass


class RangeFilter(Filter):
    min: int | None
    max: int | None

    def __init__(self, min: int | None = None, max: int | None = None):
        self.min = min
        self.max = max

    @override
    def __str__(self) -> str:
        return "{" + f"min: {self.min}, max: {self.max}" + "}"

    @override
    def __eq__(self, other: object, /) -> bool:
        return (
            type(other) is RangeFilter
            and self.min == other.min
            and self.max == other.max
        )

    @override
    def test(self, x: int):
        return (self.min or x) <= x and x <= (self.max or x)


UNFILTERED = RangeFilter()


class FilterView(QGroupBox):
    filters_changed: Signal = Signal(object)
    _range_filters: dict[str, RangeFilterWidget] = dict()
    _apply_button: QPushButton
    _filter_state: dict[str, RangeFilter]

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Filter", parent)
        layout = QGridLayout(self)
        for i, filter in enumerate(FILTERS):
            self._range_filters[filter] = RangeFilterWidget(filter, i, layout, self)
        self._apply_button = QPushButton("Apply")
        layout.addWidget(self._apply_button, len(FILTERS) * 2, 0, 1, 3)
        self._apply_button.clicked.connect(self._apply_filters)
        self._filter_state = {filter: UNFILTERED for filter in FILTERS}

    @Slot()
    def _apply_filters(self):
        new_filter_state = {
            name: rf.state() for name, rf in self._range_filters.items()
        }
        # Do not update filters where the values have not changed
        self.filters_changed.emit(
            {
                filter: state
                for filter, state in new_filter_state.items()
                if state != self._filter_state[filter]
            }
        )
        self._filter_state = new_filter_state
