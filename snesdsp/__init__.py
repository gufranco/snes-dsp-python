"""Models of the DSP-1, DSP-2, DSP-3 and DSP-4, the coprocessors in SNES cartridges.

    from snesdsp import Dsp

    chip = Dsp(model="dsp2")
    chip.write(0x09)
    for byte in (0x02, 0x00, 0x03, 0x00):
        chip.write(byte)
    [chip.read() for _ in range(4)]

Nothing starts clean. The chip's parameter RAM holds whatever the previous
command left, because the hardware never clears it, and one command reads past
its own data straight into that.
"""

from .backend import BACKENDS, MODELLED, SILICON, UnknownBackend, chosen
from .chip import (
    COMMAND_MERGE,
    COMMAND_MIRROR,
    COMMAND_MULTIPLY,
    COMMAND_SCALE,
    COMMAND_SYNC,
    COMMAND_TILE,
    COMMAND_TRANSPARENT,
    IDLE_BYTE,
    Chip,
)
from .commands import merge, mirror, multiply, scale, tile
from .dsp1 import Dsp1
from .dsp3 import Dsp3
from .dsp4 import Dsp4
from .memory import PARAMETER_BYTES, UNSET_SEED, parameter_ram, scramble
from .models import MODELS, UnknownModelError, describe
from .silicon import NoFirmware, Silicon
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "dsp2"


def Dsp(model=DEFAULT_MODEL, backend=None, **options):  # noqa: N802
    """A part of that name, run by its own microcode when an image is present.

    `backend` forces one of the two. Left alone, the microcode is used wherever
    there is an image for the part and the model is used where there is not,
    because a definition beats a description of it.
    """
    which = chosen(model, backend)
    chip = Silicon(model, **options) if which == SILICON else describe(model).build(**options)
    chip.backend = which
    return chip


__all__ = [
    "BACKENDS",
    "COMMAND_MERGE",
    "COMMAND_MIRROR",
    "COMMAND_MULTIPLY",
    "COMMAND_SCALE",
    "COMMAND_SYNC",
    "COMMAND_TILE",
    "COMMAND_TRANSPARENT",
    "IDLE_BYTE",
    "MODELLED",
    "MODELS",
    "PARAMETER_BYTES",
    "SILICON",
    "UNSET_SEED",
    "Chip",
    "Dsp",
    "Dsp1",
    "Dsp3",
    "Dsp4",
    "NoFirmware",
    "Silicon",
    "UnknownBackend",
    "UnknownModelError",
    "__version__",
    "chosen",
    "describe",
    "merge",
    "mirror",
    "multiply",
    "parameter_ram",
    "scale",
    "scramble",
    "tile",
]
