from typing import Callable

import qtawesome as qta
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mpiperfcli.parser import Component, WorldData
from mpiperfcli.plots import (
    CountMatrixPlot,
    Counts2DBarPlot,
    MatrixGroupBy,
    PlotBase,
    SizeBar3DPlot,
    SizeMatrixPlot,
    SizePixelPlot,
    TagsBar3DPlot,
    TagsPixelPlot,
)
from mpiperfviewer.create_views import (
    MatrixMetric,
    RankPlotMetric,
    RankPlotType,
)
from mpiperfviewer.filter_widgets import FilterView


class PlotWidget(QWidget):
    title: str
    icon: QIcon | None
    plot: PlotBase
    filter_view: FilterView
    reattach_or_detach_requested: Signal = Signal()
    _reattach_or_detach_button: QPushButton
    _cmd_line_edit: QLineEdit

    def __init__(
        self,
        title: str,
        plot_factory: Callable[[Figure], PlotBase],
        icon: QIcon | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.title = title
        self.icon = icon
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
        self._reattach_or_detach_button = QPushButton("Detach")
        self._reattach_or_detach_button.setIcon(qta.icon("mdi6.open-in-new"))
        self._reattach_or_detach_button.clicked.connect(self._attach_detach_clicked)
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
        cmd = f'mpiperfcli -p "{name}'
        if self.plot.cli_param() != "":
            cmd += "." + self.plot.cli_param()
        cmd += '"'
        cli_filters = self.filter_view.filter_state.cli_format()
        if cli_filters != "":
            cmd += f' -x "{name}={cli_filters}"'
        cmd += f' "{self.plot.world_meta.source_directory.absolute()}"'
        cmd += f' "{self.plot.component_data.name}"'
        self._cmd_line_edit.setText(cmd)

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
        self.plot.fig.clear()
        self.init_plot()
        self.canvas.draw_idle()
        self._update_cmd()

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

    def add_tab(self, plot: PlotWidget, activate: bool = False):
        _ = plot.reattach_or_detach_requested.connect(self.reattach_or_detach_tab)
        if plot.icon is None:
            _ = self._tab_widget.addTab(plot, plot.title)
        else:
            _ = self._tab_widget.addTab(plot, plot.icon, plot.title)
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
    def reattach_or_detach_tab(self):
        sender = self.sender()
        if not isinstance(sender, PlotWidget):
            raise Exception(f"Detach was called outside of a plot, from {sender}.")
        if sender.parent() is not None:  # pyright: ignore[reportUnnecessaryComparison]
            index = self._tab_widget.indexOf(sender)
            self._tab_widget.removeTab(index)
            sender.setParent(None)
            sender.showNormal()
        else:
            if sender.icon is None:
                _ = self._tab_widget.addTab(sender, sender.title)
            else:
                _ = self._tab_widget.addTab(sender, sender.icon, sender.title)

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

        icon = type.icon(color=metric.color)
        plot_widget = PlotWidget(
            tab_title,
            lambda f: PlotType(f, self._world_data.meta, self.component_data, rank),
            icon=icon,
            parent=self,
        )
        self.add_tab(plot_widget, activate=True)

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
        icon = metric.icon()
        widget = PlotWidget(
            tab_title,
            lambda fig: PlotType(
                fig, self._world_data.meta, self.component_data, group_by
            ),
            icon=icon,
            parent=self,
        )
        self.add_tab(widget, activate=True)

    def _update_plots(self):
        for plot in self._plots:
            plot.canvas.figure.clear()
            plot.init_plot()
            plot.canvas.draw_idle()
