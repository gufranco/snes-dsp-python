"""A model of the DSP-2, the coprocessor in one SNES cartridge.

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
from .memory import PARAMETER_BYTES, UNSET_SEED, parameter_ram, scramble
from .models import MODELS, UnknownModelError, describe
from .version import VERSION

__version__ = VERSION

DEFAULT_MODEL = "dsp2"


def Dsp(model=DEFAULT_MODEL, **options):  # noqa: N802
    """A chip of the named model, sharing one interface across the family."""
    return describe(model).build(**options)


__all__ = [
    "COMMAND_MERGE",
    "COMMAND_MIRROR",
    "COMMAND_MULTIPLY",
    "COMMAND_SCALE",
    "COMMAND_SYNC",
    "COMMAND_TILE",
    "COMMAND_TRANSPARENT",
    "IDLE_BYTE",
    "MODELS",
    "PARAMETER_BYTES",
    "UNSET_SEED",
    "Chip",
    "Dsp",
    "UnknownModelError",
    "__version__",
    "describe",
    "merge",
    "mirror",
    "multiply",
    "parameter_ram",
    "scale",
    "scramble",
    "tile",
]
