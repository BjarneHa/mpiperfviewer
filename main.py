#!/usr/bin/env python3

import sys
from PySide6.QtWidgets import QApplication

from application_window import ApplicationWindow


if __name__ == "__main__":
    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QApplication.instance()
    if not qapp:
        qapp = QApplication(sys.argv)
    qapp.setApplicationName("MPI Performance Analysis")
    app = ApplicationWindow()
    app.show()
    app.activateWindow()
    app.raise_()
    qapp.exec()
