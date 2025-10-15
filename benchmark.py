import statistics
import timeit
from itertools import chain
from pathlib import Path

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
    tags_data_size = sum([t.data.nbytes for t in cd._tags_data_list])
    sizes_data_size = sum([s.data.nbytes for s in cd._size_data_list])
    occuring_tags_size = sum([t.occuring_tags.nbytes for t in cd._tags_data_list])
    occuring_sizes_size = sum([s.occuring_sizes.nbytes for s in cd._size_data_list])
    peers_size = sum([data.peers.nbytes for data in chain(cd._size_data_list, cd._tags_data_list)])
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


wd = WorldData(Path("./testdata"))
cd = wd.components["mtl"]
total_numpy_size(cd)


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



def do_draw():
    plot = SizePixelPlot(Figure(), wd.meta, cd, 0)
    plot.draw_plot(fs)
    plot.fig.canvas.draw()

generation_time = timeit.repeat(generate_data, number=1, repeat=10**6)
draw_time = timeit.repeat(stmt=do_draw, number=1, repeat=1000)

avg_gen = statistics.mean(generation_time)
avg_draw = statistics.mean(draw_time)

print(f"Data generation took {avg_gen} seconds on average.")
print(f"Draw call took {avg_draw} seconds on average.")
