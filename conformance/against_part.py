"""Hold every model to its own part, on a machine that has no parts.

Running a part's microcode needs an image of it, and an image belongs to whoever
made the part. Most machines will never have one. So each part is asked a fixed
set of questions once, on a machine that does, and what it answered is recorded
here beside the questions. Everywhere else the models are replayed against that
record.

This is the gate that makes the two backends one promise rather than two. The
microcode is used wherever an image is present and is right by construction. The
model is what ships, and this says exactly how far it is from the part: not as a
percentage and not as a claim, but byte by byte, with the command and the input
that produced each one.

Where a model does not yet answer what its part answered, the file says so. That
list is a gate rather than an excuse. Fixing one removes a line, breaking one
adds a line, and either way this check fails until somebody writes down what
changed. A number in a README drifts; this cannot.

A command that reads a part's own table back is checked in two halves. With the
table present the answer must be the part's, to the byte, compared as one digest
so that nothing of the table is written down here. Without it the answer must be
a refusal naming what is missing. Both are behaviour and both are checked, so
such a command is never reported as skipped and never left unexamined.

Three rules shape the questions.

One command per script, on a part that has just been started. Running a whole
session into one part reads as a fuller test and is a worse one: the first wrong
answer leaves the part somewhere the model is not, and every command after it
measures the drift rather than itself.

The inputs are uniform and generated from a seed. A script shaped around what a
command is believed to want is shaped by the belief, and the belief is the thing
under test.

And nothing recorded here belongs to anybody. The scripts are arithmetic, and the
answers are a handful of bytes each part produced from them.

Usage:
    python3 conformance/against_part.py [corpus.json]
"""

import base64
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import chip as tiles
from snesdsp import commands
from snesdsp import dsp1 as projector
from snesdsp import dsp3 as clocked
from snesdsp import dsp4 as road
from snesdsp.dsp1 import DataRomMissing

ROOT = Path(__file__).resolve().parent

DEFAULT_CORPUS = ROOT / "against_part.json"

WRITE = "w"

READ = "r"

REPORT_LIMIT = 6

DEFAULT_SEEDS = 5

BYTE_COMMAND = 1

WORD_COMMAND = 2
"""What the DSP-4 takes, where the other parts take a byte.

Writing one byte to it leaves the command half written, every parameter after it
is read as the other half, and the part never executes anything at all. A sweep
that did that asked fifteen commands, got no answer from any of them, and
reported agreement on nothing as though it were a clean result.
"""


DSP1_DUMPS = frozenset(projector.DUMP_OFFSET) | {
    alias for alias, real in projector.ALIASES.items() if real in projector.DUMP_OFFSET
}
"""The DSP-1 commands that hand back words of the part's own mask ROM."""

DSP3_DUMP = 0x1F
"""The DSP-3 command that does the same."""


class Unknown(Exception):
    pass


class Profile:
    """How one part is spoken to: its commands, and how much each one takes."""

    def __init__(
        self,
        part,
        commands,
        arguments,
        reads,
        command_width=BYTE_COMMAND,
        build=None,
        pinned=None,
        answers=None,
        dumps=(),
    ):
        self.part = part
        self.commands = tuple(sorted(commands))
        self.arguments = dict(arguments)
        self.reads = reads
        self.command_width = command_width
        self.build = build or {}
        self.pinned = dict(pinned or {})
        self.answers = dict(answers or {})
        self.dumps = frozenset(dumps)

    def argument_bytes(self, command):
        """How many bytes follow the command before the part will answer."""
        return self.arguments.get(command, 0)

    def pinned_bytes(self, command):
        """Argument bytes that must hold a particular value rather than a random one.

        A length byte is the case this exists for. Some commands read one and
        then take that many bytes of payload, so a random length asks for a
        payload nobody sent and the part spends the rest of the script waiting
        for bytes that never come. Pinning it small keeps the script a question
        about the command rather than about starvation.
        """
        return self.pinned.get(command, {})

    def reads_for(self, command):
        """How many answers to take, which some commands produce more of."""
        return self.answers.get(command, self.reads)

    def dumps_rom(self, command):
        """Whether this command hands back words of the part's own mask ROM.

        What such a command answers is content rather than behaviour, so it is
        never written down. Its answer is compared by digest instead, which
        settles whether two parts said the same thing and reconstructs nothing.
        """
        return command in self.dumps

    def __repr__(self):
        return f"<Profile {self.part}, {len(self.commands)} commands>"


