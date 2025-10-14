from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from weakref import WeakValueDictionary

import numpy as np
from serde import deserialize, field, from_dict
from serde.toml import from_toml

# If more rank files are part of WorldData, they are not cached
RANK_FILE_CACHE_THRESHOLD = 500

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
    num_processes: int
    mpi_runtime: str
    version: tuple[int, int, int]
    source_directory: Path
    components: frozenset[Component] = frozenset()
    num_nodes: int | None = field(default=None)
    num_cores: int | None = field(default=None)
    num_numa: int | None = field(default=None)
    num_sockets: int | None = field(default=None)


def rankfile_name(i: int):
    return f"pc_data_{i}.toml"


class GroupedMatrices:
    # count[sender, receiver] = occurances
    msgs_sent: UInt64Array[tuple[int, int]]
    # total[sender, receiver] = occurances
    total_sent: UInt64Array[tuple[int, int]]

    def __init__(
        self,
        count: UInt64Array[tuple[int, int]],
        total: UInt64Array[tuple[int, int]],
    ):
        self.msgs_sent = count
        self.total_sent = total

    @classmethod
    def create_empty(cls, n: int):
        count = np.zeros((n, n), dtype=np.uint64).view()
        total = np.zeros((n, n), dtype=np.uint64).view()
        return cls(count, total)

    def regroup(self, localities: list[list[int]]|None):
        if localities is None:
            return None
        num_localities = len(localities)
        gm = GroupedMatrices.create_empty(num_localities)
        for sender_locality, sender_ranks in enumerate(localities):
            for recipient_locality, recipient_ranks in enumerate(localities):
                for sender in sender_ranks:
                    for recipient in recipient_ranks:
                        gm.msgs_sent[sender_locality, recipient_locality] += self.msgs_sent[sender, recipient]
                        gm.total_sent[sender_locality, recipient_locality] += self.total_sent[sender, recipient]
        return gm

@dataclass
class SizeData:
    rank: int
    occuring_sizes: UInt64Array[tuple[int]]
    peers: UInt64Array[tuple[int]]
    data: UInt64Array[tuple[int, int]]

    @staticmethod
    def from_rf(sender_rf: RankFile, component_name: Component):
        occuring_sizes_set = set[int]()
        peers = np.array(list(sender_rf.peers.keys()), dtype=np.uint64).ravel()
        for recipient, peer in sender_rf.peers.items():
            if recipient >= sender_rf.general.num_procs:
                raise ValueError(
                    f"Invalid peer {recipient}>=num_proc for rank {sender_rf.general.own_rank}."
                )
            for callsite in peer.sent_messages.get(component_name, []):
                for msg in callsite.msgs:
                    occuring_sizes_set.add(msg.size)
        occuring_sizes = np.array(list(occuring_sizes_set)).ravel() # ravel is only relevant for type hints
        occuring_sizes.sort()
        size_to_idx_map = {size: i for i, size in enumerate(occuring_sizes)}
        recipient_to_idx_map = {int(peer): i for i, peer in enumerate(peers)}
        data = np.zeros((len(peers), len(occuring_sizes)), np.uint64)
        for recipient, peer in sender_rf.peers.items():
            recipient_idx = recipient_to_idx_map[recipient]
            for callsite in peer.sent_messages.get(component_name, []):
                for msg in callsite.msgs:
                    size_idx = size_to_idx_map[msg.size]
                    data[recipient_idx, size_idx] += sum(msg.tags.values())
        return SizeData(sender_rf.general.own_rank, occuring_sizes, peers, data)

@dataclass
class TagData:
    rank: int
    occuring_tags: UInt64Array[tuple[int]]
    peers: UInt64Array[tuple[int]]
    data: UInt64Array[tuple[int, int]]

    @staticmethod
    def from_rf(sender_rf: RankFile, component_name: Component):
        occuring_tags_set = set[int]()
        peers = np.array(list(sender_rf.peers.keys()), dtype=np.uint64).ravel()
        for recipient, peer_data in sender_rf.peers.items():
            if recipient >= sender_rf.general.num_procs:
                raise ValueError(
                    f"Invalid peer {recipient}>=num_proc for rank {sender_rf.general.own_rank}."
                )
            for callsite in peer_data.sent_messages.get(component_name, []):
                for msg in callsite.msgs:
                    occuring_tags_set.update(msg.tags.keys())
        occuring_tags = np.array(list(occuring_tags_set)).ravel() # ravel is only relevant for type hints
        occuring_tags.sort()
        tags_to_idx_map = {tag: i for i, tag in enumerate(occuring_tags)}
        recipient_to_idx_map = {int(peer): i for i, peer in enumerate(peers)}
        data = np.zeros((len(peers), len(occuring_tags)), np.uint64)
        for recipient, peer_data in sender_rf.peers.items():
            recipient_idx = recipient_to_idx_map[recipient]
            for callsite in peer_data.sent_messages.get(component_name, []):
                for msg in callsite.msgs:
                    for tag, occurances in msg.tags.items():
                        tag_idx = tags_to_idx_map[tag]
                        data[recipient_idx, tag_idx] += occurances
        return TagData(sender_rf.general.own_rank, occuring_tags, peers, data)


