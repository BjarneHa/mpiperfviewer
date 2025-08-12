#!/usr/bin/env python3

import sys

from PySide6.QtCore import QCommandLineParser
from PySide6.QtWidgets import QApplication

from application_window import ApplicationWindow

if __name__ == "__main__":
    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QApplication.instance()
    if not qapp:
        qapp = QApplication(sys.argv)
    qapp.setApplicationName("MPI Performance Analysis")
    qapp.setApplicationVersion("0.1.0")
    parser = QCommandLineParser()
    _ = parser.addVersionOption()
    _ = parser.addHelpOption()
    parser.addPositionalArgument("directory", "Data Directory")
    parser.addPositionalArgument("component", "Component")
    parser.process(qapp)

    app = ApplicationWindow(parser.positionalArguments())
    app.show()
    app.activateWindow()
    app.raise_()
    _ = qapp.exec()