DSP3_COMMANDS = (
    0x02,
    0x03,
    0x06,
    0x07,
    0x0C,
    0x0F,
    0x10,
    0x18,
    0x1C,
    0x1E,
    0x1F,
    0x38,
    0x3E,
)
"""Every command the DSP-3 has, the one that reads out its mask ROM included.

That one is asked like any other and compared like no other. What it hands back
is the part's own table, which belongs to whoever made the part, so the answer is
never written down: a digest of it is. A digest over the whole answer settles
whether two parts said the same thing and reconstructs nothing, which is the
whole point of using one.
"""

DSP3_ARGUMENTS = {
    0x02: 6,
    0x03: 2,
    0x06: 2,
    0x07: 1,
    0x0C: 2,
    0x0F: 2,
    0x10: 6,
    0x18: 2 + 8,
    0x1C: 2,
    0x1E: 2,
    DSP3_DUMP: 2,
    0x38: 4,
    0x3E: 2,
}
"""What each DSP-3 command takes, read off the part rather than off the model.

Found by feeding one word at a time and watching for the first answer that is
not an echo of what was just written. A part that is still waiting hands back the
last word it was given, so the point where that stops is the point where the
command had everything it needed.

The tile conversion is the one that is not simply words: a count arrives as a
word and the eight bytes of bitmap follow one at a time, which is what the part
asks for in its own status register while they arrive.

Command 0x1c never stops echoing, whatever it is fed. That is the whole of its
behaviour and it is why it is here with a nominal word.
"""

DSP2_RUN = 4
"""The length pinned into the DSP-2 commands that read one before their payload."""

DSP2_ARGUMENTS = {
    tiles.COMMAND_TILE: commands.TILE_BYTES,
    tiles.COMMAND_TRANSPARENT: 1,
    tiles.COMMAND_MERGE: 1 + 2 * DSP2_RUN,
    tiles.COMMAND_MIRROR: 1 + DSP2_RUN,
    tiles.COMMAND_MULTIPLY: commands.MULTIPLY_BYTES,
    tiles.COMMAND_SCALE: 2 + DSP2_RUN,
}
"""What each DSP-2 command takes in full, header and payload together.

The header alone is what the part reads before it first acts, which is not the
same thing: three of these read a length and then take that many bytes, so a
script that stops at the header asks a question the part is still waiting to
hear the end of.
"""

DSP2_PINNED = {
    tiles.COMMAND_MERGE: {0: DSP2_RUN},
    tiles.COMMAND_MIRROR: {0: DSP2_RUN},
    tiles.COMMAND_SCALE: {0: DSP2_RUN, 1: DSP2_RUN},
}

DSP2_ANSWERS = {
    tiles.COMMAND_TILE: commands.TILE_BYTES,
    tiles.COMMAND_MERGE: DSP2_RUN,
    tiles.COMMAND_MIRROR: DSP2_RUN,
    tiles.COMMAND_SCALE: DSP2_RUN,
}

DSP1_COMMANDS = tuple(sorted(set(projector.WORDS_WANTED) | set(projector.ALIASES)))


def _dsp1_arguments():
    """Bytes per DSP-1 command, since it counts words and the port counts bytes."""
    held = {command: words * 2 for command, words in projector.WORDS_WANTED.items()}
    for alias, real in projector.ALIASES.items():
        held.setdefault(alias, held.get(real, 0))
    return held


