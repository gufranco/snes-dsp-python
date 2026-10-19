from typing import Any

from . import chip as chip
from . import models as models
from .chip import available, why_not
from .errors import (
    Corrupt,
    NeverReady,
    NoFirmware,
    NotDecoded,
    UnknownModelError,
    Unrecognised,
    WrongShape,
)
from .firmware import (
    HIGH_BYTE_FIRST,
    LOW_BYTE_FIRST,
    canonical,
    digests_of,
    directories,
    identify,
    search,
)
from .models import MODELS, SHARES_MICROCODE, Model
from .timing import DSP_CLOCK, GAP, MASTER_CLOCK, clock_of, steps_for
from .version import VERSION

__version__ = VERSION


def Chip(model: str | None = None, **options: "Any") -> chip.Chip:  # noqa: N802
    return chip.Chip(models.lookup(model).name, **options)


__all__ = [
    "DSP_CLOCK",
    "GAP",
    "HIGH_BYTE_FIRST",
    "LOW_BYTE_FIRST",
    "MASTER_CLOCK",
    "MODELS",
    "SHARES_MICROCODE",
    "Chip",
    "Corrupt",
    "Model",
    "NeverReady",
    "NoFirmware",
    "NotDecoded",
    "UnknownModelError",
    "Unrecognised",
    "WrongShape",
    "__version__",
    "available",
    "canonical",
    "clock_of",
    "digests_of",
    "directories",
    "identify",
    "search",
    "steps_for",
    "why_not",
]
