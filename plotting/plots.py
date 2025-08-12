from typing import Any, cast, override

import numpy as np
from matplotlib.backend_bases import FigureCanvasBase
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from mpl_toolkits.mplot3d.axes3d import Axes3D
from numpy.typing import NDArray
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QWidget

from filter_view import Filter, FilterView
from parser import ComponentData, UInt64Array, WorldMeta


class PlotBase(QWidget):
    canvas: FigureCanvasBase
    filter_view: FilterView
    world_meta: WorldMeta
    component_data: ComponentData

    @property
    def fig(self):
        return self.canvas.figure

    @property
    def filters(self):
        return self.filter_view.filter_state

    def __init__(
        self,
        meta: WorldMeta,
        component_data: ComponentData,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.world_meta = meta
        self.component_data = component_data
        layout = QHBoxLayout(self)
        plot_box = QGroupBox("Plot", self)
        self.filter_view = FilterView(self)
        _ = self.filter_view.filters_changed.connect(self.filters_changed)
        layout.addWidget(plot_box, stretch=1)
        layout.addWidget(self.filter_view, stretch=0)
        plot_layout = QVBoxLayout(plot_box)
        self.canvas = FigureCanvasQTAgg()
        plot_layout.addWidget(self.canvas)
        plot_layout.addWidget(NavigationToolbar2QT(self.canvas, self))

    @Slot()
    def filters_changed(self):
        self.fig.clear()
        self.init_plot()
        self.canvas.draw_idle()

    def init_plot(self):
        pass


class MatrixPlotBase(PlotBase):
    _plot_title: str
    _legend_label: str
    _cmap: str

    def __init__(
        self,
        meta: WorldMeta,
        component_data: ComponentData,
        plot_title: str,
        legend_label: str,
        cmap: str = "viridis",
        parent: QWidget | None = None,
    ):
        super().__init__(meta, component_data, parent)
        self._plot_title = plot_title
        self._legend_label = legend_label
        self._cmap = cmap

    def plot_matrix(
        self,
        matrix: UInt64Array[tuple[int, int]],
        separators: list[int] | None = None,
    ):
        separators = separators or []
        ranks = list(range(self.world_meta.num_processes))
        ax = self.fig.add_subplot()
        ticks = np.arange(0, len(matrix))

        img = ax.imshow(matrix, self._cmap, norm="log")
        # TODO labels do not work correctly
        _ = ax.set_xticks(ticks, labels=[str(r) for r in ranks], minor=True)
        _ = ax.set_yticks(ticks, labels=[str(r) for r in ranks], minor=True)

        cbar = self.fig.colorbar(img)
        _ = cbar.ax.set_ylabel(self._legend_label, rotation=-90, va="bottom")
        for sep in separators:
            _ = ax.axvline(x=sep + 0.5, color="black")
            _ = ax.axhline(y=sep + 0.5, color="black")

        _ = ax.set_xlabel("Receiver")
        _ = ax.set_ylabel("Sender")
        _ = ax.set_title(self._plot_title)


class SizeMatrixPlot(MatrixPlotBase):
    _cmap: str

    def __init__(
        self,
        meta: WorldMeta,
        component_data: ComponentData,
        plot_title: str = "Communication Matrix (message size)",
        legend_label: str = "messages sent",
        cmap: str = "Reds",
        parent: QWidget | None = None,
    ):
        super().__init__(meta, component_data, plot_title, legend_label, cmap, parent)

    @override
    def init_plot(self):
        component_data = self.component_data
        matrix_dims = component_data.rank_sizes.shape[:2]
        matrix = np.zeros(matrix_dims, dtype=np.uint64).view()
        for sender in range(matrix_dims[0]):
            for receiver in range(matrix_dims[1]):
                for i, size in enumerate(component_data.occuring_sizes):
                    matrix[sender, receiver] += (
                        size * component_data.rank_sizes[sender, receiver, i]
                    )
        self.plot_matrix(matrix)


class CountMatrixPlot(MatrixPlotBase):
    def __init__(
        self,
        meta: WorldMeta,
        component_data: ComponentData,
        plot_title: str = "Communication Matrix (message count)",
        legend_label: str = "messages sent",
        cmap: str = "Blues",
        parent: QWidget | None = None,
    ):
        super().__init__(meta, component_data, plot_title, legend_label, cmap, parent)

    @override
    def init_plot(self):
        self.plot_matrix(self.component_data.rank_count)


class ThreeDimPlotBase(PlotBase):
    _rank: int

    def __init__(
        self,
        meta: WorldMeta,
        component_data: ComponentData,
        rank: int,
        parent: QWidget | None = None,
    ):
        super().__init__(meta, component_data, parent)
        self._rank = rank

    def generate_3d_data(
        self,
        metrics_legend: NDArray[Any],
        metrics_data: UInt64Array[tuple[int, int, int]],
        legend_filter: Filter,
        count_filter: Filter,
    ):
        component_data = self.component_data
        occurances = metrics_data[self._rank, :, :]

        # Apply range filter to tags
        metric = metrics_legend
        metric_filter_array = legend_filter.apply(metric)
        metric = metric[metric_filter_array]

        occurances = occurances[:, metric_filter_array]

        # Only show procs that are actually communicated with
        # Applies count filter (after size/tags filter, perhaps this should be changable)
        procs = np.arange(0, self.world_meta.num_processes, dtype=np.uint64)
        procs_count_filter_array = (component_data.rank_count[self._rank, :] > 0) & (
            count_filter.apply(occurances.max(1))
        )
        metric_count_filter_array = count_filter.apply(occurances.max(0))
        procs = procs[procs_count_filter_array]
        metric = metric[metric_count_filter_array]
        occurances = occurances[procs_count_filter_array, :][
            :, metric_count_filter_array
        ]

        # Collect data from collected dict into lists for plot
        xticks = np.arange(0, len(procs))
        yticks = np.arange(0, len(metric))

        return (occurances.T, xticks, yticks, procs, metric)


class TagsBar3DPlot(ThreeDimPlotBase):
    @override
    def init_plot(self):
        ax = cast(Axes3D, self.fig.add_subplot(projection="3d"))  # Poor typing from mpl
        component_data = self.component_data
        tag_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            component_data.occuring_tags,
            component_data.rank_tags,
            self.filters.tags,
            self.filters.count,
        )

        _xx, _yy = np.meshgrid(xticks, yticks)
        x, y = _xx.ravel() - 0.4, _yy.ravel() - 0.4
        z = np.zeros_like(x)
        dx = np.ones_like(x) * 0.8
        dy = np.ones_like(y) * 0.8
        dz = tag_occurances.ravel()

        _ = ax.bar3d(x, y, z, dx, dy, dz, color="green")
        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("Rank")
        _ = ax.set_ylabel("Tag")
        _ = ax.set_zlabel("No. of messages")
        _ = ax.set_title(f"Messages with tag to peer from Rank {self._rank}")


