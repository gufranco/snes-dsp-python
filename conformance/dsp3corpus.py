"""Hold the DSP-3 to the chip's own reference.

Each case is a session rather than a command: the chip has no framing, so what a
byte means depends on what was sent before it, and a case that sends one command
in isolation proves nothing about the state it leaves behind. So a session sets
the grid up, walks it, converts a tile, decompresses a stream and searches for a
route, in that order, with the reads interleaved exactly where a driver would put
them.

The bytes filling those shapes are generated from a seed. They are arithmetic
rather than anything a cartridge holds, which is the whole reason this file can
ship: the shapes are the chip's interface and the payloads are ours.

The answers were computed by the reference, not by this model, which is what makes
agreement a cross-check rather than a restatement. Recording them needs the
reference driver; replaying them does not, so this runs anywhere.

One command is deliberately absent. The chip can hand back its own mask ROM word
by word, and a corpus that asked it to would be a copy of that ROM wearing a test
harness. Every other command is here.

The corpus was recorded from the reference implementation named in this file
and is replayed here. It is a recording rather than a live comparison: the
implementation it came from is a separate work in another language, and this
repository is Python throughout, so what it carries is the evidence rather
than the tooling that produced it. New evidence comes from a different and
stronger direction now, in `conformance/against_firmware.py`, which runs the
microcode the cartridge itself carries.

Usage:
    python3 conformance/dsp3corpus.py [--corpus PATH]
"""

import base64
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp3

USAGE = "usage: dsp3corpus.py [--corpus PATH] [--cases N]"

DEFAULT_CORPUS = Path(__file__).resolve().parent / "dsp3corpus.json"

WRITE = "w"

READ = "r"

CASES = 60

REPORT_LIMIT = 5

RAM_BYTES = 512

SET_WINDOW = 0x06

CELL_OF = 0x03

STEP_FROM = 0x07

COORDINATE = 0x02

CONVERT = 0x18

DECODE = 0x38

SET_ORIGIN = 0x3E

SEARCH = 0x1E

ABSORB_ONE = 0x0C

ABSORB_UNTIL_END = 0x10

ABSORB_TWO = 0x1C

TEST_MEMORY = 0x0F

EXERCISED = (
    SET_WINDOW,
    CELL_OF,
    STEP_FROM,
    COORDINATE,
    CONVERT,
    DECODE,
    SET_ORIGIN,
    SEARCH,
    ABSORB_ONE,
    ABSORB_UNTIL_END,
    ABSORB_TWO,
    TEST_MEMORY,
)
"""Every command the chip answers except the one that hands back its mask ROM."""

GRID_WIDTH = 0x14

GRID_HEIGHT = 0x0C

TILES = 2

DECODE_WORDS = 6

RING_CELLS = 36
"""Six turns of one, two and three steps, which is what the radius below asks for."""

SEED_LIMIT = 10_000

SEARCH_RADIUS = 0x0301

MOVES_TRIED = 20

DECODE_STEPS = 48

MORE_INPUT = 0x0040

END_OF_LIST = 0xFFFF


class Usage(Exception):
    pass


class Options:
    def __init__(self, corpus=None, cases=CASES):
        self.corpus = corpus
        self.cases = cases


def _word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


class Session:
    """A session being built, and the model chip that says where it has got to.

    The chip has no framing, so the shape of an exchange is not something a
    generator can know in advance: how many bytes a command wants next depends on
    a bit in the status register that the command before it set. A driver reads
    that bit, and so does this. What gets recorded is the byte stream that comes
    out, which the reference then answers on its own terms.
    """

    def __init__(self, seed):
        self.source = random.Random(seed)
        self.chip = dsp3.Dsp3()
        self.steps = []

    def write(self, *values):
        for value in values:
            self.steps.append((WRITE, value))
            self.chip.write(value)

    def word(self, value):
        self.write(*_word(value))

    def read(self, count=1):
        found = []
        for _ in range(count):
            self.steps.append((READ, 0))
            found.append(self.chip.read())
        return found

    def wants_input(self):
        return bool(self.chip.status & MORE_INPUT)

    def any(self, limit):
        return self.source.randrange(0, limit)


def _window(session):
    """How big the grid is, which every cell lookup afterwards wraps against."""
    session.write(SET_WINDOW)
    session.word((GRID_HEIGHT << 8) | GRID_WIDTH)


def _cell(session):
    """A coordinate turned into an index, which is the chip's simplest command."""
    session.write(CELL_OF)
    session.word((session.any(GRID_HEIGHT) << 8) | session.any(GRID_WIDTH))
    session.read(2)


def _step(session):
    """One move across the grid, including moves past the end of the move table.

    The move arrives as a single byte rather than as a word, because this is the
    one command the dispatcher accepts without also clearing the bit that makes
    the port byte wide.
    """
    session.write(STEP_FROM)
    session.write(session.any(MOVES_TRIED))
    session.word((session.any(GRID_HEIGHT) << 8) | session.any(GRID_WIDTH))
    session.read(4)


def _coordinate(session):
    """A pair handed in and handed straight back, one word at a time."""
    session.write(COORDINATE)
    for _ in range(3):
        session.word(session.any(0x8000))
    session.word(session.any(0x8000))
    session.word(session.any(0x8000))
    session.read(6)
    session.word(0)
    session.word(END_OF_LIST)


