from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
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
        return f"[{self.min};{self.max}]"

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

    @override
    def __str__(self) -> str:
        return str(self.n)

    @override
    def __eq__(self, other: object, /) -> bool:
        return type(other) is ExactFilter and self.n == other.n

    @override
    def apply(self, data: NDArray[Any]) -> NDArray[Any]:
        return data == self.n


class DiscreteMultiRangeFilter(Filter):
    ranges: list[RangeFilter]
    exact: list[ExactFilter]

    def __init__(self, text: str | None = None, tolerant: bool = False):
        self.ranges = list()
        self.exact = list()
        if text is None or len(text) == 0:
            return

        for i, el in enumerate(text.split(",")):
            try:
                if el.startswith("["):
                    if not el.endswith("]"):
                        raise ValueError(f'Range not closed in "{el}".')
                    min, max = el[1:-1].split(";")
                    if min == "inf" or min == "+inf":
                        raise ValueError(
                            f'Range minimum may not be positive infinity: "{el}"'
                        )
                    if max == "-inf":
                        raise ValueError(
                            f'Range maximum may not be negative infinity: "{el}"'
                        )

                    range_filter = RangeFilter(
                        int(min) if min != "-inf" else None,
                        int(max) if max != "inf" and max != "+inf" else None,
                        i,
                    )
                    self.ranges.append(range_filter)
                else:
                    exact = int(el)
                    self.exact.append(ExactFilter(exact, i))
            except ValueError as e:
                if tolerant:
                    continue
                raise e

    @override
    def apply(self, data: NDArray[Any]):
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
    def apply(self, data: NDArray[Any]):
        return ~self._inner.apply(data)


@dataclass
class FilterState:
    size: Filter = field(default_factory=lambda: Unfiltered())
    count: Filter = field(default_factory=lambda: Unfiltered())
    tags: Filter = field(default_factory=lambda: Unfiltered())
