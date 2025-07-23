from dataclasses import dataclass
from typing import Callable

from matplotlib.backend_bases import FigureCanvasBase
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from create_views import MatrixMetric, RankPlotMetric, RankPlotType
from filter_view import INITIAL_GLOBAL_FILTERS, GlobalFilters
from parser import Component, WorldData
from plots import (
    plot_counts_2d,
    plot_msgs_matrix,
    plot_size_matrix,
    plot_sizes_3d,
    plot_sizes_px,
    plot_tags_3d,
    plot_tags_px,
)

UpdateFn = Callable[[Figure, WorldData, Component, GlobalFilters], None]


@dataclass
class PlotTab:
    title: str
    update: UpdateFn
    canvas: FigureCanvasBase


INITIAL_TABS = ["total size", "msg count"]


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _plots: list[PlotTab] = list()
    _tab_widget: QTabWidget
    _filters: GlobalFilters
    _component: Component

    def __init__(
        self, world_data: WorldData, component: Component, parent: QWidget | None = None
    ):
        super().__init__("Plot Viewer", parent)
        self._component = component
        self._world_data = world_data
        self._filters = INITIAL_GLOBAL_FILTERS
        layout = QVBoxLayout(self)
        # mplstyle.use("fast")

        self._tab_widget = QTabWidget(self, tabsClosable=True)
        layout.addWidget(self._tab_widget)
        self._initialize_tabs()
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
        pt.update(canvas.figure, self._world_data, self._component, self._filters)
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
        # plotfn = plot_tags_3d  # TODO remove
        self.add_tab(
            tab_title,
            lambda fig, wd, comp, filters: plotfn(fig, rank, wd, comp, filters),
            activate=True,
        )

    @Slot()
    def add_matrix_plot(self, metric: MatrixMetric, group_by: str):
        match metric:
            case MatrixMetric.BYTES_SENT:
                self.add_tab("total size", plot_size_matrix, activate=True)
            case MatrixMetric.MESSAGES_SENT:
                self.add_tab("message count", plot_msgs_matrix, activate=True)

    # If filters is not None, only plots related to the filters will be redrawn
    def _update_plots(self):
        for plot_tab in self._plots:
            plot_tab.canvas.figure.clear()
            plot_tab.update(
                plot_tab.canvas.figure, self._world_data, self._component, self._filters
            )
            plot_tab.canvas.draw_idle()

    @Slot(object)
    def filters_changed(self, filters: GlobalFilters):
        self._filters = filters
        self._update_plots()
