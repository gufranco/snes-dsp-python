import json
import random
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import override

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance.driven import Watched

ROOT = Path(__file__).resolve().parent

WRITE = "write"

READ = "read"

POLL = "poll"

STEPS = (WRITE, READ, POLL)

DEFAULT_SEED = 0x5D3A9C

WIDTHS = (1, 2)

DRIVEN_LIKE = {"dsp1a": "dsp1", "dsp1b": "dsp1"}

Shapes = tuple[tuple["tuple[Step, ...]", int], ...]


class Malformed(Exception):
    pass


class Step:
    def __init__(self, what: str, width: int) -> None:
        self.what = what
        self.width = width

    @property
    def moves(self) -> bool:
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


def named(part: str) -> str:
    return DRIVEN_LIKE.get(part, part)


def recorded(part: str, where: Path | str | None = None) -> "Shapes":
    owner = named(part)
    path = Path(where) if where is not None else ROOT / f"{owner}shapes.json"
    if not path.exists():
        return ()
    held = json.loads(path.read_text())
    assert isinstance(held, dict), f"{path} does not hold an object"
    if held.get("part") != owner:
        raise Malformed(f"{path} holds shapes for {held.get('part')}, not for {owner}")
    found = [(parse(one["shape"]), one["seen"]) for one in held["shapes"]]
    return tuple(sorted(found, key=lambda one: (-len(one[0]), -one[1])))


def interesting(shapes: "Shapes") -> "Shapes":
    return tuple(
        (steps, seen)
        for steps, seen in shapes
        if any(step.what == WRITE for step in steps) and any(step.what == READ for step in steps)
    )


def payload_for(steps: "Iterable[Step]", chance: random.Random) -> list[list[int]]:
    return [
        [chance.randrange(0x100) for _ in range(step.width)] for step in steps if step.what == WRITE
    ]


def commanded(payload: Sequence[Sequence[int]], command: int) -> list[list[int]]:
    if not payload:
        return []
    return [[command, *payload[0][1:]], *(list(one) for one in payload[1:])]


def drive(
    part: Watched, steps: "Iterable[Step]", payload: Iterable[Sequence[int]]
) -> list[list[int]]:
    giving = iter(payload)
    said: list[list[int]] = []
    for step in steps:
        if step.what == WRITE:
            written(part, next(giving))
        elif step.what == READ:
            said.append(taken(part, step.width))
        else:
            waited = getattr(part, "waited", None)
            if callable(waited):
                waited()
            said.append([part.read_status() for _ in range(step.width)])
    return said


def written(part: Watched, held: Sequence[int]) -> None:
    word = getattr(part, "write_word", None)
    if len(held) == WIDTHS[1] and callable(word):
        word(held[0] | held[1] << 8)
        return
    for byte in held:
        part.write(byte)


def taken(part: Watched, width: int) -> list[int]:
    word = getattr(part, "read_word", None)
    if width == WIDTHS[1] and callable(word):
        found = int(word())
        return [found & 0xFF, found >> 8]
    return [part.read() for _ in range(width)]


def rolls(seed: int = DEFAULT_SEED) -> random.Random:
    return random.Random(seed)