class ComponentData:
    name: str
    by_rank: GroupedMatrices
    by_core: GroupedMatrices | None = None
    by_numa: GroupedMatrices | None = None
    by_socket: GroupedMatrices | None = None
    by_node: GroupedMatrices | None = None
    total_bytes_sent: int
    total_msgs_sent: int
    _size_data_list: WeakValueDictionary[int, SizeData]
    _tags_data_list: WeakValueDictionary[int, TagData]
    _world_data: "WorldData"

    def __init__(
        self,
        name: str,
        num_processes: int,
        world_data: "WorldData",
    ):
        self.name = name
        self._world_data = world_data
        self._size_data_list = WeakValueDictionary()
        self._tags_data_list = WeakValueDictionary()
        n = num_processes

        self.by_rank = GroupedMatrices.create_empty(n)
        self.total_bytes_sent = 0
        self.total_msgs_sent = 0

    def tags(self, rank: int):
        lazy_data = self._tags_data_list.get(rank)
        if lazy_data is not None:
            return lazy_data
        with self._world_data.open_rank(rank) as sender_rf:
            data = TagData.from_rf(sender_rf, self.name)
            self._tags_data_list[rank] = data
            return data

    def sizes(self, rank: int):
         lazy_data = self._size_data_list.get(rank)
         if lazy_data is not None:
             return lazy_data
         with self._world_data.open_rank(rank) as sender_rf:
             data = SizeData.from_rf(sender_rf, self.name)
             self._size_data_list[rank] = data
             return data

class WorldData:
    meta: WorldMeta
    components: dict[Component, ComponentData]
    wall_time: timedelta
    _rank_file_cache: dict[int, RankFile] | None

    def __init__(self, world_path: Path):
        self._rank_file_cache = None
        self.parse_metadata(world_path)
        self.parse_ranks()

    @contextmanager
    def open_rank(self, rank: int):
        if self._rank_file_cache is not None:
            cached = self._rank_file_cache.get(rank)
            if cached is not None:
                yield cached
                return
        f = open(self.meta.source_directory / rankfile_name(rank), "r")
        try:
            parsed = from_toml(RankFile, f.read())
            if self._rank_file_cache is not None:
                self._rank_file_cache[rank] = parsed
            yield parsed
        finally:
            f.close()


    # TODO this will hopefully be done differently in the future
    def parse_metadata(self, world_path: Path):
        """Parse metadata from the world file/path required for further processing."""
        # set source_directory for open_rank()
        self.meta = WorldMeta(
            num_processes=0,
            mpi_runtime="",
            version=(0, 0, 0),
            source_directory=world_path,
        )
        with self.open_rank(0) as rf0:
            self.meta.num_processes = rf0.general.num_procs
            self.meta.mpi_runtime = rf0.general.mpi_runtime
            if self.meta.num_processes < RANK_FILE_CACHE_THRESHOLD:
                self._rank_file_cache = {0: rf0}


    def parse_ranks(self):
        """Read data from rank files into multi-dimensional numpy arrays, which can then be used for plotting."""
        wall_time = 0

        component_set = set[Component]()
        unparsed_localities = list[list[RankLocality]]()

        for rank in range(self.meta.num_processes):
            with self.open_rank(rank) as sender_rf:
                wall_time = max(wall_time, sender_rf.general.wall_time)
                unparsed_localities.append(sender_rf.general.localities)
                for peer in sender_rf.peers.values():
                    component_set.update(peer.sent_count.keys())
                    component_set.update(peer.sent_messages.keys())
                assert sender_rf.general.own_rank == rank

        self.wall_time = timedelta(microseconds=wall_time // 1000)
        self.meta.components = frozenset(component_set)

        n = self.meta.num_processes
        self.components = {}
        for c in self.meta.components:
            cd = ComponentData(c, n, self)
            self.components[c] = cd

        node_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.NODE)
        numa_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.NUMA)
        socket_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.SOCKET)
        core_locality = self._get_localities_from_rfs(unparsed_localities, LocalityType.CORE)
        self.meta.num_nodes = len(node_locality) if node_locality is not None else None
        self.meta.num_cores = len(core_locality) if core_locality is not None else None
        self.meta.num_numa = len(numa_locality) if numa_locality is not None else None
        self.meta.num_sockets = len(socket_locality) if socket_locality is not None else None

        for rank in range(self.meta.num_processes):
            with self.open_rank(rank) as sender_rf:
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
                                for msgs_sent in msg.tags.values():
                                    comp.total_bytes_sent += msgs_sent * msg.size
                                    comp.by_rank.total_sent[sender, recipient] += msgs_sent * msg.size
                        comp.total_msgs_sent += peer.sent_count[comp_n]
                        comp.by_rank.msgs_sent[sender, recipient] = peer.sent_count[comp_n]

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
