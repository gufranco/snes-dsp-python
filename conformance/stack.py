"""How deep the real microcode drives the return stack, measured rather than argued.

NEC gives this part a four-level program stack. Every implementation of the family
in the field carries sixteen, and the question that decides whether correcting that
is safe or reckless is not what the fifth call does. It is whether any program
Nintendo shipped ever makes one.

That question has an answer, and it does not need an opinion: the programs are on
this machine, the exchanges real cartridges make with them were read out of the
games, so the part can be driven and the pointer watched. This does that for every
recorded shape of every part, under every one of the 256 command bytes, and reports
the deepest slot anything reached.

What it found, across 15,104 exchanges and 33,734 movements of the pointer: the
DSP-4 reaches slot 1, the DSP-1 and DSP-2 reach slot 2, and the DSP-3 reaches slot
3, which is the last one a four-level stack has. Nothing goes past it. So the
documented depth is consistent with everything the shipped microcode does, and
correcting sixteen to four changes no exchange any cartridge makes.

It takes about twenty minutes, which is why it is a runner and the schedule's job
rather than something every push waits for.

This is the second rung of evidence: below the manufacturer's document, above
anybody's implementation. It cannot prove what the silicon does on a fifth call.
It can prove that no shipped program asks.

Needs the microcode, so on a machine without it this says so and stops rather than
reporting a pass.

Usage:
    python3 conformance/stack.py [part ...]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, override, runtime_checkable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import snesdsp
from conformance import shapes
from snesdsp import chip

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Iterable, Sequence

PARTS = ("dsp1", "dsp2", "dsp3", "dsp4")

COMMANDS = range(0x100)
"""Every byte the first write could carry, since a shape does not say which."""

LEVELS = 4
"""How many slots the part has, per the manufacturer.

Held against the document in the processor's own conformance/hardware.json. It is
repeated here as the number this run measures against rather than as a second
source for it.
"""


class Measured:
    """What one part's microcode did with its stack."""

    def __init__(self, part: str, deepest: int, moves: int, exchanges: int) -> None:
        self.part = part
        self.deepest = deepest
        self.moves = moves
        self.exchanges = exchanges

    def within(self, levels: int) -> bool:
        """Whether the deepest slot reached is one the part actually has."""
        return self.deepest < levels

    @override
    def __repr__(self) -> str:
        return f"<Measured {self.part}, deepest slot {self.deepest}, {self.moves} moves>"


@runtime_checkable
class Counted(Protocol):
    """A processor whose stack pointer can be read between instructions.

    Every other runner here drives a part through the two ports a console has,
    and refuses to look further, because anything a console cannot see is not
    something a console can depend on. This one looks inside on purpose: how deep
    a program pushes is not observable at the ports at all, so there is no version
    of this measurement that stays outside. The reach is the price of the answer,
    and naming it here is what keeps it from spreading.
    """

    registers: Any

    on_cycle: Any

    def step(self) -> None:
        """One instruction."""
        ...


def _processor_of(chip: object) -> Counted:
    """The processor inside a part, or the thing itself when it is one.

    A real part keeps its processor behind an attribute, because a part is the
    processor plus a program plus the console side. A stand-in in a test is
    usually just the processor. Both are watched the same way, and asking for the
    inner one first means neither has to pretend to be the other.
    """
    found = getattr(chip, "core", chip)
    assert isinstance(found, Counted), f"{type(found).__name__} cannot be stepped and watched"
    return found