def _convert(session):
    """Tiles turned from rows of pixels into planes of one bit each."""
    session.write(CONVERT)
    session.word(TILES)
    for _ in range(TILES):
        for _ in range(4):
            session.word(session.any(0x10000))
        session.read(8)


def _absorbing(session):
    """The four commands that swallow a word and answer little or nothing."""
    session.write(ABSORB_ONE)
    session.word(session.any(0x10000))
    session.read(2)

    session.write(ABSORB_UNTIL_END)
    session.word(session.any(0x8000))
    session.word(END_OF_LIST)

    session.write(ABSORB_TWO)
    session.word(session.any(0x10000))
    session.word(session.any(0x10000))
    session.read(4)

    session.write(TEST_MEMORY)
    session.word(0)


def _decode(session):
    """A compressed stream, which the chip pulls apart a bit at a time.

    The stream is noise rather than anything that was ever compressed, and that
    is the point: a decoder handed noise walks its tables in ways a real stream
    never would, and the two implementations either agree about where it lands or
    they do not. Whether the next thing to do is feed it or read from it is the
    chip's own answer, which is the only way this could be driven at all.
    """
    session.write(DECODE)
    session.word(session.any(6) + 1)
    session.word(DECODE_WORDS)
    for _ in range(DECODE_STEPS):
        if session.wants_input():
            session.word(session.any(0x10000))
        else:
            session.read(2)


def _search(session):
    """The route search, which asks about a cell and is answered twice per cell.

    Every answer is a single byte, because naming a cell leaves the port byte
    wide, and the answers are what the caller would have read off its own map.
    """
    session.write(SET_ORIGIN)
    session.word((session.any(GRID_HEIGHT - 4) + 2 << 8) | (session.any(GRID_WIDTH - 4) + 2))
    session.read(2)

    session.write(SEARCH)
    session.word(SEARCH_RADIUS)
    for _ in range(RING_CELLS):
        session.read(2)
        session.write(session.any(0x80))
        session.write(session.any(0x40))
    session.read(2)


def _report(session):
    """The same rings again, this time with the chip answering what each cost."""
    session.word(SEARCH_RADIUS)
    for _ in range(RING_CELLS):
        session.read(2)
        session.read(1)
    session.read(2)


SESSION = (
    _window,
    _cell,
    _step,
    _coordinate,
    _convert,
    _absorbing,
    _search,
    _report,
    _decode,
)
"""The order the parts run in. The decompressor is last because it is the only
one that can refuse to finish, and a part that leaves the chip mid-command would
have every byte after it read as something else."""


def steps_for(seed):
    """The whole session for one seed, as writes and reads in order.

    A stream of noise can ask the decompressor for a symbol past the end of the
    table it built, and what happens there is a property of whichever memory the
    reference keeps after its own array rather than of the chip. Those sessions
    are not recorded, and the seed says so by refusing rather than by shortening.
    """
    session = Session(seed)
    for part in SESSION:
        part(session)
    return session.steps


def buildable(seed):
    """Whether a seed produces a session that stays inside the chip's own tables."""
    try:
        steps_for(seed)
    except dsp3.TableOverrun:
        return False
    return True


def buildable_seeds(wanted):
    """The first seeds that build, in order, however many were asked for."""
    found = []
    seed = 0
    while len(found) < wanted and seed < SEED_LIMIT:
        if buildable(seed):
            found.append(seed)
        seed += 1
    return found


def replay(steps):
    """The session through the model."""
    chip = dsp3.Dsp3()
    answers = []
    for kind, value in steps:
        if kind == WRITE:
            chip.write(value)
        else:
            answers.append(chip.read())
    return answers


def encode(answers):
    """Answers as one string, because a byte per line is a file nobody can read."""
    return base64.b64encode(bytes(answers)).decode("ascii")


def expected_of(case):
    """The bytes the reference gave for one case."""
    return list(base64.b64decode(case["expected"]))


def load(path=None):
    """The corpus, from where it was asked for or from the one that ships."""
    with Path(path or DEFAULT_CORPUS).open() as handle:
        return json.load(handle)


def disagreement(expected, actual):
    """The first byte the two answers differ on, or nothing."""
    for index in range(max(len(expected), len(actual))):
        theirs = expected[index] if index < len(expected) else None
        ours = actual[index] if index < len(actual) else None
        if theirs != ours:
            return index, theirs, ours
    return None


def options(argv):
    chosen = Options()
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item not in ("--corpus", "--cases"):
            raise Usage(USAGE)
        if not rest:
            raise Usage(USAGE)
        value = rest.pop(0)
        if item == "--corpus":
            chosen.corpus = value
        else:
            chosen.cases = int(value)
    return chosen


def run(argv):
    chosen = options(argv)
    corpus = load(chosen.corpus)
    failed = 0
    checked = 0
    for case in corpus["cases"]:
        expected = expected_of(case)
        checked += len(expected)
        if not buildable(case["seed"]):
            failed += 1
            if failed <= REPORT_LIMIT:
                print(f"FAIL seed {case['seed']}: this seed no longer builds a session")
            continue
        found = disagreement(expected, replay(steps_for(case["seed"])))
        if found is None:
            continue
        failed += 1
        index, theirs, ours = found
        if failed <= REPORT_LIMIT:
            print(f"FAIL seed {case['seed']} at byte {index}: reference {theirs}, model {ours}")

    print(f"{len(corpus['cases'])} sessions, {checked:,} bytes compared, {failed} disagreed")
    return 1 if failed else 0


def main(argv):
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
