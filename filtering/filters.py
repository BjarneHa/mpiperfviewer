from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, override

import numpy as np
from numpy.typing import NDArray


class FilterType(Enum):
    TAGS = 0
    SIZE = 1
    COUNT = 2


class Filter(ABC):
    @abstractmethod
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        pass


class Unfiltered(Filter):
    @override
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        return np.ones_like(data, dtype=np.dtype(np.bool))


class BadFilter(Unfiltered):
    pass


class RangeFilter(Filter):
    min: int | None
    max: int | None

    def __init__(self, min: int | None = None, max: int | None = None):
        self.min = min
        self.max = max

    @override
    def __str__(self) -> str:
        return "{" + f"min: {self.min}, max: {self.max}" + "}"

    @override
    def __eq__(self, other: object, /) -> bool:
        return (
            type(other) is RangeFilter
            and self.min == other.min
            and self.max == other.max
        )

    @override
    def apply(self, data: NDArray[Any]):
        metric_min = np.iinfo(data.dtype).min if self.min is None else self.min
        metric_max = np.iinfo(data.dtype).max if self.max is None else self.max
        filter = (metric_min <= data) & (data <= metric_max)
        return filter


class ExactFilter(Filter):
    n: int

    def __init__(self, n: int):
        self.n = n

    @override
    def __str__(self) -> str:
        return "{" + f"n: {self.n}" + "}"

    @override
    def __eq__(self, other: object, /) -> bool:
        return type(other) is ExactFilter and self.n == other.n

    @override
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        return data == self.n


class DiscreteMultiRangeFilter(Filter):
    ranges: list[RangeFilter]
    exact: list[ExactFilter]

    def __init__(self):
        self.ranges = list()
        self.exact = list()

    @override
    def apply(self, data: NDArray[Any]):
        filter = np.zeros_like(data, dtype=np.bool)
        for range in self.ranges:
            filter |= range.apply(data)
        for exact in self.exact:
            filter |= exact.apply(data)
        return filter


class InvertedFilter(Filter):
    _inner: Filter

    def __init__(self, inner: Filter):
        self._inner = inner

    @override
    def apply(self, data: NDArray[Any]):
        return ~self._inner.apply(data)


@dataclass
class FilterState:
    size: Filter = field(default_factory=lambda: Unfiltered())
    count: Filter = field(default_factory=lambda: Unfiltered())
    tags: Filter = field(default_factory=lambda: Unfiltered())
