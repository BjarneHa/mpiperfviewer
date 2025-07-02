from dataclasses import dataclass
from typing import Any, override

import numpy as np
from numpy.typing import NDArray
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
        layout.addWidget(self._checkbox, i * 2, 0, 1, 5)
        self._min_edit = QLineEdit(parent, placeholderText="-∞")
        self._min_edit.setDisabled(True)
        self._min_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        self._max_edit = QLineEdit(parent, placeholderText="∞")
        self._max_edit.setDisabled(True)
        self._max_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        layout.addWidget(self._min_edit, i * 2 + 1, 0)
        layout.addWidget(QLabel("≤"), i * 2 + 1, 1)
        layout.addWidget(QLabel("≤"), i * 2 + 1, 3)
        filter_label = QLabel(f"{filter}")
        layout.addWidget(
            filter_label, i * 2 + 1, 2, alignment=Qt.AlignmentFlag.AlignCenter
        )
        layout.addWidget(self._max_edit, i * 2 + 1, 4)

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


class RangeFilter:
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

    def apply(self, metric: NDArray[Any]):
        metric_min = self.min or np.iinfo(metric.dtype).min
        metric_max = self.max or np.iinfo(metric.dtype).max
        filter = (metric_min <= metric) & (metric <= metric_max)
        return filter


UNFILTERED = RangeFilter()


@dataclass
class GlobalFilters:
    size: RangeFilter
    count: RangeFilter
    tags: RangeFilter


INITIAL_GLOBAL_FILTERS = GlobalFilters(UNFILTERED, UNFILTERED, UNFILTERED)


class FilterView(QGroupBox):
    filters_changed: Signal = Signal(object)
    _size_filter: RangeFilterWidget
    _count_filter: RangeFilterWidget
    _tags_filter: RangeFilterWidget
    _apply_button: QPushButton
    _filter_state: GlobalFilters

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Filter", parent)
        layout = QGridLayout(self)
        self._size_filter = RangeFilterWidget("size", 0, layout, self)
        self._count_filter = RangeFilterWidget("count", 1, layout, self)
        self._tags_filter = RangeFilterWidget("tags", 2, layout, self)
        self._apply_button = QPushButton("Apply")
        layout.addWidget(self._apply_button, 6, 0, 1, 5)
        self._apply_button.clicked.connect(self._apply_filters)
        self._filter_state = INITIAL_GLOBAL_FILTERS

    @Slot()
    def _apply_filters(self):
        self._filter_state.size = self._size_filter.state()
        self._filter_state.count = self._count_filter.state()
        self._filter_state.tags = self._tags_filter.state()
        self.filters_changed.emit(self._filter_state)
