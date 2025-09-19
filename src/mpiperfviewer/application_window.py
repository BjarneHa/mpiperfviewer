from pathlib import Path
from tomllib import TOMLDecodeError
from typing import final

from mpiperfcli.parser import WorldData
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from mpiperfviewer.create_views import CreateMatrixView, CreateRankView
from mpiperfviewer.plot_view import PlotViewer, ProjectData
from mpiperfviewer.statistics_view import StatisticsView


@final
class ApplicationWindow(QWidget):
    def _get_directory_from_dialog(self):
        file = QFileDialog.getExistingDirectory(self)
        if file == "":
            exit(0)
        return Path(file)

    def __init__(self, project_data: ProjectData | None = None):
        super().__init__()
        if project_data is None:
            project_data = ProjectData(None, None, [], [])
        if project_data.source_directory is None:
            project_data.source_directory = self._get_directory_from_dialog()

        while True:
            try:
                self.world_data = WorldData(project_data.source_directory)
                break
            except (FileNotFoundError, TOMLDecodeError) as e:
                _ = QMessageBox.warning(
                    self,
                    "Error",
                    f"Directory did not contain valid MPI performance counter data: {e}.",
                )
                project_data.source_directory = self._get_directory_from_dialog()

        project_data.component, ok = (
            (project_data.component, True)
            if project_data.component is not None
            and project_data.component in self.world_data.components.keys()
            else QInputDialog.getItem(
                self,
                "Select which component to view.",
                "Component",
                sorted(self.world_data.components.keys()),
                0,
                False,
            )
        )
        if not ok:
            raise Exception("User did not choose a component")

        row_layout = QHBoxLayout(self)
        self._left_col = QVBoxLayout()
        self.statistics_view = StatisticsView(
            self.world_data, project_data.component, self
        )
        self.create_matrix_view = CreateMatrixView(self)
        self.create_rank_view = CreateRankView(self.world_data, self)
        self._left_col.addWidget(self.statistics_view)
        self._left_col.addWidget(self.create_matrix_view)
        self._left_col.addWidget(self.create_rank_view)
        self._left_col.addStretch()
        self._right_col = QVBoxLayout()
        self.plot_viewer = PlotViewer(self.world_data, project_data, self)
        _ = self.create_matrix_view.create_tab.connect(self.plot_viewer.add_matrix_plot)
        _ = self.create_rank_view.create_tab.connect(self.plot_viewer.add_rank_plot)
        self._right_col.addWidget(self.plot_viewer)
        row_layout.addLayout(self._left_col, 0)
        row_layout.addLayout(self._right_col, 1)
        self.project_data = project_data

    def export_project(self):
        return ProjectData(
            self.project_data.source_directory,
            self.project_data.component,
            self.plot_viewer.export_tab_plots(),
            self.plot_viewer.export_detached_plots(),
        )
