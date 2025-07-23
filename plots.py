from typing import Any, cast

import numpy as np
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from numpy.typing import NDArray

from filter_view import Filter, GlobalFilters
from parser import Component, UInt64Array, WorldData


# TODO code duplication
def plot_size_matrix(
    fig: Figure, world_data: WorldData, component: Component, filters: GlobalFilters
):
    component_data = world_data.components[component]
    matrix_dims = component_data.rank_sizes.shape[:2]
    matrix = np.zeros(matrix_dims, dtype=np.uint64).view()
    for sender in range(matrix_dims[0]):
        for receiver in range(matrix_dims[1]):
            for i, size in enumerate(component_data.occuring_sizes):
                matrix[sender, receiver] += (
                    size * component_data.rank_sizes[sender, receiver, i]
                )

    plot_matrix(
        "Communication Matrix (message size)",
        "bytes sent",
        fig,
        matrix,
        list(range(world_data.meta.num_processes)),
        "Reds",
    )


# TODO code duplication
def plot_msgs_matrix(
    fig: Figure, world_data: WorldData, component: Component, filters: GlobalFilters
):
    component_data = world_data.components[component]
    plot_matrix(
        "Communication Matrix (message count)",
        "messages sent",
        fig,
        component_data.rank_count,
        list(range(world_data.meta.num_processes)),
        "Blues",
    )


def plot_matrix(
    title: str,
    legend_title: str,
    fig: Figure,
    matrix: UInt64Array[tuple[int, int]],
    ranks: list[int],
    cmap: str = "viridis",
    seperators: list[int] | None = None,
):
    ax = fig.add_subplot()
    ticks = np.arange(0, len(matrix))

    img = ax.imshow(matrix, cmap, norm="log")
    # TODO labels do not work correctly
    ax.set_xticks(ticks, labels=[str(r) for r in ranks], minor=True)
    ax.set_yticks(ticks, labels=[str(r) for r in ranks], minor=True)

    cbar = fig.colorbar(img)
    cbar.ax.set_ylabel(legend_title, rotation=-90, va="bottom")
    seperators = seperators or []
    for sep in seperators:
        ax.axvline(x=sep + 0.5, color="black")
        ax.axhline(y=sep + 0.5, color="black")

    ax.set_xlabel("Receiver")
    ax.set_ylabel("Sender")
    ax.set_title(title)


def generate_3d_data(
    rank: int,
    world_data: WorldData,
    component: Component,
    metrics_legend: NDArray[Any],
    metrics_data: UInt64Array[tuple[int, int, int]],
    filter: Filter,
    count_filter: Filter,
):
    component_data = world_data.components[component]
    occurances = metrics_data[rank, :, :]

    # Only show procs that are actually communicated with
    # Applies count filter (before size/tags filter, perhaps this should be changable)
    procs = np.arange(0, world_data.meta.num_processes, dtype=np.uint64)
    procs_filter_array = (component_data.rank_count[rank, :] > 0) & (
        count_filter.apply(occurances.max(1))
    )
    procs = procs[procs_filter_array]

    # Apply range filter to tags
    metric = metrics_legend
    metric_filter_array = filter.apply(metric)
    metric = metric[metric_filter_array]

    occurances = occurances[procs_filter_array, :][:, metric_filter_array]

    # Collect data from collected dict into lists for plot
    xticks = np.arange(0, len(procs))
    yticks = np.arange(0, len(metric))

    return (occurances.T, xticks, yticks, procs, metric)


def plot_tags_3d(
    fig: Figure,
    rank: int,
    world_data: WorldData,
    component: Component,
    filters: GlobalFilters,
):
    ax = cast(Axes3D, fig.add_subplot(projection="3d"))  # Poor typing from mpl
    component_data = world_data.components[component]
    tag_occurances, xticks, yticks, xlabels, ylabels = generate_3d_data(
        rank,
        world_data,
        component,
        component_data.occuring_tags,
        component_data.rank_tags,
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
    _ = ax.set_title(f"Messages with tag to peer from Rank {rank}")


def plot_sizes_3d(
    fig: Figure,
    rank: int,
    world_data: WorldData,
    component: Component,
    filters: GlobalFilters,
):
    ax = cast(Axes3D, fig.add_subplot(projection="3d"))  # Poor typing from mpl
    component_data = world_data.components[component]
    size_occurances, xticks, yticks, xlabels, ylabels = generate_3d_data(
        rank,
        world_data,
        component,
        component_data.occuring_sizes,
        component_data.rank_sizes,
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
    _ = ax.set_title(f"Messages with size to peer from Rank {rank}")


def plot_counts_2d(
    fig: Figure,
    rank: int,
    world_data: WorldData,
    component: Component,
    filters: GlobalFilters,
):
    ax = fig.add_subplot()
    x = np.arange(0, world_data.meta.num_processes)
    y = world_data.components[component].rank_count[rank, :]
    count_filter = filters.count.apply(y)
    x = x[count_filter]
    y = y[count_filter]
    xticks = np.arange(0, len(x))

    _ = ax.bar(x, y, color="teal", width=0.8)
    _ = ax.set_xticks(xticks, labels=x)
    _ = ax.set_xlabel("MPI_COMM_WORLD Rank")
    _ = ax.set_ylabel("Messages sent")
    _ = ax.set_title(f"Messages sent to peers by Rank {rank}")


def plot_tags_px(
    fig: Figure,
    rank: int,
    world_data: WorldData,
    component: Component,
    filters: GlobalFilters,
):
    ax = fig.add_subplot()
    component_data = world_data.components[component]
    tag_occurances, xticks, yticks, xlabels, ylabels = generate_3d_data(
        rank,
        world_data,
        component,
        component_data.occuring_tags,
        component_data.rank_tags,
        filters.tags,
        filters.count,
    )

    img = ax.imshow(tag_occurances, cmap="Greens", norm="log", aspect="auto")

    _ = ax.set_xticks(xticks, labels=xlabels)
    _ = ax.set_yticks(yticks, labels=ylabels)
    _ = ax.set_xlabel("peer MPI_COMM_WORLD Rank")
    _ = ax.set_ylabel("Tag")
    _ = ax.set_title(f"Messages with tags to peer from Rank {rank}")

    cbar = fig.colorbar(img)

    _ = cbar.ax.set_ylabel("Message count", rotation=-90, va="bottom")


def plot_sizes_px(
    fig: Figure,
    rank: int,
    world_data: WorldData,
    component: Component,
    filters: GlobalFilters,
):
    ax = fig.add_subplot()
    component_data = world_data.components[component]
    size_occurances, xticks, yticks, xlabels, ylabels = generate_3d_data(
        rank,
        world_data,
        component,
        component_data.occuring_sizes,
        component_data.rank_sizes,
        filters.size,
        filters.count,
    )

    img = ax.imshow(size_occurances, cmap="Oranges", norm="log", aspect="auto")

    _ = ax.set_xticks(xticks, labels=xlabels)
    _ = ax.set_yticks(yticks, labels=ylabels)
    _ = ax.set_xlabel("MPI_COMM_WORLD Rank of peer")
    _ = ax.set_ylabel("Size in Bytes")
    _ = ax.set_title(f"Messages with size to peer from Rank {rank}")

    cbar = fig.colorbar(img)

    _ = cbar.ax.set_ylabel("Message count", rotation=-90, va="bottom")
