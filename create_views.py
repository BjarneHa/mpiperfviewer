from enum import StrEnum

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from parser import WorldData


class MatrixMetric(StrEnum):
    BYTES_SENT = "bytes sent"
    MESSAGES_SENT = "messages sent"


class MatrixGroupBy(StrEnum):
    RANK = "Rank"
    NUMA = "NUMA Node"
    SOCKET = "Socket"
    NODE = "Node"


class RankPlotMetric(StrEnum):
    SENT_SIZES = "sent sizes"
    MESSAGE_COUNT = "message count"
    TAGS = "tags"


class RankPlotType(StrEnum):
    PIXEL_PLOT = "Pixel Plot"
    BAR3D = "3D Bar"


class CreateRankView(QGroupBox):
    _rank_edit: QLineEdit
    _metric_box: QComboBox
    _type_box: QComboBox
    create_tab: Signal = Signal(int, str, str)

    def __init__(self, world_data: WorldData, parent: QWidget):
        super().__init__("Create Rank Communication Plot", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Rank"), 0, 0)
        max_rank = world_data.meta.num_processes - 1
        rank_placeholder_text = f"0-{max_rank}"
        self._rank_edit = QLineEdit(self, placeholderText=rank_placeholder_text)
        self._rank_edit.setValidator(QIntValidator(self, bottom=0, top=max_rank))
        self._rank_edit.rect
        layout.addWidget(self._rank_edit, 0, 1)
        layout.addWidget(QLabel("Metric"), 1, 0)
        self._metric_box = QComboBox(self)
        for metric in RankPlotMetric:
            self._metric_box.addItem(metric)
        layout.addWidget(self._metric_box, 1, 1)
        layout.addWidget(QLabel("Plot type"), 2, 0)
        self._type_box = QComboBox(self)
        for metric in RankPlotType:
            self._type_box.addItem(metric)
        layout.addWidget(self._type_box, 2, 1)
        create_button = QPushButton("Create")
        layout.addWidget(create_button, 3, 0, 1, 2)
        _ = create_button.clicked.connect(self.on_create)
        _ = self._metric_box.currentTextChanged.connect(self.on_select_metric)

    @Slot()
    def on_create(self):
        rank = int(
            self._rank_edit.text()
        )  # TODO valueerror when empty => user feedback
        metric = self._metric_box.currentText()
        type = self._type_box.currentText()
        self.create_tab.emit(rank, metric, type)

    @Slot()
    def on_select_metric(self, selected: str):
        if selected == RankPlotMetric.MESSAGE_COUNT:
            self._type_box.clear()
            self._type_box.addItem("Bar Chart")
        elif self._type_box.currentText() == "Bar Chart":
            self._type_box.clear()
            self._type_box.addItem(RankPlotType.PIXEL_PLOT)
            self._type_box.addItem(RankPlotType.BAR3D)


class CreateMatrixView(QGroupBox):
    _metric_box: QComboBox
    _group_by_box: QComboBox
    create_tab: Signal = Signal(str, str)

    def __init__(self, parent: QWidget):
        super().__init__("Create Global Communication Matrix", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Metric:"), 0, 0)
        self._metric_box = QComboBox(self)
        for m in MatrixMetric:
            self._metric_box.addItem(m.value)
        layout.addWidget(self._metric_box, 0, 1)
        group_by_label = QLabel("Group by:")
        layout.addWidget(group_by_label, 1, 0)
        self._group_by_box = QComboBox(self)
        for item in MatrixGroupBy:
            self._group_by_box.addItem(item)
        layout.addWidget(self._group_by_box, 1, 1)
        create_button = QPushButton("Create")
        layout.addWidget(create_button, 2, 0, 1, 2)
        _ = create_button.clicked.connect(self.on_create)

    @Slot()
    def on_create(self):
        metric = (
            self._metric_box.currentText()
        )  # TODO valueerror when empty => user feedback
        group_by = self._group_by_box.currentText()
        self.create_tab.emit(metric, group_by)
