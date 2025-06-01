from math import inf, isnan

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QWidget

from parser import Rank

SI_PREFIXES = "kMGTPEZYRQ"


def si_str(n: float):
    if n < 1000:
        return f"{n:.3}"
    if isnan(n) or n == inf or n == -inf:
        return str(n)
    m = n
    for pref in SI_PREFIXES:
        m /= 1000
        if m < 1000:
            return f"{m:.3} {pref}"
    return f"{n:.3}"  # return exponential form


class StatisticsView(QGroupBox):
    def __init__(self, rank_file: Rank, parent: QWidget | None = None):
        super().__init__("Statistics", parent)
        layout = QGridLayout(self)
        layout.addWidget(QLabel("#Nodes"), 0, 0)
        nodes_label = QLabel("?", alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(nodes_label, 0, 1)
        layout.addWidget(QLabel("#MPI Processes"), 1, 0)
        procs_label = QLabel(
            text=f"{rank_file.general().num_procs:,}",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        layout.addWidget(procs_label, 1, 1)
        layout.addWidget(QLabel("Total msg count"), 2, 0)
        total_msg_counts_label = QLabel(
            text=f"{rank_file.total_msgs_sent:,}", alignment=Qt.AlignmentFlag.AlignRight
        )
        layout.addWidget(total_msg_counts_label, 2, 1)
        layout.addWidget(QLabel("Total msg size"), 3, 0)
        total_msg_sizes_label = QLabel(
            text=si_str(rank_file.total_bytes_sent) + "B",
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        layout.addWidget(total_msg_sizes_label, 3, 1)
