"""Drive a part through the exchanges a real cartridge has with it.

Running a part's microcode is only half of getting it right. The other half is
sending it what a console sends: these parts have no framing, so a byte means
whatever the state left by the bytes before it decides, and a sequence no game
ever sent asks a question nobody has an answer for.

What a game sends is not something to derive. It is written down in the game, as
ordinary 65816 code, and `snes-driver-python` reads it out by disassembling the
routine rather than running it. What comes back is a shape: the accesses a
routine makes, in order, with the width of each and no payload attached. Those
shapes are recorded beside this, with the digests of the cartridge they came from
and none of its bytes.

This plays them at the part and prints what it said. It is not a comparison
against anything written down, because there is nothing left to compare against:
the part is the authority. What it catches is the part not answering at all,
which is what a broken port layer, a wrong image or a mis-paced read looks like.

A shape carries no payload, so the bytes that fill it are generated, and the
first of them is a command the part may not have. Most of the 256 possible bytes
are not commands on these parts, and a part answering nothing to one of those has
not been shown to answer nothing: it has been asked a question it does not have.
So a shape that says nothing is asked again under every command byte in turn, and
is reported as silent only when all 256 leave it silent. Which command made it
speak is printed, because a shape that answers under one byte and no other is
worth knowing about even when it is not a fault.

Needs an image, so on a machine without one it says so and stops rather than
reporting a pass.

Usage:
    python3 conformance/against_cartridges.py [part]
"""

import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import snesdsp
from conformance import shapes
from conformance.driven import BuildWatched, Watched
from snesdsp import chip

DEFAULT_PART = "dsp3"

SHOWN = 8

COMMANDS = range(0x100)
"""Every byte the first write could carry, since the shape does not say which."""


class Usage(Exception):
    pass


class Played:
    """One shape, and everything the part said while it was played.

    Named for the run rather than for the part: this holds what came back, and
    the thing that came back is not something anybody can drive.
    """

    def __init__(
        self,
        shape: str,
        said: Sequence[Sequence[int]],
        kinds: Iterable[str] = (),
        command: int | None = None,
    ) -> None:
        self.shape = shape
        self.said = said
        self.kinds = tuple(kinds)
        self.command = command
        self.kinds_in_order = tuple(one.what for one in shapes.parse(shape))

    @property
    def unprompted(self) -> bool:
        """Whether this shape reads before it has written anything.

        On a console such a read follows an earlier exchange and is answered by
        what that exchange left behind. Played on its own at a part that has just
        booted there is nothing behind it, and no command byte can change that:
        the read happens before the command does.
        """
        for kind in self.kinds_in_order:
            if kind == shapes.WRITE:
                return False
            if kind == shapes.READ:
                return True
        return False

    @property
    def answered(self) -> bool:
        """Whether anything came back from the data port that was not a zero.

        The data port only. A part that is doing nothing still has a status
        register, and a register that reads as ready is not an answer: counting
        it would let a part that computes nothing look like one that does.

        A part answering nothing but zeroes to every exchange a real game makes
        is not answering. It is the shape a wrong image, an unbooted part and a
        port read at the wrong moment all take.
        """
        return any(
            byte
            for kind, run in zip(self.kinds, self.said, strict=False)
            if kind == shapes.READ
            for byte in run
        )

    @override
    def __repr__(self) -> str:
        return f"<Played {self.shape}, {len(self.said)} answers>"


def _silicon(part: str) -> Watched:  # pragma: no cover
    return snesdsp.Chip(part)


class Spoke:
    """A command byte that got an answer, and the answer it got."""

    def __init__(self, command: int, said: Sequence[Sequence[int]]) -> None:
        self.command = command
        self.said = said

    @override
    def __repr__(self) -> str:
        return f"<Spoke under {self.command:#04x}>"


def speaking(
    build: BuildWatched,
    part: str,
    steps: "Iterable[shapes.Step]",
    payload: Sequence[Sequence[int]],
    commands: Iterable[int] = COMMANDS,
) -> "Spoke | None":
    """The first command byte under which that shape gets an answer, if any.

    Everything but the first byte is left as it was, so the only thing that
    changes between attempts is the command. A shape with nothing to write cannot
    carry a command and cannot be swept, which is not the same as being silent.
    """
    steps = tuple(steps)
    kinds = [one.what for one in steps if one.what in (shapes.READ, shapes.POLL)]
    if not payload:
        return None
    for command in commands:
        said = shapes.drive(build(part), steps, shapes.commanded(payload, command))
        if Played("", said, kinds).answered:
            return Spoke(command, said)
    return None


def driven(
    part: str = DEFAULT_PART, build: BuildWatched = _silicon, seed: int | None = None
) -> "list[Played]":
    """Every recorded shape for that part, played at a freshly started one."""
    held = shapes.interesting(shapes.recorded(part))
    if not held:
        raise Usage(f"no cartridge exchanges are recorded for {part}")
    chance = shapes.rolls() if seed is None else shapes.rolls(seed)
    found: list[Played] = []
    for steps, _seen in held:
        payload = shapes.payload_for(steps, chance)
        said = shapes.drive(build(part), steps, payload)
        taken = [one.what for one in steps if one.what in (shapes.READ, shapes.POLL)]
        named = " ".join(f"{one.what}{one.width}" for one in steps)
        played = Played(named, said, taken)
        if not played.answered and not played.unprompted:
            spoke = speaking(build, part, steps, payload)
            if spoke is not None:
                played = Played(named, spoke.said, taken, spoke.command)
        found.append(played)
    return found


def report(found: "Sequence[Played]") -> list[str]:
    """The lines a person reads, one exchange at a time."""
    said = []
    for one in found[:SHOWN]:
        under = "" if one.command is None else f" (only under command {one.command:#04x})"
        said.append(f"    {one.shape}{under}: {[[hex(byte) for byte in run] for run in one.said]}")
    return said


def silent(found: "Iterable[Played]") -> "list[Played]":
    """Every exchange the part answered nothing to, having been asked in order."""
    return [one for one in found if not one.answered and not one.unprompted]


def unprompted(found: "Iterable[Played]") -> "list[Played]":
    """Every exchange whose first read comes before its first write."""
    return [one for one in found if one.unprompted]


def lines_for(found: "Sequence[Played]", part: str) -> list[str]:
    """What the run says about one part."""
    quiet = silent(found)
    lines = [f"  {part}: {len(found)} exchanges a real cartridge makes, played at the part"]
    lines.extend(report(found))
    if quiet:
        lines.append(
            f"  {len(quiet)} of them got nothing back under any of the"
            f" {len(COMMANDS)} command bytes:"
        )
        lines.extend(f"    {one.shape}" for one in quiet[:SHOWN])

    early = unprompted(found)
    if early:
        lines.append(
            f"  {len(early)} of them read before writing, so a part that has just"
            " booted has nothing to answer them with. Not counted as silence:"
        )
        lines.extend(f"    {one.shape}" for one in early[:SHOWN])
    return lines


def main(
    argv: Sequence[str],
    why_not: Callable[[], str | None] = chip.why_not,
    build: BuildWatched = _silicon,
    say: Callable[[str], object] = print,
) -> int:
    reason = why_not()
    if reason:
        say(f"  nothing was driven: {reason}")
        return 2

    part = argv[0] if argv else DEFAULT_PART
    found = driven(part, build)
    for line in lines_for(found, part):
        say(line)
    return 1 if silent(found) else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Usage as refusal:
        print(refusal)
        sys.exit(2)
