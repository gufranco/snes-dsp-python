"""Hold the DSP-4's track projection to the chip's own reference.

Each case is a road, drawn by one of the three projections in turn: a viewpoint
and a stretch of track, then several more stretches fed in as the projection asks
for them, then the marker that says the track has ended. The numbers are generated from a seed but shaped like a road
rather than like noise, because a projection given nonsense produces nonsense and
the two would agree about it without either being right.

The answers in the corpus were computed by the reference, not by this model,
which is what makes agreement a cross-check rather than a restatement. Recording
them needs the reference driver; replaying them does not, so this runs anywhere.

One case in a hundred is thrown away before it is recorded, and the reason is
worth stating. The chip's output buffer is five hundred and twelve bytes, and a
stretch that would produce more than that cannot be expressed through the
interface at all: there is nowhere for the bytes to go. The reference does not
notice. It keeps writing past the end of its own buffer and over the variables
that follow it, one of which is the loop counter, so the loop stops at a length
decided by the layout of a C struct. That is a property of that program rather
than of the chip, so cases that reach it are not recorded. Every case that is
recorded stays inside the buffer the hardware has.

Usage:
    python3 conformance/dsp4corpus.py [--corpus PATH]
    python3 conformance/dsp4corpus.py --record --driver PATH
"""

import json
import random
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp4

USAGE = "usage: dsp4corpus.py [--corpus PATH] [--record --driver PATH] [--cases N]"

DEFAULT_CORPUS = Path(__file__).resolve().parent / "dsp4corpus.json"

WRITE = "w"

READ = "r"

BUFFER_BYTES = 512

CASES = 80

STRETCHES = 4

DRIVER_TIMEOUT = 120

REPORT_LIMIT = 5

PROJECT_TRACK = 0x0001

PROJECT_TURNOFF = 0x0007

PROJECT_SHARED = 0x000D

PROJECTIONS = (PROJECT_TRACK, PROJECT_TURNOFF, PROJECT_SHARED)

END_OF_TRACK = (0x00, 0x80)

OVERRUNNING_SEED = 105
"""A road that asks for more scanlines than the buffer can carry, so it is skipped."""


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


def _dword(value):
    return [(value >> shift) & 0xFF for shift in (0, 8, 16, 24)]


def _viewport(source):
    """The part of the opening every projection shares: where the viewer is looking."""
    return (
        _dword(source.randrange(-0x40000, 0x40000))
        + _word(source.randrange(150, 224))
        + _word(source.randrange(0, 60))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0, 224))
        + _dword(source.randrange(-0x200000, 0x200000))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0, 0x4000))
        + _word(source.randrange(-128, 128))
    )


def _road(source):
    """One stretch of the single-player track, in the ranges a road would use."""
    return (
        _viewport(source)
        + _dword(source.randrange(-0x4000, 0x4000))
        + _dword(source.randrange(-0x8000, 0x8000))
        + _word(source.randrange(0x0400, 0x4000))
        + _word(0)
        + _dword(source.randrange(-0x1000, 0x1000))
        + _curvature(source)
    )


def _shared(source):
    """The multi-player road, whose horizontal shaping is one word rather than two."""
    return (
        _viewport(source)
        + _dword(source.randrange(-0x4000, 0x4000))
        + _dword(source.randrange(-0x8000, 0x8000))
        + _word(source.randrange(0x0400, 0x4000))
        + _word(0)
        + _word(source.randrange(-64, 64))
        + _curvature(source)
    )


def _branch(source):
    """The fork, which is told where it sits on screen rather than where it is in the world."""
    return _viewport(source) + _word(source.randrange(0x0400, 0x4000)) + _branch_shape(source)


def _curvature(source):
    """How the road bends over the next stretch."""
    return (
        _word(source.randrange(-32, 32))
        + _word(source.randrange(-32, 32))
        + _word(source.randrange(-32, 32))
    )


