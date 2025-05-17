from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QWidget

from parser import Rank


class StatisticsView(QGroupBox):
    def __init__(self, rank_file: Rank, parent: QWidget | None = None):
        super().__init__("Statistics", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("#Nodes"), 0, 0)
        nodes_label = QLabel("?", alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(nodes_label, 0, 1)
        layout.addWidget(QLabel("#MPI Processes"), 1, 0)
        procs_label = QLabel(
            text=str(rank_file.general().num_procs),
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        layout.addWidget(procs_label, 1, 1)
        layout.addWidget(QLabel("Total msg count"), 2, 0)
        total_msg_counts_label = QLabel(
            text=str(rank_file.total_msgs_sent), alignment=Qt.AlignmentFlag.AlignRight
        )
        layout.addWidget(total_msg_counts_label, 2, 1)
        layout.addWidget(QLabel("Total msg size"), 3, 0)
        total_msg_sizes_label = QLabel(
            text=str(rank_file.total_bytes_sent) + " B",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        layout.addWidget(total_msg_sizes_label, 3, 1)
