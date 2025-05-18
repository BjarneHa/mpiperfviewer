from dataclasses import dataclass

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

    def __init__(self, file: str):
        with open(file, "r") as f:
            self._rf = from_toml(RankFile, f.read())
        self.calculate_totals()

    def calculate_totals(self):
        for sent in self.exact_sizes().values():
            for size, occ in sent.items():
                self.total_bytes_sent += size * occ
        for count in self.count().values():
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

    def count(self, component: str = "pml", filter: Filter = UNFILTERED):
        return {
            peer: data.sent_count[component]
            for peer, data in self._rf.peers.items()
            if component in data.components and filter.test(data.sent_count[component])
        }
