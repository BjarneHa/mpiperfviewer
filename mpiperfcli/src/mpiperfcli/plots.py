from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, cast, override

import numpy as np
from matplotlib import colormaps, ticker
from matplotlib.axes import Axes
from matplotlib.colors import Colormap, LogNorm
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from numpy.typing import NDArray

from mpiperfcli.filters import Filter, FilterState, FilterType, RangeFilter, Unfiltered
from mpiperfcli.parser import ComponentData, SizeData, TagData, UInt64Array, WorldMeta


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

SIZES_COLOR = (1, 0.85, 0, 1)
TAGS_COLOR = (0, 0.5, 0, 1)
HIDDEN_COLOR = (0, 0, 0, 0.15)


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
    def draw_plot(self, filters: FilterState) -> None: ...

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
        ax = self.fig.add_subplot()

        img = ax.imshow(matrix, self._cmap, norm="log", interpolation="nearest")
        loc = ticker.MaxNLocator('auto', integer=True, min_n_ticks=-1)
        ax.xaxis.set_minor_locator(ticker.NullLocator())
        ax.yaxis.set_minor_locator(ticker.NullLocator())
        ax.xaxis.set_major_locator(loc)
        ax.yaxis.set_major_locator(loc)

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
        plot_title: str = "Communication Matrix (total bytes sent)",
        legend_label: str = "bytes sent",
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
    def draw_plot(self, filters: FilterState):
        self.plot_matrix(self.group.total_sent)

    @override
    @classmethod
    def metric(cls) -> MatrixMetric:
        return MatrixMetric.BYTES_SENT

    @override
    def tab_title(self) -> str:
        return f"total size ({self._group_by})"


class CountMatrixPlot(MatrixPlotBase):
    def __init__(
        self,
        fig: Figure,
        meta: WorldMeta,
        component_data: ComponentData,
        group_by: MatrixGroupBy,
        plot_title: str = "Communication Matrix (total messages sent)",
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
    def draw_plot(self, filters: FilterState):
        self.plot_matrix(self.group.msgs_sent)

    @override
    @classmethod
    def metric(cls) -> MatrixMetric:
        return MatrixMetric.MESSAGES_SENT

    @override
    def tab_title(self) -> str:
        return f"message count ({self._group_by})"


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
        peers: UInt64Array[tuple[int]],
        metrics_legend: NDArray[Any],
        data: UInt64Array[tuple[int, int]],
        legend_filter: Filter,
        count_filter: Filter,
    ):
        # Apply range filter to tags
        metric = metrics_legend
        metric_filter_array = legend_filter.apply(metric)
        metric = metric[metric_filter_array]

        occurances = data[:, metric_filter_array]

        # `.sum(DIM, dtype=np.bool)` is equivalent to an OR-Operation and
        # is used to filter out irrelevant rows and columns in the graph
        filtered_occurances = count_filter.apply(occurances) & (occurances > 0)

        # Only show procs that are actually communicated with
        # Applies count filter (after size/tags filter, perhaps this should be changable)
        procs_count_filter_array = filtered_occurances.sum(1, dtype=np.bool)
        metric_count_filter_array = filtered_occurances.sum(0, dtype=np.bool)
        peers = peers[procs_count_filter_array].ravel()
        metric = metric[metric_count_filter_array]
        occurances = occurances[np.ix_(procs_count_filter_array, metric_count_filter_array)]

        # Collect data from collected dict into lists for plot
        xticks = np.arange(0, len(peers))
        yticks = np.arange(0, len(metric))

        return (occurances.T, xticks, yticks, peers, metric)


class PixelPlotBase(ThreeDimPlotBase, ABC):
    def _get_norm(self, filters: FilterState):
        if isinstance(filters.count, RangeFilter):
            # LogNorm can not have 0 as vmin or vmax
            vmin = max(filters.count.min, 1) if filters.count.min is not None else None
            vmax = max(filters.count.max, 1) if filters.count.max is not None else None
            return LogNorm(vmin, vmax, False)
        else:
            return LogNorm()

    def _get_cmap(self, cmap: Colormap, filters: FilterState):
        cmap = cmap.copy()
        col = HIDDEN_COLOR # grayscale format
        if isinstance(filters.count, Unfiltered) or filters.count.min is None or filters.count.min < 1:
            cmap.set_extremes(over=col)
        else:
            # bad explicitly affects zero entries, as log(0) is undefined an LogNorm is used
            cmap.set_extremes(bad=col, under=col, over=col)
        return cmap

    def imshow(self, ax: Axes, occurances: NDArray[np.uint64], cmap: Colormap, filters: FilterState):
        cmap = self._get_cmap(cmap, filters)
        img = ax.imshow(occurances, cmap=cmap, norm=self._get_norm(filters), aspect="auto", interpolation="nearest")
        return img

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
    _data: TagData

    def __init__(self, fig: Figure, meta: WorldMeta, component_data: ComponentData, rank: int):
        super().__init__(fig, meta, component_data, rank)
        self._data = self.component_data.tags(self._rank)

    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.TAG]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "tags_3d"

    @override
    def draw_plot(self, filters: FilterState):
        ax = cast(Axes3D, self.fig.add_subplot(projection="3d"))  # Poor typing from mpl

        tag_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self._data.peers,
            self._data.occuring_tags,
            self._data.data,
            filters.tag,
            filters.count,
        )

        dz = tag_occurances.ravel()
        zero_filter = dz > 0
        dz = dz[zero_filter]

        _xx, _yy = np.meshgrid(xticks, yticks)
        x, y = _xx.ravel() - 0.4, _yy.ravel() - 0.4
        x, y = x[zero_filter], y[zero_filter]
        z = np.zeros_like(dz)
        dx = dy = np.full_like(dz, 0.8, dtype=np.float64)

        colors = np.full((len(dz), 4), HIDDEN_COLOR)
        colors[filters.count.apply(dz), :] = TAGS_COLOR

        if isinstance(filters.count, RangeFilter) and filters.count.max is not None:
            dz[dz > filters.count.max] = filters.count.max

        _ = ax.bar3d(x, y, z, dx, dy, dz, color=colors)
        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD rank of peer")
        _ = ax.set_ylabel("Message tag")
        _ = ax.set_zlabel("No. of messages sent")
        _ = ax.set_title(f"Messages sent to peers from rank {self._rank} by tag")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.TAGS


