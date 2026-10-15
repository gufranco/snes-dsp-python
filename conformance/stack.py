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

LEVELS = 4


class Measured:
    def __init__(self, part: str, deepest: int, moves: int, exchanges: int) -> None:
        self.part = part
        self.deepest = deepest
        self.moves = moves
        self.exchanges = exchanges

    def within(self, levels: int) -> bool:
        return self.deepest < levels

    @override
    def __repr__(self) -> str:
        return f"<Measured {self.part}, deepest slot {self.deepest}, {self.moves} moves>"


@runtime_checkable
class Counted(Protocol):
    registers: Any

    on_cycle: Any

    def step(self) -> None: ...


def _processor_of(chip: object) -> Counted:
    found = getattr(chip, "core", chip)
    assert isinstance(found, Counted), f"{type(found).__name__} cannot be stepped and watched"
    return found


class _Watching:
    def __init__(self, chip: object) -> None:
        self.core = chip
        self.deepest = 0
        self.moves = 0
        self._install()

    def _install(self) -> None:
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
