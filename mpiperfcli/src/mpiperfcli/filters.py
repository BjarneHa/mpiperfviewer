import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
from typing import override

import numpy as np
from numpy.typing import NDArray


class FilterType(Enum):
    TAG = 0
    SIZE = 1
    COUNT = 2


class Filter(ABC):
    @abstractmethod
    def apply(self, data: NDArray[np.int64] | NDArray[np.uint64]) -> NDArray[np.bool]:
        pass


class Unfiltered(Filter):
    @override
    def apply(self, data: NDArray[np.int64] | NDArray[np.uint64]) -> NDArray[np.bool]:
        return np.ones_like(data, dtype=np.dtype(np.bool))


class BadFilter(Unfiltered):
    pass


class SerializedFilter(Filter, ABC):
    segment: int | None

    def __init__(self, segment: int | None = None):
        super().__init__()
        self.segment = segment


class RangeFilter(SerializedFilter):
    min: int | None
    max: int | None

    def __init__(
        self, min: int | None = None, max: int | None = None, segment: int | None = None
    ):
        super().__init__(segment)
        self.min = min
        self.max = max

    @override
    def __str__(self) -> str:
        min_str = "-inf" if self.min is None else str(self.min)
        max_str = "+inf" if self.max is None else str(self.max)
        return f"[{min_str};{max_str}]"

    @override
    def __eq__(self, other: object, /) -> bool:
        return (
            type(other) is RangeFilter
            and self.min == other.min
            and self.max == other.max
        )

    @override
    def apply(self, data: NDArray[np.int64] | NDArray[np.uint64]):
        metric_min = np.iinfo(data.dtype).min if self.min is None else self.min
        metric_max = np.iinfo(data.dtype).max if self.max is None else self.max
        filter = (metric_min <= data) & (data <= metric_max)
        return filter

    @staticmethod
    def from_str(s: str, segment: int | None = None):
        range_match = re.match(r"^\[((?:\+|\-)?(?:inf|\d+));((?:\+|\-)?(?:inf|\d+))\]$", s)
        if range_match is None:
            return None
        min, max = range_match.groups()

        try:
            min = int(min) if min != "-inf" else None
        except ValueError:
            raise ValueError(
                f'Minimum "{min}" of range "{s}" is not an integer or negative infinity.'
            )

        try:
            max = int(max) if max != "inf" and max != "+inf" else None
        except ValueError:
            raise ValueError(
                f'Maximum "{max}" of range "{s}" is not an integer or positive infinity.'
            )
        return RangeFilter(min, max, segment)

    def remove_exact(self, n: int) -> str:
        min_str = "-inf" if self.min is None else str(self.min)
        max_str = "+inf" if self.max is None else str(self.max)
        if (self.min is not None and n < self.min) or (
            self.max is not None and n > self.max
        ):
            return f"[{min_str};{max_str}]"
        match self.min:
            case min if min == n:
                left = ""
            case min if min == n - 1:
                left = min_str
            case _:
                left = f"[{min_str}; {n - 1}]"

        match self.max:
            case max if max == n:
                right = ""
            case max if max == n + 1:
                right = max_str
            case _:
                right = f"[{n + 1};{max_str}]"

        if left == "":
            return right
        if right == "":
            return left
        return f"{left},{right}"


class ExactFilter(SerializedFilter):
    n: int

    def __init__(self, n: int, segment: int | None = None):
        super().__init__(segment)
        self.n = n

    @staticmethod
    def from_str(s: str, segment: int | None = None):
        try:
            return ExactFilter(int(s), segment)
        except ValueError:
            raise ValueError(f'"{s}" is not a finite integer.')

    @override
    def __str__(self) -> str:
        return str(self.n)

    @override
    def __eq__(self, other: object, /) -> bool:
        return type(other) is ExactFilter and self.n == other.n

    @override
    def apply(self, data: NDArray[np.int64] | NDArray[np.uint64]) -> NDArray[np.bool]:
        return data == self.n


class MultiRangeFilter(Filter):
    ranges: list[RangeFilter]
    exact: list[ExactFilter]
    text: str

    def __init__(self, text: str | None = None, tolerant: bool = False):
        self.ranges = list()
        self.exact = list()
        self.text = text if text is not None else ""
        if text is None or len(text) == 0:
            return

        for i, el in enumerate(text.split(",")):
            try:
                range_filter = RangeFilter.from_str(el)
                if range_filter is not None:
                    self.ranges.append(range_filter)
                else:
                    self.exact.append(ExactFilter.from_str(el, i))
            except ValueError as e:
                if tolerant:
                    continue
                raise e

    @staticmethod
    def from_str(s: str):
        return MultiRangeFilter(s)

    @override
    def apply(self, data: NDArray[np.int64] | NDArray[np.uint64]):
        filter = np.zeros_like(data, dtype=np.bool)
        for range in self.ranges:
            filter |= range.apply(data)
        for exact in self.exact:
            filter |= exact.apply(data)
        return filter

    @override
    def __str__(self) -> str:
        return ",".join([str(f) for f in chain(self.ranges, self.exact)])


class InvertedFilter(Filter):
    _inner: Filter

    def __init__(self, inner: Filter):
        self._inner = inner

    @override
    def apply(self, data: NDArray[np.int64] | NDArray[np.uint64]):
        return ~self._inner.apply(data)

    @override
    def __str__(self) -> str:
        return "!" + str(self._inner)


@dataclass
class FilterState:
    size: Filter = field(default_factory=lambda: Unfiltered())
    count: RangeFilter | Unfiltered = field(default_factory=lambda: Unfiltered())
    tag: Filter = field(default_factory=lambda: Unfiltered())

    def cli_format(self):
        active_filters = list[str]()
        self._format_single_filter(active_filters, "size", self.size)
        self._format_single_filter(active_filters, "count", self.count)
        self._format_single_filter(active_filters, "tag", self.tag)
        return "=".join(active_filters)

    def _format_single_filter(self, list: list[str], filter_name: str, filter: Filter):
        if isinstance(filter, Unfiltered) or isinstance(filter, BadFilter):
            return
        list.append(f"{filter_name}:{filter}")
