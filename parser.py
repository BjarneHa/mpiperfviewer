from dataclasses import dataclass
from serde import deserialize, field, from_dict
from serde.toml import from_toml

@dataclass
class RankGeneric:
    own_rank: int
    num_procs: int
    wall_time: int
    hostname: str
    mpi_version: str

def deserialize_sent_sizes(x: dict[str, dict[str, list[tuple[int, int]]]]) -> dict[str, dict[str, dict[int, int]]]:
    return {
        type: {
            comp: {
                size: occurances for size, occurances in tuples
            } for comp, tuples in comps.items()
        }
        for type, comps in x.items()
    }

@deserialize
class RankPeer:
    locality: str
    sent_count: dict[str, int]
    sent_tags: dict[str, dict[int, int]] = field(deserializer=lambda x : {comp: { tag: occ for tag, occ in v} for comp, v in x.items()})
    sent_sizes: dict[str, dict[str, dict[int, int]]] = field(deserializer=deserialize_sent_sizes)
    components: list[str] = field(deserializer=lambda x: x.split(","))

@deserialize
class Rank:
    general: RankGeneric
    peers: dict[int, RankPeer] = field(rename="peer", deserializer=lambda x: {int(k) : from_dict(RankPeer, v) for k,v in x.items()})


def parse(file: str):
    with open(file, "r") as f:
        return from_toml(Rank, f.read())
