"""What the conformance runs need a part to be, which is less than a part is.

Every script in here drives something by writing bytes into it and reading bytes
back out. That is the whole of the contract, and it is deliberately smaller than
the class that satisfies it: the real part also exposes its registers, its clock,
and its status port, and a conformance run that reached for any of those would be
checking the model's internals rather than what a console can observe.

Writing it as a protocol rather than as the class means the stand-ins the tests
use are checked against the same contract the real part meets. A double that
grows a differently-shaped read stops type-checking, which is the point: a test
that drives something a console could not drive proves nothing about the part.
"""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Driven(Protocol):
    """Anything a console could drive: a byte in, a byte out."""

    def write(self, value: int) -> None:
        """Give it one byte."""
        ...

    def read(self) -> int:
        """Take one byte."""
        ...


@runtime_checkable
class Watched(Driven, Protocol):
    """A part whose status register is also read, which is how a console polls.

    Separate from Driven because most runs never look: a shape that only writes
    and reads needs the two ports and nothing more, and asking every stand-in for
    a register it is never asked for would be asking for ceremony.
    """

    def read_status(self) -> int:
        """The register that says whether it wants attention."""
        ...


@runtime_checkable
class Identified(Driven, Protocol):
    """A part that also names the image it is running.

    The name is what tells a DSP-1A from a DSP-1 when the two share one image,
    and it is the only thing here that is not a port. Its own shape belongs to
    the loader that produced it, which is why it stays open: this contract says
    that a part knows what it is running, never what that knowledge looks like.
    """

    identity: Any


Build = Callable[[str], Driven]
"""How a run gets a part by name, so a test can hand it something else."""

BuildWatched = Callable[[str], Watched]
"""The same, for a run that also polls the status register."""

BuildIdentified = Callable[[str], Identified]
"""The same, for a run that asks a part which image it is running."""
