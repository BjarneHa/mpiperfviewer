from itertools import chain
from typing import Callable, override

import qtawesome as qta
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpiperfcli.parser import Component, ComponentData, WorldData, WorldMeta
from mpiperfcli.plots import (
    CountMatrixPlot,
    Counts2DBarPlot,
    MatrixGroupBy,
    MatrixMetric,
    MatrixPlotBase,
    PlotBase,
    RankPlotBase,
    RankPlotMetric,
    RankPlotType,
    SizeBar3DPlot,
    SizeMatrixPlot,
    SizePixelPlot,
    TagsBar3DPlot,
    TagsPixelPlot,
)
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QCloseEvent, QFont, QGuiApplication, QIcon, Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from serde import field, serde

from mpiperfcli import create_plot_from_plot_and_param
from mpiperfviewer.create_views import (
    matrix_metric_icon,
    rank_metric_color,
    rank_type_icon,
)
from mpiperfviewer.filter_widgets import FilterPresets, FilterView, FilterViewData
from mpiperfviewer.project_state import project_updated


@serde
class PlotWidgetData:
    name: str
    param: str
    filters: FilterViewData


def get_icon_for_plot(plot: PlotBase):
    if isinstance(plot, RankPlotBase):
        return rank_type_icon(plot.type(), rank_metric_color(plot.metric()))
    elif isinstance(plot, MatrixPlotBase):
        return matrix_metric_icon(plot.metric())


