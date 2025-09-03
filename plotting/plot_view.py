from typing import Callable

import qtawesome as qta
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QGroupBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qtpy.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QVBoxLayout

from create_views import MatrixGroupBy, MatrixMetric, RankPlotMetric, RankPlotType
from filtering.filter_widgets import FilterView
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


class PlotWidget(QWidget):
    plot: PlotBase
    filter_view: FilterView
    detach_requested: Signal = Signal()
    _detach_button: QPushButton

    def __init__(
        self,
        plot_factory: Callable[[Figure], PlotBase],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        plot_box = QGroupBox("Plot", self)
        self.canvas = FigureCanvasQTAgg()
        self.plot = plot_factory(self.canvas.figure)
        self.filter_view = FilterView(self.plot.filter_types(), self)
        _ = self.filter_view.filters_changed.connect(self.filters_changed)
        layout.addWidget(plot_box, stretch=1)
        layout.addWidget(self.filter_view, stretch=0)
        if len(self.plot.filter_types()) == 0:
            self.filter_view.hide()
        plot_layout = QVBoxLayout(plot_box)
        plot_layout.addWidget(self.canvas)
        toolbar_layout = QHBoxLayout()
        plot_layout.addLayout(toolbar_layout)
        toolbar_layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        self._detach_button = QPushButton("Detach")
        self._detach_button.setIcon(qta.icon("mdi6.open-in-new"))
        toolbar_layout.addWidget(self._detach_button)
        _ = self._detach_button.clicked.connect(self._detach_clicked)

    @Slot()
    def _detach_clicked(self):
        # Resending a different signal causes the sender of the signal to be changed
        self.detach_requested.emit()
        self._detach_button.hide()

    @Slot()
    def filters_changed(self):
        self.plot.fig.clear()
        self.init_plot()
        self.canvas.draw_idle()

    def init_plot(self):
        self.plot.init_plot(self.filter_view.filter_state)


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _plots: list[PlotWidget] = list()
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
        plot: PlotWidget,
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
        if not isinstance(sender, PlotWidget):
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

        plot_widget = PlotWidget(
            lambda f: PlotType(f, self._world_data.meta, self.component_data, rank),
            parent=self,
        )
        self.add_tab(
            tab_title, plot_widget, type.icon(color=metric.color), activate=True
        )

    @Slot()
    def add_matrix_plot(self, metric: str, group_by: str):
        metric = MatrixMetric(metric)
        group_by = MatrixGroupBy(group_by)
        match metric:
            case MatrixMetric.BYTES_SENT:
                tab_title = "total size"
                PlotType = SizeMatrixPlot

            case MatrixMetric.MESSAGES_SENT:
                tab_title = "message count"
                PlotType = CountMatrixPlot
        widget = PlotWidget(
            lambda fig: PlotType(
                fig, self._world_data.meta, self.component_data, group_by
            ),
            parent=self,
        )
        self.add_tab(
            tab_title,
            widget,
            metric.icon(),
            activate=True,
        )

    def _update_plots(self):
        for plot in self._plots:
            plot.canvas.figure.clear()
            plot.init_plot()
            plot.canvas.draw_idle()
