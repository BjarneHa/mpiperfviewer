from PySide6.QtCore import Slot
from PySide6.QtGui import QIcon
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
        self._tab_widget.setMovable(True)
        _ = self._tab_widget.tabCloseRequested.connect(self.close_tab)

    @property
    def world_data(self):
        return self._world_data

    @property
    def component_data(self):
        return self._world_data.components[self._component]

    def _initialize_tabs(self):
        self.add_matrix_plot(MatrixMetric.MESSAGES_SENT, MatrixGroupBy.RANK)
        self.add_matrix_plot(MatrixMetric.BYTES_SENT, MatrixGroupBy.RANK)

    def add_tab(
        self,
        tab_title: str,
        plot: PlotBase,
        icon: QIcon | None = None,
        activate: bool = False,
    ):
        _ = plot.detach_requested.connect(self.detach_tab)
        if icon is None:
            _ = self._tab_widget.addTab(plot, tab_title)
        else:
            _ = self._tab_widget.addTab(plot, icon, tab_title)
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
    def detach_tab(self):
        sender = self.sender()
        if not isinstance(sender, PlotBase):
            raise Exception(f"Detach was called outside of a plot, from {sender}.")
        index = self._tab_widget.indexOf(sender)
        self._tab_widget.removeTab(index)
        sender.setParent(None)
        sender.showNormal()

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
    def add_rank_plot(self, rank: int, metric: str, type: str):
        metric = RankPlotMetric(metric)
        type = RankPlotType(type)
        tab_title = f"rank {rank} – {metric} ({type})"
        match metric:
            case RankPlotMetric.TAGS:
                match type:
                    case RankPlotType.PIXEL_PLOT:
                        PlotType = TagsPixelPlot
                    case RankPlotType.BAR3D:
                        PlotType = TagsBar3DPlot
                    case _:
                        raise Exception("Unexpected option.")
            case RankPlotMetric.SENT_SIZES:
                match type:
                    case RankPlotType.PIXEL_PLOT:
                        PlotType = SizePixelPlot
                    case RankPlotType.BAR3D:
                        PlotType = SizeBar3DPlot
                    case _:
                        raise Exception("Unexpected option.")
            case RankPlotMetric.MESSAGE_COUNT:
                PlotType = Counts2DBarPlot

        plot = PlotType(self._world_data.meta, self.component_data, rank, parent=self)
        self.add_tab(tab_title, plot, type.icon(color=metric.color), activate=True)

    @Slot()
    def add_matrix_plot(self, metric: str, group_by: str):
        metric = MatrixMetric(metric)
        group_by = MatrixGroupBy(group_by)
        match metric:
            case MatrixMetric.BYTES_SENT:
                self.add_tab(
                    "total size",
                    SizeMatrixPlot(
                        self._world_data.meta, self.component_data, group_by
                    ),
                    metric.icon(),
                    activate=True,
                )
            case MatrixMetric.MESSAGES_SENT:
                self.add_tab(
                    "message count",
                    CountMatrixPlot(
                        self._world_data.meta, self.component_data, group_by
                    ),
                    metric.icon(),
                    activate=True,
                )

    def _update_plots(self):
        for plot in self._plots:
            plot.canvas.figure.clear()
            plot.init_plot()
            plot.canvas.draw_idle()
