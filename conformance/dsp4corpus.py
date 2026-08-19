"""Hold the DSP-4's track projection to the chip's own reference.

Each case is one command driven to completion, cycling through the renderers that
suspend. Four of them are roads: a viewpoint and a stretch of track, then several
more stretches fed in as the projection asks for them, then the marker that says
the track has ended. The fifth is a screen of sprites, which opens with a
selection because a chip that has not been told how many sprites a row may hold
refuses every one of them, and a case that draws nothing agrees with anything. The numbers are generated from a seed but shaped like a road
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

import base64
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

CASES = 140

STRETCHES = 4

DRIVER_TIMEOUT = 120

REPORT_LIMIT = 5

PROJECT_TRACK = 0x0001

PROJECT_TURNOFF = 0x0007

PROJECT_SHARED = 0x000D

RENDER_SOLID = 0x0008

FORK_LEFT = -0x3FFF

FORK_RIGHT = 0x3FFF

PROJECT_SPRITES = 0x0009

PROJECT_LIT_TRACK = 0x000F

PROJECT_LIT_TURNOFF = 0x0010

PROJECTIONS = (
    PROJECT_TRACK,
    PROJECT_TURNOFF,
    PROJECT_SHARED,
    RENDER_SOLID,
    PROJECT_SPRITES,
    PROJECT_LIT_TRACK,
    PROJECT_LIT_TURNOFF,
)

LIGHTING_COLOURS = 4

COLOUR_BYTES = 8

VEHICLE = -0x7000

SPRITE_HEADERS = (0x20, 0x2E, 0x40, 0x60, 0xA0, 0xC0, 0xE0)

SPRITES = 4

TILES = 3

SPRITE_BYTES = 32

SELECT_ONE_PLAYER = 0x0003

SELECT_TWO_PLAYER = 0x000E

BAD_HEADER = 0x1234

TURNOFF = 0x8001

NEAR_DISTANCE = (0x0400, 0x4000)

FAR_DISTANCE = (0x6000, 0x7C00)

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


def _shared(source, level):
    """The multi-player road, whose horizontal shaping is one word rather than two.

    Its viewer sits low on the screen and looks a long way down the road, because
    it counts its scanlines from where the viewer was rather than from the last
    line drawn, and a viewer near the horizon draws nothing at all.
    """
    return (
        _dword(level << 16)
        + _word(level + 10)
        + _word(source.randrange(0, 20))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0, 224))
        + _dword(source.randrange(-0x200000, 0x200000))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0, 0x4000))
        + _word(source.randrange(-128, 128))
        + _dword(source.randrange(-0x4000, 0x4000))
        + _dword(source.randrange(-0x8000, 0x8000))
        + _word(source.randrange(*FAR_DISTANCE))
        + _word(0)
        + _word(source.randrange(-64, 64))
        + _curvature(source)
    )


def _branch(source, level):
    """The fork, which is told where it sits on screen rather than where it is in the world."""
    return (
        _dword(level << 16)
        + _word(level + 10)
        + _word(source.randrange(0, 10))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0, 224))
        + _dword(source.randrange(-0x200000, 0x200000))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0, 0x4000))
        + _word(source.randrange(-128, 128))
        + _word(source.randrange(0x0400, 0x4000))
        + _branch_shape(source, level)
    )


def _lit_road(source):
    """The lit single-player road, whose opening carries a leading zero."""
    return _word(0) + _road(source)


def _lit_branch(source, level):
    """The lit fork, whose opening carries a leading zero."""
    return _word(0) + _branch(source, level)


def _lighting(source):
    """A distance and a colour, which come back as the colour dimmed by it."""
    return _word(source.randrange(0, 0x8000)) + _word(source.randrange(0, 0x8000))


def _fork(source):
    """A road leaving the road, which restarts the wait for a distance."""
    return (
        _word(source.randrange(0x0400, 0x4000))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-32, 32))
    )


def _curvature(source):
    """How the road bends over the next stretch."""
    return (
        _word(source.randrange(-32, 32))
        + _word(source.randrange(-32, 32))
        + _word(source.randrange(-32, 32))
    )


def _branch_shape(source, level):
    """Where the fork sits on screen and how fast it crosses it.

    Its height is handed down rather than drawn at random, because a fork told to
    jump about produces no scanlines and a case that draws nothing agrees with
    anything.
    """
    return (
        _word(level)
        + _word(-source.randrange(1, 8))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-32, 32))
        + _word(source.randrange(-32, 32))
    )


def _pair_of_pairs(source, low, high):
    """Four words that belong to two shapes, each with a left and a right."""
    return [byte for _ in range(4) for byte in _word(source.randrange(low, high))]


def _solid(source):
    """Two solid shapes: the window they are carved from, and where they start."""
    return (
        _pair_of_pairs(source, 200, 256)
        + _pair_of_pairs(source, 0, 40)
        + _pair_of_pairs(source, -0x4000, 0x4000)
        + _pair_of_pairs(source, -0x4000, 0x4000)
        + _pair_of_pairs(source, 0, 256)
        + _pair_of_pairs(source, 0x0400, 0x4000)
        + _pair_of_pairs(source, 150, 224)
        + _pair_of_pairs(source, 0, 180)
        + _pair_of_pairs(source, -0x4000, 0x4000)
        + _word(source.randrange(0x0400, 0x4000))
        + _solid_shape(source)
    )


def _solid_shape(source):
    """Where each shape sits this stretch, and how its two edges are pulled."""
    return (
        _word(source.randrange(-256, 256))
        + _word(source.randrange(150, 200))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(150, 200))
        + _envelope(source)
        + _envelope(source)
        + _envelope(source)
        + _envelope(source)
    )


def _envelope(source):
    """One shaping word, which now and then names the fork rather than a nudge."""
    picked = source.randrange(0, 6)
    if picked == 0:
        return _word(FORK_LEFT)
    if picked == 1:
        return _word(FORK_RIGHT)
    return _word(source.randrange(-64, 64))


def _screen(source):
    """The screen the sprites are placed on."""
    return (
        _word(source.randrange(100, 160))
        + _word(source.randrange(80, 120))
        + _word(0)
        + _word(source.randrange(0, 32))
        + _word(source.randrange(224, 256))
        + _word(source.randrange(0, 32))
        + _word(source.randrange(190, 224))
    )


def _vehicle(source):
    """A car, its collision vector, and how far away it is."""
    return (
        _word(source.randrange(0, 0x8000))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(0x0400, 0x4000))
        + _word(source.randrange(-256, 256))
    )


def _terrain(source):
    """Something standing beside the road."""
    return (
        _word(source.randrange(0, 256))
        + _word(source.randrange(0, 256))
        + _word(source.randrange(-256, 256))
        + _word(source.randrange(-256, 256))
    )


def _tile(source):
    """One tile of a sprite: a header that is also its attribute delta, then offsets."""
    header = source.choice(SPRITE_HEADERS) << 8
    offsets = _word(source.randrange(-64, 64)) + _word(source.randrange(-64, 64))
    return _word(header | source.randrange(0, 256)), offsets


def _command(command):
    return [(WRITE, command & 0xFF), (WRITE, command >> 8)]


def _writes(values):
    return [(WRITE, value) for value in values]


def _sprite_tiles(source):
    """The tiles of one sprite, and whatever ends the run.

    Three things end it: a header the chip does not recognise, a zero once the
    tiles have already been switched to the smaller size, and the marker that
    ends the whole command. The first two are here; the third ends the case.
    """
    steps = []
    size = 1
    for _ in range(TILES):
        picked = source.randrange(0, 8)
        if picked == 0:
            return steps + _writes(_word(BAD_HEADER))
        if picked == 1 and size:
            size = 0
            steps += _writes(_word(0))
            continue
        header, offsets = _tile(source)
        steps += _writes(header) + _writes(offsets) + [(READ, 0)] * SPRITE_BYTES
    if size:
        steps += _writes(_word(0))
    return steps + _writes(_word(0))


def _one_sprite(source):
    """One sprite: which kind it is, where it sits, and the tiles it is made of."""
    vehicle = source.randrange(0, 4) == 0
    steps = _writes(_word(source.randrange(0, 224)))
    steps += _writes(_word(VEHICLE if vehicle else source.randrange(0x0400, 0x4000)))
    if vehicle:
        steps += _writes(_vehicle(source)) + [(READ, 0)] * SPRITE_BYTES
        steps += _writes(_word(source.randrange(-32, 32)))
    else:
        steps += _writes(_terrain(source))
    steps += _writes(_word(source.randrange(0, 0x4000)))
    return steps + _sprite_tiles(source)


def _sprite_steps(source):
    """The whole exchange for a screen of sprites.

    It opens with a selection, because a chip that has not been told how many
    sprites a row may hold refuses every one of them, and a case that draws
    nothing agrees with anything.
    """
    selection = SELECT_ONE_PLAYER if source.randrange(0, 2) else SELECT_TWO_PLAYER
    steps = _command(selection) + _command(PROJECT_SPRITES) + _writes(_screen(source))
    for _ in range(SPRITES):
        steps += _one_sprite(source)
    steps += _writes(_word(source.randrange(0, 224))) + _writes(END_OF_TRACK)
    return steps + [(READ, 0)] * 8


def command_for(seed):
    """Which of the three projections a seed exercises."""
    return PROJECTIONS[seed % len(PROJECTIONS)]


def steps_for(seed):
    """The whole exchange for one case, as writes and reads in order."""
    source = random.Random(seed)
    command = command_for(seed)
    if command == PROJECT_SPRITES:
        return _sprite_steps(source)
    return _command(command) + _road_steps(source, command)


def _lighting_steps(source):
    """The four colours a lit projection asks for before it draws a stretch.

    Only a stretch with scanlines in it asks, so the reads between them are what
    tell the two implementations apart when one of them asks and the other does
    not.
    """
    steps = []
    for index in range(LIGHTING_COLOURS):
        last = index == LIGHTING_COLOURS - 1
        steps += _writes(_lighting(source))
        steps += [(READ, 0)] * (BUFFER_BYTES if last else COLOUR_BYTES)
    return steps


def _road_steps(source, command):
    """A road, drawn a stretch at a time until the caller says the track has ended."""
    forks = command in (PROJECT_TRACK, PROJECT_LIT_TRACK)
    branches = command in (PROJECT_TURNOFF, PROJECT_LIT_TURNOFF)
    lit = command in (PROJECT_LIT_TRACK, PROJECT_LIT_TURNOFF)
    following = {
        PROJECT_TRACK: _curvature,
        PROJECT_SHARED: _curvature,
        RENDER_SOLID: _solid_shape,
        PROJECT_LIT_TRACK: _curvature,
    }.get(command)
    level = source.randrange(200, 224)
    reach = FAR_DISTANCE if command == PROJECT_SHARED else NEAR_DISTANCE

    if branches:
        opening = _lit_branch(source, level) if lit else _branch(source, level)
    elif command == PROJECT_SHARED:
        opening = _shared(source, level)
    else:
        opening = {
            PROJECT_TRACK: _road,
            RENDER_SOLID: _solid,
            PROJECT_LIT_TRACK: _lit_road,
        }[command](source)

    steps = [(WRITE, value) for value in opening]
    steps += [(READ, 0)] * BUFFER_BYTES
    if lit:
        steps += _lighting_steps(source)
    for _ in range(STRETCHES):
        level = max(level - source.randrange(20, 36), 30)
        if forks and source.randrange(0, 3) == 0:
            steps += _writes(_word(TURNOFF)) + [(READ, 0)] * BUFFER_BYTES
            steps += _writes(_fork(source)) + [(READ, 0)] * BUFFER_BYTES
        steps += _writes(_word(source.randrange(*reach)))
        steps += [(READ, 0)] * BUFFER_BYTES
        shape = _branch_shape(source, level) if branches else following(source)
        steps += _writes(shape)
        steps += [(READ, 0)] * BUFFER_BYTES
        if lit:
            steps += _lighting_steps(source)
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
        cases.append({"seed": seed - 1, "expected": encode(ask(steps, driver))})
    return {
        "comment": (
            "Cases generated from seeds and answered by the chip's own reference. "
            "Cases whose output would not fit the chip's 512 byte buffer are not here."
        ),
        "reference": "snes9x dsp4.cpp, through conformance/ref",
        "cases": cases,
    }


def encode(answers):
    """Answers as one string, because a byte per line is a file nobody can read."""
    return base64.b64encode(bytes(answers)).decode("ascii")


def expected_of(case):
    """The bytes the reference gave for one case."""
    return list(base64.b64decode(case["expected"]))


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
        print(f"recorded {len(found['cases'])} cases")
        return 0

    corpus = load(chosen.corpus)
    failed = 0
    checked = 0
    for case in corpus["cases"]:
        expected = expected_of(case)
        found = disagreement(expected, replay(steps_for(case["seed"])))
        checked += len(expected)
        if found is None:
            continue
        failed += 1
        index, theirs, ours = found
        if failed <= REPORT_LIMIT:
            print(f"FAIL seed {case['seed']} at byte {index}: reference {theirs}, model {ours}")

    print(f"{len(corpus['cases'])} cases, {checked:,} bytes compared, {failed} disagreed")
    return 1 if failed else 0


def main(argv):
    try:
        return run(argv)
    except Usage as error:
        print(error)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