PROFILES = {
    "dsp1": Profile(
        part="dsp1",
        commands=DSP1_COMMANDS,
        arguments=_dsp1_arguments(),
        reads=6,
        build={"fill": 0},
        dumps=DSP1_DUMPS,
    ),
    "dsp1b": Profile(
        part="dsp1b",
        commands=DSP1_COMMANDS,
        arguments=_dsp1_arguments(),
        reads=6,
        build={"fill": 0},
        dumps=DSP1_DUMPS,
    ),
    "dsp2": Profile(
        part="dsp2",
        commands=tuple(sorted(tiles.HEADER_INPUT)),
        arguments=DSP2_ARGUMENTS,
        reads=4,
        build={"fill": 0},
        pinned=DSP2_PINNED,
        answers=DSP2_ANSWERS,
    ),
    "dsp3": Profile(
        part="dsp3",
        commands=DSP3_COMMANDS,
        arguments=DSP3_ARGUMENTS,
        reads=6,
        dumps={DSP3_DUMP},
    ),
    "dsp4": Profile(
        part="dsp4",
        commands=tuple(sorted(road.INPUT_COUNTS)),
        arguments=dict(road.INPUT_COUNTS),
        reads=6,
        command_width=WORD_COMMAND,
        build={"fill": 0},
    ),
}


def profile_for(part):
    """How to speak to that part, or a refusal naming the ones that are known."""
    found = PROFILES.get(part)
    if found is None:
        raise Unknown(f"{part} is not a part here; there are {', '.join(sorted(PROFILES))}")
    return found


def script_for(part, command, seed):
    """One command as a plain list of steps, decided by the part, command and seed."""
    profile = profile_for(part)
    chance = random.Random(seed)
    steps = [[WRITE, command & 0xFF]]
    if profile.command_width == WORD_COMMAND:
        steps.append([WRITE, command >> 8 & 0xFF])
    pinned = profile.pinned_bytes(command)
    steps.extend(
        [WRITE, pinned.get(at, chance.randrange(0x100))]
        for at in range(profile.argument_bytes(command))
    )
    steps.extend([READ, 0] for _ in range(profile.reads_for(command)))
    return steps


def answers_of(steps, chip):
    """What one part says when a script is played at it."""
    said = []
    for kind, value in steps:
        if kind == WRITE:
            chip.write(value)
        else:
            said.append(chip.read())
    return said


def digest_of(answers):
    """One digest over a whole answer, which settles it and reconstructs nothing.

    Over the whole answer rather than over each word. A digest per word would let
    somebody walk the table back out of the file a value at a time, which is the
    thing this arrangement exists to avoid; one digest over the lot proves two
    parts said the same thing and proves nothing else.
    """
    return hashlib.sha256(bytes(answers)).hexdigest()


def table_of(part, held=None):
    """The part's own table, from an image of it, or nothing when none is here.

    `held` is the catalogue of images, passed in so the reading can be exercised
    on a machine that has none: what it needs is a file and a shape, not anybody's
    microcode in particular.
    """
    from snesdsp import silicon

    if held is None:
        held = silicon.available()
    wanted = silicon.SHARES_IMAGE.get(part, part)
    if wanted not in held:
        return None
    identity, path = held[wanted]
    image = Path(path).read_bytes()[identity.program_words * 3 :]
    return [image[at] << 8 | image[at + 1] for at in range(0, len(image), 2)]


def _model(part, command=None, table=None):
    profile = profile_for(part)
    options = dict(profile.build)
    if command is not None and profile.dumps_rom(command):
        options["data_rom"] = table_of(part) if table is None else table
    return snesdsp.Dsp(model=part, backend=snesdsp.MODELLED, **options)


def _silicon(part):  # pragma: no cover
    """A real part, which needs an image and so cannot be built on a bare runner."""
    return snesdsp.Dsp(model=part, backend=snesdsp.SILICON, **profile_for(part).build)


def replay(part, steps, command=None, table=None):
    """One script through the model of that part."""
    return answers_of(steps, _model(part, command, table))


def record(part, seeds, commands=None, build=_silicon):
    """Every command of one part against every seed, one fresh part per script."""
    profile = profile_for(part)
    found = []
    for command in commands if commands is not None else profile.commands:
        for seed in seeds:
            steps = script_for(part, command, seed)
            said = answers_of(steps, build(part))
            case = {"part": part, "command": command, "seed": seed, "script": steps}
            if profile.dumps_rom(command):
                case["expectedDigest"] = digest_of(said)
            else:
                case["expected"] = base64.b64encode(bytes(said)).decode("ascii")
            found.append(case)
    return found