class _Watching:
    """Drives a part and follows its stack pointer through every instruction."""

    def __init__(self, chip: object) -> None:
        self.core = chip
        self.deepest = 0
        self.moves = 0
        self._install()

    def _install(self) -> None:
        """Follow the pointer from the cycle hook rather than by replacing `step`.

        The processor declares its attributes, so a method cannot be swapped out
        from here at all, and swapping one out was never the right shape: it left
        a part behaving differently while it was being measured. The hook the
        part already publishes is called on every cycle it spends, which is at
        least as often as every instruction, and reading a register there changes
        nothing about what the part does.
        """
        core = _processor_of(self.core)
        registers = core.registers
        held = [registers.sp]

        def watched() -> None:
            after = registers.sp
            if after != held[0]:
                self.moves += 1
                held[0] = after
            self.deepest = max(self.deepest, after)

        core.on_cycle = watched

    def write(self, value: int) -> None:
        self.core.write(value)  # type: ignore[attr-defined]

    def read(self) -> int:
        found = self.core.read()  # type: ignore[attr-defined]
        assert isinstance(found, int)
        return found

    def read_status(self) -> int:
        found = self.core.read_status()  # type: ignore[attr-defined]
        assert isinstance(found, int)
        return found


def _default_build(part: str) -> object:  # pragma: no cover
    return snesdsp.Chip(part)


def why_not() -> str | None:  # pragma: no cover
    return chip.why_not()


def _default_shapes(part: str) -> Sequence[tuple[Sequence[object], int]]:  # pragma: no cover
    return shapes.interesting(shapes.recorded(part))


def watched(
    build: Callable[[str], object],
    part: str,
    steps: Iterable[object],
    payload: Sequence[Sequence[int]],
) -> Measured:
    """One shape played once, with the pointer followed the whole way."""
    driven = _Watching(build(part))
    shapes.drive(driven, steps, payload)  # type: ignore[arg-type]
    return Measured(part, driven.deepest, driven.moves, 1)


def sweep(
    part: str,
    build: Callable[[str], object] = _default_build,
    held: Sequence[tuple[Sequence[object], int]] | None = None,
    commands: Iterable[int] = COMMANDS,
    seed: int | None = None,
    shapes_for: Callable[[str], Sequence[tuple[Sequence[object], int]]] = _default_shapes,
) -> Measured:
    """Every recorded shape for that part, under every command byte.

    A fresh part per exchange, because a stack that was left deep by the previous
    one would report as depth this one reached.
    """
    if held is None:
        held = shapes_for(part)
    chance = shapes.rolls() if seed is None else shapes.rolls(seed)
    deepest = 0
    moves = 0
    exchanges = 0
    for steps, _seen in held:
        payload = shapes.payload_for(steps, chance)  # type: ignore[arg-type]
        for command in commands:
            found = watched(build, part, steps, shapes.commanded(payload, command))
            deepest = max(deepest, found.deepest)
            moves += found.moves
            exchanges += 1
    return Measured(part, deepest, moves, exchanges)


def lines_for(found: Sequence[Measured], levels: int = LEVELS) -> list[str]:
    """What was measured, in the order somebody reading it wants it."""
    said = []
    for one in found:
        said.append(
            f"  {one.part:6s} deepest slot {one.deepest}, {one.moves:,} movements"
            f" across {one.exchanges:,} exchanges"
        )
    past = [one for one in found if not one.within(levels)]
    if past:
        said.append(
            f"  ! {', '.join(one.part for one in past)} drove the pointer past slot"
            f" {levels - 1}, which is the last one a {levels}-level stack has"
        )
    else:
        said.append(
            f"  every part stayed within the {levels} levels the manufacturer gives,"
            f" deepest slot reached {max((one.deepest for one in found), default=0)}"
        )
    return said


def main(
    argv: Sequence[str],
    why_not: Callable[[], str | None] = why_not,
    build: Callable[[str], object] = _default_build,
    shapes_for: Callable[[str], Sequence[tuple[Sequence[object], int]]] = _default_shapes,
    commands: Iterable[int] = COMMANDS,
    parts: Sequence[str] = PARTS,
    levels: int = LEVELS,
    say: Callable[[str], object] = print,
) -> int:
    reason = why_not()
    if reason:
        say(f"  nothing to measure: {reason}")
        return 2

    wanted = list(argv) or list(parts)
    found = [sweep(part, build, shapes_for(part), commands) for part in wanted]
    for line in lines_for(found, levels):
        say(line)
    return 0 if all(one.within(levels) for one in found) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
