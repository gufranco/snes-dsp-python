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

Needs an image, so on a machine without one it says so and stops rather than
reporting a pass.

Usage:
    python3 conformance/against_cartridges.py [part]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import shapes

import snesdsp
from snesdsp import silicon

DEFAULT_PART = "dsp3"

SHOWN = 8


class Usage(Exception):
    pass


class Driven:
    """One shape, and everything the part said while it was played."""

    def __init__(self, shape, said, kinds=()):
        self.shape = shape
        self.said = said
        self.kinds = tuple(kinds)

    @property
    def answered(self):
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

    def __repr__(self):
        return f"<Driven {self.shape}, {len(self.said)} answers>"


def _silicon(part):  # pragma: no cover
    return snesdsp.Dsp(part)


def driven(part=DEFAULT_PART, build=_silicon, seed=None):
    """Every recorded shape for that part, played at a freshly started one."""
    held = shapes.interesting(shapes.recorded(part))
    if not held:
        raise Usage(f"no cartridge exchanges are recorded for {part}")
    chance = shapes.rolls() if seed is None else shapes.rolls(seed)
    found = []
    for steps, _seen in held:
        payload = shapes.payload_for(steps, chance)
        said = shapes.drive(build(part), steps, payload)
        taken = [one.what for one in steps if one.what in (shapes.READ, shapes.POLL)]
        found.append(Driven(" ".join(f"{one.what}{one.width}" for one in steps), said, taken))
    return found


def report(found):
    """The lines a person reads, one exchange at a time."""
    return [
        f"    {one.shape}: {[[hex(byte) for byte in run] for run in one.said]}"
        for one in found[:SHOWN]
    ]


def silent(found):
    """Every exchange the part answered nothing to."""
    return [one for one in found if not one.answered]


def lines_for(found, part):
    """What the run says about one part."""
    quiet = silent(found)
    lines = [f"  {part}: {len(found)} exchanges a real cartridge makes, played at the part"]
    lines.extend(report(found))
    if quiet:
        lines.append(f"  {len(quiet)} of them got nothing back:")
        lines.extend(f"    {one.shape}" for one in quiet[:SHOWN])
    return lines


def main(argv, why_not=silicon.why_not, build=_silicon, say=print):
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
