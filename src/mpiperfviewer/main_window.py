from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)
from serde.json import from_json, to_json

from mpiperfviewer.plot_view import PlotViewerData
from mpiperfviewer.project_state import (
    project_saved,
    project_saved_in_current_state,
    project_updated,
)
from mpiperfviewer.project_view import ProjectData, ProjectView
from mpiperfviewer.start_dialog import FILE_EXTENSION, StartDialog


class MainWindow(QMainWindow):
    current_project_file: Path | None

    @property
    def app_window(self) -> ProjectView:
        widget = self.centralWidget()
        if not isinstance(widget, ProjectView):
            raise Exception(f"Central widget is of unexpected type {type(widget)}")
        return widget

    def __init__(self, args: list[str] | None = None):
        super().__init__(None)
        self.current_project_file = None
        args = args if args is not None else []
        source_dir = component = None
        if len(args) > 0:
            source_dir = Path(args[0])
        if len(args) > 1:
            component = args[1]

        self._setup_menubar()

        if source_dir is None:
            action, path = StartDialog.get_choice(self)
            path = Path(path)
            match action:
                case StartDialog.Choice.NEW_PROJECT:
                    self.setCentralWidget(ProjectView(ProjectData(source_directory=path)))
                case StartDialog.Choice.OPEN_PROJECT:
                    self._open_project_from_path(path)
            return

        app_window = ProjectView(
            ProjectData(source_dir, component, PlotViewerData())
        )
        self.setCentralWidget(app_window)

    def _setup_menubar(self):
        menu_bar = self.menuBar()
        project_menu = menu_bar.addMenu("Project")
        new_action = project_menu.addAction("New Project")
        new_action.setShortcut(QKeySequence(QKeySequence.StandardKey.New))
        _ = new_action.triggered.connect(self.new_project)
        open_action = project_menu.addAction("Open Project")
        open_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Open))
        _ = open_action.triggered.connect(self.open_project)
        save_action = project_menu.addAction("Save Project")
        save_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Save))
        _ = save_action.triggered.connect(self.save_project)
        save_action = project_menu.addAction("Save Project as")
        save_action.setShortcut(QKeySequence(QKeySequence.StandardKey.SaveAs))
        _ = save_action.triggered.connect(self.save_project_as)
        exit_action = project_menu.addAction("Exit")
        exit_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Quit))
        _ = exit_action.triggered.connect(self.exit_app)

    @Slot()
    def new_project(self):
        if not self.are_you_sure():
            return
        self.hide()
        self.app_window.plot_viewer.close_detached_plots()
        _ = self.takeCentralWidget()
        self.setCentralWidget(ProjectView())
        self.show()
        project_updated()

    @Slot()
    def open_project(self):
        if not self.are_you_sure():
            return
        save_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            f"mpiperfviewer Project (*.{FILE_EXTENSION});;All files (*)",
        )
        if save_name == "":
            return
        self.app_window.plot_viewer.close_detached_plots()
        self._open_project_from_path(Path(save_name))

    def _open_project_from_path(self, path: Path):
        with open(path, "r") as f:
            data = f.read()
        project_data = from_json(ProjectData, data)
        self.hide()
        _ = self.takeCentralWidget()
        app_window = ProjectView(project_data)
        self.setCentralWidget(app_window)
        self.current_project_file = path
        self.show()
        project_saved()

    def are_you_sure(self):
        if project_saved_in_current_state():
            return True
        else:
            response = QMessageBox.question(
                self,
                "Are you sure?",
                "There are unsaved changes to your current project. Are you sure?",
            )
            return response == QMessageBox.StandardButton.Yes

    @Slot()
    def save_project(self):
        if self.current_project_file is None:
            self.save_project_as()
            return
        project_data = self.app_window.export_project()
        with open(str(self.current_project_file), "w") as f:
            _ = f.write(to_json(project_data))
            project_saved()

    @Slot()
    def save_project_as(self):
        save_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project as",
            "",
            f"mpiperfviewer Project (*.{FILE_EXTENSION});;All files (*)",
        )
        if save_name == "":
            return
        if not save_name.endswith(f".{FILE_EXTENSION}"):
            save_name += f".{FILE_EXTENSION}"
        self.current_project_file = Path(save_name)
        try:
            self.save_project()
        except Exception as e:
            _ = QMessageBox.warning(self, "Failed to save project", str(e))
            self.current_project_file = None

    @Slot()
    def exit_app(self):
        if not self.are_you_sure():
            return
        QApplication.exit(0)
