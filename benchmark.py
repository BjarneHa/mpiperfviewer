import statistics
import timeit
import tracemalloc
from itertools import chain
from pathlib import Path
from weakref import WeakValueDictionary

import matplotlib
from matplotlib.figure import Figure
from mpiperfcli.filters import FilterState
from mpiperfcli.parser import ComponentData, GroupedMatrices, WorldData
from mpiperfcli.plots import SizePixelPlot


def total_numpy_size(cd: ComponentData):
    mats = list[GroupedMatrices]()
    if cd.by_core is not None:
        mats.append(cd.by_core)
    if cd.by_numa is not None:
        mats.append(cd.by_numa)
    if cd.by_socket is not None:
        mats.append(cd.by_socket)
    if cd.by_node is not None:
        mats.append(cd.by_node)
    _sizes_data = [cd.sizes(i) for i in range(5)]
    _tags_data = [cd.tags(i) for i in range(5)]
    matrices_size = sum([m.msgs_sent.nbytes + m.total_sent.nbytes for m in mats])
    tags_data_size = sum([t.data.nbytes for t in cd._tags_data_list.values()])
    sizes_data_size = sum([s.data.nbytes for s in cd._size_data_list.values()])
    occuring_tags_size = sum([t.occuring_tags.nbytes for t in cd._tags_data_list.values()])
    occuring_sizes_size = sum([s.occuring_sizes.nbytes for s in cd._size_data_list.values()])
    peers_size = sum([data.peers.nbytes for data in chain(cd._size_data_list.values(), cd._tags_data_list.values())])
    total = (
        matrices_size
        + tags_data_size
        + sizes_data_size
        + occuring_tags_size
        + occuring_sizes_size
        + peers_size
    )
    print("matrices_size", matrices_size)
    print("tags_data_size", tags_data_size)
    print("sizes_data_size", sizes_data_size)
    print("occuring_tags_size", occuring_tags_size)
    print("occuring_sizes_size", occuring_sizes_size)
    print("peers_size", peers_size)
    print("total", total)

tracemalloc.start()

wd = WorldData(Path("./testdata"))
cd = wd.components["mtl"]
total_numpy_size(cd)

snapshot = tracemalloc.take_snapshot()
for data in snapshot.statistics('lineno')[:10]:
    print(data)

nums_sizes = []
nums_tags = []
nums_peers = []
for i in range(wd.meta.num_processes):
    nums_sizes.append(cd.sizes(i).occuring_sizes.size)
    nums_peers.append(cd.sizes(i).peers.size)
    nums_tags.append(cd.tags(i).occuring_tags.size)

avg_sizes = statistics.mean(nums_sizes)
avg_tags = statistics.mean(nums_tags)
avg_peers = statistics.mean(nums_peers)
print(f"Avg sizes {avg_sizes}")
print(f"Avg tags {avg_tags}")
print(f"Avg peers {avg_peers}")

matplotlib.use("qtagg")
plot = SizePixelPlot(Figure(), wd.meta, cd, 0)
fs = FilterState()

def generate_data():
    data = cd.sizes(0)
    _ = plot.generate_3d_data(
        data.peers,
        data.occuring_sizes,
        data.data,
        fs.tag,
        fs.count,
    )


def clear_weak_refs():
    cd._size_data_list = WeakValueDictionary()


def do_draw():
    plot = SizePixelPlot(Figure(), wd.meta, cd, 0)
    plot.draw_plot(fs)
    plot.fig.canvas.draw()

generation_time_sizecached = timeit.repeat(generate_data, number=1, repeat=10**5)
draw_time_sizecached = timeit.repeat(stmt=do_draw, number=1, repeat=1000)
generation_time_rfcached = timeit.repeat(generate_data, setup=clear_weak_refs, number=1, repeat=10**5)
draw_time_rfcached = timeit.repeat(stmt=do_draw, setup=clear_weak_refs, number=1, repeat=1000)

avg_gen_sizecached = statistics.mean(generation_time_sizecached)
avg_gen_rfcached = statistics.mean(generation_time_rfcached)
avg_draw_sizecached = statistics.mean(draw_time_sizecached)
avg_draw_rfcached = statistics.mean(draw_time_rfcached)

print(f"Data generation took {avg_gen_sizecached} seconds on average when SizeData was cached.")
print(f"Data generation took {avg_gen_rfcached} seconds on average when parsed RankFile was cached.")
print(f"Draw call took {avg_draw_sizecached} seconds on average when SizeData was cached.")
print(f"Draw call took {avg_draw_rfcached} seconds on average when parsed RankFile was cached.")

# Disable cache
wd._rank_file_cache = None
generation_time_uncached = timeit.repeat(generate_data, setup=clear_weak_refs, number=1, repeat=1000)
draw_time_uncached = timeit.repeat(stmt=do_draw, setup=clear_weak_refs, number=1, repeat=1000)
avg_gen_rfcached = statistics.mean(generation_time_uncached)
avg_draw_uncached = statistics.mean(draw_time_uncached)
print(f"Data generation took {avg_gen_rfcached} seconds on average when parsed RankFile was not cached.")
print(f"Draw call took {avg_draw_uncached} seconds on average when parsed RankFile was not cached.")
