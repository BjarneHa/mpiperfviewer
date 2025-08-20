from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum
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
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class Filter(ABC):
    @abstractmethod
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        pass


class Unfiltered(Filter):
    @override
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        return np.ones_like(data, dtype=np.dtype(np.bool))


class BadFilter(Unfiltered):
    pass


@dataclass
class FilterState:
    size: Filter = field(default_factory=lambda: Unfiltered())
    count: Filter = field(default_factory=lambda: Unfiltered())
    tags: Filter = field(default_factory=lambda: Unfiltered())


class FilterObjectBase(QObject):
    def update_filterstate(self, fs: FilterState) -> None:
        raise Exception("Unimplemented!")


class RangeFilterObject(FilterObjectBase):
    _checkbox: QCheckBox
    _min_edit: QLineEdit
    _max_edit: QLineEdit

    def __init__(
        self,
        filter: str,
        description: str,
        layout: QGridLayout,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._checkbox = QCheckBox(filter, parent)
        self._checkbox.setToolTip(description)
        _ = self._checkbox.checkStateChanged.connect(self._check_changed)
        r = layout.rowCount()
        layout.addWidget(self._checkbox, r, 0, 1, 5)
        self._min_edit = QLineEdit(parent, placeholderText="-∞")
        self._min_edit.setDisabled(True)
        self._min_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        self._max_edit = QLineEdit(parent, placeholderText="∞")
        self._max_edit.setDisabled(True)
        self._max_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        layout.addWidget(self._min_edit, r + 1, 0)
        layout.addWidget(QLabel("≤"), r + 1, 1)
        layout.addWidget(QLabel("≤"), r + 1, 3)
        filter_label = QLabel(f"{filter}")
        layout.addWidget(filter_label, r + 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._max_edit, r + 1, 4)

    @Slot()
    def _check_changed(self, value: Qt.CheckState):
        checked = value == Qt.CheckState.Checked
        self._min_edit.setDisabled(not checked)
        self._max_edit.setDisabled(not checked)

    def state(self):
        if not self._checkbox.isChecked():
            return Unfiltered()
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

    def copy_values(self, other: "RangeFilterObject"):
        self._checkbox.setCheckState(other._checkbox.checkState())
        self._min_edit.setText(other._min_edit.text())
        self._max_edit.setText(other._max_edit.text())


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
        metric_min = np.iinfo(data.dtype).min if self.min is None else self.min
        metric_max = np.iinfo(data.dtype).max if self.max is None else self.max
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
        _ = button.pressed.connect(self.close_pressed)
        layout.addWidget(button)

    def state(self):
        return [
            tag for cb, (tag, _) in zip(self._checkboxes, COLLECTIVES) if cb.isChecked()
        ]

    @Slot()
    def close_pressed(self):
        self.hide()

    def copy_values(self, other: "CollectivesDialog"):
        for self_cb, other_cb in zip(self._checkboxes, other._checkboxes):
            self_cb.setCheckState(other_cb.checkState())


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
        _ = self._button.pressed.connect(self.edit_pressed)
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
            return BadFilter()

    def set_disabled(self, disabled: bool):
        self._line_edit.setDisabled(disabled)
        self._button.setDisabled(disabled)
        if disabled:
            self._collectives.hide()

    def copy_values(self, other: "DiscreteMultiRangeFilterWidget"):
        self._line_edit.setText(other._line_edit.text())
        self._collectives.copy_values(other._collectives)


class TagFilterObject(FilterObjectBase):
    _checkbox: QCheckBox
    _include_filter: DiscreteMultiRangeFilterWidget
    _radio_group: QButtonGroup
    _include_radio: QRadioButton
    _exclude_filter: DiscreteMultiRangeFilterWidget
    _exclude_radio: QRadioButton

    class RadioOptions(IntEnum):
        INCLUDE = 0
        EXCLUDE = 1

    def __init__(self, layout: QGridLayout, parent: QWidget | None = None):
        super().__init__(parent)
        tags_description = "Select specific ranges of tags to plot."
        self._checkbox = QCheckBox("tags", parent)
        self._checkbox.setToolTip(tags_description)
        _ = self._checkbox.checkStateChanged.connect(self._check_changed)
        r = layout.rowCount()
        layout.addWidget(self._checkbox, r, 0, 1, 5)

        self._radio_group = QButtonGroup(parent, exclusive=True)

        self._include_radio = QRadioButton(parent)
        self._include_radio.setChecked(True)
        self._radio_group.addButton(
            self._include_radio, TagFilterObject.RadioOptions.INCLUDE
        )
        self._include_radio.setText("Include")
        layout.addWidget(self._include_radio, r + 1, 0, 1, 5)

        self._include_filter = DiscreteMultiRangeFilterWidget(parent)
        layout.addWidget(self._include_filter, r + 2, 0, 1, 5)

        self._exclude_radio = QRadioButton(parent)
        self._radio_group.addButton(
            self._exclude_radio, TagFilterObject.RadioOptions.EXCLUDE
        )
        self._exclude_radio.setText("Exclude")
        layout.addWidget(self._exclude_radio, r + 3, 0, 1, 5)

        self._exclude_filter = DiscreteMultiRangeFilterWidget(parent)
        layout.addWidget(self._exclude_filter, r + 4, 0, 1, 5)

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
            return Unfiltered()
        match self._radio_group.checkedId():
            case TagFilterObject.RadioOptions.INCLUDE:
                return self._include_filter.state()
            case TagFilterObject.RadioOptions.EXCLUDE:
                exclude_filter = self._exclude_filter.state()
                if type(exclude_filter) is BadFilter:
                    return exclude_filter
                return InvertedFilter(exclude_filter)
            case _:
                raise Exception("Unexpected active radio.")

    @override
    def update_filterstate(self, fs: FilterState):
        fs.tags = self.state()

    def copy_values(self, other: "TagFilterObject"):
        self._checkbox.setCheckState(other._checkbox.checkState())
        checked_id = other._radio_group.checkedId()
        self._radio_group.button(checked_id).setChecked(True)
        self._include_filter.copy_values(other._include_filter)
        self._exclude_filter.copy_values(other._exclude_filter)


class SizeFilterObject(RangeFilterObject):
    description: str = "Select a specific range of sizes to plot."

    def __init__(self, layout: QGridLayout, parent: QWidget | None = None):
        super().__init__("size", self.description, layout, parent)

    @override
    def update_filterstate(self, fs: FilterState):
        fs.size = super().state()


class CountFilterObject(RangeFilterObject):
    description: str = (
        "Filter out ranks and sizes/tags whose max entry is not within the given range."
    )

    def __init__(self, layout: QGridLayout, parent: QWidget | None = None):
        super().__init__("count", self.description, layout, parent)

    @override
    def update_filterstate(self, fs: FilterState):
        fs.count = super().state()


class FilterType(Enum):
    TAGS = 0
    SIZE = 1
    COUNT = 2


class FilterView(QGroupBox):
    filters_changed: Signal = Signal()
    filter_applied_globally: Signal = Signal(object)
    _size_filter: SizeFilterObject | None
    _count_filter: CountFilterObject | None
    _tags_filter: TagFilterObject | None
    _apply_buttons: dict[QPushButton, FilterObjectBase] = dict()
    _apply_everywhere_buttons: dict[QPushButton, FilterObjectBase] = dict()
    _filter_state: FilterState = FilterState()
    _layout: QGridLayout

    @property
    def filter_state(self):
        return self._filter_state

    def __init__(
        self,
        filter_types: list[FilterType] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__("Filter", parent)
        self._layout = QGridLayout(self)
        if filter_types is None or FilterType.SIZE in filter_types:
            self._size_filter = SizeFilterObject(self._layout, self)
            self._add_filter_object(self._size_filter)
        if filter_types is None or FilterType.COUNT in filter_types:
            self._count_filter = CountFilterObject(self._layout, self)
            self._add_filter_object(self._count_filter)
        if filter_types is None or FilterType.TAGS in filter_types:
            self._tags_filter = TagFilterObject(self._layout, self)
            self._add_filter_object(self._tags_filter)
        self._layout.setRowStretch(self._layout.rowCount(), 1)

    def _add_filter_object(self, object: FilterObjectBase):
        r = self._layout.rowCount()
        apply = QPushButton("Apply")
        apply_everywhere = QPushButton("Apply Everywhere")
        self._layout.addWidget(apply, r, 0, 1, 5)
        self._layout.addWidget(apply_everywhere, r + 1, 0, 1, 5)
        _ = apply.clicked.connect(self._apply_filters)
        _ = apply_everywhere.clicked.connect(self._apply_filter_everywhere)
        self._apply_buttons[apply] = object
        self._apply_everywhere_buttons[apply_everywhere] = object

    def _get_filter_for_sender(
        self, sender: QObject, buttons_map: dict[QPushButton, FilterObjectBase]
    ):
        if type(sender) is not QPushButton:
            raise TypeError(
                "FilterView._apply_filter slot was not called by an apply button"
            )
        filter_object = buttons_map.get(sender)
        if filter_object is None:
            raise TypeError(
                "FilterView._apply_filter slot was called by an unexpected apply button"
            )
        return filter_object

    def _apply_filter_object(self, filter_object: FilterObjectBase):
        filter_object.update_filterstate(self._filter_state)
        self.filters_changed.emit()

    @Slot()
    def _apply_filters(self):
        sender = self.sender()
        filter_object = self._get_filter_for_sender(sender, self._apply_buttons)
        self._apply_filter_object(filter_object)

    @Slot()
    def _apply_filter_everywhere(self):
        sender = self.sender()
        filter_object = self._get_filter_for_sender(
            sender, self._apply_everywhere_buttons
        )
        self.filter_applied_globally.emit(filter_object)
        self._apply_filter_object(filter_object)

    @Slot(object)
    def apply_nonlocal_filter(self, filter_object: FilterObjectBase):
        match filter_object:
            case TagFilterObject():
                if self._tags_filter is not None:
                    self._tags_filter.copy_values(filter_object)
            case SizeFilterObject():
                if self._size_filter is not None:
                    self._size_filter.copy_values(filter_object)
            case CountFilterObject():
                if self._count_filter is not None:
                    self._count_filter.copy_values(filter_object)
            case FilterObjectBase():
                raise Exception("Unreachable!")
        self._apply_filter_object(filter_object)
