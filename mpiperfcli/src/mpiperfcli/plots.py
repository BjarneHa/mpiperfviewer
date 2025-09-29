from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, cast, override

import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from numpy.typing import NDArray

from mpiperfcli.filters import Filter, FilterState, FilterType, RangeFilter
from mpiperfcli.parser import ComponentData, UInt64Array, WorldMeta


class MatrixGroupBy(StrEnum):
    RANK = "Rank"
    CORE = "Core"
    NUMA = "NUMA Node"
    SOCKET = "Socket"
    NODE = "Node"


class MatrixMetric(StrEnum):
    BYTES_SENT = "bytes sent"
    MESSAGES_SENT = "messages sent"


class RankPlotMetric(StrEnum):
    SENT_SIZES = "sent sizes"
    MESSAGE_COUNT = "message count"
    TAGS = "tags"


class RankPlotType(StrEnum):
    PIXEL_PLOT = "Pixel Plot"
    BAR3D = "3D Bar"
    BAR = "Bar Chart"


class PlotBase(ABC):
    fig: Figure
    world_meta: WorldMeta
    component_data: ComponentData

    def __init__(self, fig: Figure, meta: WorldMeta, component_data: ComponentData):
        super().__init__()
        self.fig = fig
        self.world_meta = meta
        self.component_data = component_data

    @classmethod
    @abstractmethod
    def cli_name(cls) -> str: ...

    @abstractmethod
    def cli_param(self) -> str: ...

    @classmethod
    @abstractmethod
    def filter_types(cls) -> list[FilterType]: ...

    @abstractmethod
    def init_plot(self, filters: FilterState) -> None: ...

    @abstractmethod
    def tab_title(self) -> str: ...


class MatrixPlotBase(PlotBase, ABC):
    _plot_title: str
    _legend_label: str
    _cmap: str
    _group_by: MatrixGroupBy

    def __init__(
        self,
        fig: Figure,
        meta: WorldMeta,
        component_data: ComponentData,
        group_by: MatrixGroupBy,
        plot_title: str,
        legend_label: str,
        cmap: str = "viridis",
    ):
        super().__init__(fig, meta, component_data)
        self._group_by = group_by
        self._plot_title = plot_title
        self._legend_label = legend_label
        self._cmap = cmap

    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return []

    @override
    def cli_param(self):
        return self._group_by.name.lower()

    def plot_matrix(
        self, matrix: UInt64Array[tuple[int, int]], separators: list[int] | None = None
    ):
        separators = separators or []
        peers = list(range(self.group.count.shape[0]))
        ax = self.fig.add_subplot()
        ticks = np.arange(0, len(matrix))

        img = ax.imshow(matrix, self._cmap, norm="log")
        # TODO labels do not work correctly
        _ = ax.set_xticks(ticks, labels=[str(r) for r in peers], minor=True)
        _ = ax.set_yticks(ticks, labels=[str(r) for r in peers], minor=True)

        cbar = self.fig.colorbar(img)
        _ = cbar.ax.set_ylabel(self._legend_label, rotation=-90, va="bottom")
        for sep in separators:
            _ = ax.axvline(x=sep + 0.5, color="black")
            _ = ax.axhline(y=sep + 0.5, color="black")

        _ = ax.set_xlabel(f"Receiver ({self._group_by})")
        _ = ax.set_ylabel(f"Sender ({self._group_by})")
        _ = ax.set_title(self._plot_title)

    @property
    def group(self):
        match self._group_by:
            case MatrixGroupBy.RANK:
                group = self.component_data.by_rank
            case MatrixGroupBy.CORE:
                group = self.component_data.by_core
            case MatrixGroupBy.NUMA:
                group = self.component_data.by_numa
            case MatrixGroupBy.SOCKET:
                group = self.component_data.by_socket
            case MatrixGroupBy.NODE:
                group = self.component_data.by_node
        if group is None:
            raise Exception(f"Cannot group by {self._group_by} due to missing data.")
        return group

    @classmethod
    @abstractmethod
    def metric(cls) -> MatrixMetric: ...


