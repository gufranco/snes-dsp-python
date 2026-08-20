"""Hold every model here to the part's own program, running on the part's own processor.

This is the strongest evidence in this repository, and the only kind that does not
rest on somebody's reading of what the chips do. The models are behavioural: each
command is written down as a function of its arguments, and they were settled
against another implementation of those same commands. Two people can read a part
the same way and be wrong together.

Running the microcode removes that. The `processor` submodule is a model of the
NEC uPD7725 settled instruction by instruction on its own, and the program it runs
is the one the cartridge actually carries.

The console side had to be read out of the cartridges to get this far, and it is
not what a reader would guess. Two things matter and both came from the games'
own driver routines:

**The console does not wait between writes.** Pilotwings writes the command and
then all three arguments back to back, with no status poll between them, and
Dungeon Master writes five bytes and reads four without polling at all. The part
keeps up because it runs several instructions per console access. A driver that
waits for the part's attention bit before every byte, which is the obvious thing
to write, makes the part assemble its arguments into different words entirely.

**How wide a transfer is comes from the console, not the part.** Pilotwings sets
its accumulator to eight bits for the command and sixteen for each argument, so
one instruction moves one byte or two. Dungeon Master keeps eight bits throughout.
That is why the two parts need different drivers for the same silicon.

No program is carried here. Images are supplied by whoever owns them, identified
by digest before use, and every check reports as skipped when none is present.

Usage:
    python3 conformance/against_firmware.py [--sequences N]
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import shapes

import snesdsp
from snesdsp import chip as tiles
from snesdsp import dsp1 as projector
from snesdsp import dsp4 as road

ROOT = Path(__file__).resolve().parent.parent

PROCESSOR = ROOT / "processor"

SETTLE_LIMIT = 400000

BOOT_STEPS = 20000

GAP = 32
"""Instructions the part runs between one console access and the next.

Measured rather than chosen. Below eight the part cannot keep up and its answers
change with the number; from eight upwards every value gives the same answer, so
the model of the console is no longer racing it. Real hardware clocks the part at
around twice the bus, which is comfortably inside that range.
"""

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
"""One command hands back the part's own table rather than an answer.

The model refuses it unless a table is handed to it, because a table that is
absent is not a table of zeroes. Here the table comes out of the image its owner
supplied, which is the only place one exists, so the command is swept like any
other rather than skipped.
"""

DUMPED_WORDS = 1024
"""How much of the table that command hands back."""

NOT_SWEPT_YET = ()
"""Parts with no sweep here yet."""

DSP3_COMMANDS = (0x02, 0x03, 0x06, 0x07, 0x0C, 0x0F, 0x10, 0x18, 0x1C, 0x1E, 0x38, 0x3E)
"""Every command the DSP-3 has, except the one that hands back its mask ROM.

That one is left out because answering it needs the mask ROM, which is content
rather than behaviour and is not shipped here. The part has it and the model does
not, so a comparison would be measuring the absence of a file.
"""


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
    return {identity.part: (identity, path) for identity, path in found[0].search()}


def why_not():
    if _processor() is None:
        return WHY_NOT_PROCESSOR
    if not images():
        return WHY_NOT_FIRMWARE
    return None


class Console:
    """The console's side of the port, paced the way a cartridge paces it."""

    def __init__(self, part):
        firmware, models, ports = _processor()
        identity, path = images()[part]
        self.ports = ports
        self.chip = models.describe(identity.processor).build(fill=0)
        firmware.load(self.chip, path.read_bytes(), identity)
        self.console = ports.Console(self.chip)
        self.step(BOOT_STEPS)

    def step(self, count=GAP):
        for _ in range(count):
            self.chip.step()

    def settle(self):
        for _ in range(SETTLE_LIMIT):
            if self.chip.registers.sr.rqm:
                return True
            self.chip.step()
        return False

    def put(self, value, width):
        self.console.write(self.ports.DATA, value & 0xFF)
        self.step()
        if width == 2:
            self.console.write(self.ports.DATA, value >> 8 & 0xFF)
            self.step()

    def get(self, width):
        low = self.console.read(self.ports.DATA)
        self.step()
        if width == 1:
            return low
        high = self.console.read(self.ports.DATA)
        self.step()
        return low | high << 8


def _with_aliases(wanted, aliases):
    """Argument counts for every command byte, including the ones that alias another.

    A third of this part's command space is aliases: bytes that do the same thing
    as another byte. The model says which is which, and sweeping them against the
    microcode is the only way to know whether it is right about that rather than
    merely consistent with itself.
    """
    found = {command: words * 2 for command, words in wanted.items()}
    for alias, canonical in aliases.items():
        found[alias] = found[canonical]
    return found


def table_of(part):
    """The constant table inside an image, as the words the part reads from it."""
    found = _processor()
    if found is None:
        return None
    identity, path = images()[part]
    image = path.read_bytes()
    held = image[identity.program_words * 3 :]
    return [held[at] << 8 | held[at + 1] for at in range(0, len(held), 2)]