class SizeBar3DPlot(ThreeDimBarBase):
    _data: SizeData

    def __init__(self, fig: Figure, meta: WorldMeta, component_data: ComponentData, rank: int):
        super().__init__(fig, meta, component_data, rank)
        self._data = self.component_data.sizes(rank)

    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.SIZE]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "sizes_3d"

    @override
    def draw_plot(self, filters: FilterState):
        ax = cast(Axes3D, self.fig.add_subplot(projection="3d"))  # Poor typing from mpl
        size_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self._data.peers,
            self._data.occuring_sizes,
            self._data.data,
            filters.size,
            filters.count,
        )

        dz = size_occurances.ravel()
        zero_filter = dz > 0
        dz = dz[zero_filter]

        _xx, _yy = np.meshgrid(xticks, yticks)
        x, y = _xx.ravel() - 0.4, _yy.ravel() - 0.4
        x, y = x[zero_filter], y[zero_filter]
        z = np.zeros_like(dz)
        dx = dy = np.full_like(dz, 0.8, dtype=np.float64)
        colors = np.full((len(dz), 4), HIDDEN_COLOR)
        colors[filters.count.apply(dz), :] = SIZES_COLOR
        if isinstance(filters.count, RangeFilter) and filters.count.max is not None:
            dz[dz > filters.count.max] = filters.count.max

        _ = ax.bar3d(x, y, z, dx, dy, dz, color=colors)
        _ = ax.set_xticks(xticks, labels=xlabels)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD rank of peer")
        _ = ax.set_ylabel("Message size in bytes")
        _ = ax.set_zlabel("No. of messages sent")
        _ = ax.set_title(f"Messages sent to peers from rank {self._rank} by message size")

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
    def draw_plot(self, filters: FilterState):
        ax = self.fig.add_subplot()
        x = np.arange(0, self.world_meta.num_processes)
        y = self.component_data.by_rank.msgs_sent[self._rank, :]
        count_filter = filters.count.apply(y) & (y > 0)
        x = x[count_filter]
        y = y[count_filter]
        xticks = np.arange(0, len(x))

        _ = ax.bar(xticks, y, color="teal", width=0.8)
        _ = ax.set_xticks(xticks, labels=x)
        _ = ax.set_xlabel("MPI_COMM_WORLD rank of peer")
        _ = ax.set_ylabel("No. of messages sent")
        _ = ax.set_title(f"Messages sent to peers from rank {self._rank}")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.MESSAGE_COUNT

    @override
    @classmethod
    def type(cls) -> RankPlotType:
        return RankPlotType.BAR


class TagsPixelPlot(PixelPlotBase):
    _data: TagData

    def __init__(self, fig: Figure, meta: WorldMeta, component_data: ComponentData, rank: int):
        super().__init__(fig, meta, component_data, rank)
        self._data = self.component_data.tags(self._rank)

    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.TAG]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "tags_px"

    @override
    def draw_plot(self, filters: FilterState):
        ax = self.fig.add_subplot()
        tag_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self._data.peers,
            self._data.occuring_tags,
            self._data.data,
            filters.tag,
            filters.count,
        )

        img = self.imshow(ax, tag_occurances, colormaps["Greens"], filters)

        _ = ax.set_xticks(xticks, labels=xlabels, rotation=-90)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD rank of peer")
        _ = ax.set_ylabel("Message tag")
        _ = ax.set_title(f"Messages sent to peers from rank {self._rank} by tag")

        cbar = self.fig.colorbar(img)

        _ = cbar.ax.set_ylabel("No. of messages sent", rotation=-90, va="bottom")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.TAGS


class SizePixelPlot(PixelPlotBase):
    _data: SizeData

    def __init__(self, fig: Figure, meta: WorldMeta, component_data: ComponentData, rank: int):
        super().__init__(fig, meta, component_data, rank)
        self._data = self.component_data.sizes(rank)

    @override
    @classmethod
    def filter_types(cls) -> list[FilterType]:
        return [FilterType.COUNT, FilterType.SIZE]

    @override
    @classmethod
    def cli_name(cls) -> str:
        return "sizes_px"

    @override
    def draw_plot(self, filters: FilterState):
        ax = self.fig.add_subplot()
        size_occurances, xticks, yticks, xlabels, ylabels = self.generate_3d_data(
            self._data.peers,
            self._data.occuring_sizes,
            self._data.data,
            filters.size,
            filters.count,
        )

        img = self.imshow(ax, size_occurances, colormaps["Oranges"], filters)

        _ = ax.set_xticks(xticks, labels=xlabels, rotation=-90)
        _ = ax.set_yticks(yticks, labels=ylabels)
        _ = ax.set_xlabel("MPI_COMM_WORLD rank of peer")
        _ = ax.set_ylabel("Message size in bytes")
        _ = ax.set_title(f"Messages sent to peers from rank {self._rank} by message size")

        cbar = self.fig.colorbar(img)

        _ = cbar.ax.set_ylabel("No. of messages sent", rotation=-90, va="bottom")

    @override
    @classmethod
    def metric(cls) -> RankPlotMetric:
        return RankPlotMetric.SENT_SIZES
