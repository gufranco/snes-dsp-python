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


class Usage(Exception):
    pass


class Played:
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
        self.assumed = shapes.assumed(shapes.parse(shape))

    @property
    def unprompted(self) -> bool:
        for kind in self.kinds_in_order:
            if kind == shapes.WRITE:
                return False
            if kind == shapes.READ:
                return True
        return False

    @property
    def answered(self) -> bool:
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
    held = shapes.interesting(shapes.recorded(part))
    if not held:
        raise Usage(f"no cartridge exchanges are recorded for {part}")
    chance = shapes.rolls() if seed is None else shapes.rolls(seed)
    found: list[Played] = []
    for steps, _seen in held:
        payload = shapes.payload_for(steps, chance)
        said = shapes.drive(build(part), steps, payload)
        taken = [one.what for one in steps if one.what in (shapes.READ, shapes.POLL)]
        named = " ".join(one.token for one in steps)
        played = Played(named, said, taken)
        if not played.answered and not played.unprompted:
            spoke = speaking(build, part, steps, payload)
            if spoke is not None:
                played = Played(named, spoke.said, taken, spoke.command)
        found.append(played)
    return found


def report(found: "Sequence[Played]") -> list[str]:
    said = []
    for one in found[:SHOWN]:
        under = "" if one.command is None else f" (only under command {one.command:#04x})"
        said.append(f"    {one.shape}{under}: {[[hex(byte) for byte in run] for run in one.said]}")
    return said


def silent(found: "Iterable[Played]") -> "list[Played]":
    return [one for one in found if not one.answered and not one.unprompted]


def unprompted(found: "Iterable[Played]") -> "list[Played]":
    return [one for one in found if one.unprompted]


def lines_for(found: "Sequence[Played]", part: str) -> list[str]:
    quiet = silent(found)
    lines = [
        f"  {part}: {len(found)} exchanges a real cartridge makes, played at the part",
        f"  {sum(one.assumed for one in found)} of their"
        f" {sum(len(one.kinds_in_order) for one in found)} accesses rest on an assumed width,"
        " replayed as one byte",
    ]
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
