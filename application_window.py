from typing import final

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

from filter_view import FilterView
from parser import Rank
from plot_view import PlotViewer
from statistics_view import StatisticsView


@final
class ApplicationWindow(QWidget):
    def __init__(self):
        super().__init__()
        file, _ = QFileDialog.getOpenFileName(self, filter="*.toml")
        rank_file = Rank(file)

        row_layout = QHBoxLayout(self)
        self._left_col = QVBoxLayout()
        self.statistics_view = StatisticsView(rank_file, self)
        self.filter_view = FilterView(self)
        self._left_col.addWidget(self.statistics_view)
        self._left_col.addWidget(self.filter_view)
        self._left_col.addStretch()
        row_layout.addLayout(self._left_col, 0)
        self._right_col = QVBoxLayout()
        self.plot_viewer = PlotViewer(rank_file, self)
        self._right_col.addWidget(self.plot_viewer)
        row_layout.addLayout(self._right_col, 1)
        self.filter_view.filters_changed.connect(self.plot_viewer.filters_changed)
