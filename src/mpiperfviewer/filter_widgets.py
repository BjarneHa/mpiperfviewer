from enum import IntEnum
from typing import Self, override

import numpy as np
import qtawesome as qta
from PySide6.QtCore import (
    QObject,
    Qt,
    Signal,
    Slot,
)
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
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)
from serde import field, serde

from mpiperfcli.filters import (
    BadFilter,
    FilterState,
    FilterType,
    InvertedFilter,
    MultiRangeFilter,
    RangeFilter,
    Unfiltered,
)


class PresetEditDialog[T](QDialog):
    _ok: bool
    _filter_layout: QGridLayout
    _name_edit: QLineEdit
    _finish_button: QPushButton

    def __init__(self, parent: QWidget, name: str):
        super().__init__(parent)
        self._ok = False
        self.setWindowTitle("Edit preset")
        layout = QVBoxLayout(self)
        general_group = QGroupBox("General", self)
        filter_group = QGroupBox("Filter", self)
        general_layout = QGridLayout(general_group)
        self._filter_layout = QGridLayout(filter_group)
        layout.addWidget(general_group)
        layout.addWidget(filter_group)

        name_label = QLabel(self, text="Preset name:")
        self._name_edit = QLineEdit(self, text=name)
        _ = self._name_edit.textChanged.connect(self._name_changed)
        general_layout.addWidget(name_label, 0, 0)
        general_layout.addWidget(self._name_edit, 0, 1)

        footer_buttons = QHBoxLayout()
        layout.addLayout(footer_buttons)
        self._finish_button = QPushButton("Finish")
        self._finish_button.setIcon(qta.icon("mdi6.check"))
        self._finish_button.setEnabled(len(name) > 0)
        _ = self._finish_button.clicked.connect(self._finish_clicked)
        footer_buttons.addWidget(self._finish_button)
        close_button = QPushButton("Cancel")
        close_button.setIcon(qta.icon("mdi6.close"))
        _ = close_button.clicked.connect(self.close)
        footer_buttons.addWidget(close_button)

    @Slot()
    def _name_changed(self, text: str):
        self._finish_button.setEnabled(len(text.rstrip()) > 0)

    @Slot()
    def _finish_clicked(self):
        self._ok = True
        _ = self.close()


