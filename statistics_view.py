from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QWidget

from parser import Rank


class StatisticsView(QGroupBox):
    def __init__(self, rank_file: Rank, parent: QWidget | None=None):
        super().__init__("Statistics", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("?", alignment=Qt.AlignmentFlag.AlignRight), 0, 1)
        layout.addWidget(QLabel("#Nodes"), 0, 0)
        layout.addWidget(QLabel("#MPI Processes"), 1, 0)
        layout.addWidget(QLabel(str(rank_file.general().num_procs), alignment=Qt.AlignmentFlag.AlignRight), 1, 1)
        layout.addWidget(QLabel("Total msg count"), 2, 0)
        layout.addWidget(QLabel(str(rank_file.total_msgs_sent), alignment=Qt.AlignmentFlag.AlignRight), 2, 1)
        layout.addWidget(QLabel("Total msg size"), 3, 0)
        layout.addWidget(QLabel(str(rank_file.total_bytes_sent) + " B", alignment=Qt.AlignmentFlag.AlignRight), 3, 1)
