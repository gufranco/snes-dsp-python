"""Drive a part the way a cartridge drives it, rather than the way a table says.

Two of the four parts here cannot be swept by picking a command and reading a
known number of words back. The DSP-3 is clocked a word at a time and watches its
own status register instead of answering a count. The DSP-4 draws rather than
answers: it consumes a batch, produces some output, and waits for the next batch,
and how much comes back depends on what the earlier batches left behind.

For both, the missing piece is not the part. It is knowing what the console
actually says to it, and that is not something to derive: it is written down in
the game, as ordinary 65816 code, and can be read out of the cartridge with
`snes-driver-python`. What that reads back is a shape, the sequence of accesses a
routine makes and how wide each one was, with no payload attached.

A shape is what this file replays. The bytes filling it are generated from a seed
here, so nothing belonging to the cartridge is needed to run the sweep and
nothing belonging to it is stored. What a shape is for is driving the part the
way the game drives it, which is the only driving that has ever had to work: a
part fed a sequence no cartridge ever sent is being asked a question nobody has
an answer for.

The shapes sit in a JSON file beside this one, with the digests of the cartridge
they were read from, so anybody holding the same cartridge can confirm they are
looking at the same thing.
"""

import json
import random
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import override

sys.path.insert(0, str(Path(__file__).resolve().parent))

from driven import Watched

ROOT = Path(__file__).resolve().parent

WRITE = "write"

READ = "read"

POLL = "poll"

STEPS = (WRITE, READ, POLL)

DEFAULT_SEED = 0x5D3A9C

WIDTHS = (1, 2)

Shapes = tuple[tuple["tuple[Step, ...]", int], ...]
"""Recorded shapes and how many sites used each, longest first."""


class Malformed(Exception):
    pass


class Step:
    """One access in a shape: what kind it was and how many bytes wide."""

    def __init__(self, what: str, width: int) -> None:
        self.what = what
        self.width = width

    @property
    def moves(self) -> bool:
        """Whether this access carries a payload rather than watching a register."""
        return self.what in (WRITE, READ)

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Step) and self.what == other.what and self.width == other.width

    @override
    def __hash__(self) -> int:
        return hash((self.what, self.width))

    @override
    def __repr__(self) -> str:
        return f"<Step {self.what}{self.width}>"


def parse(shape: str) -> "tuple[Step, ...]":
    """One recorded shape, as the steps it describes."""
    steps: list[Step] = []
    for word in shape.split():
        for what in STEPS:
            if not word.startswith(what):
                continue
            tail = word[len(what) :]
            if not tail.isdigit() or int(tail) not in WIDTHS:
                raise Malformed(f"{word} does not name a width of 1 or 2")
            steps.append(Step(what, int(tail)))
            break
        else:
            raise Malformed(f"{word} is not one of {', '.join(STEPS)}")
    return tuple(steps)


def recorded(part: str, where: Path | str | None = None) -> "Shapes":
    """Every shape read out of a cartridge for that part, longest first.

    Longest first because a long shape exercises more of the part than a short
    one, and a sweep that is cut short should have spent its budget on those.
    """
    path = Path(where) if where is not None else ROOT / f"{part}shapes.json"
    if not path.exists():
        return ()
    held = json.loads(path.read_text())
    assert isinstance(held, dict), f"{path} does not hold an object"
    if held.get("part") != part:
        raise Malformed(f"{path} holds shapes for {held.get('part')}, not for {part}")
    found = [(parse(one["shape"]), one["seen"]) for one in held["shapes"]]
    return tuple(sorted(found, key=lambda one: (-len(one[0]), -one[1])))


def interesting(shapes: "Shapes") -> "Shapes":
    """The shapes worth sweeping: the ones that both give and take.

    A shape that only writes proves nothing about what comes back, and a shape
    that only reads has nothing behind it that produced what comes back. Both are
    real things a cartridge does, and neither is a comparison.
    """
    return tuple(
        (steps, seen)
        for steps, seen in shapes
        if any(step.what == WRITE for step in steps) and any(step.what == READ for step in steps)
    )


def payload_for(steps: "Iterable[Step]", chance: random.Random) -> list[list[int]]:
    """Bytes to fill one shape's writes, generated rather than taken from anywhere."""
    return [
        [chance.randrange(0x100) for _ in range(step.width)] for step in steps if step.what == WRITE
    ]


def commanded(payload: Sequence[Sequence[int]], command: int) -> list[list[int]]:
    """The same payload with a real command in front of it.

    A shape says how a routine drives the part; it does not say which command it
    was driving. Filling the first byte at random sweeps mostly undefined
    behaviour, where the two are free to differ and where nothing has ever had to
    work. Putting a command the part actually has in that byte sweeps the part.
    """
    if not payload:
        return []
    return [[command, *payload[0][1:]], *(list(one) for one in payload[1:])]


def drive(
    chip: Watched, steps: "Iterable[Step]", payload: Iterable[Sequence[int]]
) -> list[list[int]]:
    """One shape through one part, returning everything it said back.

    Three calls, which is everything a console can do to one of these: give it a
    byte, take a byte, and look at the register that says whether it wants
    attention.
    """
    giving = iter(payload)
    said: list[list[int]] = []
    for step in steps:
        if step.what == WRITE:
            for byte in next(giving):
                chip.write(byte)
        elif step.what == READ:
            said.append([chip.read() for _ in range(step.width)])
        else:
            said.append([chip.read_status() for _ in range(step.width)])
    return said


def rolls(seed: int = DEFAULT_SEED) -> random.Random:
    """The generator the payloads come from, seeded so a run repeats."""
    return random.Random(seed)
