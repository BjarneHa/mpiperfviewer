from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QGroupBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from create_views import MatrixGroupBy, MatrixMetric, RankPlotMetric, RankPlotType
from parser import Component, WorldData
from plotting.plots import (
    CountMatrixPlot,
    Counts2DBarPlot,
    PlotBase,
    SizeBar3DPlot,
    SizeMatrixPlot,
    SizePixelPlot,
    TagsBar3DPlot,
    TagsPixelPlot,
)

INITIAL_TABS = ["total size", "msg count"]


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _plots: list[PlotBase] = list()
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
        _ = self._tab_widget.tabCloseRequested.connect(self.close_tab)

    @property
    def world_data(self):
        return self._world_data

    @property
    def component_data(self):
        return self._world_data.components[self._component]

    def _initialize_tabs(self):
        self.add_tab(
            "total size",
            SizeMatrixPlot(
                self._world_data.meta, self.component_data, MatrixGroupBy.RANK
            ),
        )
        self.add_tab(
            "message count",
            CountMatrixPlot(
                self._world_data.meta, self.component_data, MatrixGroupBy.RANK
            ),
        )

    def add_tab(self, tab_title: str, plot: PlotBase, activate: bool = False):
        _ = self._tab_widget.insertTab(len(self._plots), plot, tab_title)
        self._plots.append(plot)
        for other_plot in self._plots:
            _ = plot.filter_view.filter_applied_globally.connect(
                other_plot.filter_view.apply_nonlocal_filter
            )
            _ = other_plot.filter_view.filter_applied_globally.connect(
                plot.filter_view.apply_nonlocal_filter
            )
        plot.init_plot()
        if activate:
            self._tab_widget.setCurrentWidget(plot)

    @Slot()
    def close_tab(self, index: int):
        self._tab_widget.removeTab(index)
        plot = self._plots.pop(index)
        for plot in self._plots:
            _ = plot.filter_view.filter_applied_globally.disconnect(
                plot.filter_view.apply_nonlocal_filter
            )
            _ = plot.filter_view.filter_applied_globally.disconnect(
                plot.filter_view.apply_nonlocal_filter
            )

    @Slot()
    def add_rank_plot(self, rank: int, metric: RankPlotMetric, type: RankPlotType):
        tab_title = f"rank {rank} – {metric} ({type})"
        match metric:
            case RankPlotMetric.TAGS:
                match type:
                    case RankPlotType.PIXEL_PLOT:
                        PlotType = TagsPixelPlot
                    case RankPlotType.BAR3D:
                        PlotType = TagsBar3DPlot
            case RankPlotMetric.SENT_SIZES:
                match type:
                    case RankPlotType.PIXEL_PLOT:
                        PlotType = SizePixelPlot
                    case RankPlotType.BAR3D:
                        PlotType = SizeBar3DPlot
            case RankPlotMetric.MESSAGE_COUNT:
                PlotType = Counts2DBarPlot

        plot = PlotType(self._world_data.meta, self.component_data, rank)
        self.add_tab(tab_title, plot, activate=True)

    @Slot()
    def add_matrix_plot(self, metric: MatrixMetric, group_by: MatrixGroupBy):
        match metric:
            case MatrixMetric.BYTES_SENT:
                self.add_tab(
                    "total size",
                    SizeMatrixPlot(
                        self._world_data.meta, self.component_data, group_by
                    ),
                    activate=True,
                )
            case MatrixMetric.MESSAGES_SENT:
                self.add_tab(
                    "message count",
                    CountMatrixPlot(
                        self._world_data.meta, self.component_data, group_by
                    ),
                    activate=True,
                )

    def _update_plots(self):
        for plot in self._plots:
            plot.canvas.figure.clear()
            plot.init_plot()
            plot.canvas.draw_idle()
