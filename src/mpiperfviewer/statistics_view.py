import re
from math import inf, isnan

from mpiperfcli.parser import Component, WorldData
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QWidget

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
    _num_items: int
    _layout: QGridLayout

    def __init__(
        self, world_data: WorldData, component: Component, parent: QWidget | None = None
    ):
        super().__init__("Statistics", parent)
        self._num_items = 0
        component_data = world_data.components[component]
        self._layout = QGridLayout(self)
        self.add_stat("Open MPI Component", component)
        self.add_stat("#MPI Processes", world_data.meta.num_processes)
        self.add_stat("#Cores", world_data.meta.num_cores)
        self.add_stat("#NUMA Nodes", world_data.meta.num_numa)
        self.add_stat("#Hardware Sockets", world_data.meta.num_sockets)
        self.add_stat("#Nodes", world_data.meta.num_nodes)
        self.add_stat("Total msg count", component_data.total_msgs_sent)
        self.add_stat(
            "Total msg size",
            si_str(float(component_data.total_bytes_sent)) + "B",
        )
        # Cut out microseconds from format
        self.add_stat("Wall time", re.sub(r".\d+$", "", str(world_data.wall_time)))

    def add_stat(self, stat: str, value: str | int | None):
        if value is None:
            return
        if isinstance(value, int):
            value = f"{value:,}"
        self._layout.addWidget(QLabel(stat), self._num_items, 0)
        total_msg_sizes_label = QLabel(
            text=value,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        self._layout.addWidget(total_msg_sizes_label, self._num_items, 1)
        self._num_items += 1