class SizeMatrixPlot(MatrixPlotBase):
    _cmap: str

    def __init__(
        self,
        fig: Figure,
        meta: WorldMeta,
        component_data: ComponentData,
        group_by: MatrixGroupBy,
        plot_title: str = "Communication Matrix (message size)",
        legend_label: str = "messages sent",
        cmap: str = "Reds",
    ):
        super().__init__(
            fig, meta, component_data, group_by, plot_title, legend_label, cmap
        )

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "total_matrix"

    @override
    def init_plot(self, filters: FilterState):
        matrix_dims = self.group.sizes.shape[:2]
        matrix = np.zeros(matrix_dims, dtype=np.uint64).view()
        for sender in range(matrix_dims[0]):
            for receiver in range(matrix_dims[1]):
                for i, size in enumerate(self.component_data.occuring_sizes):
                    matrix[sender, receiver] += (
                        size * self.group.sizes[sender, receiver, i]
                    )
        self.plot_matrix(matrix)

    @override
    @classmethod
    def metric(cls) -> MatrixMetric:
        return MatrixMetric.BYTES_SENT

    @override
    def tab_title(self) -> str:
        return "total size"


class CountMatrixPlot(MatrixPlotBase):
    def __init__(
        self,
        fig: Figure,
        meta: WorldMeta,
        component_data: ComponentData,
        group_by: MatrixGroupBy,
        plot_title: str = "Communication Matrix (message count)",
        legend_label: str = "messages sent",
        cmap: str = "Blues",
    ):
        super().__init__(
            fig, meta, component_data, group_by, plot_title, legend_label, cmap
        )

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "msgs_matrix"

    @override
    def init_plot(self, filters: FilterState):
        self.plot_matrix(self.group.count)

    @override
    @classmethod
    def metric(cls) -> MatrixMetric:
        return MatrixMetric.MESSAGES_SENT

    @override
    def tab_title(self) -> str:
        return "message count"


class RankPlotBase(PlotBase, ABC):
    _rank: int

    def __init__(
        self, fig: Figure, meta: WorldMeta, component_data: ComponentData, rank: int
    ):
        super().__init__(fig, meta, component_data)
        self._rank = rank

    @override
    def cli_param(self) -> str:
        return str(self._rank)

    @classmethod
    @abstractmethod
    def type(cls) -> RankPlotType: ...

    @classmethod
    @abstractmethod
    def metric(cls) -> RankPlotMetric: ...

    @override
    def tab_title(self) -> str:
        return f"rank {self._rank} – {self.metric()} ({self.type()})"


class ThreeDimPlotBase(RankPlotBase, ABC):
    def generate_3d_data(
        self,
        metrics_legend: NDArray[Any],
        metrics_data: UInt64Array[tuple[int, int, int]],
        legend_filter: Filter,
        count_filter: Filter,
    ):
        occurances = metrics_data[self._rank, :, :]

        # Apply range filter to tags
        metric = metrics_legend
        metric_filter_array = legend_filter.apply(metric)
        metric = metric[metric_filter_array]

        occurances = occurances[:, metric_filter_array]

        # `.sum(DIM, dtype=np.bool)` is equivalent to an OR-Operation and
        # is used to filter out irrelevant rows and columns in the graph
        filtered_occurances = count_filter.apply(occurances)

        # Only show procs that are actually communicated with
        # Applies count filter (after size/tags filter, perhaps this should be changable)
        procs = np.arange(0, self.world_meta.num_processes, dtype=np.uint64)
        procs_count_filter_array = (
            self.component_data.by_rank.count[self._rank, :] > 0
        ) & (filtered_occurances.sum(1, dtype=np.bool))
        metric_count_filter_array = filtered_occurances.sum(0, dtype=np.bool)
        procs = procs[procs_count_filter_array]
        metric = metric[metric_count_filter_array]
        occurances = occurances[procs_count_filter_array, :][
            :, metric_count_filter_array
        ]

        # Collect data from collected dict into lists for plot
        xticks = np.arange(0, len(procs))
        yticks = np.arange(0, len(metric))

        return (occurances.T, xticks, yticks, procs, metric)


