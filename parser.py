from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
from serde import deserialize, field, from_dict
from serde.toml import from_toml


@dataclass
class RankGeneric:
    own_rank: int
    num_procs: int
    wall_time: int
    hostname: str
    mpi_version: str


def deserialize_sent_sizes(
    x: dict[str, dict[str, list[tuple[int, int]]]],
) -> dict[str, dict[str, dict[int, int]]]:
    return {
        type: {
            comp: {size: occurances for size, occurances in tuples}
            for comp, tuples in comps.items()
        }
        for type, comps in x.items()
    }


def deserialize_sent_tags(
    x: dict[str, list[tuple[int, int]]],
) -> dict[str, dict[int, int]]:
    return {comp: {tag: occ for tag, occ in v} for comp, v in x.items()}


@deserialize
class RankPeer:
    locality: str
    sent_count: dict[str, int]
    sent_tags: dict[str, dict[int, int]] = field(deserializer=deserialize_sent_tags)
    sent_sizes: dict[str, dict[str, dict[int, int]]] = field(
        deserializer=deserialize_sent_sizes
    )
    components: list[str] = field(deserializer=lambda x: x.split(","))  # TODO remove


def cast_dict_keys_to_int(x: dict[str, Any]):
    return {int(k): from_dict(RankPeer, v) for k, v in x.items()}


@deserialize
class RankFile:
    general: RankGeneric
    peers: dict[int, RankPeer] = field(
        rename="peer",
        deserializer=cast_dict_keys_to_int,
    )


type UInt64Array[T: tuple[int, ...]] = np.ndarray[T, np.dtype[np.uint64]]
type Int64Array[T: tuple[int, ...]] = np.ndarray[T, np.dtype[np.int64]]
type Component = str


@dataclass
class WorldMeta:
    num_nodes: int
    num_processes: int
    mpi_version: str
    version: tuple[int, int, int]
    components: frozenset[Component] = frozenset()


def rankfile_name(i: int):
    return f"pc_data_{i}.toml"


class GroupedMatrices:
    # sizes[sender, receiver, size_index] = occurances
    sizes: UInt64Array[tuple[int, int, int]]
    # tags[sender, receiver, tag_index] = occurances
    tags: UInt64Array[tuple[int, int, int]]
    # count[sender, receiver] = occurances
    count: UInt64Array[tuple[int, int]]

    def __init__(
        self,
        sizes: UInt64Array[tuple[int, int, int]],
        tags: UInt64Array[tuple[int, int, int]],
        count: UInt64Array[tuple[int, int]],
    ):
        self.sizes = sizes
        self.tags = tags
        self.count = count

    @classmethod
    def create_empty(cls, n: int, num_tags: int, num_sizes: int):
        sizes = np.zeros((n, n, num_sizes), dtype=np.uint64).view()
        tags = np.zeros((n, n, num_tags), dtype=np.uint64).view()
        count = np.zeros((n, n), dtype=np.uint64).view()
        return cls(sizes, tags, count)

    def regroup(self, group_size: int):
        if group_size == 0:
            return None

        slice_size = self.sizes.shape[0] // group_size
        new_sizes = self.sizes.reshape(
            slice_size, group_size, slice_size, group_size, self.sizes.shape[2]
        ).sum((1, 3))
        new_tags = self.tags.reshape(
            slice_size, group_size, slice_size, group_size, self.tags.shape[2]
        ).sum((1, 3))
        new_count = self.count.reshape(
            slice_size, group_size, slice_size, group_size
        ).sum((1, 3))
        return GroupedMatrices(new_sizes, new_tags, new_count)


class ComponentData:
    by_rank: GroupedMatrices
    by_numa: GroupedMatrices | None = None
    by_socket: GroupedMatrices | None = None
    by_node: GroupedMatrices | None = None
    # occuring_sizes[size_index] = size
    occuring_sizes: UInt64Array[tuple[int]]
    # occuring_sizes[tag_index] = tag
    occuring_tags: Int64Array[tuple[int]]
    total_bytes_sent: int
    total_msgs_sent: int

    def __init__(
        self,
        occuring_sizes: UInt64Array[tuple[int]],
        occuring_tags: Int64Array[tuple[int]],
        num_processes: int,
    ):
        n = num_processes
        self.occuring_sizes = occuring_sizes
        self.occuring_tags = occuring_tags

        self.by_rank = GroupedMatrices.create_empty(
            n, occuring_tags.size, occuring_sizes.size
        )
        self.total_bytes_sent = 0
        self.total_msgs_sent = 0

    def group_by_numa(self, ranks_per_numa: int):
        if self.by_rank.sizes.shape[0] % ranks_per_numa != 0:
            raise Exception("Invalid NUMA grouping. Check data.")
        self.by_numa = self.by_rank.regroup(ranks_per_numa)

    def group_by_socket(self, ranks_per_socket: int):
        if self.by_rank.sizes.shape[0] % ranks_per_socket != 0:
            raise Exception("Invalid socket grouping. Check data.")
        self.by_socket = self.by_rank.regroup(ranks_per_socket)

    def group_by_node(self, ranks_per_node: int):
        if self.by_rank.sizes.shape[0] % ranks_per_node != 0:
            raise Exception("Invalid node grouping. Check data.")
        self.by_node = self.by_rank.regroup(ranks_per_node)


