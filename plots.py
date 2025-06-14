from typing import cast

import numpy as np
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.axes3d import Axes3D
from numpy.typing import NDArray

from filter_view import GlobalFilters
from parser import WorldData


# TODO refactor using numpy filter
def _get_filtered_ranks(world_data: WorldData, filters: GlobalFilters):
    return [
        rank.general().own_rank
        for rank in world_data.ranks
        if filters.count.test(rank.total_msgs_sent)
    ]


# TODO code duplication
def plot_size_matrix(fig: Figure, world_data: WorldData, filters: GlobalFilters):
    ranks = _get_filtered_ranks(world_data, filters)
    n = len(ranks)
    matrix = np.zeros((n, n), dtype=np.uint64)
    i = 0
    for sender in world_data.ranks:
        s = sender.general().own_rank
        if s not in ranks:
            continue
        j = 0
        for r, sent in sender.bytes_sent().items():
            if r not in ranks:
                continue
            matrix[i][j] = sent
            j += 1
        i += 1

    plot_matrix(
        "Communication Matrix (message size)",
        "bytes sent",
        fig,
        matrix,
        ranks,
        "viridis",
    )


# TODO code duplication
def plot_msgs_matrix(fig: Figure, world_data: WorldData, filters: GlobalFilters):
    ranks = _get_filtered_ranks(world_data, filters)
    n = len(ranks)
    matrix = np.zeros((n, n), dtype=np.uint64)
    i = 0
    for sender in world_data.ranks:
        s = sender.general().own_rank
        if s not in ranks:
            continue
        j = 0
        for r, sent in sender.msgs_sent().items():
            if r not in ranks:
                continue
            matrix[i][j] = sent
            j += 1
        i += 1

    plot_matrix(
        "Communication Matrix (message count)",
        "messages sent",
        fig,
        matrix,
        ranks,
        "Blues",
    )


def plot_matrix(
    title: str,
    legend_title: str,
    fig: Figure,
    matrix: NDArray[np.uint64],
    ranks: list[int],
    cmap: str = "viridis",
    seperators: list[int] | None = None,
):
    fig.clear()
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


def plot_tags_3d(
    title: str,
    fig: Figure,
    rank: int,
    world_data: WorldData,
    filters: GlobalFilters,
):
    ax = cast(Axes3D, fig.add_subplot(projection="3d"))  # Poor typing from mpl

    # TODO this is not strictly the same as in the script... Should this be changed?
    # sent_sizes_cumulative = dict[int, int]()
    # for sizes in exact_sizes.values():
    #     for size, occ in sizes.items():
    #         sent_sizes_cumulative[size] = sent_sizes_cumulative.get(size, 0) + occ
    # procs = set([i for i in range(self._rank_data.general.num_procs)])
    # procs = set([rank for rank, v in exact_sizes.items() if sum(v.values()) > 0])

    cur_rank = world_data.ranks[rank]
    tags = world_data.ranks[rank].tags(filter=filters.tags)
    procs = set(
        [rank for rank, v in cur_rank.exact_sizes().items() if sum(v.values()) > 0]
    )

    # TODO move into parser.py?
    unique_tags: set[int] = set()
    for peer_tags in tags.values():
        unique_tags.update(peer_tags.keys())

    # Collect data from collected dict into lists for plot
    xticks = np.arange(0, len(procs))
    yticks = np.arange(0, len(unique_tags))

    x = list[float]()
    y = list[float]()
    z = list[float]()
    dx = list[float]()
    dy = list[float]()
    dz = list[float]()

    # Also works without casting to str, but produces type error
    # Perhaps this should e dealt with differently
    xlabels = [str(i) for i in sorted(procs)]
    ylabels = [str(i) for i in sorted(unique_tags)]

    proc_to_pos = dict(zip(sorted(procs), xticks))
    tag_to_pos = dict(zip(sorted(unique_tags), yticks))

    for proc, pairs in tags.items():
        for tag, count in pairs.items():
            x.append(proc_to_pos[proc] - 0.4)
            y.append(tag_to_pos[tag] - 0.4)
            z.append(0)
            dx.append(0.8)
            dy.append(0.8)
            dz.append(count)

    _ = ax.bar3d(x, y, z, dx, dy, dz, color="green")
    _ = ax.set_xticks(xticks, labels=xlabels)
    _ = ax.set_yticks(yticks, labels=ylabels)
    _ = ax.set_xlabel("Rank")
    _ = ax.set_ylabel("Tag")
    _ = ax.set_zlabel("No. of messages")
    _ = ax.set_title(title)


def plot_sizes_3d(
    title: str,
    fig: Figure,
    rank: int,
    world_data: WorldData,
    filters: GlobalFilters,
):
    fig.clear()
    ax = cast(Axes3D, fig.add_subplot(projection="3d"))  # Poor typing from mpl
    cur_rank = world_data.ranks[rank]
    sizes = cur_rank.exact_sizes(filter=filters.size)
    procs = set(
        [rank for rank, v in cur_rank.exact_sizes().items() if sum(v.values()) > 0]
    )  # TODO is this expected behavior?

    # TODO move into parser.py?
    unique_sizes: set[int] = set()
    for peer_tags in sizes.values():
        unique_sizes.update(
            peer_tags.keys()
        )  # TODO filter out sizes that are never sent?

    # Collect data from collected dict into lists for plot
    xticks = np.arange(0, len(procs))
    yticks = np.arange(0, len(unique_sizes))

    x = list[float]()
    y = list[float]()
    z = list[float]()

    dx = list[float]()
    dy = list[float]()
    dz = list[float]()

    # Also works without casting to str, but produces type error
    # Perhaps this should e dealt with differently
    xlabels = [str(i) for i in sorted(procs)]
    ylabels = [str(i) for i in sorted(unique_sizes)]

    proc_to_pos = dict(zip(sorted(procs), xticks))
    size_to_pos = dict(zip(sorted(unique_sizes), yticks))

    for proc, pairs in sizes.items():
        for size, count in pairs.items():
            x.append(proc_to_pos[proc] - 0.4)
            y.append(size_to_pos[size] - 0.4)
            z.append(0)
            dx.append(0.8)
            dy.append(0.8)
            dz.append(count)

    _ = ax.bar3d(x, y, z, dx, dy, dz, color="gold")
    _ = ax.set_xticks(xticks, labels=xlabels)
    _ = ax.set_yticks(yticks, labels=ylabels)
    _ = ax.set_xlabel("MPI_COMM_WORLD Rank of peer")
    _ = ax.set_ylabel("Size in Bytes")
    _ = ax.set_zlabel("Messages sent")
    _ = ax.set_title(title)


def plot_counts_2d(
    title: str,
    fig: Figure,
    rank: int,
    world_data: WorldData,
    filters: GlobalFilters,
):
    counts = world_data.ranks[rank].msgs_sent(filter=filters.count)
    fig.clear()
    ax = fig.add_subplot()

    _ = ax.bar(list(counts.keys()), list(counts.values()), color="teal", width=0.8)
    _ = ax.set_xlabel("MPI_COMM_WORLD Rank")
    _ = ax.set_ylabel("Messages sent")
    _ = ax.set_title(title)

    # Idea is good, but looks weird for larger numbers
    # ax_counts.bar_label(p, label_type="center")
