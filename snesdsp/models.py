"""Which parts this package covers, and what each one is.

The DSP-2 is one member of a family of NEC uPD77C25 derivatives that Nintendo
shipped under the DSP name. They share silicon and differ in the microcode masked
into it, which is why the DSP-1, DSP-2, DSP-3 and DSP-4 answer completely
different commands while being the same part underneath. All four are modelled
here, each a separate command set held to its own corpus: the DSP-1, which does
fixed point three dimensional maths, the DSP-2, which converts tiles, the DSP-3,
which decompresses and searches a hex grid, and the DSP-4, which draws a road.

The DSP-1 was masked three times. The DSP-1, the DSP-1A and the DSP-1B are three
microcodes rather than three spellings of one, and the last corrected the first.
Two of the three are modelled here as separate parts, because two of the three
were measured: both images were run on the processor they are masked into and
asked the same questions, and they answer command 0x2F differently every time.
The middle mask has no image here, so it is refused by name rather than assumed
to match either of its neighbours.

A model with no corpus behind it does not belong in this table, because then its
fidelity would be a claim rather than a measurement.
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

    def __init__(self, name, summary, parameter_bytes, core, aliases=()):
        self.name = name
        self.summary = summary
        self.parameter_bytes = parameter_bytes
        self.core = core
        self.aliases = tuple(aliases)

    def build(self, **options):
        return self.core(self, **options)

    def __repr__(self):
        return f"<Model {self.name}, {self.parameter_bytes} bytes of parameter RAM>"


def _build_dsp2(model, **options):
    from .chip import Chip as Dsp2

    chip = Dsp2(**options)
    chip.model = model.name
    return chip


def _build_dsp1a(model, **options):
    """The middle mask, which runs the first mask's program on a smaller die."""
    from .dsp1 import Dsp1

    chip = Dsp1(revision=SHARES_MICROCODE[model.name], **options)
    chip.model = model.name
    return chip


def _build_dsp1(model, **options):
    from .dsp1 import Dsp1

    chip = Dsp1(revision=model.name, **options)
    chip.model = model.name
    return chip


def _build_dsp3(model, **options):
    from .dsp3 import Dsp3

    chip = Dsp3(**options)
    chip.model = model.name
    return chip


def _build_dsp4(model, **options):
    from .dsp4 import Dsp4

    chip = Dsp4(**options)
    chip.model = model.name
    return chip


_CATALOGUE = (
    Model(
        name="dsp1",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-1 microcode, shipped in more "
            "cartridges than the rest of the family together. Thirty one commands "
            "over a single byte wide port: a camera, three attitude matrices, and "
            "the projections and rotations that ask questions of them."
        ),
        parameter_bytes=512,
        core=_build_dsp1,
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
        parameter_bytes=512,
        core=_build_dsp1a,
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
        parameter_bytes=512,
        core=_build_dsp1,
        aliases=("dsp-1b", "upd77c25dsp1b", "nintendodsp1b"),
    ),
    Model(
        name="dsp2",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-2 microcode, shipped in exactly "
            "one cartridge. Six commands over a single byte wide port: tile conversion, "
            "transparent colour, merge, mirror, multiply and rescale."
        ),
        parameter_bytes=512,
        core=_build_dsp2,
        aliases=("dsp-2", "upd77c25dsp2", "nintendodsp2"),
    ),
    Model(
        name="dsp3",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-3 microcode, shipped in exactly "
            "one cartridge. Thirteen commands over a single byte wide port: a "
            "decompressor, a bit plane converter, and a search across a hex grid."
        ),
        parameter_bytes=0,
        core=_build_dsp3,
        aliases=("dsp-3", "upd77c25dsp3", "nintendodsp3"),
    ),
    Model(
        name="dsp4",
        summary=(
            "The NEC uPD77C25 carrying Nintendo DSP-4 microcode, shipped in exactly "
            "one cartridge. Fifteen commands over a single byte wide port, seven of "
            "which are renderers that suspend part way through a road and resume."
        ),
        parameter_bytes=512,
        core=_build_dsp4,
        aliases=("dsp-4", "upd77c25dsp4", "nintendodsp4"),
    ),
)

MODELS = {model.name: model for model in _CATALOGUE}

NOT_MODELLED = {}
"""Names that belong to a real part the package deliberately does not answer to."""

_BY_ALIAS = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name):
    return str(name).strip().lower().replace("-", "").replace("_", "")


def describe(name):
    """The model of that name, however it happens to be written."""
    wanted = _normalise(name)
    found = _BY_ALIAS.get(wanted)
    if found is not None:
        return found
    if wanted in NOT_MODELLED:
        raise UnknownModelError(f"{name} is not modelled here: {NOT_MODELLED[wanted]}")
    raise UnknownModelError(
        f"{name} is not a model this package covers; it has {', '.join(sorted(MODELS))}"
    )