class WorldData:
    meta: WorldMeta
    components: dict[Component, ComponentData]
    wall_time: timedelta

    def __init__(self, world_path: Path):
        self.parse_metadata(world_path)
        self.parse_ranks(world_path)

    # TODO this will hopefully be done differently in the future
    def parse_metadata(self, world_path: Path):
        """Parse metadata from the world file/path required for further processing."""
        with open(world_path / rankfile_name(0), "r") as f:
            rf0 = from_toml(RankFile, f.read())
            self.meta = WorldMeta(
                num_processes=rf0.general.num_procs,
                mpi_version=rf0.general.mpi_version,
                version=(0, 0, 0),
                num_nodes=0,
            )

    def parse_ranks(self, world_path: Path):
        """Read data from rank files into multi-dimensional numpy arrays, which can then be used for plotting."""
        hostnames = set[str]()
        rank_files = list[RankFile]()
        wall_time = 0

        for i in range(self.meta.num_processes):
            with open(world_path / rankfile_name(i), "r") as f:
                sender = from_toml(RankFile, f.read())
                hostnames.add(sender.general.hostname)
                rank_files.append(sender)
                wall_time = max(wall_time, sender.general.wall_time)

        self.wall_time = timedelta(microseconds=wall_time // 1000)
        component_set = set[Component]()

        for sender in rank_files:
            for peer in sender.peers.values():
                component_set.update(peer.components)

        self.meta.components = frozenset(component_set)

        occuring_sizes = {c: set[int]() for c in self.meta.components}
        occuring_tags = {c: set[int]() for c in self.meta.components}
        for sender in rank_files:
            for peer in sender.peers.values():
                for comp in self.meta.components:
                    occuring_sizes[comp].update(
                        peer.sent_sizes.get("exact", {}).get(comp, {}).keys()
                    )
                    occuring_tags[comp].update(peer.sent_tags.get(comp, {}).keys())

        self.meta.num_nodes = len(hostnames)

        n = self.meta.num_processes
        self.components = {}
        for c in self.meta.components:
            # .view() and .ravel() do not change/copy the array and are only necessary for typing
            cd_occuring_sizes = (
                np.array(sorted(occuring_sizes[c]), dtype=np.uint64).view().ravel()
            )
            cd_occuring_tags = (
                np.array(sorted(occuring_tags[c]), dtype=np.int64).view().ravel()
            )
            cd = ComponentData(cd_occuring_sizes, cd_occuring_tags, n)
            self.components[c] = cd

        for comp_n in self.meta.components:
            # Map from a given size/tag to its index in the relevant numpy array in self.rank_sizes/self.rank_tags respectively
            comp = self.components[comp_n]
            tags_index_map = {
                int(value): index for index, value in enumerate(comp.occuring_tags)
            }
            sizes_index_map = {
                int(value): index for index, value in enumerate(comp.occuring_sizes)
            }

            for sender in rank_files:
                from_rank = sender.general.own_rank
                if sender.general.own_rank >= n:
                    raise ValueError(f"Invalid own_rank {from_rank}>=num_proc.")

                for receiver, peer in sender.peers.items():
                    if receiver >= n:
                        raise ValueError(
                            f"Invalid peer {receiver}>=num_proc for rank {from_rank}."
                        )
                    for size, occurances in (
                        peer.sent_sizes.get("exact", {}).get(comp_n, {}).items()
                    ):
                        size_index = sizes_index_map[size]
                        comp.by_rank.sizes[from_rank, receiver, size_index] = occurances
                        comp.total_bytes_sent += size * occurances
                    for tags, occurances in peer.sent_tags.get(comp_n, {}).items():
                        tag_index = tags_index_map[tags]
                        comp.by_rank.tags[from_rank, receiver, tag_index] = occurances
                    comp.by_rank.count[from_rank, receiver] = peer.sent_count[comp_n]
                    comp.total_msgs_sent += peer.sent_count[comp_n]
            comp.group_by_node(self.meta.num_processes // self.meta.num_nodes)
