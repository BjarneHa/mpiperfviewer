from matplotlib import style as mplstyle
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGroupBox, QTabWidget, QVBoxLayout, QWidget

from filter_view import UNFILTERED, Filter
from parser import Rank
from plots import counts_plot_2d, sizes_plot_3d, tags_plot_3d

TABS = ["matrix", "total size", "msg count", "tags"]


class PlotViewer(QGroupBox):
    _rank_data: Rank
    _canvases: dict[str, FigureCanvasQTAgg] = dict()

    def __init__(self, rank_data: Rank, parent: QWidget | None = None):
        super().__init__("Plot Viewer", parent)
        self._rank_data = rank_data
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
        ranks = list(range(self._rank_data.general().num_procs))
        if "size" in _filters.keys() or filters is None:
            sizes_plot_3d(
                f"Messages with size to peer from Rank {self._rank_data.general().own_rank}",
                self._canvases["total size"].figure,
                ranks,
                self._rank_data.exact_sizes(filter=_filters.get("size", UNFILTERED)),
            )
            self._canvases["total size"].draw()
        if "count" in _filters.keys() or filters is None:
            counts_plot_2d(
                f"Messages sent to peers by Rank {self._rank_data.general().own_rank}",
                self._canvases["msg count"].figure,
                ranks,
                self._rank_data.count(filter=_filters.get("count", UNFILTERED)),
            )
            self._canvases["msg count"].draw()
        if "tags" in _filters.keys() or filters is None:
            tags_plot_3d(
                f"Messages with tag to peer from Rank {self._rank_data.general().own_rank}",
                self._canvases["tags"].figure,
                ranks,
                self._rank_data.tags(filter=_filters.get("tags", UNFILTERED)),
            )
            self._canvases["tags"].draw()

    @Slot(object)
    def filters_changed(self, filters: dict[str, Filter]):
        self._update_plots(filters)
