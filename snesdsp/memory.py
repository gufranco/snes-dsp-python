"""Storage that holds what it held, because hardware never hands over a clean one.

The DSP-2 carries 512 bytes of parameter RAM and never clears it. A command that
reads past the data it was given, and the rescale does exactly that, reads
whatever the previous command left behind. Starting that RAM at zero makes those
reads look deliberate and stable, which is how a bug in that path survives every
test and then appears on a console.
"""

import random

UNSET_SEED = 0x5A5A5A5A

PARAMETER_BYTES = 512


def scramble(size, seed=UNSET_SEED):
    """A deterministic fill that is nothing like a cleared machine.

    Reproducible from the seed, so a differential run stays comparable, and
    obviously not clean, so a read of something never written shows up.
    """
    return bytearray(random.Random(seed).randbytes(size))


def parameter_ram(fill=None, seed=UNSET_SEED):
    """The chip's parameter RAM, filled rather than cleared.

    `fill` is a byte, a bytes-like image loaded at the bottom, or None for the
    scrambled pattern above. A caller that genuinely wants zeroes asks for zero
    and says so, which is the point: it becomes a decision rather than a default.
    """
    if fill is None:
        return scramble(PARAMETER_BYTES, seed)
    if isinstance(fill, int):
        return bytearray([fill & 0xFF]) * PARAMETER_BYTES
    held = bytearray(PARAMETER_BYTES)
    held[: len(fill)] = fill[:PARAMETER_BYTES]
    return held
