from pathlib import Path
from tomllib import TOMLDecodeError
from typing import final

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from mpiperfcli.parser import WorldData
from mpiperfviewer.create_views import CreateMatrixView, CreateRankView
from mpiperfviewer.plot_view import PlotViewer
from mpiperfviewer.statistics_view import StatisticsView


@final
class ApplicationWindow(QWidget):
    def _get_directory_from_dialog(self):
        file = QFileDialog.getExistingDirectory(self)
        if file == "":
            exit(0)
        return file

    def __init__(self, args: list[str]):
        super().__init__()
        if len(args) > 0:
            file = args[0]
        else:
            file = self._get_directory_from_dialog()

        while True:
            try:
                world_data = WorldData(Path(file))
                break
            except (FileNotFoundError, TOMLDecodeError) as e:
                _ = QMessageBox.warning(
                    self,
                    "Error",
                    f"Directory did not contain valid MPI performance counter data: {e}.",
                )
                file = self._get_directory_from_dialog()

        component, ok = (
            (args[1], True)
            if len(args) > 1 and args[1] in world_data.components.keys()
            else QInputDialog.getItem(
                self,
                "Select which component to view.",
                "Component",
                list(world_data.components.keys()),
                0,
                False,
            )
        )
        if not ok:
            raise Exception("User did not choose a component")

        row_layout = QHBoxLayout(self)
        self._left_col = QVBoxLayout()
        self.statistics_view = StatisticsView(world_data, component, self)
        self.create_matrix_view = CreateMatrixView(self)
        self.create_rank_view = CreateRankView(world_data, self)
        self._left_col.addWidget(self.statistics_view)
        self._left_col.addWidget(self.create_matrix_view)
        self._left_col.addWidget(self.create_rank_view)
        self._left_col.addStretch()
        self._right_col = QVBoxLayout()
        self.plot_viewer = PlotViewer(world_data, component, self)
        _ = self.create_matrix_view.create_tab.connect(self.plot_viewer.add_matrix_plot)
        _ = self.create_rank_view.create_tab.connect(self.plot_viewer.add_rank_plot)
        self._right_col.addWidget(self.plot_viewer)
        row_layout.addLayout(self._left_col, 0)
        row_layout.addLayout(self._right_col, 1)
