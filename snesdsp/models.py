from __future__ import annotations

from typing import TYPE_CHECKING, override

from snesdsp.errors import UnknownModelError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable


SHARES_MICROCODE = {"dsp1a": "dsp1"}


class Model:
    __slots__ = ("aliases", "name", "summary")

    def __init__(self, name: str, summary: str, aliases: Iterable[str] = ()) -> None:
        self.name = name
        self.summary = summary
        self.aliases = tuple(aliases)

    @property
    def image(self) -> str:
        return SHARES_MICROCODE.get(self.name, self.name)

    @override
    def __repr__(self) -> str:
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


def _normalise(name: str) -> str:
    return str(name).strip().lower().replace("-", "").replace("_", "")


def lookup(name: str | None) -> Model:
    if name is None:
        raise UnknownModelError(
            "no model was named, and this package will not choose one for you."
            f" Name one of: {', '.join(sorted(MODELS))}"
        )
    wanted = _normalise(name)
    found = _BY_ALIAS.get(wanted)
    if found is not None:
        return found
    raise UnknownModelError(
        f"{name} is not a part this package covers; it has {', '.join(sorted(MODELS))}"
    )
