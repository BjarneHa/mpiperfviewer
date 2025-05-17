from PySide6.QtWidgets import QFileDialog, QGroupBox, QTabWidget, QVBoxLayout, QWidget
from matplotlib import style as mplstyle
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

from parser import RankFile, parse_rankfile
from plots import counts_plot_2d, sizes_plot_3d, tags_plot_3d

TABS = ["matrix", "total size", "msg count", "tags"]

class PlotViewer(QGroupBox):
    _rank_data: RankFile
    _canvases: dict[str, FigureCanvasQTAgg] = dict()

    def __init__(self, parent: QWidget | None=None):
        super().__init__("Plot Viewer", parent)
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        mplstyle.use("fast")

        tabwidget = QTabWidget(self)
        layout.addWidget(tabwidget)
        file, _ = QFileDialog.getOpenFileName(self, filter="*.toml")
        self._rank_data = parse_rankfile(file)
        for tab in TABS:
            tabQWidget = QWidget(self)
            layout = QVBoxLayout(tabQWidget)
            tabQWidget.setLayout(layout)
            _ = tabwidget.addTab(tabQWidget, tab)

            canvas = FigureCanvasQTAgg(Figure(figsize=(5, 3)))
            layout.addWidget(canvas)
            layout.addWidget(NavigationToolbar2QT(canvas, self))
            self._canvases[tab] = canvas

        ranks = [i for i in range(self._rank_data.general.num_procs)]

        sizes_plot_3d(f"Messages with size to peer from Rank {self._rank_data.general.own_rank}", self._canvases["total size"].figure, ranks, self._rank_data.exact_sizes())
        counts_plot_2d(f"Messages sent to peers by Rank {self._rank_data.general.own_rank}", self._canvases["msg count"].figure, ranks, self._rank_data.count())
        tags_plot_3d(f"Messages with tag to peer from Rank {self._rank_data.general.own_rank}", self._canvases["tags"].figure, ranks, self._rank_data.tags())
