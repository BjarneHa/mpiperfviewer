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
    matrices_size = sum([m.msgs_sent.nbytes + m.bytes_sent.nbytes for m in mats])
    tags_data_size = cd.tags.nbytes
    sizes_data_size = cd.sizes.nbytes
    occuring_tags_size = cd.occuring_tags.nbytes
    occuring_sizes_size = cd.occuring_sizes.nbytes
    total = (
        matrices_size
        + tags_data_size
        + sizes_data_size
        + occuring_tags_size
        + occuring_sizes_size
    )
    print("matrices_size", matrices_size)
    print("tags_data_size", tags_data_size)
    print("sizes_data_size", sizes_data_size)
    print("occuring_tags_size", occuring_tags_size)
    print("occuring_sizes_size", occuring_sizes_size)
    print("total", total)


wd = WorldData(Path("./testdata"))
total_numpy_size(wd.components["mtl"])
