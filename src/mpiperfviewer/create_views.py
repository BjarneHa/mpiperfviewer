import qtawesome as qta
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QIcon, QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from mpiperfcli.parser import ComponentData, WorldData
from mpiperfcli.plots import MatrixGroupBy, MatrixMetric, RankPlotMetric, RankPlotType


def rank_type_icon(type: RankPlotType, color: str | None = None) -> QIcon:
    match type:
        case type.PIXEL_PLOT:
            name = "gradient-vertical"
        case type.BAR3D:
            name = "cube-outline"
        case type.BAR:
            name = "chart-bar"
    return qta.icon(f"mdi6.{name}", color=color)


def rank_metric_color(metric: RankPlotMetric):
    match metric:
        case metric.SENT_SIZES:
            return "orange"
        case metric.MESSAGE_COUNT:
            return "cyan"
        case metric.TAGS:
            return "green"


def rank_metric_icon(metric: RankPlotMetric, color: str | None = None) -> QIcon:
    return qta.icon(
        "mdi6.circle", color=rank_metric_color(metric) if color is None else color
    )


def matrix_metric_color(metric: MatrixMetric) -> str:
    match metric:
        case metric.BYTES_SENT:
            return "red"
        case metric.MESSAGES_SENT:
            return "blue"


def matrix_metric_icon(metric: MatrixMetric, color: str | None = None) -> QIcon:
    return qta.icon(
        "mdi6.data-matrix",
        color=matrix_metric_color(metric) if color is None else color,
    )


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
            self._metric_box.addItem(rank_metric_icon(metric), metric)
        layout.addWidget(self._metric_box, 1, 1)
        layout.addWidget(QLabel("Plot type"), 2, 0)
        self._type_box = QComboBox(self)
        self._add_type(RankPlotType.PIXEL_PLOT)
        self._add_type(RankPlotType.BAR3D)
        layout.addWidget(self._type_box, 2, 1)
        create_button = QPushButton("Create")
        create_button.setIcon(qta.icon("mdi6.plus"))
        layout.addWidget(create_button, 3, 0, 1, 2)
        _ = create_button.clicked.connect(self.on_create)
        _ = self._metric_box.currentTextChanged.connect(self.on_select_metric)

    def _add_type(self, type: RankPlotType):
        self._type_box.addItem(rank_type_icon(type), type)

    @Slot()
    def on_create(self):
        try:
            rank = int(self._rank_edit.text())
        except Exception:
            _ = QMessageBox.warning(self, "Error", "Please specify a rank.")
            return
        metric = self._metric_box.currentText()
        type = self._type_box.currentText()
        self.create_tab.emit(rank, metric, type)

    @Slot()
    def on_select_metric(self, selected: str):
        if selected == RankPlotMetric.MESSAGE_COUNT:
            self._type_box.clear()
            self._add_type(RankPlotType.BAR)
        elif self._type_box.currentText() == RankPlotType.BAR:
            self._type_box.clear()
            self._add_type(RankPlotType.PIXEL_PLOT)
            self._add_type(RankPlotType.BAR3D)


class CreateMatrixView(QGroupBox):
    _metric_box: QComboBox
    _group_by_box: QComboBox
    create_tab: Signal = Signal(str, str)

    def __init__(self, component_data: ComponentData, parent: QWidget):
        super().__init__("Create Global Communication Matrix", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Metric:"), 0, 0)
        self._metric_box = QComboBox(self)
        for m in MatrixMetric:
            self._metric_box.addItem(matrix_metric_icon(m), m.value)
        layout.addWidget(self._metric_box, 0, 1)
        group_by_label = QLabel("Group by:")
        layout.addWidget(group_by_label, 1, 0)
        self._group_by_box = QComboBox(self)
        self._group_by_box.addItem(MatrixGroupBy.RANK)
        if component_data.by_core is not None:
            self._group_by_box.addItem(MatrixGroupBy.CORE)
        if component_data.by_socket is not None:
            self._group_by_box.addItem(MatrixGroupBy.SOCKET)
        if component_data.by_numa is not None:
            self._group_by_box.addItem(MatrixGroupBy.NUMA)
        if component_data.by_node is not None:
            self._group_by_box.addItem(MatrixGroupBy.NODE)
        layout.addWidget(self._group_by_box, 1, 1)
        create_button = QPushButton("Create")
        create_button.setIcon(qta.icon("mdi6.plus"))
        layout.addWidget(create_button, 2, 0, 1, 2)
        _ = create_button.clicked.connect(self.on_create)

    @Slot()
    def on_create(self):
        metric = self._metric_box.currentText()
        group_by = self._group_by_box.currentText()
        self.create_tab.emit(metric, group_by)
