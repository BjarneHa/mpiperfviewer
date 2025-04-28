from PySide6.QtWidgets import QGroupBox, QTabBar, QTabWidget, QVBoxLayout, QWidget
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

TABS = ["matrix", "total size", "msg count", "tags"]

class PlotViewer(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Plot Viewer", parent)
        layout = QVBoxLayout(self)
        self.setLayout(layout)

        tabwidget = QTabWidget(self)
        layout.addWidget(tabwidget)
        for (i, tab) in enumerate(TABS):
            tabWidget = QWidget(self)
            layout = QVBoxLayout(self)
            tabWidget.setLayout(layout)

            static_canvas = FigureCanvasQTAgg(Figure(figsize=(5, 3)))
            layout.addWidget(static_canvas)
            layout.addWidget(NavigationToolbar2QT(static_canvas, self))

            self._static_ax = static_canvas.figure.subplots()
            t = np.linspace(0, 10, 501)
            self._static_ax.plot(t, np.tan(t + i), ".")
            tabwidget.addTab(tabWidget, tab)
