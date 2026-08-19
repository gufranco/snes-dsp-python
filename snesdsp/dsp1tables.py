"""The numbers the DSP-1 works from, as the formulas that make them.

This chip carries a thousand-word table masked into its silicon. That table is
chip content rather than a description of behaviour, so it is not here. What is
here is what the chip's arithmetic actually reads out of it, which turns out to
be a handful of things that can be stated rather than copied.

Two of them are trigonometry and come out exactly: a sine over a turn of two
hundred and fifty six steps, and the straight line the chip interpolates along
between two of those steps. That line is not pi. It is three hundred and fifty
five over one hundred and thirteen, which is the rational approximation a fixed
point designer reaches for, and it disagrees with pi often enough over the table
to be visible.

Two more are ladders of powers of two, used to shift a value without a shifter.
One of them has a step that holds one where it should hold sixteen, which breaks
an otherwise exact run and is reproduced because the reference has it and the
comparison is against the reference.

The rest are measurements: sixty six nodes of a square root curve and five
coefficients of a horizon correction. Both are numbers rather than expression,
and each is stated with the shape it fits so that nothing here is a copy of
something whose form is unknown.
"""

import math


class BeyondTheTable(Exception):
    pass


TURN = 256

SATURATED = 0x7FFF

PI_NUMERATOR = 355

PI_DENOMINATOR = 113
"""Milue's ratio, accurate to seven digits, and the one the chip used."""

ROOT_SCALE = 32767.021
"""The scale the square root nodes fit, which is a hair above a saturated word.

The chip computed them with its own iterative root rather than from a rounded
ideal, so the fit is slightly high. Every node is the truncation of this scale
times the root of the step over sixty four, and every one of them agrees.
"""

RECIPROCAL_SCALE = 1 << 29

RECIPROCAL_STEP = 128

SEED_BASE = 0x0065

SEED_LAST = 0x00E4

NODE_BASE = 0x00D5

RISE_BASE = 0x00E5

RISE_FIRST_STEP = 16

QUARTER_TURN = 64


def _sine_of(step):
    """One step of the turn, truncated toward zero and clamped into a word."""
    wanted = int(0x8000 * math.sin(2 * math.pi * step / TURN))
    return max(-SATURATED, min(SATURATED, wanted))


SINE = tuple(_sine_of(step) for step in range(TURN))

INTERPOLATION = tuple(PI_NUMERATOR * step // PI_DENOMINATOR for step in range(TURN))

LADDER_ZEROES = 0x22

LADDER_ONE = 0x31

LADDER_END = 0x40

LADDER_TAIL = 0x62

LADDER_ANOMALY = 0x3C
"""The one word of the ladder that is not a power of two.

Every word either side of it doubles. This one holds one where the run says
sixteen, which is what a slip in transcribing a table looks like and is what the
reference has. It is reachable from three different directions, so it is not
quietly corrected here.
"""

SHIFT_BASE = 0x21

SPREAD_BASE = 0x12

ROUND_BASE = 0x40


def ladder(at):
    """One word of the ladder the chip shifts with, by its own place in the table.

    The chip has no shifter. It multiplies by a power of two and narrows, and the
    powers live in one run of the mask ROM that rises to a saturated word in the
    middle and falls away again. Four different offsets read that same run, which
    is why this is one function rather than four tables.
    """
    if at < 0:
        raise BeyondTheTable(
            f"word {at} of a table that starts at zero; what the chip finds there is "
            "not something this model knows, and the reference reads whatever its own "
            "memory happens to hold before it"
        )
    if at < LADDER_ZEROES:
        return 0
    if at <= LADDER_ONE - 1:
        return 1 << (at - LADDER_ZEROES)
    if at == LADDER_ONE:
        return SATURATED
    if at == LADDER_ANOMALY:
        return 1
    if at <= LADDER_END:
        return 1 << (LADDER_END - at)
    if at < LADDER_TAIL:
        return 0
    raise BeyondTheTable(
        f"word {at} is past the ladder and inside the reciprocal seeds, which is not "
        "a shift by anything and is not something this model will pretend to know"
    )


def shift_up(shift):
    """The multiplier that moves a value left, which the chip doubles again after."""
    return ladder(SHIFT_BASE + shift)


def spread(shift):
    """The same ladder, reached by the offset a long exponent uses."""
    return ladder(SPREAD_BASE + shift)


def round_up(shift):
    """And again, reached from the far end by the doubling half of a wide normalise."""
    return ladder(ROUND_BASE - shift)


def shift_down(exponent):
    """The multiplier that moves a value right, which is the same run read from its middle.

    An exponent of nothing is as close to one as a word gets, which is why a value
    passed through it comes back one part in thirty two thousand smaller.
    """
    return ladder(LADDER_ONE + exponent)


HORIZON = (
    0x0A26,
    0x277A,
    0x00CE,
    0x6488,
    0x14AC,
)
"""Five coefficients of the curve that bends the horizon once the view is clipped."""

MAX_ZENITH = (
    0x38B4,
    0x38B7,
    0x38BA,
    0x38BE,
    0x38C0,
    0x38C4,
    0x38C7,
    0x38CA,
    0x38CE,
    0x38D0,
    0x38D4,
    0x38D7,
    0x38DA,
    0x38DD,
    0x38E0,
    0x38E4,
)
"""How far the view may tilt before the projection is clipped, one bound per exponent."""


SHIFT_TABLE_BASE = 0x31

SHIFT_TABLE_ZEROES = 0x22
"""Where the ladder starts. Everything the lookup can reach below it holds nothing."""


def newton_seed(step):
    """One over a normalised value, to a part in two hundred and fifty six.

    The reciprocal starts from here and refines it twice, so the seed only has
    to be close. Every one of the hundred and twenty eight entries the chip
    carries is this expression, rounded rather than truncated.
    """
    return min(SATURATED, round(RECIPROCAL_SCALE / (0x4000 + RECIPROCAL_STEP * step)))


def node(position):
    """One node of the square root curve, at an offset from where the curve starts.

    The offset can be negative, and when it is, the lookup lands before the curve
    and inside the reciprocal seeds instead. That is not a mistake to be guarded
    against: a vector long enough to wrap its own squared length produces a
    negative coefficient, and the chip reads whatever the offset lands on.
    """
    at = NODE_BASE + position
    if at <= SEED_LAST:
        return newton_seed(at - SEED_BASE)
    step = at - RISE_BASE + RISE_FIRST_STEP
    return int(ROOT_SCALE * math.sqrt(step / QUARTER_TURN))
