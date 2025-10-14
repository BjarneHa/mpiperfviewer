from itertools import chain
from pathlib import Path

from mpiperfcli.parser import ComponentData, GroupedMatrices, WorldData


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
total_numpy_size(wd.components["mtl"])