def load(path=None):
    """The corpus, from where it was asked for or from the one that ships."""
    with Path(path or DEFAULT_CORPUS).open() as handle:
        return json.load(handle)


def expected_of(case):
    """The bytes the part gave for one case, or nothing when only a digest was kept."""
    held = case.get("expected")
    return list(base64.b64decode(held)) if held is not None else []


def by_digest(case):
    """Whether this case was recorded as a digest rather than as its bytes."""
    return "expectedDigest" in case


REFUSALS = (DataRomMissing, clocked.DataRomMissing)
"""The refusal each model raises when asked for a table it has not got.

One per model rather than one shared, because each is its own package-level
error. A check that knew only one of them would read the other as a crash.
"""


def refuses(case, table=None):
    """Whether the model refuses the case, which is right when it has no table."""
    try:
        replay(case["part"], case["script"], case["command"], table)
    except REFUSALS:
        return True
    return False


def differences(case, table=None):
    """Every index where the model does not say what the part said.

    A case recorded as a digest is a command that reads a table out. With a table
    the model must produce the part's own bytes, and without one it must refuse.
    Both are checked; neither is skipped.
    """
    if by_digest(case):
        held = table_of(case["part"]) if table is None else table
        if held is None:
            return () if refuses(case) else (0,)
        got = replay(case["part"], case["script"], case["command"], held)
        return () if digest_of(got) == case["expectedDigest"] else (0,)

    wanted = expected_of(case)
    got = replay(case["part"], case["script"], case["command"])
    return tuple(
        index
        for index in range(max(len(wanted), len(got)))
        if (wanted[index] if index < len(wanted) else None)
        != (got[index] if index < len(got) else None)
    )


def names(case):
    """What identifies one case: its part, its command and its seed.

    All three, because a seed is reused across commands and a command number is
    reused across parts. Keying on fewer of them merges cases and hides the ones
    that were merged away.
    """
    return case["part"], case["command"], case["seed"]


def measured(held):
    """Where the models and the parts part company right now."""
    found = {}
    for case in held["cases"]:
        where = differences(case)
        if where:
            found[names(case)] = where
    return found


def recorded(held):
    """Where the file says they part company."""
    return {names(one): tuple(one["indices"]) for one in held.get("knownGaps", ())}


def drifted(held):
    """Cases whose disagreement is not the one that was written down."""
    now, before = measured(held), recorded(held)
    return {
        which: (before.get(which, ()), now.get(which, ()))
        for which in sorted(set(now) | set(before))
        if now.get(which, ()) != before.get(which, ())
    }


def per_part(held):
    """How many bytes were compared and how many differ, one part at a time."""
    now = measured(held)
    found = {}
    for case in held["cases"]:
        total, off = found.get(case["part"], (0, 0))
        found[case["part"]] = (
            total + (1 if by_digest(case) else len(expected_of(case))),
            off + len(now.get(names(case), ())),
        )
    return found


def refusals(held):
    """Every case checked as a refusal rather than as bytes, by part."""
    found = {}
    for case in held["cases"]:
        if by_digest(case) and table_of(case["part"]) is None:
            found[case["part"]] = found.get(case["part"], 0) + 1
    return found


def lines_for(held):
    """The lines a person reads."""
    off = drifted(held)
    lines = []
    for part, (total, differing) in sorted(per_part(held).items()):
        share = 100 * (total - differing) / total if total else 100
        lines.append(
            f"  {part}: {total - differing} of {total} bytes match the part ({share:.0f}%)"
        )

    for part, count in sorted(refusals(held).items()):
        lines.append(
            f"  {part}: {count} of those read a table that is not here, so what is"
            " checked is that the model refuses rather than answers"
        )

    if not off:
        lines.append("  nothing has drifted from what was written down")
        return lines

    lines.append(f"  {len(off)} scripts no longer match what was written down:")
    for (part, command, seed), (before, now) in list(off.items())[:REPORT_LIMIT]:
        lines.append(
            f"    {part} command {command:#04x} seed {seed}:"
            f" was {before or 'clean'}, now {now or 'clean'}"
        )
    return lines


def main(argv):
    held = load(Path(argv[0]) if argv else None)
    for line in lines_for(held):
        print(line)
    return 1 if drifted(held) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
