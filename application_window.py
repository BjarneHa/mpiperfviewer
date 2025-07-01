from pathlib import Path
from typing import final

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QVBoxLayout,
    QWidget,
)

from filter_view import FilterView
from parser import WorldData
from plot_view import PlotViewer
from statistics_view import StatisticsView


@final
class ApplicationWindow(QWidget):
    def __init__(self):
        super().__init__()
        while True:
            file = QFileDialog.getExistingDirectory(self)  # TODO FileNotFoundError
            world_data = WorldData(Path(file))

            component, ok = QInputDialog.getItem(
                self,
                "Select which component to view.",
                "Component",
                list(world_data.components.keys()),
                0,
                False,
            )
            if ok:
                break

        row_layout = QHBoxLayout(self)
        self._left_col = QVBoxLayout()
        self.statistics_view = StatisticsView(world_data, component, self)
        self.filter_view = FilterView(self)
        self._left_col.addWidget(self.statistics_view)
        self._left_col.addWidget(self.filter_view)
        self._left_col.addStretch()
        self._right_col = QVBoxLayout()
        self.plot_viewer = PlotViewer(world_data, component, self)
        self._right_col.addWidget(self.plot_viewer)
        self.filter_view.filters_changed.connect(self.plot_viewer.filters_changed)
        row_layout.addLayout(self._left_col, 0)
        row_layout.addLayout(self._right_col, 1)
