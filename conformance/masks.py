import hashlib
import json
import random
import sys
from collections.abc import Callable, Collection, Container, Iterable, Sequence
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from conformance.driven import Build, Driven
from snesdsp import chip

ROOT = Path(__file__).resolve().parent

FILE = "dsp1masks.json"

Divergence = dict[str, Any]

MASKS = ("dsp1", "dsp1b")

WORDS = 6

READS = 8

COMMANDS = tuple(range(0x100))

SEED = 0x1B

EDGES = (
    (0x0000,) * WORDS,
    (0x7FFF,) * WORDS,
    (0x8000,) * WORDS,
    (0x0001,) * WORDS,
    (0xFFFF,) * WORDS,
    (0x4000, 0x2000, 0x1000, 0x0800, 0x0400, 0x0200),
)

NOTE = (
    "Every input found where two masks of the DSP-1 answer differently. Each case"
    " names the command, the argument words that produced it, what each mask said,"
    " and where the two answers first part company. The images that answered are"
    " named by digest: a case pinned against one pair of images says nothing about"
    " another pair."
)


class Checked:
    def __init__(
        self,
        disagreements: Iterable[tuple[int, str, str, str]],
        converged: Iterable[int],
        checked: int,
    ) -> None:
        self.disagreements = tuple(disagreements)
        self.converged = tuple(converged)
        self.checked = checked

    @property
    def agrees(self) -> bool:
        return not self.disagreements and not self.converged

    @override
    def __repr__(self) -> str:
        return f"<Checked {self.checked} cases, {len(self.disagreements)} wrong>"


def argument_sets(seed: int = SEED, extra: int = 10) -> tuple[tuple[int, ...], ...]:
    chance = random.Random(seed)
    return (
        *EDGES,
        *(tuple(chance.randrange(0x10000) for _ in range(WORDS)) for _ in range(extra)),
    )


ARGUMENTS = argument_sets()


def _default_build(part: str) -> Driven:  # pragma: no cover
    return snesdsp.Chip(part)


def _default_available() -> set[str]:  # pragma: no cover
    return set(chip.available())


def _default_digest(part: str) -> str:  # pragma: no cover
    wanted = chip.SHARES_IMAGE.get(part, part)
    held = chip.available()
    if wanted not in held:
        return "no image on this machine"
    return hashlib.sha256(Path(held[wanted][1]).read_bytes()).hexdigest()


def answer(
    build: Build, part: str, command: int, arguments: Sequence[int], reads: int = READS
) -> bytes:
    chip = build(part)
    chip.write(command)
    for word in arguments:
        chip.write(word & 0xFF)
        chip.write((word >> 8) & 0xFF)
    return bytes(polled(chip) for _ in range(reads))


def polled(chip: Driven) -> int:
    waited = getattr(chip, "waited", None)
    if callable(waited):
        waited()
    return chip.read()


def first_difference(first: bytes, second: bytes) -> int:
    for at, (one, other) in enumerate(zip(first, second, strict=False)):
        if one != other:
            return at
    return min(len(first), len(second))


def sweep(
    build: Build = _default_build,
    commands: Sequence[int] = COMMANDS,
    arguments: Sequence[Sequence[int]] = ARGUMENTS,
    reads: int = READS,
) -> list[Divergence]:
    found = []
    for command in commands:
        for held in arguments:
            said = {mask: answer(build, mask, command, held, reads) for mask in MASKS}
            first, second = (said[mask] for mask in MASKS)
            if first == second:
                continue
            found.append(
                {
                    "command": command,
                    "arguments": list(held),
                    "answers": {mask: said[mask].hex() for mask in MASKS},
                    "firstDifferingByte": first_difference(first, second),
                }
            )
    return found


def check(
    divergences: Collection[Divergence], build: Build = _default_build, reads: int = READS
) -> "Checked":
    disagreements = []
    converged = []
    for one in divergences:
        said = {
            mask: answer(build, mask, one["command"], one["arguments"], reads).hex()
            for mask in MASKS
        }
        if said[MASKS[0]] == said[MASKS[1]]:
            converged.append(one["command"])
            continue
        for mask, wanted in one["answers"].items():
            if said[mask] != wanted:
                disagreements.append((one["command"], mask, wanted, said[mask]))
    return Checked(disagreements, converged, len(divergences))


def store(
    divergences: Sequence[Divergence],
    where: Path = ROOT,
    digest: Callable[[str], str] = _default_digest,
) -> Path:
    path = Path(where) / FILE
    path.write_text(
        json.dumps(
            {
                "note": NOTE,
                "compared": list(MASKS),
                "images": {mask: digest(mask) for mask in MASKS},
                "swept": {
                    "commands": len(COMMANDS),
                    "argumentSets": len(ARGUMENTS),
                    "words": WORDS,
                    "seed": SEED,
                },
                "divergences": divergences,
            },
            indent=2,
        )
        + "\n"
    )
    return path


def load(where: Path = ROOT) -> dict[str, Any] | None:
    path = Path(where) / FILE
    if not path.exists():
        return None
    held = json.loads(path.read_text())
    assert isinstance(held, dict), f"{path} does not hold an object"
    return held


def lines_for(found: "Checked") -> list[str]:
    said = [f"  {found.checked} pinned divergences re-derived"]
    for command, mask, wanted, got in found.disagreements:
        said.append(f"       ! {command:#04x} on {mask}: pinned {wanted}, answered {got}")
    for command in found.converged:
        said.append(
            f"       ! {command:#04x}: the two masks no longer differ here."
            " Either an image changed or one of them is not what it says"
        )
    return said


def lines_for_sweep(
    divergences: Collection[Divergence],
    commands: Sequence[int] = COMMANDS,
    arguments: Sequence[Sequence[int]] = ARGUMENTS,
) -> list[str]:
    said = [
        f"  swept {len(commands)} commands x {len(arguments)} argument sets"
        f" of {WORDS} words, {len(divergences)} differ"
    ]
    for one in divergences:
        said.append(f"      {one['command']:#04x} on {[hex(word) for word in one['arguments']]}")
        for mask, hexed in one["answers"].items():
            said.append(f"          {mask:6} {hexed}")
    return said


def main(
    argv: Sequence[str] = (),
    available: Callable[[], Container[str]] = _default_available,
    build: Build = _default_build,
    commands: Sequence[int] = COMMANDS,
    arguments: Sequence[Sequence[int]] = ARGUMENTS,
    digest: Callable[[str], str] = _default_digest,
    where: Path = ROOT,
    say: Callable[[str], object] = print,
) -> int:
    held = available()
    absent = [mask for mask in MASKS if mask not in held]
    if absent:
        say(
            f"  nothing to compare: this needs an image for each of {', '.join(MASKS)}"
            f" and has none for {', '.join(absent)}"
        )
        return 2

    if "--sweep" in argv:
        swept = sweep(build, commands, arguments)
        store(swept, where, digest)
        for line in lines_for_sweep(swept, commands, arguments):
            say(line)
        return 0

    pinned = load(where)
    if pinned is None:
        say("  nothing is pinned yet. Sweep for divergences with --sweep")
        return 1

    found = check(pinned["divergences"], build)
    for line in lines_for(found):
        say(line)
    return 0 if found.agrees else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
