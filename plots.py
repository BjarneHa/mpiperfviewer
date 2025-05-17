from typing import cast
from matplotlib.figure import Figure
import numpy as np
from mpl_toolkits.mplot3d.axes3d import Axes3D

def tags_plot_3d(title: str, fig: Figure, procs: list[int], tags: dict[int, dict[int, int]]):
    ax = cast(Axes3D, fig.add_subplot(projection='3d')) # Poor typing from mpl

    # TODO this is not strictly the same as in the script... Should this be changed?
    # sent_sizes_cumulative = dict[int, int]()
    # for sizes in exact_sizes.values():
    #     for size, occ in sizes.items():
    #         sent_sizes_cumulative[size] = sent_sizes_cumulative.get(size, 0) + occ
    # procs = set([i for i in range(self._rank_data.general.num_procs)])
    # procs = set([rank for rank, v in exact_sizes.items() if sum(v.values()) > 0])

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

    for proc,pairs in tags.items():
        for tag,count in pairs.items():
            x.append(proc_to_pos[proc]-0.4)
            y.append(tag_to_pos[tag]-0.4)
            z.append(0)
            dx.append(0.8)
            dy.append(0.8)
            dz.append(count)

    _ = ax.bar3d(x, y, z, dx, dy, dz, color='green')
    _ = ax.set_xticks(xticks, labels=xlabels)
    _ = ax.set_yticks(yticks, labels=ylabels)
    _ = ax.set_xlabel("Rank")
    _ = ax.set_ylabel("Tag")
    _ = ax.set_zlabel("No. of messages")
    _ = ax.set_title(title)


def sizes_plot_3d(title: str, fig: Figure, procs: list[int], sizes: dict[int, dict[int, int]]):
    ax = cast(Axes3D, fig.add_subplot(projection='3d')) # Poor typing from mpl

    # TODO move into parser.py?
    unique_sizes: set[int] = set()
    for peer_tags in sizes.values():
        unique_sizes.update(peer_tags.keys()) # TODO filter out sizes that are never sent?

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

    for proc,pairs in sizes.items():
        for size,count in pairs.items():
            x.append(proc_to_pos[proc]-0.4)
            y.append(size_to_pos[size]-0.4)
            z.append(0)
            dx.append(0.8)
            dy.append(0.8)
            dz.append(count)

    _ = ax.bar3d(x, y, z, dx, dy, dz, color='gold')
    _ = ax.set_xticks(xticks, labels=xlabels)
    _ = ax.set_yticks(yticks, labels=ylabels)
    _ = ax.set_xlabel("MPI_COMM_WORLD Rank of peer")
    _ = ax.set_ylabel("Size in Bytes")
    _ = ax.set_zlabel("Messages sent")
    _ = ax.set_title(title)

def counts_plot_2d(title: str, fig: Figure, procs: list[int], counts: dict[int, int]):
    ax = fig.add_subplot()

    _ = ax.bar(list(counts.keys()), list(counts.values()), color='teal', width=0.8)
    _ = ax.set_xlabel("MPI_COMM_WORLD Rank")
    _ = ax.set_ylabel("Messages sent")
    _ = ax.set_title(title)

    # Idea is good, but looks weird for larger numbers
    #ax_counts.bar_label(p, label_type="center")
