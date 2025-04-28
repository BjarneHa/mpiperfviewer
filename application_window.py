import sys
import time

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
import numpy as np

from filter_view import FilterView
from plot_view import PlotViewer
from statistics_view import StatisticsView


class ApplicationWindow(QWidget):
    def __init__(self):
        super().__init__()
        row_layout = QHBoxLayout(self)
        self._left_col = QVBoxLayout(self)
        self.statistics_view = StatisticsView(self)
        self.filter_view = FilterView(self)
        self._left_col.addWidget(self.statistics_view)
        self._left_col.addWidget(self.filter_view)
        row_layout.addLayout(self._left_col)
        self._right_col = QVBoxLayout(self)
        self.plot_viewer = PlotViewer(self)
        self._right_col.addWidget(self.plot_viewer)
        row_layout.addLayout(self._right_col)
        self.setLayout(row_layout)
