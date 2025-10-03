#!/usr/bin/env python3

import sys

from PySide6.QtCore import QCommandLineParser
from PySide6.QtWidgets import QApplication

from mpiperfviewer.main_window import MainWindow


def main():
    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QApplication.instance()
    if not qapp:
        qapp = QApplication(sys.argv)
    qapp.setApplicationName("MPI Performance Analysis")
    qapp.setApplicationVersion("0.3.1")
    parser = QCommandLineParser()
    _ = parser.addVersionOption()
    _ = parser.addHelpOption()
    parser.addPositionalArgument("directory", "Data Directory")
    parser.addPositionalArgument("component", "Component")
    parser.process(qapp)

    main_window = MainWindow(parser.positionalArguments())
    main_window.show()
    main_window.activateWindow()
    main_window.raise_()

    _ = qapp.exec()


if __name__ == "__main__":
    main()
