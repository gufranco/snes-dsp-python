"""Hold the DSP-1 to the chip's own reference.

Each case is a session rather than a command. Most of this chip's commands ask
questions of a camera that an earlier command set up, so a case that sends one in
isolation asks about a camera that was never placed, and every implementation
agrees about the answer to that because there is nothing to disagree about. So a
session places a camera, builds three attitude matrices, and then asks everything
else in turn.

The numbers filling those shapes are generated from a seed and are arithmetic
rather than anything a cartridge holds.

One command is deliberately absent. The chip can hand back its own mask ROM, and
a corpus that asked it to would be a copy of that ROM wearing a test harness. The
reference's version of that command is broken in two ways besides, reading past
its own output buffer and then past its own table, so there would be nothing to
compare against even if there were something to ship.

Usage:
    python3 conformance/dsp1corpus.py [--corpus PATH]
    python3 conformance/dsp1corpus.py --record --driver PATH
"""

import base64
import json
import random
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp1

USAGE = "usage: dsp1corpus.py [--corpus PATH] [--record --driver PATH] [--cases N]"

DEFAULT_CORPUS = Path(__file__).resolve().parent / "dsp1corpus.json"

WRITE = "w"

READ = "r"

CASES = 80

DRIVER_TIMEOUT = 120

REPORT_LIMIT = 5

RAM_BYTES = 512

SET_CAMERA = 0x02

RASTER_LINES = 6

QUESTIONS = (
    (0x00, 2, 2),
    (0x20, 2, 2),
    (0x10, 2, 4),
    (0x04, 2, 4),
    (0x08, 3, 4),
    (0x18, 4, 2),
    (0x38, 4, 2),
    (0x28, 3, 2),
    (0x0C, 3, 4),
    (0x1C, 6, 6),
    (0x06, 3, 6),
    (0x0E, 2, 4),
    (0x0D, 3, 6),
    (0x1D, 3, 6),
    (0x2D, 3, 6),
    (0x03, 3, 6),
    (0x13, 3, 6),
    (0x23, 3, 6),
    (0x0B, 3, 2),
    (0x1B, 3, 2),
    (0x2B, 3, 2),
    (0x14, 6, 6),
    (0x0F, 1, 2),
    (0x2F, 1, 2),
)
"""Every command except the two that set a matrix, the camera, and the mask ROM dump.

Each row is the command, how many words it takes, and how many bytes it answers.
"""

MATRIX_COMMANDS = (0x01, 0x11, 0x21)


class Usage(Exception):
    pass


class Options:
    def __init__(self, corpus=None, driver=None, record=False, cases=CASES):
        self.corpus = corpus
        self.driver = driver
        self.record = record
        self.cases = cases


def _word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


class Session:
    """A session being built, and the model chip that answers alongside it."""

    def __init__(self, seed):
        self.source = random.Random(seed)
        self.chip = dsp1.Dsp1(fill=0)
        self.steps = []

    def write(self, *values):
        for value in values:
            self.steps.append((WRITE, value))
            self.chip.write(value)

    def word(self, value):
        self.write(*_word(value))

    def read(self, count):
        for _ in range(count):
            self.steps.append((READ, 0))
            self.chip.read()

    def any(self, limit):
        return self.source.randrange(-limit, limit)


def _camera(session):
    """Where the camera is and where it looks, which everything else asks about.

    One session in three tilts the view past the angle the projection can carry,
    which is where the chip clips it and bends the horizon to compensate. That
    correction is five coefficients and a cubic, and nothing else reaches it.
    """
    steep = session.source.randrange(0, 3) == 0
    session.write(SET_CAMERA)
    session.word(session.any(0x2000))
    session.word(session.any(0x2000))
    session.word(session.source.randrange(0x0400, 0x4000))
    session.word(session.source.randrange(0x0100, 0x2000))
    session.word(session.source.randrange(0x0100, 0x2000))
    session.word(session.any(0x4000))
    session.word(_beyond_the_clip(session) if steep else session.any(0x2000))
    session.read(8)