def _branch_shape(source):
    """Where the fork sits on screen and how fast it crosses it."""
    return (
        _word(source.randrange(0, 224))
        + _word(source.randrange(-32, 32))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-32, 32))
        + _word(source.randrange(-32, 32))
    )


def command_for(seed):
    """Which of the three projections a seed exercises."""
    return PROJECTIONS[seed % len(PROJECTIONS)]


def steps_for(seed):
    """The whole exchange for one road, as writes and reads in order."""
    source = random.Random(seed)
    command = command_for(seed)
    opening = {PROJECT_TRACK: _road, PROJECT_TURNOFF: _branch, PROJECT_SHARED: _shared}[command]
    following = _branch_shape if command == PROJECT_TURNOFF else _curvature

    steps = [(WRITE, command & 0xFF), (WRITE, command >> 8)]
    steps += [(WRITE, value) for value in opening(source)]
    steps += [(READ, 0)] * BUFFER_BYTES
    for _ in range(STRETCHES):
        steps += [(WRITE, value) for value in _word(source.randrange(0x0400, 0x4000))]
        steps += [(READ, 0)] * BUFFER_BYTES
        steps += [(WRITE, value) for value in following(source)]
        steps += [(READ, 0)] * BUFFER_BYTES
    steps += [(WRITE, value) for value in END_OF_TRACK]
    steps += [(READ, 0)] * 8
    return steps


def fits(steps):
    """Whether every answer in a case stays inside the buffer the chip has."""
    chip = dsp4.Dsp4()
    for kind, value in steps:
        if kind == WRITE:
            chip.write(value)
            if chip.out_count > BUFFER_BYTES:
                return False
        else:
            chip.read()
    return True


def replay(steps):
    """The case through the model."""
    chip = dsp4.Dsp4()
    answers = []
    for kind, value in steps:
        if kind == WRITE:
            chip.write(value)
        else:
            answers.append(chip.read())
    return answers


def ask(steps, driver):
    """The case through the reference, whose answers are the ones recorded."""
    payload = struct.pack("<I", 1) + bytes(dsp4.PARAMETER_BYTES) + struct.pack("<I", len(steps))
    for kind, value in steps:
        payload += bytes([ord(kind), value])
    done = subprocess.run(
        [driver, "dsp4"], input=payload, capture_output=True, check=False, timeout=DRIVER_TIMEOUT
    )
    if done.returncode:
        raise Usage(f"the reference driver failed: {done.stderr.decode(errors='replace').strip()}")
    return list(done.stdout[4:])


def load(path=None):
    """The corpus, from where it was asked for or from the one that ships."""
    with Path(path or DEFAULT_CORPUS).open() as handle:
        return json.load(handle)


def record(driver, wanted):
    """Ask the reference for the answers, keeping only cases the buffer can carry."""
    cases = []
    seed = 0
    while len(cases) < wanted:
        steps = steps_for(seed)
        seed += 1
        if not fits(steps):
            continue
        cases.append({"seed": seed - 1, "expected": ask(steps, driver)})
    return {
        "comment": (
            "Roads generated from seeds and answered by the chip's own reference. "
            "Cases whose output would not fit the chip's 512 byte buffer are not here."
        ),
        "reference": "snes9x dsp4.cpp, through conformance/ref",
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
        print(f"recorded {len(found['cases'])} roads")
        return 0

    corpus = load(chosen.corpus)
    failed = 0
    checked = 0
    for case in corpus["cases"]:
        found = disagreement(case["expected"], replay(steps_for(case["seed"])))
        checked += len(case["expected"])
        if found is None:
            continue
        failed += 1
        index, theirs, ours = found
        if failed <= REPORT_LIMIT:
            print(f"FAIL seed {case['seed']} at byte {index}: reference {theirs}, model {ours}")

    print(f"{len(corpus['cases'])} roads, {checked:,} bytes compared, {failed} disagreed")
    return 1 if failed else 0


def main(argv):
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
