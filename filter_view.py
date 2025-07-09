from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, override

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class RangeFilterObject(QObject):
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


class Filter(ABC):
    @abstractmethod
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
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
    def apply(self, data: NDArray[Any]):
        metric_min = self.min or np.iinfo(data.dtype).min
        metric_max = self.max or np.iinfo(data.dtype).max
        filter = (metric_min <= data) & (data <= metric_max)
        return filter


class ExactFilter(Filter):
    n: int

    def __init__(self, n: int):
        self.n = n

    @override
    def __str__(self) -> str:
        return "{" + f"n: {self.n}" + "}"

    @override
    def __eq__(self, other: object, /) -> bool:
        return type(other) is ExactFilter and self.n == other.n

    @override
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        return data == self.n


# class TagFilter(QWidget):
#     _checkbox: QCheckBox
#     _radio_include: QRadioButton
#     _radio_exclude: QRadioButton

#     def __init__(self, parent: QWidget | None = None):
#         super().__init__(parent)
#         self._radio_include = QRadioButton()
#         self._radio_exclude = QRadioButton()
#         # self._checkbox = QCheckBox(filter, parent)
#         _ = self._checkbox.checkStateChanged.connect(self._check_changed)
#         # layout.addWidget(self._checkbox, i * 2, 0, 1, 5)

#     @Slot()
#     def _check_changed(self, value: Qt.CheckState):
#         checked = value == Qt.CheckState.Checked

#     def state(self):
#         pass

DISCRETE_MULTIRANGE_REGEXP = r"|(-?\d+|\[-?\d+;-?\d+\])(,(-?\d+|\[-?\d+;-?\d+\]))*"

COLLECTIVES = [
    (-10, "MPI_Allgather"),
    (-11, "MPI_Allgatherv"),
    (-12, "MPI_Allreduce"),
    (-13, "MPI_Alltoall"),
    (-14, "MPI_Alltoallv"),
    (-15, "MPI_Alltoallw"),
    (-16, "MPI_Barrier"),
    (-17, "MPI_Bcast"),
    (-18, "MPI_Exscan"),
    (-19, "MPI_Gather"),
    (-20, "MPI_Gatherv"),
    (-21, "MPI_Reduce"),
    (-22, "MPI_Reduce_scatter"),
    (-23, "MPI_Reduce_scatter_block"),
    (-24, "MPI_Scan"),
    (-25, "MPI_Scatter"),
    (-26, "MPI_Scatterv"),
]


class CollectivesDialog(QDialog):
    changed: Signal = Signal(object)
    _checkboxes: list[QCheckBox]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._checkboxes = [QCheckBox(f"{s} ({n})") for n, s in COLLECTIVES]
        for cb in self._checkboxes:
            layout.addWidget(cb)
        button = QPushButton(self)
        button.setText("Close")
        button.pressed.connect(self.close_pressed)
        layout.addWidget(button)

    def state(self):
        return [
            tag for cb, (tag, _) in zip(self._checkboxes, COLLECTIVES) if cb.isChecked()
        ]

    @Slot()
    def close_pressed(self):
        self.hide()


class DiscreteMultiRangeFilter(Filter):
    ranges: list[RangeFilter]
    exact: list[ExactFilter]

    def __init__(self):
        self.ranges = list()
        self.exact = list()

    @override
    def apply(self, data: NDArray[Any]):
        filter = np.zeros_like(data, dtype=np.bool)
        for range in self.ranges:
            filter |= range.apply(data)
        for exact in self.exact:
            filter |= exact.apply(data)
        return filter


class InvertedFilter(Filter):
    _inner: Filter

    def __init__(self, inner: Filter):
        self._inner = inner

    @override
    def apply(self, data: NDArray[Any]):
        return ~self._inner.apply(data)


class DiscreteMultiRangeFilterWidget(QWidget):
    """A filter which allows the user to enter multiple ranges and values in a comma-separated format."""

    _line_edit: QLineEdit
    _button: QPushButton
    _collectives: CollectivesDialog

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QGridLayout(self)

        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText("x,[y;z]")
        validator = QRegularExpressionValidator(DISCRETE_MULTIRANGE_REGEXP)
        self._line_edit.setValidator(validator)
        layout.addWidget(self._line_edit, 0, 0, 1, 2)

        layout.addWidget(QLabel("Collectives:"), 1, 0, 1, 1)

        self._button = QPushButton()
        self._button.setText("Edit")
        self._button.pressed.connect(self.edit_pressed)
        layout.addWidget(self._button, 1, 1, 1, 1)

        self._collectives = CollectivesDialog()

    @Slot()
    def edit_pressed(self):
        self._collectives.show()

    def state(self) -> Filter:
        filter = DiscreteMultiRangeFilter()
        try:
            for tag in self._collectives.state():
                filter.exact.append(ExactFilter(tag))

            text = self._line_edit.text()
            if len(text) == 0:
                return filter

            for el in text.split(","):
                if "[" in el:
                    if el[-1] != "]":
                        raise ValueError("Range not closed.")
                    min, max = el[1:-1].split(";")
                    print(min, max)
                    filter.ranges.append(RangeFilter(int(min), int(max)))
                else:
                    filter.exact.append(ExactFilter(int(el)))
            return filter
        except ValueError as e:
            # TODO report error
            print(f"Bad filter. {e}")
            return UNFILTERED

    def set_disabled(self, disabled: bool):
        self._line_edit.setDisabled(disabled)
        self._button.setDisabled(disabled)
        if disabled:
            self._collectives.hide()


