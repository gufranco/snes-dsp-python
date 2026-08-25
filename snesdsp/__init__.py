"""The DSP-1, DSP-2, DSP-3 and DSP-4, run rather than described.

    from snesdsp import Chip

    part = Chip("dsp2")
    part.write(0x09)
    for byte in (0x02, 0x00, 0x03, 0x00):
        part.write(byte)
    [part.read() for _ in range(4)]

All four are one processor, a NEC uPD77C25, with different microcode masked into
it. So there is nothing here that works out what a command computes: the answer
to that is the program the part carries, and this runs it.

That is a deliberate narrowing. A hand-written model of a command set can be
checked and can never be finished, because what it covers is the commands
somebody thought to look at, and the corners nobody characterised are exactly
where it is silently wrong. Running the program has no such edge: the answer to
every command, in every state, including the ones no cartridge ever used, is
whatever the part answers.

What it costs is the microcode, which belongs to whoever made the part and is
never carried here. A copy you already own goes in the firmware directory of this
project, or of the project this one sits inside, or in any directory named by
`UPD7725_FIRMWARE_DIR`. Without one this refuses and says so. It does not fall
back to a guess.
"""

from typing import Any

from . import chip as chip
from .chip import available, why_not
from .errors import (
    Corrupt,
    NeverReady,
    NoFirmware,
    UnknownModelError,
    Unrecognised,
    WrongShape,
)
from .models import MODELS, SHARES_MICROCODE, Model, describe
from .timing import DSP_CLOCK, GAP, MASTER_CLOCK, clock_of, steps_for
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "dsp1"


def Chip(model: str = DEFAULT_MODEL, **options: "Any") -> chip.Chip:  # noqa: N802
    """A chip of the named model, sharing one interface across the family.

    The model comes first because it is the thing a caller always knows. There
    is no second positional argument here and there is nothing for one to carry:
    what this part runs on is a program read from a file, not a store a caller
    hands over, so the shape stops at the argument every member takes.

    The same shape as `Cpu(model, memory)` on the members that run a program, and
    named for what this is rather than for what it does. This part answers the
    accesses a cartridge makes; the cycles are spent inside the processor it
    composes, and that member is the one that reports them.

    Refuses when there is no image for the named part rather than answering from
    somewhere else, because an answer that did not come from the part is worse
    than none.
    """
    return chip.Chip(describe(model).name, **options)


__all__ = [
    "DEFAULT_MODEL",
    "DSP_CLOCK",
    "GAP",
    "MASTER_CLOCK",
    "MODELS",
    "SHARES_MICROCODE",
    "Chip",
    "Corrupt",
    "Model",
    "NeverReady",
    "NoFirmware",
    "UnknownModelError",
    "Unrecognised",
    "WrongShape",
    "__version__",
    "available",
    "clock_of",
    "describe",
    "steps_for",
    "why_not",
]
