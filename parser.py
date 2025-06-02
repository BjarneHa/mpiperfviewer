from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from serde import deserialize, field, from_dict
from serde.toml import from_toml

from filter_view import UNFILTERED, Filter


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


@deserialize
class RankPeer:
    locality: str
    sent_count: dict[str, int]
    sent_tags: dict[str, dict[int, int]] = field(
        deserializer=lambda x: {
            comp: {tag: occ for tag, occ in v} for comp, v in x.items()
        }
    )
    sent_sizes: dict[str, dict[str, dict[int, int]]] = field(
        deserializer=deserialize_sent_sizes
    )
    components: list[str] = field(deserializer=lambda x: x.split(","))


@deserialize
class RankFile:
    general: RankGeneric
    peers: dict[int, RankPeer] = field(
        rename="peer",
        deserializer=lambda x: {int(k): from_dict(RankPeer, v) for k, v in x.items()},
    )


class Rank:
    _rf: RankFile
    total_bytes_sent: int = 0
    total_msgs_sent: int = 0

    def __init__(self, rankfile: RankFile):
        self._rf = rankfile
        self.calculate_totals()

    def calculate_totals(self):
        for sent in self.exact_sizes().values():
            for size, occ in sent.items():
                self.total_bytes_sent += size * occ
        for count in self.msgs_sent().values():
            self.total_msgs_sent += count

    def general(self):
        return self._rf.general

    def tags(self, component: str = "pml", filter: Filter = UNFILTERED):
        return {
            peer: {
                tag: occ
                for tag, occ in data.sent_tags[component].items()
                if filter.test(tag)
            }
            for peer, data in self._rf.peers.items()
            if component in data.components
        }

    def exact_sizes(self, component: str = "pml", filter: Filter = UNFILTERED):
        return {
            peer: {
                size: occ
                for size, occ in data.sent_sizes["exact"][component].items()
                if filter.test(size)
            }
            for peer, data in self._rf.peers.items()
            if component in data.components
        }

    # TODO filtering?
    def bytes_sent(self, component: str = "pml"):
        return {
            peer: sum(
                [
                    size * occ
                    for size, occ in data.sent_sizes["exact"][component].items()
                ]
            )
            for peer, data in self._rf.peers.items()
            if component in data.components
        }

    def msgs_sent(self, component: str = "pml", filter: Filter = UNFILTERED):
        return {
            peer: data.sent_count[component]
            for peer, data in self._rf.peers.items()
            if component in data.components and filter.test(data.sent_count[component])
        }


@dataclass
class WorldMeta:
    num_nodes: int
    num_processes: int
    mpi_version: str
    version: tuple[int, int, int]


def rankfile_name(i: int):
    return f"pc_data_{i}.toml"


class WorldData:
    meta: WorldMeta
    ranks: list[Rank]
    total_bytes_sent: int
    total_msgs_sent: int
    wall_time: timedelta

    def __init__(self, world_path: Path):
        self.get_metadata(world_path)
        self.get_ranks(world_path)
        self.get_derived_statistics()

    # TODO this will hopefully be done differently in the future
    def get_metadata(self, world_path: Path):
        with open(world_path / rankfile_name(0), "r") as f:
            rf0 = from_toml(RankFile, f.read())
            self.meta = WorldMeta(
                num_processes=rf0.general.num_procs,
                mpi_version=rf0.general.mpi_version,
                version=(0, 0, 0),
                num_nodes=0,
            )

    def get_ranks(self, world_path: Path):
        self.ranks = list()
        hostnames = set[str]()
        for i in range(self.meta.num_processes):
            with open(world_path / rankfile_name(i), "r") as f:
                rank = Rank(from_toml(RankFile, f.read()))
                hostnames.add(rank.general().hostname)
                self.ranks.append(rank)
        self.meta.num_nodes = len(hostnames)

    def get_derived_statistics(self):
        self.total_bytes_sent = sum([rank.total_bytes_sent for rank in self.ranks])
        self.total_msgs_sent = sum([rank.total_msgs_sent for rank in self.ranks])
        self.wall_time = timedelta(
            microseconds=max([rank.general().wall_time for rank in self.ranks])
        )
