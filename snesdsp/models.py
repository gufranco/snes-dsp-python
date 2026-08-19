"""Which parts this package covers, and what each one is.

The DSP-2 is one member of a family of NEC uPD77C25 derivatives that Nintendo
shipped under the DSP name. They share silicon and differ in the microcode masked
into it, which is why the DSP-1, DSP-2, DSP-3 and DSP-4 answer completely
different commands while being the same part underneath. Two are modelled here,
each a separate command set held to its own corpus: the DSP-2, which answers
questions, and the DSP-4, which draws a road.

A model with no corpus behind it does not belong in this table, because then its
fidelity would be a claim rather than a measurement.
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


def _build_dsp4(model, **options):
    from .dsp4 import Dsp4

    chip = Dsp4(**options)
    chip.model = model.name
    return chip


_CATALOGUE = (
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

_BY_ALIAS = {}
for _model in _CATALOGUE:
    _BY_ALIAS[_model.name] = _model
    for _alias in _model.aliases:
        _BY_ALIAS[_alias] = _model


def _normalise(name):
    return str(name).strip().lower().replace("-", "").replace("_", "")


def describe(name):
    """The model of that name, however it happens to be written."""
    found = _BY_ALIAS.get(_normalise(name))
    if found is None:
        raise UnknownModelError(
            f"{name} is not a model this package covers; it has {', '.join(sorted(MODELS))}"
        )
    return found