class PixelPlotBase(ThreeDimPlotBase, ABC):
    def _get_norm(self, filters: FilterState):
        if isinstance(filters.count, RangeFilter):
            return LogNorm(filters.count.min, filters.count.max)
        else:
            return LogNorm()

    @override
    @classmethod
    def type(cls) -> RankPlotType:
        return RankPlotType.PIXEL_PLOT


class ThreeDimBarBase(ThreeDimPlotBase, ABC):
    @override
    @classmethod
    def type(cls) -> RankPlotType:
        return RankPlotType.BAR3D


class TagsBar3DPlot(ThreeDimBarBase):
    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.TAGS]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "tags_3d"

    @override
    def init_plot(self, filters: FilterState):
        ax = cast(Axes3D, self.fig.add_subplot(projection="3d"))  # Poor typing from mpl
        component_data = self.component_data
        tag_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            component_data.occuring_tags,
            component_data.by_rank.tags,
            filters.tags,
            filters.count,
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

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.TAGS


class SizeBar3DPlot(ThreeDimBarBase):
    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.SIZE]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "size_3d"

    @override
    def init_plot(self, filters: FilterState):
        ax = cast(Axes3D, self.fig.add_subplot(projection="3d"))  # Poor typing from mpl
        size_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self.component_data.occuring_sizes,
            self.component_data.by_rank.sizes,
            filters.size,
            filters.count,
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

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.SENT_SIZES


class Counts2DBarPlot(RankPlotBase):
    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "counts"

    @override
    def init_plot(self, filters: FilterState):
        ax = self.fig.add_subplot()
        x = np.arange(0, self.world_meta.num_processes)
        y = self.component_data.by_rank.count[self._rank, :]
        count_filter = filters.count.apply(y)
        x = x[count_filter]
        y = y[count_filter]
        xticks = np.arange(0, len(x))

        _ = ax.bar(x, y, color="teal", width=0.8)
        _ = ax.set_xticks(xticks, labels=x)
        _ = ax.set_xlabel("MPI_COMM_WORLD Rank")
        _ = ax.set_ylabel("Messages sent")
        _ = ax.set_title(f"Messages sent to peers by Rank {self._rank}")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.MESSAGE_COUNT

    @override
    @classmethod
    def type(cls) -> RankPlotType:
        return RankPlotType.BAR


class TagsPixelPlot(PixelPlotBase):
    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.TAGS]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "tags_px"

    @override
    def init_plot(self, filters: FilterState):
        ax = self.fig.add_subplot()
        tag_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self.component_data.occuring_tags,
            self.component_data.by_rank.tags,
            filters.tags,
            filters.count,
        )

        img = ax.imshow(
            tag_occurances, cmap="Greens", norm=self._get_norm(filters), aspect="auto"
        )

        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("peer MPI_COMM_WORLD Rank")
        _ = ax.set_ylabel("Tag")
        _ = ax.set_title(f"Messages with tags to peer from Rank {self._rank}")

        cbar = self.fig.colorbar(img)

        _ = cbar.ax.set_ylabel("Message count", rotation=-90, va="bottom")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.TAGS


class SizePixelPlot(PixelPlotBase):
    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.SIZE]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "size_px"

    @override
    def init_plot(self, filters: FilterState):
        ax = self.fig.add_subplot()
        size_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self.component_data.occuring_sizes,
            self.component_data.by_rank.sizes,
            filters.size,
            filters.count,
        )

        img = ax.imshow(
            size_occurances, cmap="Oranges", norm=self._get_norm(filters), aspect="auto"
        )

        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD Rank of peer")
        _ = ax.set_ylabel("Size in Bytes")
        _ = ax.set_title(f"Messages with size to peer from Rank {self._rank}")

        cbar = self.fig.colorbar(img)

        _ = cbar.ax.set_ylabel("Message count", rotation=-90, va="bottom")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.SENT_SIZES
