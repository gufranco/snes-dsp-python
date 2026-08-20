"""Which parts this package covers, and what each one is.

The DSP-1, DSP-2, DSP-3 and DSP-4 are one piece of silicon, a NEC uPD77C25, with
different microcode masked into it. That is why they answer completely different
commands while being the same part underneath, and it is why this file describes
them rather than implementing them: what a part does is the program it carries,
and the program is run rather than restated.

So a part here is three things. What it is, so a reader knows which cartridge it
came out of. What it answers to, so a name written any of the ways people write
it finds the right one. And which image it runs, which is usually its own.

The DSP-1 was masked three times. The DSP-1, the DSP-1A and the DSP-1B are three
parts and two programs: the DSP-1A is a die shrink of the DSP-1 carrying the same
program and data ROM, and the DSP-1B is the one that corrected an arithmetic
fault Pilotwings had come to depend on. Saying which shares which is more honest
than collapsing the middle one into the first or refusing to name it at all.
"""

SHARES_MICROCODE = {"dsp1a": "dsp1"}
"""Parts whose program is another part's, so their behaviour is that part's.

The DSP-1 was masked three times and only twice did the program change. The
DSP-1A is a die shrink of the DSP-1 with the same program and data ROM; the
DSP-1B is the one that corrected an arithmetic fault, which Pilotwings had come
to depend on for its attract sequence.

So this is three parts and two programs, and saying which shares which is more
honest than either collapsing the middle one into the first or refusing to answer
for it at all.
"""


class UnknownModelError(Exception):
    pass


class Model:
    """One part: what it is, what it holds, and how to build it."""

    def __init__(self, name, summary, aliases=()):
        self.name = name
        self.summary = summary
        self.aliases = tuple(aliases)

    @property
    def image(self):
        """The name of the image this part runs, which may be another part's."""
        return SHARES_MICROCODE.get(self.name, self.name)

    def __repr__(self):
        return f"<Model {self.name}, running the {self.image} image>"


_CATALOGUE = (
    Model(
        name="dsp1",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-1 microcode, shipped in more "
            "cartridges than the rest of the family together. Thirty one commands "
            "over a single byte wide port: a camera, three attitude matrices, and "
            "the projections and rotations that ask questions of them."
        ),
        aliases=("dsp-1", "upd77c25dsp1", "nintendodsp1"),
    ),
    Model(
        name="dsp1a",
        summary=(
            "The same program on a smaller die. The DSP-1A is a die shrink of the "
            "DSP-1 carrying the same program and data ROM, so it answers everything "
            "the DSP-1 answers and shares its one arithmetic fault. It is a part in "
            "its own right and is answered as one, and the microcode backend runs "
            "the DSP-1 image for it because that is the image it has."
        ),
        aliases=("dsp-1a", "upd77c25dsp1a", "nintendodsp1a"),
    ),
    Model(
        name="dsp1b",
        summary=(
            "The last mask of the DSP-1, and the one nearly every cartridge in the "
            "family carries; the first mask shipped in Pilotwings alone. Thirty one "
            "commands, the same as the mask before it apart from where it corrected "
            "it, and it names itself differently when asked."
        ),
        aliases=("dsp-1b", "upd77c25dsp1b", "nintendodsp1b"),
    ),
    Model(
        name="dsp2",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-2 microcode, shipped in exactly "
            "one cartridge. Six commands over a single byte wide port: tile conversion, "
            "transparent colour, merge, mirror, multiply and rescale."
        ),
        aliases=("dsp-2", "upd77c25dsp2", "nintendodsp2"),
    ),
    Model(
        name="dsp3",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-3 microcode, shipped in exactly "
            "one cartridge. Thirteen commands over a single byte wide port: a "
            "decompressor, a bit plane converter, and a search across a hex grid."
        ),
        aliases=("dsp-3", "upd77c25dsp3", "nintendodsp3"),
    ),
    Model(
        name="dsp4",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-4 microcode, shipped in exactly "
            "one cartridge. Fifteen commands over a single byte wide port, seven of "
            "which are renderers that suspend part way through a road and resume."
        ),
        aliases=("dsp-4", "upd77c25dsp4", "nintendodsp4"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}

_BY_ALIAS = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name):
    return str(name).strip().lower().replace("-", "").replace("_", "")


def describe(name):
    """The part of that name, however it happens to be written."""
    wanted = _normalise(name)
    found = _BY_ALIAS.get(wanted)
    if found is not None:
        return found
    raise UnknownModelError(
        f"{name} is not a part this package covers; it has {', '.join(sorted(MODELS))}"
    )
