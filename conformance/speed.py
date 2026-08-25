"""How fast the part runs its microcode, and a floor it must not fall through.

Not a benchmark for its own sake. Every question this repository answers is
answered by stepping the processor, and replaying the exchanges read out of
thirty six cartridges steps it millions of times. The way that stops being usable
is gradual: a lookup grows an allocation, an offset becomes a comprehension, and
a year later a run nobody changed takes an hour. A floor that fails loudly is
cheaper than noticing.

The floor is deliberately far below what the chip does today. It is there to
catch something several times slower, not to police the noise between one runner
and another, because a shared runner's variance is larger than any change worth
arguing about.

Every figure is a median across repeats rather than a mean, because one
scheduling hiccup moves a mean and moves a median much less, and the runtime
version is printed beside it because it is the single thing that changes these
numbers most.

Run it outside the coverage step. A tracer costs about ten times what this does,
so a floor measured under one measures the tracer.
"""

from __future__ import annotations

import statistics
import sys
import time
from typing import TYPE_CHECKING

import snesdsp

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

FLOOR = 150_000
"""Steps per second this must beat, an order of magnitude below what it does.

Lower than the floor on a part that only answers accesses, because a step here
executes an instruction of somebody's microcode rather than reading a byte out of
an array.
"""

CALLS = 20_000
"""Steps per repeat. Enough that the clock's resolution does not decide."""

REPEATS = 5
"""How many repeats the median is taken across."""

MODEL = "dsp1"
"""The part measured, which is the one shipped in more cartridges than the rest.

One part rather than all six, because all six are the same processor running
different programs and a floor is about the processor.
"""


class Timed:
    """One measured run, and what it is allowed to say about itself."""

    __slots__ = ("calls", "seconds", "what")

    def __init__(self, what: str, calls: int, seconds: Sequence[float]) -> None:
        self.what = what
        self.calls = calls
        self.seconds = list(seconds)

    def median(self) -> float:
        return statistics.median(self.seconds)

    def rate(self) -> float:
        """Calls per second, or zero when the clock could not see the work.

        A run that measured zero seconds is a reading about the clock rather
        than about the code, and reporting it as unbounded speed would let a
        machine with a coarse timer pass a floor it never met.
        """
        taken = self.median()
        return self.calls / taken if taken > 0 else 0.0

    def beats(self, floor: int) -> bool:
        return self.rate() >= floor


def measure(calls: int = CALLS, repeats: int = REPEATS) -> Timed:  # pragma: no cover
    """Step the part through its own microcode, and time it.

    Measured out of the coverage gate on purpose, for the same reason the checks
    that drive real microcode are: it needs a program nobody may distribute, so a
    machine that has one runs a path a machine without one cannot, and a gate
    that demands the impossible gets switched off rather than met.
    """
    part = snesdsp.Chip(MODEL)
    seconds = []
    for _ in range(repeats):
        started = time.perf_counter()
        part.step(calls)
        seconds.append(time.perf_counter() - started)
    return Timed("step", calls, seconds)


def lines_for(found: Timed, floor: int = FLOOR) -> list[str]:
    """What the run reports, whether it passed or not."""
    runtime = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    lines = [
        f"  {found.what}: {found.rate():,.0f} per second"
        f" (median of {len(found.seconds)}) on Python {runtime}",
        f"  floor: {floor:,} per second",
    ]
    if not found.beats(floor):
        lines.append(f"  below the floor: {found.rate():,.0f} is under {floor:,}")
    return lines


def reported(found: Timed, floor: int) -> int:
    """Print what a run found, and say whether it beat the floor."""
    for line in lines_for(found, floor):
        print(line)
    return 0 if found.beats(floor) else 1


def on_this_machine(calls: int, repeats: int, floor: int) -> int:  # pragma: no cover
    """Measure this machine, or say why there is nothing here to measure.

    Out of the coverage gate because no single machine can run both of its
    paths: one needs the program the part runs, and the other needs it absent.
    A gate that demands the impossible gets switched off rather than met, so the
    reason is written here instead.
    """
    missing = snesdsp.why_not()
    if missing is not None:
        print(f"  nothing measured: {missing}")
        return 0
    return reported(measure(calls, repeats), floor)


def main(
    calls: int = CALLS,
    repeats: int = REPEATS,
    floor: int = FLOOR,
    taken: Callable[[int, int], Timed] | None = None,
) -> int:
    """Measure, report, and say whether the floor was beaten.

    `taken` is a parameter so the report can be checked on a machine that cannot
    measure. The part runs a program this repository is not allowed to carry, so
    a test that measures for real passes where the program is present and reports
    success on a runner that measured nothing at all.
    """
    if taken is not None:
        return reported(taken(calls, repeats), floor)
    return on_this_machine(calls, repeats, floor)


if __name__ == "__main__":
    raise SystemExit(main())
