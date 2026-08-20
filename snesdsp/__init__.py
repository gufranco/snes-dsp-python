"""The DSP-1, DSP-2, DSP-3 and DSP-4, run rather than described.

    from snesdsp import Dsp

    chip = Dsp("dsp2")
    chip.write(0x09)
    for byte in (0x02, 0x00, 0x03, 0x00):
        chip.write(byte)
    [chip.read() for _ in range(4)]

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

from .doctor import examine, report
from .models import MODELS, SHARES_MICROCODE, UnknownModelError, describe
from .silicon import NeverReady, NoFirmware, Silicon, available, why_not
from .timing import DSP_CLOCK, GAP, MASTER_CLOCK, clock_of, steps_for
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "dsp1"


def Dsp(model=DEFAULT_MODEL, **options):  # noqa: N802
    """One part of that name, running its own microcode.

    Refuses when there is no image for it rather than answering from somewhere
    else, because an answer that did not come from the part is worse than none.
    """
    return Silicon(describe(model).name, **options)


__all__ = [
    "DSP_CLOCK",
    "GAP",
    "MASTER_CLOCK",
    "MODELS",
    "SHARES_MICROCODE",
    "Dsp",
    "NeverReady",
    "NoFirmware",
    "Silicon",
    "UnknownModelError",
    "__version__",
    "available",
    "clock_of",
    "describe",
    "examine",
    "report",
    "steps_for",
    "why_not",
]