def _beyond_the_clip(session):
    """A zenith angle past where the projection stops making sense."""
    if session.source.randrange(0, 2):
        return session.source.randrange(0x3900, 0x7FFF)
    return session.source.randrange(-0x7FFF, -0x3900)


def _matrices(session):
    """Three attitude matrices, which three pairs of commands then read back."""
    for command in MATRIX_COMMANDS:
        session.write(command)
        session.word(session.source.randrange(0x0400, 0x7FFF))
        session.word(session.any(0x4000))
        session.word(session.any(0x4000))
        session.word(session.any(0x4000))


def _questions(session):
    """Everything else, once each, with numbers in the ranges a flight model uses."""
    for command, words, answers in QUESTIONS:
        session.write(command)
        for _ in range(words):
            session.word(session.any(0x4000))
        session.read(answers)


def _raster(session):
    """The scanline matrices, which keep coming until something else is asked."""
    session.write(0x0A)
    session.word(session.source.randrange(0, 0xE0))
    for _ in range(RASTER_LINES):
        session.read(8)


def steps_for(seed):
    """The whole session for one seed, as writes and reads in order.

    An exponent can in principle fall far enough that the chip's own shift table
    is read before its start, and the model refuses rather than guessing there.
    No session built from a seed has been seen to reach it, so nothing here
    filters for it: a seed that did would fail loudly rather than quietly.
    """
    session = Session(seed)
    for part in (_camera, _matrices, _questions, _raster):
        part(session)
    return session.steps


def replay(steps):
    """The session through the model."""
    chip = dsp1.Dsp1(fill=0)
    answers = []
    for kind, value in steps:
        if kind == WRITE:
            chip.write(value)
        else:
            answers.append(chip.read())
    return answers


def ask(steps, driver):
    """The session through the reference, whose answers are the ones recorded."""
    payload = struct.pack("<I", 1) + bytes(RAM_BYTES) + struct.pack("<I", len(steps))
    for kind, value in steps:
        payload += bytes([ord(kind), value])
    done = subprocess.run(
        [driver, "dsp1"], input=payload, capture_output=True, check=False, timeout=DRIVER_TIMEOUT
    )
    if done.returncode:
        raise Usage(f"the reference driver failed: {done.stderr.decode(errors='replace').strip()}")
    return list(done.stdout[4:])


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


def record(driver, wanted):
    """Ask the reference for the answers to every session."""
    cases = [
        {"seed": seed, "expected": encode(ask(steps_for(seed), driver))} for seed in range(wanted)
    ]
    return {
        "comment": (
            "Sessions generated from seeds and answered by the chip's own reference. "
            "The command that hands back the chip's mask ROM is not among them."
        ),
        "reference": "snes9x dsp1.cpp, through conformance/ref",
        "cases": cases,
    }


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
        if item == "--record":
            chosen.record = True
            continue
        if item not in ("--corpus", "--driver", "--cases"):
            raise Usage(USAGE)
        if not rest:
            raise Usage(USAGE)
        value = rest.pop(0)
        if item == "--corpus":
            chosen.corpus = value
        elif item == "--driver":
            chosen.driver = value
        else:
            chosen.cases = int(value)
    return chosen


def run(argv):
    chosen = options(argv)
    if chosen.record:
        if not chosen.driver:
            print("recording needs --driver, which is where the reference was built")
            return 2
        found = record(chosen.driver, chosen.cases)
        Path(chosen.corpus or DEFAULT_CORPUS).write_text(json.dumps(found, indent=2) + "\n")
        print(f"recorded {len(found['cases'])} sessions")
        return 0

    corpus = load(chosen.corpus)
    failed = 0
    checked = 0
    for case in corpus["cases"]:
        expected = expected_of(case)
        checked += len(expected)
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
