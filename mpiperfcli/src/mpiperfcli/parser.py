from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
from serde import deserialize, field, from_dict
from serde.toml import from_toml


class LocalityType(StrEnum):
    CORE = "hwcore"
    SOCKET = "socket" # TODO correct?
    NUMA = "NUMA"
    NODE = "node"

def deserialize_peers(peers: list[Any]):
    out = list[int]()
    def add_peer(peer: int):
        if peer < 0:
            raise ValueError(f"Peer \"{peer}\" invalid.")
        out.append(peer)
    for peer in peers:
        if isinstance(peer, str):
            match peer.split("-", 1):
                case start, end:
                    start = int(start)
                    end = int(end)
                    if start > end or start < 0:
                        raise ValueError(f"Peer range \"{peer}\" invalid.")
                    out += list(range(int(start), int(end)+1))
                case peer,:
                    peer = int(peer)
                    add_peer(peer)
                case _:
                    raise ValueError(f"Peer \"{peer}\" invalid.")
        elif isinstance(peer, int):
            add_peer(peer)
        else:
            raise ValueError(f"Peer \"{peer}\" invalid.")
    return out


@dataclass
class RankLocality:
    type: LocalityType = field(rename="locality")
    peers: list[int] = field(deserializer=deserialize_peers)


@dataclass
class RankGeneral:
    own_rank: int
    num_procs: int
    wall_time: int
    hostname: str
    mpi_runtime: str
    localities: list[RankLocality]



def deserialize_sent_tags(
    tags: list[tuple[int, int]],
) -> dict[int, int]:
    return {tag: occ for tag, occ in tags}

@deserialize
class CallsiteMessagesSizeEntry:
    size: int
    tags: dict[int, int] = field(deserializer=deserialize_sent_tags)


@deserialize
class CallsiteMessageData:
    callsite: int
    msgs: list[CallsiteMessagesSizeEntry]

@deserialize
class RankPeer:
    components: list[str]
    sent_count: dict[str, int]
    sent_messages: dict[str, list[CallsiteMessageData]]

def cast_dict_keys_to_int(x: dict[str, Any]):
    return {int(k): from_dict(RankPeer, v) for k, v in x.items()}


@deserialize
class RankFile:
    general: RankGeneral
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
    mpi_runtime: str
    version: tuple[int, int, int]
    source_directory: Path
    components: frozenset[Component] = frozenset()


def rankfile_name(i: int):
    return f"pc_data_{i}.toml"


class LocalityMatrix:
    # count[sender, receiver, size_idx, tag_idx] = occurances
    array: UInt64Array[tuple[int, int, int, int]]

    def __init__(
        self,
        array: UInt64Array[tuple[int, int, int, int]],
    ):
        self.array = array
        print("Size:", array.nbytes)
        print("Shape:", array.shape)

    @classmethod
    def create_empty(cls, n: int, num_tags: int, num_sizes: int):
        array = np.zeros((n, n, num_sizes, num_tags), dtype=np.uint64).view()
        return cls(array)

    def regroup(self, localities: list[list[int]]|None):
        if localities is None:
            return None
        num_localities = len(localities)
        gm = LocalityMatrix.create_empty(num_localities, self.array.shape[3], self.array.shape[2])
        for sender_locality, sender_ranks in enumerate(localities):
            for recipient_locality, recipient_ranks in enumerate(localities):
                for sender in sender_ranks:
                    for recipient in recipient_ranks:
                        gm.array[sender_locality, recipient_locality, :, :] += self.array[sender, recipient, :, :]
        return gm

    def tags(self, rank: int):
        return self.array[rank, :, :, :].sum(2)

    def sizes(self, rank: int):
        return self.array[rank, :, :, :].sum(3)

    def count(self, rank: int):
        return self.array[rank, :, :, :].sum((2, 3))

