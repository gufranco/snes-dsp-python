"""Hold every model here to the part's own program, running on the part's own processor.

This is the strongest evidence in this repository, and the only kind that does not
rest on somebody's reading of what the chips do. The models are behavioural: each
command is written down as a function of its arguments, and they were settled
against another emulator's implementation of those same commands. Two people can
read a part the same way and be wrong together.

Running the microcode removes that. The `processor` submodule is a model of the
NEC uPD7725 settled instruction by instruction on its own, and the program it runs
is the one the cartridge actually carries. Feed both sides the same bytes and
either the answers match or one of them is wrong about the part.

No program is carried here. Images are supplied by whoever owns them, identified
by digest before use, and every check reports as skipped when none is present
rather than as passed.

Usage:
    python3 conformance/against_firmware.py [--sequences N]
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import chip as tiles
from snesdsp import dsp1 as projector
from snesdsp import dsp4 as road

ROOT = Path(__file__).resolve().parent.parent

PROCESSOR = ROOT / "processor"

SETTLE_LIMIT = 200000

DEFAULT_SEQUENCES = 60

REPORT_LIMIT = 5

SEED = 20260819

WHY_NOT_PROCESSOR = (
    "the processor submodule is not checked out: run `git submodule update --init`"
    " so the microcode has something to run on"
)

WHY_NOT_FIRMWARE = (
    "no firmware image was found: this runs the microcode the cartridge carries,"
    " which belongs to whoever wrote it, so a copy you already own goes in the"
    " firmware directory of this repository"
)

DUMPS_THE_MASK_ROM = 0x1F
"""One command in two of the microcodes hands back its own table rather than an answer."""

NOT_SWEPT_YET = ("dsp3",)
"""The DSP-3 is driven differently and is not swept here yet.

Where the others take a command and a fixed count of argument bytes, it is a state
machine clocked a word at a time with its own status register, and how many words
each command consumes depends on what the earlier ones left behind. Driving it
from a table of argument counts would produce disagreements that are the driver's
fault rather than the model's, which is worse than not running it."""


class Usage(Exception):
    pass


class Options:
    def __init__(self, sequences=DEFAULT_SEQUENCES):
        self.sequences = sequences


def rolls():
    return random.Random(SEED)


def _processor():
    if str(PROCESSOR) not in sys.path:
        sys.path.insert(0, str(PROCESSOR))
    try:
        from upd7725 import firmware, models, ports
    except ImportError:
        return None
    return firmware, models, ports


def images():
    """Every firmware image the processor's manifest recognises, wherever it sits."""
    found = _processor()
    if found is None:
        return {}
    firmware = found[0]
    return {identity.part: (identity, path) for identity, path in firmware.search()}


def why_not():
    if _processor() is None:
        return WHY_NOT_PROCESSOR
    if not images():
        return WHY_NOT_FIRMWARE
    return None


def silicon(part):
    """The part itself: its own processor, carrying its own program."""
    firmware, models, ports = _processor()
    identity, path = images()[part]
    chip = models.describe(identity.processor).build(fill=0)
    firmware.load(chip, path.read_bytes(), identity)
    console = ports.Console(chip)
    console.settle(SETTLE_LIMIT)
    return console


def from_silicon(part, stream, reads):
    """What the microcode answered, at both alignments the handshake allows.

    A part raises its attention bit once more after the last argument on some
    commands and not on others, and the data register still holds the byte the
    console just wrote. So the first byte offered is sometimes the console's own
    coming back, and both alignments are returned rather than one being assumed.
    """
    _, _, ports = _processor()
    console = silicon(part)
    console.send_bytes(stream, SETTLE_LIMIT)
    console.settle(SETTLE_LIMIT)
    first = console.read(ports.DATA)
    rest = console.take_bytes(reads, SETTLE_LIMIT)
    return bytes([first, *rest[:-1]]), bytes(rest)


def agreeing(answered, wanted):
    """Whether either alignment of what the part offered is the answer wanted."""
    return any(offered == wanted for offered in answered)


def _counted(chip, stream):
    for byte in stream:
        chip.write(byte)
    return bytes(chip.read() for _ in range(chip.out_count))


class Microcode:
    """One model here, the commands it answers, and how its answers are taken."""

    def __init__(self, part, commands, arguments, collect, build=None):
        self.part = part
        self.commands = tuple(sorted(commands))
        self.arguments = arguments
        self.collect = collect
        self.build = build or {}

    def streams(self, chance, count):
        for _ in range(count):
            command = chance.choice(self.commands)
            wanted = self.arguments[command]
            yield [command, *(chance.randrange(256) for _ in range(wanted))]

    def model(self):
        return snesdsp.Dsp(model=self.part, **self.build)


def _words(table, skip=()):
    return {command: words * 2 for command, words in table.items() if command not in skip}


MICROCODES = (
    Microcode(
        part="dsp1",
        commands=set(projector.WORDS_WANTED) - {DUMPS_THE_MASK_ROM},
        arguments=_words(projector.WORDS_WANTED, skip={DUMPS_THE_MASK_ROM}),
        collect=_counted,
        build={"fill": 0},
    ),
    Microcode(
        part="dsp2",
        commands=set(tiles.HEADER_INPUT),
        arguments=dict(tiles.HEADER_INPUT),
        collect=_counted,
        build={"fill": 0},
    ),
    Microcode(
        part="dsp4",
        commands=set(road.INPUT_COUNTS),
        arguments=dict(road.INPUT_COUNTS),
        collect=_counted,
        build={"fill": 0},
    ),
)


def compare(microcode, sequences):
    """Every stream through both, and the ones where they parted."""
    found = {"asked": 0, "agreed": 0, "differed": []}

    for stream in microcode.streams(rolls(), sequences):
        wanted = microcode.collect(microcode.model(), stream)
        if not wanted:
            continue
        found["asked"] += 1
        answered = from_silicon(microcode.part, stream, len(wanted))
        if agreeing(answered, wanted):
            found["agreed"] += 1
        else:
            found["differed"].append((stream[0], wanted.hex(), answered[1].hex()))

    return found


def lines_for(sequences):
    reason = why_not()
    if reason:
        return (f"  skipped: {reason}",)

    present = images()
    lines = [
        f"  {part}: not swept here, because it is clocked rather than commanded"
        for part in NOT_SWEPT_YET
    ]
    for microcode in MICROCODES:
        if microcode.part not in present:
            lines.append(f"  {microcode.part}: skipped, no image for it is here")
            continue
        found = compare(microcode, sequences)
        lines.append(
            f"  {microcode.part}: {found['agreed']} of {found['asked']} answers"
            f" match the microcode itself"
        )
        lines.extend(
            f"    command {command:#04x}: model {wanted}, part {offered}"
            for command, wanted, offered in found["differed"][:REPORT_LIMIT]
        )
    return tuple(lines)


def options(argv):
    chosen = Options()
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item != "--sequences":
            raise Usage(f"unknown option {item}")
        if not rest:
            raise Usage(f"{item} needs a value")
        chosen.sequences = int(rest.pop(0))
    return chosen


def run(argv):
    chosen = options(argv)
    print(*lines_for(chosen.sequences), sep="\n")
    return 0


def main(argv):
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
