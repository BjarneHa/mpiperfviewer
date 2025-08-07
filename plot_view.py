from dataclasses import dataclass
from typing import Callable

from matplotlib.backend_bases import FigureCanvasBase
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from create_views import MatrixMetric, RankPlotMetric, RankPlotType
from filter_view import FilterState, FilterView
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

UpdateFn = Callable[[Figure, WorldData, Component, FilterState], None]


@dataclass
class PlotTab:
    title: str
    update: UpdateFn
    canvas: FigureCanvasBase
    filters: FilterState
    filter_view: FilterView


INITIAL_TABS = ["total size", "msg count"]


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _plots: list[PlotTab] = list()
    _tabs_by_filter_view: dict[FilterView, PlotTab] = dict()
    _tab_widget: QTabWidget
    _component: Component

    def __init__(
        self, world_data: WorldData, component: Component, parent: QWidget | None = None
    ):
        super().__init__("Plot Viewer", parent)
        self._component = component
        self._world_data = world_data
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
        layout = QHBoxLayout(tabQWidget)
        plot_box = QGroupBox("Plot", tabQWidget)
        filter_view = FilterView(tabQWidget)
        filter_view.filters_changed.connect(self.filters_changed)
        layout.addWidget(plot_box, stretch=1)
        layout.addWidget(filter_view, stretch=0)
        plot_layout = QVBoxLayout(plot_box)
        tabQWidget.setLayout(plot_layout)
        _ = self._tab_widget.insertTab(len(self._plots), tabQWidget, title)
        canvas = FigureCanvasQTAgg()
        plot_layout.addWidget(canvas)
        plot_layout.addWidget(NavigationToolbar2QT(canvas, tabQWidget))

        pt = PlotTab(title, update, canvas, FilterState(), filter_view)
        self._plots.append(pt)
        self._tabs_by_filter_view[filter_view] = pt
        for plot in self._plots:
            plot.filter_view.filter_applied_globally.connect(
                filter_view.apply_nonlocal_filter
            )
            filter_view.filter_applied_globally.connect(
                plot.filter_view.apply_nonlocal_filter
            )
        pt.update(canvas.figure, self._world_data, self._component, pt.filters)
        if activate:
            self._tab_widget.setCurrentWidget(tabQWidget)

    @Slot()
    def close_tab(self, index: int):
        # TODO check last tab
        self._tab_widget.removeTab(index)
        pt = self._plots.pop(index)
        for plot in self._plots:
            plot.filter_view.filter_applied_globally.disconnect(
                pt.filter_view.apply_nonlocal_filter
            )
            pt.filter_view.filter_applied_globally.disconnect(
                plot.filter_view.apply_nonlocal_filter
            )
        self._tabs_by_filter_view.pop(pt.filter_view)

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
                plot_tab.canvas.figure,
                self._world_data,
                self._component,
                plot_tab.filters,
            )
            plot_tab.canvas.draw_idle()

    @Slot(object)
    def filters_changed(self, filters: FilterState):
        # This is shitty code, instead every tab should be its own component
        sender = self.sender()
        if type(sender) is not FilterView:
            raise TypeError("Unexpected sender type.")
        plot_tab = self._tabs_by_filter_view[sender]
        plot_tab.filters = filters
        plot_tab.canvas.figure.clear()
        plot_tab.update(
            plot_tab.canvas.figure,
            self._world_data,
            self._component,
            plot_tab.filters,
        )
        plot_tab.canvas.draw_idle()
