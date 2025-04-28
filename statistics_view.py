from PySide6.QtWidgets import QGridLayout, QGroupBox, QVBoxLayout, QLabel


class StatisticsView(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Statistics", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("#Nodes"), 0, 0)
        layout.addWidget(QLabel("#MPI Processes"), 1, 0)
        layout.addWidget(QLabel("Total msg count"), 2, 0)
        layout.addWidget(QLabel("Total msg size"), 3, 0)
        self.setLayout(layout)
