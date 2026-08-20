"""Where the three masks of the DSP-1 answer differently, found rather than asserted.

Nintendo shipped the same program on three parts. The DSP-1A was a die shrink and
carries the DSP-1's image byte for byte, so it cannot answer differently and this
does not look. The DSP-1B is a later mask that corrected an arithmetic fault, and
that is a claim with a consequence: somewhere there is an input where the two give
different answers, and if there is not, one of the two images is not what it says.

Running both programs makes the values right without knowing where that is. It
does not make the claim checkable. So this sweeps every command byte across a
fixed set of argument words, keeps every case where the two masks part company,
and pins them. A later run re-derives exactly those cases. The correction stays
demonstrated rather than described, and a case that quietly becomes agreement is
reported as loudly as one that changes value: two images that agree everywhere are
one image under two names.

What the sweep found the first time it ran, on 256 commands and 16 argument sets:
one command, reached through six of its encodings, where the third word out
differs. Nothing else in that space differs at all, which is what a corrected
fault should look like rather than a different program.

The arguments are written here rather than generated, so the sweep is the same on
every machine and a case found on one can be reproduced on another.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import silicon

ROOT = Path(__file__).resolve().parent

FILE = "dsp1masks.json"

MASKS = ("dsp1", "dsp1b")
"""The two masks that can differ. The DSP-1A shares the DSP-1's image, so it cannot."""

WORDS = 6
"""How many argument words each set carries, being the most any DSP-1 command takes."""

READS = 8
"""How many bytes are read back, being enough for the longest answer plus the idle byte."""

COMMANDS = tuple(range(0x100))
"""Every command byte, including the ones no game sends and the part does not define.

Undefined bytes are swept for the same reason the defined ones are. A mask
correction lands where the program was wrong, and nothing says the program was
only wrong where somebody documented it.
"""

SEED = 0x1B
"""The seed the random argument sets come from, fixed so the sweep repeats."""

EDGES = (
    (0x0000,) * WORDS,
    (0x7FFF,) * WORDS,
    (0x8000,) * WORDS,
    (0x0001,) * WORDS,
    (0xFFFF,) * WORDS,
    (0x4000, 0x2000, 0x1000, 0x0800, 0x0400, 0x0200),
)
"""The corners of a sixteen bit fixed-point word: zero, both extremes, one, and a ramp."""

NOTE = (
    "Every input found where two masks of the DSP-1 answer differently. Each case"
    " names the command, the argument words that produced it, what each mask said,"
    " and where the two answers first part company. The images that answered are"
    " named by digest: a case pinned against one pair of images says nothing about"
    " another pair."
)


class Checked:
    """What the pinned cases and the parts on this machine had to say to each other."""

    def __init__(self, disagreements, converged, checked):
        self.disagreements = tuple(disagreements)
        self.converged = tuple(converged)
        self.checked = checked

    @property
    def agrees(self):
        """Whether every pinned divergence is still there, and still says what it said."""
        return not self.disagreements and not self.converged

    def __repr__(self):
        return f"<Checked {self.checked} cases, {len(self.disagreements)} wrong>"


def argument_sets(seed=SEED, extra=10):
    """The corners first, then a fixed number of random sets from the seed."""
    chance = random.Random(seed)
    return (
        *EDGES,
        *(tuple(chance.randrange(0x10000) for _ in range(WORDS)) for _ in range(extra)),
    )


ARGUMENTS = argument_sets()


def _default_build(part):  # pragma: no cover
    return snesdsp.Dsp(part)


def _default_available():  # pragma: no cover
    return set(silicon.available())


def _default_digest(part):  # pragma: no cover
    wanted = silicon.SHARES_IMAGE.get(part, part)
    held = silicon.available()
    if wanted not in held:
        return "no image on this machine"
    return hashlib.sha256(Path(held[wanted][1]).read_bytes()).hexdigest()


def answer(build, part, command, arguments, reads=READS):
    """What one mask says to one command, driven the way a console drives it."""
    chip = build(part)
    chip.write(command)
    for word in arguments:
        chip.write(word & 0xFF)
        chip.write((word >> 8) & 0xFF)
    return bytes(chip.read() for _ in range(reads))


def _first_difference(first, second):
    for at, (one, other) in enumerate(zip(first, second, strict=False)):
        if one != other:
            return at
    return min(len(first), len(second))


def sweep(build=_default_build, commands=COMMANDS, arguments=ARGUMENTS, reads=READS):
    """Every command and argument set where the two masks part company."""
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
                    "firstDifferingByte": _first_difference(first, second),
                }
            )
    return found


def check(divergences, build=_default_build, reads=READS):
    """Every pinned case re-derived, reporting anything that moved."""
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


def store(divergences, where=ROOT, digest=_default_digest):
    """What a sweep found, written with the images that produced it."""
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


def load(where=ROOT):
    """What was pinned, or nothing when no sweep has been kept."""
    path = Path(where) / FILE
    if not path.exists():
        return None
    return json.loads(path.read_text())


def lines_for(found):
    """What a comparison found, in the order somebody reading it wants it."""
    said = [f"  {found.checked} pinned divergences re-derived"]
    for command, mask, wanted, got in found.disagreements:
        said.append(f"       ! {command:#04x} on {mask}: pinned {wanted}, answered {got}")
    for command in found.converged:
        said.append(
            f"       ! {command:#04x}: the two masks no longer differ here."
            " Either an image changed or one of them is not what it says"
        )
    return said


def lines_for_sweep(divergences, commands=COMMANDS, arguments=ARGUMENTS):
    """What a sweep turned up, one case at a time.

    The counts come from what was actually swept rather than from the defaults, so
    a narrowed run cannot report the breadth of a full one.
    """
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
    argv=(),
    available=_default_available,
    build=_default_build,
    commands=COMMANDS,
    arguments=ARGUMENTS,
    digest=_default_digest,
    where=ROOT,
    say=print,
):
    """Sweep for divergences between the masks, or check the ones already pinned."""
    held = available()
    absent = [mask for mask in MASKS if mask not in held]
    if absent:
        say(
            f"  nothing to compare: this needs an image for each of {', '.join(MASKS)}"
            f" and has none for {', '.join(absent)}"
        )
        return 2

    if "--sweep" in argv:
        found = sweep(build, commands, arguments)
        store(found, where, digest)
        for line in lines_for_sweep(found, commands, arguments):
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
