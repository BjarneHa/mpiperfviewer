from pathlib import Path

from mpiperfcli.parser import ComponentData, WorldData


def total_numpy_size(cd: ComponentData):
    by_rank = cd.by_rank.array.nbytes
    by_core = cd.by_core.array.nbytes if cd.by_core is not None else 0
    by_numa = cd.by_numa.array.nbytes if cd.by_numa is not None else 0
    by_socket = cd.by_socket.array.nbytes if cd.by_socket is not None else 0
    by_node = cd.by_node.array.nbytes if cd.by_node is not None else 0
    print("by_rank", by_rank)
    print("by_core", by_core)
    print("by_numa", by_numa)
    print("by_socket", by_socket)
    print("by_node", by_node)
    print("-" * 20)
    print("total", by_rank + by_core + by_numa + by_socket + by_node)

wd = WorldData(Path("./testdata"))
total_numpy_size(wd.components["mtl"])
