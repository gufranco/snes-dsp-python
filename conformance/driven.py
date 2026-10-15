from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Driven(Protocol):
    def write(self, value: int) -> None: ...

    def read(self) -> int: ...


@runtime_checkable
class Watched(Driven, Protocol):
    def read_status(self) -> int: ...


@runtime_checkable
class Identified(Driven, Protocol):
    identity: Any


Build = Callable[[str], Driven]

BuildWatched = Callable[[str], Watched]

BuildIdentified = Callable[[str], Identified]