class SizeBar3DPlot(ThreeDimPlotBase):
    @override
    def init_plot(self):
        ax = cast(Axes3D, self.fig.add_subplot(projection="3d"))  # Poor typing from mpl
        size_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self.component_data.occuring_sizes,
            self.component_data.rank_sizes,
            self.filters.size,
            self.filters.count,
        )

        _xx, _yy = np.meshgrid(xticks, yticks)
        x, y = _xx.ravel() - 0.4, _yy.ravel() - 0.4
        z = np.zeros_like(x)
        dx = np.ones_like(x) * 0.8
        dy = np.ones_like(y) * 0.8
        dz = size_occurances.ravel()

        _ = ax.bar3d(x, y, z, dx, dy, dz, color="gold")
        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD Rank of peer")
        _ = ax.set_ylabel("Size in Bytes")
        _ = ax.set_zlabel("Messages sent")
        _ = ax.set_title(f"Messages with size to peer from Rank {self._rank}")


class Counts2DBarPlot(PlotBase):
    _rank: int

    def __init__(
        self,
        meta: WorldMeta,
        component_data: ComponentData,
        rank: int,
        parent: QWidget | None = None,
    ):
        super().__init__(meta, component_data, parent)
        self._rank = rank

    @override
    def init_plot(self):
        ax = self.fig.add_subplot()
        x = np.arange(0, self.world_meta.num_processes)
        y = self.component_data.rank_count[self._rank, :]
        count_filter = self.filters.count.apply(y)
        x = x[count_filter]
        y = y[count_filter]
        xticks = np.arange(0, len(x))

        _ = ax.bar(x, y, color="teal", width=0.8)
        _ = ax.set_xticks(xticks, labels=x)
        _ = ax.set_xlabel("MPI_COMM_WORLD Rank")
        _ = ax.set_ylabel("Messages sent")
        _ = ax.set_title(f"Messages sent to peers by Rank {self._rank}")


class TagsPixelPlot(ThreeDimPlotBase):
    @override
    def init_plot(self):
        ax = self.fig.add_subplot()
        tag_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self.component_data.occuring_tags,
            self.component_data.rank_tags,
            self.filters.tags,
            self.filters.count,
        )

        img = ax.imshow(tag_occurances, cmap="Greens", norm="log", aspect="auto")

        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("peer MPI_COMM_WORLD Rank")
        _ = ax.set_ylabel("Tag")
        _ = ax.set_title(f"Messages with tags to peer from Rank {self._rank}")

        cbar = self.fig.colorbar(img)

        _ = cbar.ax.set_ylabel("Message count", rotation=-90, va="bottom")


class SizePixelPlot(ThreeDimPlotBase):
    @override
    def init_plot(self):
        ax = self.fig.add_subplot()
        size_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self.component_data.occuring_sizes,
            self.component_data.rank_sizes,
            self.filters.size,
            self.filters.count,
        )

        img = ax.imshow(size_occurances, cmap="Oranges", norm="log", aspect="auto")

        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD Rank of peer")
        _ = ax.set_ylabel("Size in Bytes")
        _ = ax.set_title(f"Messages with size to peer from Rank {self._rank}")

        cbar = self.fig.colorbar(img)

        _ = cbar.ax.set_ylabel("Message count", rotation=-90, va="bottom")