class AbstractPresetDialog[T](QDialog):
    _ok: bool
    _list_widget: QListWidget
    _presets: dict[str, T]
    _apply_button: QPushButton
    _edit_button: QPushButton
    _delete_button: QPushButton

    def __init__[U](
        self,
        presets: dict[str, T],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._presets = presets
        self._ok = False
        self.setWindowTitle("Presets")
        layout = QVBoxLayout(self)
        list_layout = QHBoxLayout()
        layout.addLayout(list_layout)
        self._list_widget = QListWidget(self)
        _ = self._list_widget.itemSelectionChanged.connect(self._item_selection_changed)
        for preset in presets.keys():
            self._list_widget.addItem(preset)
        list_layout.addWidget(self._list_widget)
        buttons_layout = QVBoxLayout()
        list_layout.addLayout(buttons_layout)
        create_button = QPushButton(self)
        create_button.setIcon(qta.icon("mdi6.plus"))
        create_button.setToolTip("Create a new preset.")
        _ = create_button.clicked.connect(self._add_clicked)
        buttons_layout.addWidget(create_button)
        self._edit_button = QPushButton(self)
        self._edit_button.setIcon(qta.icon("mdi6.pencil"))
        self._edit_button.setToolTip("Edit the selected preset.")
        self._edit_button.setEnabled(False)
        _ = self._edit_button.clicked.connect(self._edit_clicked)
        buttons_layout.addWidget(self._edit_button)
        self._delete_button = QPushButton(self)
        self._delete_button.setIcon(qta.icon("mdi6.delete"))
        self._delete_button.setToolTip("Delete the selected preset.")
        self._delete_button.setEnabled(False)
        _ = self._delete_button.clicked.connect(self._remove_clicked)
        buttons_layout.addWidget(self._delete_button)
        buttons_layout.addStretch()
        footer_buttons = QHBoxLayout()
        self._apply_button = QPushButton("Apply")
        self._apply_button.setEnabled(False)
        self._apply_button.setIcon(qta.icon("mdi6.check"))
        _ = self._apply_button.clicked.connect(self._apply_clicked)
        footer_buttons.addWidget(self._apply_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.setIcon(qta.icon("mdi6.close"))
        _ = cancel_button.clicked.connect(self.close)
        footer_buttons.addWidget(cancel_button)
        layout.addLayout(footer_buttons)

    def _warn_duplicate_name(self, name: str):
        _ = QMessageBox.warning(
            self,
            "Choose a different name.",
            f'Preset "{name}" already exists. Please choose a different name.',
        )

    @Slot()
    def _apply_clicked(self):
        self._ok = True
        _ = self.close()

    @Slot()
    def _add_clicked(self):
        ok, name, preset = self._open_preset_edit_dialog("", None)
        if not ok:
            return
        while name in self._presets.keys():
            self._warn_duplicate_name(name)
            ok, name, preset = self._open_preset_edit_dialog(name, preset)
            if not ok:
                return
        self._presets[name] = preset
        self._list_widget.addItem(name)

    @Slot()
    def _edit_clicked(self):
        indexes = self._list_widget.selectedIndexes()
        if len(indexes) != 1:
            return
        old_index = indexes[0]
        old_name = self._list_widget.item(old_index.row()).text()
        ok, name, preset = self._open_preset_edit_dialog(
            old_name, self._presets[old_name]
        )
        if not ok:
            return
        while old_name != name and name in self._presets.keys():
            self._warn_duplicate_name(name)
            ok, name, preset = self._open_preset_edit_dialog(name, preset)
            if not ok:
                return
        self._presets[name] = preset
        if name != old_name:
            del self._presets[old_name]
            _ = self._list_widget.takeItem(old_index.row())
            self._list_widget.addItem(name)

    @Slot()
    def _remove_clicked(self):
        selected = self._list_widget.selectedIndexes()
        for item in selected:
            item = self._list_widget.takeItem(item.row())
            del self._presets[item.text()]

    @Slot()
    def _item_selection_changed(self):
        items = self._list_widget.selectedItems()
        self._apply_button.setEnabled(len(items) == 1)
        self._edit_button.setEnabled(len(items) == 1)
        self._delete_button.setEnabled(len(items) == 1)

    def _open_preset_edit_dialog(self, name: str, preset: T|None) -> tuple[bool, str, T]:
        raise Exception("Unimplemented!")

    def get_preset(self):
        _ = self.exec_()
        if not self._ok:
            return None
        items = self._list_widget.selectedItems()
        match items:
            case [item]:
                return self._presets[item.text()]
            case _:
                return None


# ABC does not work properly with PySide widgets
class FilterObjectBase[F, Data](QObject):
    filterstate_changed: Signal = Signal()
    applied_everywhere: Signal = Signal(object)

    def _apply_everywhere(self):
        self.applied_everywhere.emit(self.export_data())

    @Slot()
    def update_filterstate(self) -> None:
        raise Exception("Unimplemented!")

    def state(self) -> F | Unfiltered:
        raise Exception("Unimplemented!")

    @Slot()
    def import_preset(self, preset: Data) -> None:
        raise Exception("Unimplemented!")

    def export_data(self) -> Data:
        raise Exception("Unimplemented!")

    def _add_apply_buttons(self, layout: QGridLayout):
        r = layout.rowCount()
        apply = QPushButton("Apply")
        apply.setIcon(qta.icon("mdi6.check"))
        apply_everywhere = QPushButton("Apply Everywhere")
        apply_everywhere.setIcon(qta.icon("mdi6.check-all"))
        layout.addWidget(apply, r, 0, 1, 5)
        layout.addWidget(apply_everywhere, r + 1, 0, 1, 5)
        _ = apply.clicked.connect(self.update_filterstate)
        _ = apply_everywhere.clicked.connect(self.update_filterstate)
        _ = apply_everywhere.clicked.connect(self._apply_everywhere)


@serde
class RangeFilterData:
    enabled: bool
    min: int | None
    max: int | None


class RangeFilterObject(FilterObjectBase[RangeFilter, RangeFilterData]):
    _checkbox: QCheckBox
    _min_edit: QLineEdit
    _max_edit: QLineEdit
    _parent_widget: QWidget
    _presets: dict[str, RangeFilterData] | None
    _filter_state: FilterState

    def __init__(
        self,
        name: str,
        description: str,
        layout: QGridLayout,
        filter_state: FilterState,
        parent: QWidget,
        presets: dict[str, RangeFilterData] | None = None,
    ):
        super().__init__(parent)
        self._parent_widget = parent
        self._presets = presets
        self._filter_state = filter_state
        self._checkbox = QCheckBox(name, parent)
        self._checkbox.setToolTip(description)
        _ = self._checkbox.checkStateChanged.connect(self._check_changed)
        r = layout.rowCount()
        header_layout = QHBoxLayout()
        header_layout.addWidget(self._checkbox)
        header_layout.addStretch()
        if presets is not None:
            preset_button = QPushButton(parent=parent)
            preset_button.setIcon(qta.icon("mdi6.folder-cog-outline"))
            preset_button.setToolTip("Use or create a filter preset.")
            _ = preset_button.clicked.connect(self._open_preset_dialogue)
            header_layout.addWidget(preset_button)
        layout.addLayout(header_layout, r, 0, 1, 5)
        self._min_edit = QLineEdit(parent, placeholderText="-∞")
        self._min_edit.setDisabled(True)
        self._min_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        self._max_edit = QLineEdit(parent, placeholderText="∞")
        self._max_edit.setDisabled(True)
        self._max_edit.setValidator(QRegularExpressionValidator(r"-?\d+", self))
        layout.addWidget(self._min_edit, r + 1, 0)
        layout.addWidget(QLabel("≤"), r + 1, 1)
        layout.addWidget(QLabel("≤"), r + 1, 3)
        filter_label = QLabel(f"{name}")
        layout.addWidget(filter_label, r + 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._max_edit, r + 1, 4)
        if presets is not None: # Only add buttons if not in preset creation dialog
            self._add_apply_buttons(layout)

    @Slot()
    def _check_changed(self, value: Qt.CheckState):
        checked = value == Qt.CheckState.Checked
        self._min_edit.setDisabled(not checked)
        self._max_edit.setDisabled(not checked)

    @override
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

    @override
    @Slot()
    def import_preset(self, preset: RangeFilterData):
        self._checkbox.setChecked(preset.enabled)
        self._min_edit.setText(str(preset.min) if preset.min is not None else "")
        self._max_edit.setText(str(preset.max) if preset.max is not None else "")
        self.update_filterstate()

    @override
    def export_data(self):
        min = self._min_edit.text()
        max = self._max_edit.text()
        return RangeFilterData(
            self._checkbox.isChecked(),
            int(min) if min != "" else None,
            int(max) if max != "" else None,
        )

    def _open_preset_dialogue(self) -> None:
        raise Exception("Unimplemented!")


MULTIRANGE_REGEXP = r"[inf0-9,;\+\-\[\]]*"

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
    checked: Signal = Signal(int)
    unchecked: Signal = Signal(int)
    checkboxes: list[QCheckBox]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.checkboxes = [QCheckBox(f"{s} ({n})") for n, s in COLLECTIVES]
        for cb in self.checkboxes:
            layout.addWidget(cb)
            _ = cb.checkStateChanged.connect(self._any_box_check_state_changed)
        button = QPushButton(self)
        button.setText("Close")
        _ = button.pressed.connect(self.close_pressed)
        layout.addWidget(button)

    def state(self):
        return [
            tag for cb, (tag, _) in zip(self.checkboxes, COLLECTIVES) if cb.isChecked()
        ]

    def _get_checkbox_index(self, sender: QObject):
        if not isinstance(sender, QCheckBox):
            raise Exception(f'Unexpected sender {sender} for "checked" slot in {self}.')
        try:
            return self.checkboxes.index(sender)
        except ValueError:
            raise Exception(f'Non-child sender {sender} for "checked" slot in {self}.')

    @Slot(Qt.CheckState)
    def _any_box_check_state_changed(self, state: Qt.CheckState):
        sender = self.sender()
        i = self._get_checkbox_index(sender)
        tag, _ = COLLECTIVES[i]
        if not self.isVisible():
            return
        if state == Qt.CheckState.Unchecked:
            self.unchecked.emit(tag)
        else:
            self.checked.emit(tag)

    @Slot()
    def close_pressed(self):
        self.hide()

    def copy_values(self, other: "CollectivesDialog"):
        for self_cb, other_cb in zip(self.checkboxes, other.checkboxes):
            self_cb.setCheckState(other_cb.checkState())


@serde
class MultiRangeFilterData:
    data: str


class MultiRangeFilterWidget(QWidget):
    """A filter which allows the user to enter multiple ranges and values in a comma-separated format."""

    _valid_syntax: str = "Filter syntax is valid."
    _line_edit: QLineEdit
    _button: QPushButton
    _collectives: CollectivesDialog
    _filter_status_btn: QPushButton

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QGridLayout(self)

        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText("x,[y;z]")
        _ = self._line_edit.textChanged.connect(self._filter_line_changed)
        validator = QRegularExpressionValidator(MULTIRANGE_REGEXP)
        self._line_edit.setValidator(validator)
        inputs_layout = QGridLayout()
        self._filter_status_btn = QPushButton(self, flat=True)
        _ = self._filter_status_btn.clicked.connect(self._status_btn_clicked)
        self._set_filter_status(ok=True)
        layout.addLayout(inputs_layout, 0, 0, 1, 2)
        inputs_layout.addWidget(self._line_edit, 0, 0, 1, 2)
        inputs_layout.addWidget(self._filter_status_btn, 0, 2)
        inputs_layout.addWidget(QLabel("Collectives:"), 1, 0)

        self._button = QPushButton("Edit", self)
        self._button.setIcon(qta.icon("mdi6.pencil"))
        _ = self._button.pressed.connect(self.edit_pressed)
        inputs_layout.addWidget(self._button, 1, 1)
        inputs_layout.setColumnStretch(0, 1)
        inputs_layout.setColumnStretch(1, 1)
        inputs_layout.setColumnStretch(2, 0)

        self._collectives = CollectivesDialog(self)
        _ = self._collectives.checked.connect(self._collectives_checked)
        _ = self._collectives.unchecked.connect(self._collectives_unchecked)

    def _set_filter_status(self, ok: bool, msg: str|None=None):
        if ok:
            self._filter_status_btn.setIcon(qta.icon("mdi6.check", color="green"))
            self._filter_status_btn.setToolTip(self._valid_syntax)
        else:
            self._filter_status_btn.setIcon(qta.icon("mdi6.alert", color="orange"))
            self._filter_status_btn.setToolTip(f"Error in filter syntax: {msg}")

    @Slot()
    def _status_btn_clicked(self):
        tooltip = self._filter_status_btn.toolTip()
        if tooltip == self._valid_syntax:
            _ = QMessageBox.information(self, tooltip, tooltip)
        else:
            _ = QMessageBox.warning(self, "Error in filter syntax.", tooltip)


    @Slot()
    def _filter_line_changed(self):
        try:
            _ = MultiRangeFilter(self._line_edit.text())
            self._set_filter_status(ok=True)
        except ValueError as e:
            self._set_filter_status(ok=False, msg=str(e))

    @Slot()
    def edit_pressed(self):
        filter = MultiRangeFilter(self._line_edit.text(), tolerant=True)
        tags = np.array([tag for tag, _ in COLLECTIVES])
        tag_included = filter.apply(tags)
        for cb, included in zip(self._collectives.checkboxes, tag_included):
            cb.setChecked(included)
        self._collectives.open()

    @Slot(int)
    def _collectives_checked(self, tag: int):
        text = self._line_edit.text()
        if text == "":
            self._line_edit.setText(str(tag))
        else:
            self._line_edit.setText(text + "," + str(tag))

    @Slot(int)
    def _collectives_unchecked(self, tag: int):
        text = self._line_edit.text()
        filter = MultiRangeFilter(text, tolerant=True)
        segments = text.split(",")
        for exact in filter.exact:
            if exact.segment is None:
                raise Exception(
                    "Unexpected Error: Filter should be associated with string segment."
                )
            if exact.n == tag:
                segments[exact.segment] = ""

        for range_ in filter.ranges:
            if range_.segment is None:
                raise Exception(
                    "Unexpected Error: Filter should be associated with string segment."
                )
            segments[range_.segment] = range_.remove_exact(tag)
        try:
            while True:
                empty_segment = segments.index("")
                _ = segments.pop(empty_segment)
        except ValueError:
            pass
        text = ",".join(segments)
        self._line_edit.setText(text)

    def state(self):
        try:
            return MultiRangeFilter(self._line_edit.text())
        except ValueError as e:
            _ = QMessageBox.warning(self, "Error in Filter", str(e))
            return BadFilter()

    def set_disabled(self, disabled: bool):
        self._line_edit.setDisabled(disabled)
        self._button.setDisabled(disabled)
        if disabled:
            self._collectives.hide()

    def copy_values(self, other: "MultiRangeFilterWidget"):
        self._line_edit.setText(other._line_edit.text())
        self._collectives.copy_values(other._collectives)

    @Slot()
    def import_preset(self, preset: MultiRangeFilterData):
        self._line_edit.setText(preset.data)

    def export_data(self):
        return MultiRangeFilterData(self._line_edit.text())


class TagFilterMode(IntEnum):
    INCLUDE = 0
    EXCLUDE = 1


@serde
class TagFilterData:
    enabled: bool
    mode: int
    include_preset: MultiRangeFilterData
    exclude_preset: MultiRangeFilterData


class TagFilterObject(FilterObjectBase[MultiRangeFilter|BadFilter|InvertedFilter, TagFilterData]):
    _checkbox: QCheckBox
    _include_filter: MultiRangeFilterWidget
    _radio_group: QButtonGroup
    _include_radio: QRadioButton
    _exclude_filter: MultiRangeFilterWidget
    _exclude_radio: QRadioButton
    _parent_widget: QWidget
    _presets: dict[str, TagFilterData] | None
    _filter_state: FilterState

    def __init__(
        self,
        layout: QGridLayout,
        filter_state: FilterState,
        parent: QWidget,
        presets: dict[str, TagFilterData] | None = None,
    ):
        super().__init__(parent)
        self._parent_widget = parent
        self._presets = presets
        self._filter_state = filter_state
        tags_description = "Select specific ranges of tags to plot."
        self._checkbox = QCheckBox("tag", parent)
        self._checkbox.setToolTip(tags_description)
        _ = self._checkbox.checkStateChanged.connect(self._check_changed)
        r = layout.rowCount()
        header_layout = QHBoxLayout()
        header_layout.addWidget(self._checkbox)
        header_layout.addStretch()
        if presets is not None:
            preset_button = QPushButton(parent=parent)
            preset_button.setIcon(qta.icon("mdi6.folder-cog-outline"))
            preset_button.setToolTip("Use or create a filter preset.")
            _ = preset_button.clicked.connect(self._open_preset_dialog)
            header_layout.addWidget(preset_button)
        layout.addLayout(header_layout, r, 0, 1, 5)
        self._radio_group = QButtonGroup(parent, exclusive=True)

        self._include_radio = QRadioButton(parent)
        self._include_radio.setChecked(True)
        self._radio_group.addButton(self._include_radio, TagFilterMode.INCLUDE)
        self._include_radio.setText("Include")
        layout.addWidget(self._include_radio, r + 1, 0, 1, 5)

        self._include_filter = MultiRangeFilterWidget(parent)
        layout.addWidget(self._include_filter, r + 2, 0, 1, 5)

        self._exclude_radio = QRadioButton(parent)
        self._radio_group.addButton(self._exclude_radio, TagFilterMode.EXCLUDE)
        self._exclude_radio.setText("Exclude")
        layout.addWidget(self._exclude_radio, r + 3, 0, 1, 5)

        self._exclude_filter = MultiRangeFilterWidget(parent)
        layout.addWidget(self._exclude_filter, r + 4, 0, 1, 5)

        self._check_changed(Qt.CheckState.Unchecked)
        if presets is not None: # Only show if not in preset creation dialog
            self._add_apply_buttons(layout)

    @Slot()
    def _check_changed(self, value: Qt.CheckState):
        checked = value == Qt.CheckState.Checked
        self._include_radio.setDisabled(not checked)
        self._exclude_radio.setDisabled(not checked)
        self._include_filter.set_disabled(not checked)
        self._exclude_filter.set_disabled(not checked)

    @override
    def state(self):
        if not self._checkbox.isChecked():
            return Unfiltered()
        match self._radio_group.checkedId():
            case TagFilterMode.INCLUDE:
                return self._include_filter.state()
            case TagFilterMode.EXCLUDE:
                exclude_filter = self._exclude_filter.state()
                if type(exclude_filter) is BadFilter:
                    return exclude_filter
                return InvertedFilter(exclude_filter)
            case _:
                raise Exception("Unexpected active radio.")

    @override
    @Slot()
    def update_filterstate(self):
        self._filter_state.tag = self.state()
        self.filterstate_changed.emit()

    def copy_values(self, other: "TagFilterObject"):
        self._checkbox.setCheckState(other._checkbox.checkState())
        checked_id = other._radio_group.checkedId()
        self._radio_group.button(checked_id).setChecked(True)
        self._include_filter.copy_values(other._include_filter)
        self._exclude_filter.copy_values(other._exclude_filter)

    @override
    @Slot()
    def import_preset(self, preset: TagFilterData):
        self._checkbox.setChecked(preset.enabled)
        match TagFilterMode(preset.mode):
            case TagFilterMode.INCLUDE:
                self._include_radio.setChecked(True)
            case TagFilterMode.EXCLUDE:
                self._exclude_radio.setChecked(True)
        self._include_filter.import_preset(preset.include_preset)
        self._exclude_filter.import_preset(preset.exclude_preset)
        self.update_filterstate()

    @override
    def export_data(self):
        return TagFilterData(
            self._checkbox.isChecked(),
            self._radio_group.checkedId(),
            self._include_filter.export_data(),
            self._exclude_filter.export_data(),
        )

    @Slot()
    def _open_preset_dialog(self):
        assert self._presets is not None
        preset = TagFilterPresetDialog(self._presets, self._parent_widget).get_preset()
        if preset is not None:
            self.import_preset(preset)


class TagFilterPresetEditDialog(PresetEditDialog[TagFilterData]):
    _filter_obj: TagFilterObject

    def __init__(self, parent: QWidget, name: str, preset: TagFilterData | None):
        super().__init__(parent, name)
        self._filter_obj = TagFilterObject(self._filter_layout, FilterState(), self)
        if preset is not None:
            self._filter_obj.import_preset(preset)

    def get_result(self) -> tuple[bool, str, TagFilterData]:
        return self._ok, self._name_edit.text().rstrip(), self._filter_obj.export_data()


class TagFilterPresetDialog(AbstractPresetDialog[TagFilterData]):
    @override
    def _open_preset_edit_dialog(self, name: str, preset: TagFilterData | None) -> tuple[bool, str, TagFilterData]:
        dialog = TagFilterPresetEditDialog(self, name, preset)
        _ = dialog.exec_()
        return dialog.get_result()

class SizeFilterObject(RangeFilterObject):
    description: str = "Select a specific range of sizes to plot."
    applied_everywhere: Signal = Signal(object)

    def __init__(
        self,
        layout: QGridLayout,
        filter_state: FilterState,
        parent: QWidget,
        presets: dict[str, RangeFilterData] | None = None,
    ):
        super().__init__("size", self.description, layout, filter_state, parent, presets)

    @override
    def _open_preset_dialogue(self):
        assert self._presets is not None
        preset = SizeFilterPresetDialog(self._presets, self._parent_widget).get_preset()
        if preset is not None:
            self.import_preset(preset)

    @override
    @Slot()
    def update_filterstate(self):
        self._filter_state.size = super().state()
        self.filterstate_changed.emit()


class SizeFilterPresetEditDialog(PresetEditDialog[RangeFilterData]):
    _filter_obj: SizeFilterObject

    def __init__(self, parent: QWidget, name: str, preset: RangeFilterData | None):
        super().__init__(parent, name)
        self._filter_obj = SizeFilterObject(self._filter_layout, FilterState(), self)
        if preset is not None:
            self._filter_obj.import_preset(preset)

    def get_result(self) -> tuple[bool, str, RangeFilterData]:
        return self._ok, self._name_edit.text().rstrip(), self._filter_obj.export_data()

class SizeFilterPresetDialog(AbstractPresetDialog[RangeFilterData]):
    @override
    def _open_preset_edit_dialog(self, name: str, preset: RangeFilterData | None) -> tuple[bool, str, RangeFilterData]:
        dialog = SizeFilterPresetEditDialog(self, name, preset)
        _ = dialog.exec_()
        return dialog.get_result()


class CountFilterObject(RangeFilterObject):
    applied_everywhere: Signal = Signal(object)
    description: str = (
        "Filter out ranks and sizes/tags whose max entry is not within the given range."
    )

    def __init__(
        self,
        layout: QGridLayout,
        filter_state: FilterState,
        parent: QWidget,
        presets: dict[str, RangeFilterData] | None = None,
    ):
        super().__init__("count", self.description, layout, filter_state, parent, presets)

    @override
    def _open_preset_dialogue(self):
        assert self._presets is not None
        preset = CountFilterPresetDialog(self._presets, self._parent_widget).get_preset()
        if preset is not None:
            self.import_preset(preset)

    @override
    @Slot()
    def update_filterstate(self):
        self._filter_state.count = super().state()
        self.filterstate_changed.emit()

class CountFilterPresetEditDialog(PresetEditDialog[RangeFilterData]):
    _filter_obj: CountFilterObject

    def __init__(self, parent: QWidget, name: str, preset: RangeFilterData | None):
        super().__init__(parent, name)
        self._filter_obj = CountFilterObject(self._filter_layout, FilterState(), self)
        if preset is not None:
            self._filter_obj.import_preset(preset)

    def get_result(self) -> tuple[bool, str, RangeFilterData]:
        return self._ok, self._name_edit.text().rstrip(), self._filter_obj.export_data()

class CountFilterPresetDialog(AbstractPresetDialog[RangeFilterData]):
    @override
    def _open_preset_edit_dialog(self, name: str, preset: RangeFilterData | None) -> tuple[bool, str, RangeFilterData]:
        dialog = CountFilterPresetEditDialog(self, name, preset)
        _ = dialog.exec_()
        return dialog.get_result()

@serde
class FilterViewData:
    size_preset: RangeFilterData | None
    count_preset: RangeFilterData | None
    tags_preset: TagFilterData | None


@serde
class FilterPresets:
    size_presets: dict[str, RangeFilterData] = field(
        default_factory=lambda: dict[str, RangeFilterData]()
    )
    count_presets: dict[str, RangeFilterData] = field(
        default_factory=lambda: dict[str, RangeFilterData]()
    )
    tags_presets: dict[str, TagFilterData] = field(
        default_factory=lambda: dict[str, TagFilterData]()
    )


class FilterView(QGroupBox):
    filters_changed: Signal = Signal()
    _size_filter: SizeFilterObject | None
    _count_filter: CountFilterObject | None
    _tags_filter: TagFilterObject | None
    _filter_state: FilterState
    _layout: QGridLayout
    _presets: FilterPresets

    @property
    def filter_state(self):
        return self._filter_state

    def __init__(
        self,
        presets: FilterPresets,
        filter_types: list[FilterType] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__("Filter", parent)
        self._presets = presets
        self._filter_state = FilterState()
        self._layout = QGridLayout(self)
        if filter_types is None or FilterType.SIZE in filter_types:
            self._size_filter = SizeFilterObject(
                self._layout, self._filter_state, self, self._presets.size_presets
            )
            _ = self._size_filter.filterstate_changed.connect(self.filters_changed)
        else:
            self._size_filter = None
        if filter_types is None or FilterType.COUNT in filter_types:
            self._count_filter = CountFilterObject(
                self._layout, self._filter_state, self, self._presets.count_presets
            )
            _ = self._count_filter.filterstate_changed.connect(self.filters_changed)
        else:
            self._count_filter = None
        if filter_types is None or FilterType.TAG in filter_types:
            self._tags_filter = TagFilterObject(
                self._layout, self._filter_state, self, self._presets.tags_presets
            )
            _ = self._tags_filter.filterstate_changed.connect(self.filters_changed)
        else:
            self._tags_filter = None
        self._layout.setRowStretch(self._layout.rowCount(), 1)

    def connect_filters(self, other: Self):
        if self._tags_filter is not None and other._tags_filter is not None:
            _ = self._tags_filter.applied_everywhere.connect(other._tags_filter.import_preset)
        if self._size_filter is not None and other._size_filter is not None:
            _ = self._size_filter.applied_everywhere.connect(other._size_filter.import_preset)
        if self._count_filter is not None and other._count_filter is not None:
            _ = self._count_filter.applied_everywhere.connect(other._count_filter.import_preset)

    @Slot()
    def filter_changed(self):
        self.filters_changed.emit()

    def export_data(self):
        return FilterViewData(
            self._size_filter.export_data() if self._size_filter is not None else None,
            self._count_filter.export_data()
            if self._count_filter is not None
            else None,
            self._tags_filter.export_data() if self._tags_filter is not None else None,
        )

    def import_preset(self, preset: FilterViewData):
        if preset.size_preset is not None and self._size_filter is not None:
            self._size_filter.import_preset(preset.size_preset)
        if preset.count_preset is not None and self._count_filter is not None:
            self._count_filter.import_preset(preset.count_preset)
        if preset.tags_preset is not None and self._tags_filter is not None:
            self._tags_filter.import_preset(preset.tags_preset)
