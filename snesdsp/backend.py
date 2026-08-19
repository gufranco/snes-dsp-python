"""Which of the two ways to run a part, and why one is preferred.

The microcode is the part's own program, so running it answers every command
including the ones nobody has characterised. The model is what somebody worked
out by hand, so it answers the commands somebody thought about. Given a choice
between a definition and a description of it, the definition wins.

So the microcode is the default wherever an image is present, and the model is
what the package falls back to when it is not. Neither is a fallback in the sense
of being lesser to use on purpose: the model is the only one that can ship, and
holding it to the microcode is what turns its fidelity from a claim into a
measurement.

A caller that wants a particular one says so. Asking for the microcode without an
image is refused rather than quietly served the model, because a caller who names
it wants the real thing and would otherwise be told nothing was wrong.
"""

from . import silicon

SILICON = "silicon"

MODELLED = "modelled"

BACKENDS = (SILICON, MODELLED)


class UnknownBackend(Exception):
    pass


def chosen(part, wanted=None, images=None):
    """Which backend to use for that part, given what was asked for.

    `images` is what is available, passed in so the decision can be exercised
    without an image on disk and so a caller can narrow it.
    """
    if wanted is not None and wanted not in BACKENDS:
        raise UnknownBackend(
            f"{wanted} is not a way to run a part; there are {', '.join(BACKENDS)}"
        )

    available = silicon.available() if images is None else images

    if wanted == MODELLED:
        return MODELLED
    if wanted == SILICON:
        if part not in available:
            raise silicon.NoFirmware(
                f"the microcode was asked for by name and there is no image for"
                f" {part}. {silicon.WHY_NOT_FIRMWARE}"
            )
        return SILICON
    return SILICON if part in available else MODELLED