class ComponentData:
    name: str
    by_rank: LocalityMatrix
    by_core: LocalityMatrix | None = None
    by_numa: LocalityMatrix | None = None
    by_socket: LocalityMatrix | None = None
    by_node: LocalityMatrix | None = None
    # occuring_sizes[size_index] = size
    occuring_sizes: UInt64Array[tuple[int]]
    # occuring_sizes[tag_index] = tag
    occuring_tags: Int64Array[tuple[int]]
    total_bytes_sent: int
    total_msgs_sent: int

    def __init__(
        self,
        name: str,
        occuring_sizes: UInt64Array[tuple[int]],
        occuring_tags: Int64Array[tuple[int]],
        num_processes: int,
    ):
        self.name = name
        n = num_processes
        self.occuring_sizes = occuring_sizes
        self.occuring_tags = occuring_tags

        self.by_rank = LocalityMatrix.create_empty(
            n, occuring_tags.size, occuring_sizes.size
        )
        self.total_bytes_sent = 0
        self.total_msgs_sent = 0

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
                mpi_runtime=rf0.general.mpi_runtime,
                version=(0, 0, 0),
                num_nodes=0,
                source_directory=world_path,
            )

    def parse_ranks(self, world_path: Path):
        """Read data from rank files into multi-dimensional numpy arrays, which can then be used for plotting."""
        hostnames = set[str]()
        rank_files = list[RankFile]()
        wall_time = 0

        for i in range(self.meta.num_processes):
            with open(world_path / rankfile_name(i), "r") as f:
                sender_rf = from_toml(RankFile, f.read())
                hostnames.add(sender_rf.general.hostname)
                rank_files.append(sender_rf)
                wall_time = max(wall_time, sender_rf.general.wall_time)
                assert sender_rf.general.own_rank == i

        self.wall_time = timedelta(microseconds=wall_time // 1000)
        component_set = set[Component]()

        for sender_rf in rank_files:
            for peer in sender_rf.peers.values():
                component_set.update(peer.components)

        self.meta.components = frozenset(component_set)

        occuring_sizes = {c: set[int]() for c in self.meta.components}
        occuring_tags = {c: set[int]() for c in self.meta.components}
        for sender_rf in rank_files:
            for peer in sender_rf.peers.values():
                for comp, callsites in peer.sent_messages.items():
                    for callsite in callsites:
                        for msg in callsite.msgs:
                            occuring_sizes[comp].add(msg.size)
                            occuring_tags[comp].update(msg.tags.keys())

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
            cd = ComponentData(c, cd_occuring_sizes, cd_occuring_tags, n)
            self.components[c] = cd

        node_locality = self._get_localities_from_rfs(rank_files, LocalityType.NODE)
        numa_locality = self._get_localities_from_rfs(rank_files, LocalityType.NUMA)
        socket_locality = self._get_localities_from_rfs(rank_files, LocalityType.SOCKET)
        core_locality = self._get_localities_from_rfs(rank_files, LocalityType.CORE)

        for comp_n in self.meta.components:
            # Map from a given size/tag to its index in the relevant numpy array in self.rank_sizes/self.rank_tags respectively
            comp = self.components[comp_n]
            tags_index_map = {
                int(value): index for index, value in enumerate(comp.occuring_tags)
            }
            sizes_index_map = {
                int(value): index for index, value in enumerate(comp.occuring_sizes)
            }

            for sender_rf in rank_files:
                sender = sender_rf.general.own_rank
                if sender_rf.general.own_rank >= n:
                    raise ValueError(f"Invalid own_rank {sender}>=num_proc.")

                for recipient, peer in sender_rf.peers.items():
                    if recipient >= n:
                        raise ValueError(
                            f"Invalid peer {recipient}>=num_proc for rank {sender}."
                        )
                    for callsite in peer.sent_messages.get(comp_n, []):
                        for msg in callsite.msgs:
                            msgs_sent_for_size = 0
                            size_index = sizes_index_map[msg.size]
                            for tag, msgs_sent in msg.tags.items():
                                tag_index = tags_index_map[tag]
                                comp.by_rank.array[sender, recipient, size_index, tag_index] += msgs_sent
                                msgs_sent_for_size += msgs_sent
                            comp.total_bytes_sent += msg.size * msgs_sent_for_size
                    comp.total_msgs_sent += peer.sent_count[comp_n]
            comp.by_numa = comp.by_rank.regroup(numa_locality)
            comp.by_socket = comp.by_rank.regroup(socket_locality)
            comp.by_node = comp.by_rank.regroup(node_locality)
            comp.by_core = comp.by_rank.regroup(core_locality)

    def _get_locality_from_rf(self, rf: RankFile, type: LocalityType):
        found = None
        for locality in rf.general.localities:
            if locality.type == type:
                if found is None:
                    found = locality
                else:
                    raise Exception(f"Locality type \"{type}\" found multiple times in rank file for rank {rf.general.own_rank}.")
        return found

    def _get_localities_from_rfs(self, rfs: list[RankFile], type: LocalityType):
        localities = list[list[int]]()
        ranks_covered = [False for _ in rfs]
        for i, rf in enumerate(rfs):
            if ranks_covered[i]:
                continue
            found = self._get_locality_from_rf(rf, type)
            if found is None:
                return None
            for other_rank in found.peers:
                found_other_rank = self._get_locality_from_rf(rfs[other_rank], type)
                if found_other_rank is None or found.peers != found_other_rank.peers:
                    raise Exception(f"Locality \"{type}\" differs in rank files for rank {i} and {other_rank}.")
                ranks_covered[other_rank] = True
            ranks_covered[i] = True
            localities.append(found.peers)
        return sorted(localities)
