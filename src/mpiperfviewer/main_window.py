from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox
from serde.msgpack import from_msgpack, to_msgpack

from mpiperfviewer.application_window import ApplicationWindow
from mpiperfviewer.filter_widgets import FilterPresets
from mpiperfviewer.plot_view import ProjectData
from mpiperfviewer.project_state import (
    project_saved,
    project_saved_in_current_state,
    project_updated,
)


class MainWindow(QMainWindow):
    current_project_file: Path | None

    @property
    def app_window(self) -> ApplicationWindow:
        widget = self.centralWidget()
        if not isinstance(widget, ApplicationWindow):
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
        app_window = ApplicationWindow(
            ProjectData(source_dir, component, [], [], FilterPresets())
        )
        self.setCentralWidget(app_window)
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
        project_updated()
        if not self.are_you_sure():
            return
        self.hide()
        _ = self.takeCentralWidget()
        self.setCentralWidget(ApplicationWindow())
        self.show()

    @Slot()
    def open_project(self):
        if not self.are_you_sure():
            return
        save_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "mpiperfviewer Project (*.mpipproj);;All files (*)",
        )
        if save_name == "":
            return
        with open(save_name, "rb") as f:
            data = f.read()
        project_data = from_msgpack(ProjectData, data)
        self.hide()
        _ = self.takeCentralWidget()
        app_window = ApplicationWindow(project_data)
        self.setCentralWidget(app_window)
        self.current_project_file = Path(save_name)
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
        with open(str(self.current_project_file), "wb") as f:
            _ = f.write(to_msgpack(project_data))
            project_saved()

    @Slot()
    def save_project_as(self):
        save_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project as",
            "",
            "mpiperfviewer Project (*.mpipproj);;All files (*)",
        )
        if save_name == "":
            return
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