class Clocked:
    """A part driven by its status register rather than by a count of answers.

    The DSP-3 does not say how many words it will hand back. It is advanced a
    word at a time and the console watches a register to know where it is, so a
    sweep that writes a command and reads a fixed number of words is describing
    something else.

    What it is driven with here comes from the cartridge: the shapes a real game
    uses, with a command the part actually has in the first byte. Everything
    compared is compared at every step, the status register included, because on
    this part the register is half of what the console is told.
    """

    def __init__(self, part, commands, build=None):
        self.part = part
        self.commands = tuple(sorted(commands))
        self.build = build or {}

    def streams(self, chance, count):
        held = shapes.interesting(shapes.recorded(self.part))
        for index in range(count):
            steps, _ = held[index % len(held)]
            command = self.commands[index % len(self.commands)]
            yield command, shapes.commanded(shapes.payload_for(steps, chance), command), steps

    def _through(self, chip, steps, payload):
        said = shapes.drive(chip, steps, payload)
        return [*said, [chip.read_status()]]

    def from_model(self, command, payload, steps):
        chip = snesdsp.Dsp(model=self.part, backend=snesdsp.MODELLED, **self.build)
        return self._through(chip, steps, payload)

    def from_silicon(self, command, payload, steps):
        chip = snesdsp.Dsp(model=self.part, backend=snesdsp.SILICON, **self.build)
        return self._through(chip, steps, payload)


class Microcode:
    """One model here, the commands it answers, and how its console drives it."""

    def __init__(
        self,
        part,
        commands,
        arguments,
        argument_width,
        answer_width,
        polls,
        build=None,
        command_width=1,
    ):
        self.part = part
        self.commands = tuple(sorted(commands))
        self.arguments = arguments
        self.argument_width = argument_width
        self.answer_width = answer_width
        self.polls = polls
        self.build = build or {}
        self.command_width = command_width

    def streams(self, chance, count):
        limit = 1 << (8 * self.argument_width)
        for _ in range(count):
            command = chance.choice(self.commands)
            wanted = self.arguments[command] // self.argument_width
            yield command, [chance.randrange(limit) for _ in range(wanted)]

    def from_model(self, command, arguments):
        options = dict(self.build)
        if projector.ALIASES.get(command, command) in projector.DUMP_OFFSET:
            options["data_rom"] = table_of(self.part)
        # The model by name, never the default. Since the microcode became the
        # default wherever an image is present, taking it here would compare the
        # silicon against itself and report perfect agreement.
        chip = snesdsp.Dsp(model=self.part, backend=snesdsp.MODELLED, **options)
        chip.write(command & 0xFF)
        if self.command_width == 2:
            chip.write(command >> 8 & 0xFF)
        for value in arguments:
            chip.write(value & 0xFF)
            if self.argument_width == 2:
                chip.write(value >> 8 & 0xFF)
        answers = chip.out_count // self.answer_width
        return [
            chip.read() if self.answer_width == 1 else chip.read() | chip.read() << 8
            for _ in range(answers)
        ]

    def from_silicon(self, command, arguments, answers):
        console = Console(self.part)
        console.put(command, self.command_width)
        for value in arguments:
            console.put(value, self.argument_width)
        found = []
        for _ in range(answers):
            if self.polls:
                console.settle()
            found.append(console.get(self.answer_width))
        return found


MICROCODES = (
    Clocked(part="dsp3", commands=DSP3_COMMANDS),
    Microcode(
        part="dsp1",
        commands=set(projector.WORDS_WANTED) | set(projector.ALIASES),
        arguments=_with_aliases(projector.WORDS_WANTED, projector.ALIASES),
        argument_width=2,
        answer_width=2,
        polls=True,
        build={"fill": 0},
    ),
    Microcode(
        part="dsp1b",
        commands=set(projector.WORDS_WANTED) | set(projector.ALIASES),
        arguments=_with_aliases(projector.WORDS_WANTED, projector.ALIASES),
        argument_width=2,
        answer_width=2,
        polls=True,
        build={"fill": 0},
    ),
    Microcode(
        part="dsp2",
        commands=set(tiles.HEADER_INPUT),
        arguments=dict(tiles.HEADER_INPUT),
        argument_width=1,
        answer_width=1,
        polls=False,
        build={"fill": 0},
    ),
    Microcode(
        part="dsp4",
        commands=set(road.INPUT_COUNTS),
        arguments=dict(road.INPUT_COUNTS),
        argument_width=1,
        answer_width=1,
        polls=False,
        build={"fill": 0},
        # This part takes its command as a word rather than a byte. Writing one
        # byte leaves the command half-written, so every parameter after it is
        # read as the other half and nothing is ever executed: the sweep asked
        # fifteen commands and got no answer from any of them, and read that as
        # agreement on nothing rather than as a question never asked.
        command_width=2,
    ),
)


def _shown(answers):
    """One side of a disagreement, as hex, whether it is words or runs of bytes."""
    if answers and isinstance(answers[0], list):
        return [[hex(byte) for byte in run] for run in answers]
    return [hex(value) for value in answers]


def compare(microcode, sequences):
    """Every stream through both, and the ones where they parted."""
    found = {"asked": 0, "agreed": 0, "differed": []}

    for stream in microcode.streams(rolls(), sequences):
        command, arguments, *rest = stream
        wanted = microcode.from_model(command, arguments, *rest)
        if not wanted:
            continue
        found["asked"] += 1
        got = microcode.from_silicon(command, arguments, *(rest or [len(wanted)]))
        if got == wanted:
            found["agreed"] += 1
        else:
            found["differed"].append((command, arguments, wanted, got))

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
            f"    command {command:#04x}: model {_shown(wanted)}, part {_shown(got)}"
            for command, _, wanted, got in found["differed"][:REPORT_LIMIT]
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