class TagFilterObject(QObject):
    _checkbox: QCheckBox
    _include_filter: DiscreteMultiRangeFilterWidget
    _radio_group: QButtonGroup
    _include_radio: QRadioButton
    _exclude_filter: DiscreteMultiRangeFilterWidget
    _exclude_radio: QRadioButton

    class RadioOptions(IntEnum):
        INCLUDE = 0
        EXCLUDE = 1

    def __init__(self, i: int, layout: QGridLayout, parent: QWidget | None = None):
        super().__init__(parent)
        self._checkbox = QCheckBox("tags", parent)
        _ = self._checkbox.checkStateChanged.connect(self._check_changed)
        layout.addWidget(self._checkbox, i * 2, 0, 1, 5)

        self._radio_group = QButtonGroup(parent, exclusive=True)

        self._include_radio = QRadioButton(parent)
        self._include_radio.setChecked(True)
        self._radio_group.addButton(
            self._include_radio, TagFilterObject.RadioOptions.INCLUDE
        )
        self._include_radio.setText("Include")
        layout.addWidget(self._include_radio, i * 2 + 1, 0, 1, 5)

        self._include_filter = DiscreteMultiRangeFilterWidget(parent)
        layout.addWidget(self._include_filter, i * 2 + 2, 0, 1, 5)

        self._exclude_radio = QRadioButton(parent)
        self._radio_group.addButton(
            self._exclude_radio, TagFilterObject.RadioOptions.EXCLUDE
        )
        self._exclude_radio.setText("Exclude")
        layout.addWidget(self._exclude_radio, i * 2 + 3, 0, 1, 5)

        self._exclude_filter = DiscreteMultiRangeFilterWidget(parent)
        layout.addWidget(self._exclude_filter, i * 2 + 4, 0, 1, 5)

        self._check_changed(Qt.CheckState.Unchecked)

    @Slot()
    def _check_changed(self, value: Qt.CheckState):
        checked = value == Qt.CheckState.Checked
        self._include_radio.setDisabled(not checked)
        self._exclude_radio.setDisabled(not checked)
        self._include_filter.set_disabled(not checked)
        self._exclude_filter.set_disabled(not checked)

    def state(self):
        if not self._checkbox.isChecked():
            return UNFILTERED
        match self._radio_group.checkedId():
            case TagFilterObject.RadioOptions.INCLUDE:
                return self._include_filter.state()
            case TagFilterObject.RadioOptions.EXCLUDE:
                return InvertedFilter(self._exclude_filter.state())
            case _:
                raise Exception("Unexpected active radio.")


class CheckFilterDialog(QDialog):
    def __init__(self, options: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        layout = QGridLayout(self)
        for i, opt in enumerate(options):
            cb = QCheckBox()
            layout.addWidget(cb, i, 0)
            layout.addWidget(QLabel(opt), i, 1)


class CheckFilterWidget(QWidget):
    _dialog: CheckFilterDialog
    _label: QLabel
    _edit_button: QPushButton

    def __init__(self, options: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        self._label = QLabel()
        self._edit_button = QPushButton()
        self._dialog = CheckFilterDialog(options)
        layout.addWidget(self._label)

    @Slot()
    def open_dialog(self):
        self._dialog.open()


UNFILTERED = RangeFilter()


@dataclass
class GlobalFilters:
    size: Filter
    count: Filter
    tags: Filter


INITIAL_GLOBAL_FILTERS = GlobalFilters(UNFILTERED, UNFILTERED, UNFILTERED)


class FilterView(QGroupBox):
    filters_changed: Signal = Signal(object)
    _size_filter: RangeFilterObject
    _count_filter: RangeFilterObject
    _tags_filter: TagFilterObject
    _apply_button: QPushButton
    _filter_state: GlobalFilters

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Filter", parent)
        layout = QVBoxLayout(self)
        range_layout = QGridLayout()
        layout.addLayout(range_layout)
        self._size_filter = RangeFilterObject("size", 0, range_layout, self)
        self._count_filter = RangeFilterObject("count", 1, range_layout, self)
        self._tags_filter = TagFilterObject(2, range_layout, self)
        self._apply_button = QPushButton("Apply")
        layout.addWidget(self._apply_button)
        self._apply_button.clicked.connect(self._apply_filters)
        self._filter_state = INITIAL_GLOBAL_FILTERS

    @Slot()
    def _apply_filters(self):
        self._filter_state.size = self._size_filter.state()
        self._filter_state.count = self._count_filter.state()
        self._filter_state.tags = self._tags_filter.state()
        self.filters_changed.emit(self._filter_state)
