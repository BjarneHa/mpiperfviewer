from matplotlib import style as mplstyle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGroupBox, QTabWidget, QVBoxLayout, QWidget

from filter_view import UNFILTERED, Filter
from parser import WorldData
from plots import plot_msgs_matrix, plot_size_matrix

TABS = ["total size", "msg count", "tags"]


class PlotViewer(QGroupBox):
    _world_data: WorldData
    _canvases: dict[str, FigureCanvasQTAgg] = dict()

    def __init__(self, world_data: WorldData, parent: QWidget | None = None):
        super().__init__("Plot Viewer", parent)
        self._world_data = world_data
        layout = QVBoxLayout(self)
        mplstyle.use("fast")

        tabwidget = QTabWidget(self)
        layout.addWidget(tabwidget)
        for tab in TABS:
            tabQWidget = QWidget(self)
            layout = QVBoxLayout(tabQWidget)
            tabQWidget.setLayout(layout)
            _ = tabwidget.addTab(tabQWidget, tab)

            canvas = FigureCanvasQTAgg()
            layout.addWidget(canvas)
            layout.addWidget(NavigationToolbar2QT(canvas, self))
            self._canvases[tab] = canvas
        self._update_plots()

    # If filters is not None, only plots related to the filters will be redrawn
    def _update_plots(self, filters: dict[str, Filter] | None = None):
        _filters = filters or dict()
        ranks = [
            rank.general().own_rank
            for rank in self._world_data.ranks
            if _filters.get("count", UNFILTERED).test(rank.total_msgs_sent)
        ]
        for rank in self._world_data.ranks:
            print(rank.total_msgs_sent)
        plot_msgs_matrix(
            "Communication Matrix (message count)",
            self._canvases["msg count"].figure,
            ranks,
            self._world_data,
        )
        plot_size_matrix(
            "Communication Matrix (total size)",
            self._canvases["total size"].figure,
            ranks,
            self._world_data,
        )
        self._canvases["total size"].draw()

    @Slot(object)
    def filters_changed(self, filters: dict[str, Filter]):
        self._update_plots(filters)
