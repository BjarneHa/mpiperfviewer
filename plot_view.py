from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, final

from matplotlib.backend_bases import FigureCanvasBase
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from filter_view import INITIAL_GLOBAL_FILTERS, GlobalFilters
from parser import WorldData
from plots import (
    plot_counts_2d,
    plot_msgs_matrix,
    plot_size_matrix,
    plot_sizes_3d,
    plot_sizes_px,
    plot_tags_3d,
    plot_tags_px,
)

UpdateFn = Callable[[Figure, WorldData, GlobalFilters], None]


@dataclass
class PlotTab:
    title: str
    update: UpdateFn
    canvas: FigureCanvasBase


class MatrixMetric(StrEnum):
    BYTES_SENT = "bytes sent"
    MESSAGES_SENT = "messages sent"


class RankPlotMetric(StrEnum):
    SENT_SIZES = "sent sizes"
    MESSAGE_COUNT = "message count"
    TAGS = "tags"


class RankPlotType(StrEnum):
    PIXEL_PLOT = "Pixel Plot"
    BAR3D = "3D Bar"


INITIAL_TABS = ["total size", "msg count"]


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _plots: list[PlotTab] = list()
    _tab_widget: QTabWidget
    _filters: GlobalFilters

    def __init__(self, world_data: WorldData, parent: QWidget | None = None):
        super().__init__("Plot Viewer", parent)
        self._world_data = world_data
        self._filters = INITIAL_GLOBAL_FILTERS
        layout = QVBoxLayout(self)
        # mplstyle.use("fast")

        self._tab_widget = QTabWidget(self, tabsClosable=True)
        layout.addWidget(self._tab_widget)
        self._initialize_tabs()
        self.add_creation_tab()
        self._tab_widget.tabCloseRequested.connect(self.close_tab)

    def _initialize_tabs(self):
        self.add_tab("total size", plot_size_matrix)
        self.add_tab("message count", plot_msgs_matrix)

    def add_tab(self, title: str, update: UpdateFn, activate: bool = False):
        tabQWidget = QWidget(self._tab_widget)
        layout = QVBoxLayout(tabQWidget)
        tabQWidget.setLayout(layout)
        _ = self._tab_widget.insertTab(len(self._plots), tabQWidget, title)

        canvas = FigureCanvasQTAgg()
        layout.addWidget(canvas)
        layout.addWidget(NavigationToolbar2QT(canvas, self))

        pt = PlotTab(title, update, canvas)
        self._plots.append(pt)
        pt.update(canvas.figure, self._world_data, self._filters)
        if activate:
            self._tab_widget.setCurrentWidget(tabQWidget)

    @Slot()
    def close_tab(self, index: int):
        # TODO check last tab
        self._tab_widget.removeTab(index)
        self._plots.pop(index)

    @Slot()
    def add_rank_plot(self, rank: int, metric: RankPlotMetric, type: RankPlotType):
        tab_title = f"rank {rank} – {metric} ({type})"
        match metric:
            case RankPlotMetric.TAGS:
                match type:
                    case RankPlotType.PIXEL_PLOT:
                        plotfn = plot_tags_px
                    case RankPlotType.BAR3D:
                        plotfn = plot_tags_3d
            case RankPlotMetric.SENT_SIZES:
                match type:
                    case RankPlotType.PIXEL_PLOT:
                        plotfn = plot_sizes_px
                    case RankPlotType.BAR3D:
                        plotfn = plot_sizes_3d
            case RankPlotMetric.MESSAGE_COUNT:
                plotfn = plot_counts_2d
        self.add_tab(
            tab_title,
            lambda fig, wd, filters: plotfn(fig, rank, wd, filters),
            activate=True,
        )

    @Slot()
    def add_matrix_plot(self, metric: MatrixMetric, group_by: str):
        match metric:
            case MatrixMetric.BYTES_SENT:
                self.add_tab("total size", plot_size_matrix, activate=True)
            case MatrixMetric.MESSAGES_SENT:
                self.add_tab("message count", plot_msgs_matrix, activate=True)

    def add_creation_tab(self):
        ct = CreationTab(self, self._world_data)
        index = self._tab_widget.addTab(ct, "+")
        self._tab_widget.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.LeftSide, None
        )
        self._tab_widget.tabBar().setTabButton(
            index, QTabBar.ButtonPosition.RightSide, None
        )
        _ = ct.matrix_view.create_tab.connect(self.add_matrix_plot)
        _ = ct.rank_view.create_tab.connect(self.add_rank_plot)

    # If filters is not None, only plots related to the filters will be redrawn
    def _update_plots(self):
        for plot_tab in self._plots:
            plot_tab.canvas.figure.clear()
            plot_tab.update(plot_tab.canvas.figure, self._world_data, self._filters)
            plot_tab.canvas.draw_idle()

    @Slot(object)
    def filters_changed(self, filters: GlobalFilters):
        self._filters = filters
        self._update_plots()


@final
class CreationTab(QWidget):
    def __init__(self, parent: QWidget, world_data: WorldData):
        super().__init__(parent)
        layout = QGridLayout(self)
        self.matrix_view = MatrixView(self)
        self.rank_view = RankView(self, world_data)
        layout.addWidget(
            self.matrix_view, 0, 0, alignment=Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self.rank_view, 0, 1, alignment=Qt.AlignmentFlag.AlignVCenter)


class RankView(QGroupBox):
    _rank_edit: QLineEdit
    _metric_box: QComboBox
    _type_box: QComboBox
    create_tab: Signal = Signal(int, str, str)

    def __init__(self, parent: CreationTab, world_data: WorldData):
        super().__init__("Rank Statistics", parent)
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
        create_button.clicked.connect(self.on_create)
        self._metric_box.currentTextChanged.connect(self.on_select_metric)

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


class MatrixView(QGroupBox):
    _metric_box: QComboBox
    _group_by_box: QComboBox
    create_tab: Signal = Signal(str, str)

    def __init__(self, parent: CreationTab):
        super().__init__("Global Communication Matrix", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Metric:"), 0, 0)
        self._metric_box = QComboBox(self)
        for m in MatrixMetric:
            self._metric_box.addItem(m.value)
        layout.addWidget(self._metric_box, 0, 1)
        group_by_label = QLabel("Group by:")
        layout.addWidget(group_by_label, 1, 0)
        group_by_label.hide()  # TODO remove
        self._group_by_box = QComboBox(self)
        for item in ["Rank", "Core", "Socket", "Node"]:
            self._group_by_box.addItem(item)
        layout.addWidget(self._group_by_box, 1, 1)
        self._group_by_box.hide()  # TODO remove
        create_button = QPushButton("Create")
        layout.addWidget(create_button, 2, 0, 1, 2)
        create_button.clicked.connect(self.on_create)

    @Slot()
    def on_create(self):
        metric = (
            self._metric_box.currentText()
        )  # TODO valueerror when empty => user feedback
        group_by = self._group_by_box.currentText()
        self.create_tab.emit(metric, group_by)
