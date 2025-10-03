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

    def regroup(self, localities: list[list[int]]|None):
        if localities is None:
            return None
        num_localities = len(localities)
        gm = GroupedMatrices.create_empty(num_localities, self.tags.shape[2], self.sizes.shape[2])
        for sender_locality, sender_ranks in enumerate(localities):
            for recipient_locality, recipient_ranks in enumerate(localities):
                for sender in sender_ranks:
                    for recipient in recipient_ranks:
                        gm.sizes[sender_locality, recipient_locality, :] += self.sizes[sender, recipient, :]
                        gm.tags[sender_locality, recipient_locality, :] += self.tags[sender, recipient, :]
                        gm.count[sender_locality, recipient_locality] += self.count[sender, recipient]
        return gm

class ComponentData:
    name: str
    by_rank: GroupedMatrices
    by_core: GroupedMatrices | None = None
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
        name: str,
        occuring_sizes: UInt64Array[tuple[int]],
        occuring_tags: Int64Array[tuple[int]],
        num_processes: int,
    ):
        self.name = name
        n = num_processes
        self.occuring_sizes = occuring_sizes
        self.occuring_tags = occuring_tags

        self.by_rank = GroupedMatrices.create_empty(
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
        wall_time = 0

        occuring_sizes = dict[Component, set[int]]()
        occuring_tags = dict[Component, set[int]]()
        unparsed_localities = list[list[RankLocality]]()

        for rank in range(self.meta.num_processes):
            with open(world_path / rankfile_name(rank), "r") as f:
                sender_rf = from_toml(RankFile, f.read())
                hostnames.add(sender_rf.general.hostname)
                wall_time = max(wall_time, sender_rf.general.wall_time)
                unparsed_localities.append(sender_rf.general.localities)
                for peer in sender_rf.peers.values():
                    for comp, callsites in peer.sent_messages.items():
                        if comp not in occuring_sizes.keys(): # since both always have the same keys, one check is sufficient
                            occuring_sizes[comp] = set()
                            occuring_tags[comp] = set()
                        for callsite in callsites:
                            for msg in callsite.msgs:
                                occuring_sizes[comp].add(msg.size)
                                occuring_tags[comp].update(msg.tags.keys())
                assert sender_rf.general.own_rank == rank


        self.wall_time = timedelta(microseconds=wall_time // 1000)
        self.meta.components = frozenset(occuring_sizes.keys())
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

        node_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.NODE)
        numa_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.NUMA)
        socket_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.SOCKET)
        core_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.CORE)

        # Map from a component and given size/tag to its index in the relevant numpy array in self.rank_sizes/self.rank_tags respectively
        tags_index_map = {
            comp_n: {int(value): index
                for index, value in enumerate(self.components[comp_n].occuring_tags)}
            for comp_n in self.meta.components
        }
        sizes_index_map = {
            comp_n: {int(value): index for index, value in enumerate(self.components[comp_n].occuring_sizes)}
            for comp_n in self.meta.components
        }

        for rank in range(self.meta.num_processes):
            with open(world_path / rankfile_name(rank), "r") as f:
                sender_rf = from_toml(RankFile, f.read())

                for comp_n in self.meta.components:
                    sender = sender_rf.general.own_rank
                    comp = self.components[comp_n]
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
                                for tag, msgs_sent in msg.tags.items():
                                    tag_index = tags_index_map[comp_n][tag]
                                    comp.by_rank.tags[sender, recipient, tag_index] += msgs_sent
                                    msgs_sent_for_size += msgs_sent

                                size_index = sizes_index_map[comp_n][msg.size]
                                comp.by_rank.sizes[sender, recipient, size_index] += msgs_sent_for_size
                                comp.total_bytes_sent += msg.size * msgs_sent_for_size
                        comp.total_msgs_sent += peer.sent_count[comp_n]
                        comp.by_rank.count[sender, recipient] = peer.sent_count[comp_n]

        for comp in self.components.values():
            comp.by_numa = comp.by_rank.regroup(numa_locality)
            comp.by_socket = comp.by_rank.regroup(socket_locality)
            comp.by_node = comp.by_rank.regroup(node_locality)
            comp.by_core = comp.by_rank.regroup(core_locality)

    def _parse_locality(self, rank: int, localities: list[RankLocality], type: LocalityType):
        found = None
        for locality in localities:
            if locality.type == type:
                if found is None:
                    found = locality
                else:
                    raise Exception(f"Locality type \"{type}\" found multiple times in rank file for rank {rank}.")
        return found

    def _get_localities_from_rfs(self, rank_localities: list[list[RankLocality]], type: LocalityType):
        localities = list[list[int]]()
        ranks_covered = [False for _ in rank_localities]
        for rank, rank_locality in enumerate(rank_localities):
            if ranks_covered[rank]:
                continue
            found = self._parse_locality(rank, rank_locality, type)
            if found is None:
                return None
            for other_rank in found.peers:
                found_other_rank = self._parse_locality(rank, rank_localities[other_rank], type)
                if found_other_rank is None or found.peers != found_other_rank.peers:
                    raise Exception(f"Locality \"{type}\" differs in rank files for rank {rank} and {other_rank}.")
                ranks_covered[other_rank] = True
            ranks_covered[rank] = True
            localities.append(found.peers)
        return sorted(localities)