class PlotWidget(QWidget):
    icon: QIcon | None
    plot: PlotBase
    canvas: FigureCanvasQTAgg
    filter_view: FilterView
    reattach_or_detach_requested: Signal = Signal()
    closed: Signal = Signal()
    _reattach_or_detach_button: QPushButton
    _cmd_line_edit: QLineEdit

    def __init__(
        self,
        plot_factory: Callable[[Figure], PlotBase],
        presets: FilterPresets,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        plot_box = QGroupBox("Plot", self)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.canvas = FigureCanvasQTAgg()
        self.plot = plot_factory(self.canvas.figure)
        self.icon = get_icon_for_plot(self.plot)
        self.filter_view = FilterView(presets, self.plot.filter_types(), self)
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
        self._reattach_or_detach_button = QPushButton("Detach")
        self._reattach_or_detach_button.setIcon(qta.icon("mdi6.open-in-new"))
        _ = self._reattach_or_detach_button.clicked.connect(self._attach_detach_clicked)
        toolbar_layout.addWidget(self._reattach_or_detach_button)
        cmd_layout = QHBoxLayout()
        self._cmd_line_edit = QLineEdit(self, readOnly=True)
        monospace_font = QFont("")
        monospace_font.setStyleHint(QFont.StyleHint.Monospace)
        self._cmd_line_edit.setFont(monospace_font)
        cmd_layout.addWidget(self._cmd_line_edit)
        copy_button = QPushButton(self)
        copy_button.setIcon(qta.icon("mdi6.content-copy"))
        _ = copy_button.clicked.connect(self._copy_cmd)
        cmd_layout.addWidget(copy_button)
        plot_layout.addLayout(cmd_layout)
        self._update_cmd()

    def _update_cmd(self):
        name = self.plot.cli_name()
        cmd = f"mpiperfcli -p '{name}"
        if self.plot.cli_param() != "":
            cmd += "." + self.plot.cli_param()
        cmd += "'"
        cli_filters = self.filter_view.filter_state.cli_format()
        if cli_filters != "":
            cmd += f" -x '{name}={cli_filters}'"
        cmd += f" '{self.plot.world_meta.source_directory.absolute()}'"
        cmd += f" '{self.plot.component_data.name}'"
        self._cmd_line_edit.setText(cmd)

    @property
    def title(self):
        return self.plot.tab_title()

    @Slot()
    def _copy_cmd(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self._cmd_line_edit.text())

    @Slot()
    def _attach_detach_clicked(self):
        # Resending a different signal causes the sender of the signal to be changed
        self.reattach_or_detach_requested.emit()
        if self._reattach_or_detach_button.text() == "Detach":
            self._reattach_or_detach_button.setText("Attach")
            self._reattach_or_detach_button.setIcon(qta.icon("mdi6.open-in-app"))
        else:
            self._reattach_or_detach_button.setText("Detach")
            self._reattach_or_detach_button.setIcon(qta.icon("mdi6.open-in-new"))

    @Slot()
    def filters_changed(self):
        project_updated()
        self.draw_plot()
        self._update_cmd()

    @override
    def closeEvent(self, _event: QCloseEvent) -> None:
        self.closed.emit()

    def draw_plot(self):
        self.canvas.figure.clear()
        self.plot.draw_plot(self.filter_view.filter_state)
        self.canvas.draw_idle()

    def export_plot(self):
        return PlotWidgetData(
            name=self.plot.cli_name(),
            param=self.plot.cli_param(),
            filters=self.filter_view.export_data(),
        )

    @staticmethod
    def import_plot(
        data: PlotWidgetData,
        world_meta: WorldMeta,
        component_data: ComponentData,
        presets: FilterPresets,
        parent: QWidget | None = None,
    ):
        widget = PlotWidget(
            lambda f: create_plot_from_plot_and_param(
                data.name, data.param, f, world_meta, component_data
            ),
            presets,
            parent,
        )
        widget.filter_view.import_preset(data.filters)
        return widget


@serde
class PlotViewerData:
    tab_plots: list[PlotWidgetData] = field(default_factory=lambda : list[PlotWidgetData]())
    detached_plots: list[PlotWidgetData] = field(default_factory=lambda : list[PlotWidgetData]())
    presets: FilterPresets = field(default_factory = lambda : FilterPresets())


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _detached_plots: list[PlotWidget]
    _tab_widget: QTabWidget
    _component: Component
    presets: FilterPresets

    def __init__(
        self,
        world_data: WorldData,
        component: Component | None,
        data: PlotViewerData,
        parent: QWidget | None = None,
    ):
        super().__init__("Plot Viewer", parent)
        self._detached_plots = []
        self.presets = data.presets
        if component is None:
            raise Exception("Invalid component for project.")
        self._component = component
        self._world_data = world_data
        layout = QVBoxLayout(self)
        # mplstyle.use("fast")

        self._tab_widget = QTabWidget(self, tabsClosable=True)
        layout.addWidget(self._tab_widget)
        self._initialize_tabs(data)
        self._tab_widget.setMovable(True)
        _ = self._tab_widget.tabCloseRequested.connect(self.close_tab)

    @property
    def _all_plots(self):
        return chain(self._tab_plots, self._detached_plots)

    @property
    def _tab_plots(self):
        return [
            widget
            for widget in [
                self._tab_widget.widget(i) for i in range(self._tab_widget.count())
            ]
            if isinstance(widget, PlotWidget)
        ]

    @property
    def world_data(self):
        return self._world_data

    @property
    def component_data(self):
        return self._world_data.components[self._component]

    def _initialize_tabs(self, data: PlotViewerData):
        if len(data.tab_plots) + len(data.detached_plots) == 0:
            self.add_matrix_plot(MatrixMetric.MESSAGES_SENT, MatrixGroupBy.RANK)
            self.add_matrix_plot(MatrixMetric.BYTES_SENT, MatrixGroupBy.RANK)
            return
        for plot in data.tab_plots:
            plot_widget = PlotWidget.import_plot(
                plot, self.world_data.meta, self.component_data, self.presets, self
            )
            self.add_plot_widget(plot_widget)
        for plot in data.detached_plots:
            plot_widget = PlotWidget.import_plot(
                plot, self.world_data.meta, self.component_data, self.presets, self
            )
            self.add_plot_widget(plot_widget, detached=True)

    def add_plot_widget(
        self, plot: PlotWidget, detached: bool = False, activate: bool = False
    ):
        project_updated()
        _ = plot.closed.connect(self.plotwidget_closed)
        _ = plot.reattach_or_detach_requested.connect(self.reattach_or_detach_tab)
        for other_plot in self._all_plots:
            _ = plot.filter_view.connect_filters(other_plot.filter_view)
            _ = other_plot.filter_view.connect_filters(plot.filter_view)
        if detached:
            plot.setParent(None)
            plot.showNormal()
            self._detached_plots.append(plot)
            if activate:
                plot.raise_()
                plot.activateWindow()
        else:
            if plot.icon is None:
                _ = self._tab_widget.addTab(plot, plot.title)
            else:
                _ = self._tab_widget.addTab(plot, plot.icon, plot.title)
            if activate:
                self._tab_widget.setCurrentWidget(plot)
        plot.draw_plot()

    @Slot()
    def reattach_or_detach_tab(self):
        sender = self.sender()
        if not isinstance(sender, PlotWidget):
            raise Exception(f"Detach was called outside of a plot, from {sender}.")
        if sender.parent() is not None:  # pyright: ignore[reportUnnecessaryComparison]
            self._detached_plots.append(sender)
            index = self._tab_widget.indexOf(sender)
            self._tab_widget.removeTab(index)
            sender.setParent(None)
            sender.showNormal()
        else:
            self._detached_plots.remove(sender)
            if sender.icon is None:
                _ = self._tab_widget.addTab(sender, sender.title)
            else:
                _ = self._tab_widget.addTab(sender, sender.icon, sender.title)

    @Slot()
    def close_tab(self, index: int):
        project_updated()
        item = self._tab_widget.widget(index)
        self._tab_widget.removeTab(index)
        item.deleteLater()

    @Slot()
    def plotwidget_closed(self):
        sender = self.sender()
        if not isinstance(sender, PlotWidget):
            raise Exception(
                f"plotwidget_closed was called outside of a plot, from {sender}."
            )
        if sender.parent() is not None:  # pyright: ignore[reportUnnecessaryComparison]
            return
        try:
            self._detached_plots.remove(sender)
        except ValueError:
            print(f"{sender} not removed detached lit")

    @Slot()
    def add_rank_plot(self, rank: int, metric: str, type: str):
        metric = RankPlotMetric(metric)
        type = RankPlotType(type)
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
            presets=self.presets,
            parent=self,
        )
        self.add_plot_widget(plot_widget, activate=True)

    @Slot(str, str)
    def add_matrix_plot(self, metric: str, group_by: str):
        metric = MatrixMetric(metric)
        group_by = MatrixGroupBy(group_by)
        match metric:
            case MatrixMetric.BYTES_SENT:
                PlotType = SizeMatrixPlot
            case MatrixMetric.MESSAGES_SENT:
                PlotType = CountMatrixPlot
        widget = PlotWidget(
            lambda fig: PlotType(
                fig, self._world_data.meta, self.component_data, group_by
            ),
            presets=self.presets,
            parent=self,
        )
        self.add_plot_widget(widget, activate=True)

    def _update_plots(self):
        for plot in self._all_plots:
            plot.draw_plot()

    def _export_tab_plots(self):
        return [plot.export_plot() for plot in self._tab_plots]

    def _export_detached_plots(self):
        return [plot.export_plot() for plot in self._detached_plots]

    def export_data(self):
        return PlotViewerData(
            self._export_tab_plots(),
            self._export_detached_plots(),
            self.presets,
        )
