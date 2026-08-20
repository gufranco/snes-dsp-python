"""What each part answers, written down, so nothing here can quietly change it.

Running the part's own microcode makes the values right by construction. That is
the whole argument of this package, and it has one hole in it: the microcode is
not the only thing between a caller and an answer. The port decode is here, the
pacing is here, the read semantics are here, the boot handshake is here. Any of
those can change what comes back while the microcode stays byte for byte the same,
and nothing would notice.

So this takes what the parts answer today and keeps it. A later run re-derives
every answer and compares. Change the gap between accesses, or make a read wait
where it used to take whatever was latched, and the comparison names the exchange
and both bytes rather than leaving it to be found by someone playing a game.

Three things make the corpus honest.

The payloads are generated from a seed recorded in the file, so a run repeats
exactly and no byte of anybody's cartridge is needed to reproduce it. The shapes
come from the cartridge corpus, so what is pinned is what games actually send.
And the digest of the microcode that answered is recorded: a corpus taken against
one image and checked against another is refused rather than reported as a
disagreement, because two different images are entitled to answer differently.

What is stored is the output of a computation on inputs generated here. It is a
few hundred bytes per part, sampled from a function over a space of 2^128 or more,
and it reconstructs nothing: the program that produced it stays where it was.
"""

import hashlib
import json
import random
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import shapes as shapes_module
from driven import BuildWatched, Watched

import snesdsp
from snesdsp import models, silicon

ROOT = Path(__file__).resolve().parent

PARTS = tuple(sorted(models.MODELS))

DRIVEN_LIKE = {"dsp1a": "dsp1", "dsp1b": "dsp1"}
"""Which part's shapes drive another, where two parts answer the same protocol.

The DSP-1A is a die shrink of the DSP-1 and the DSP-1B is a later mask of it. All
three take the same commands in the same order, so all three are driven through
the shapes the DSP-1 games use. That is not a convenience: driving them through
one set of shapes is what makes their answers comparable, and comparing their
answers is the only way to see where the DSP-1B's correction actually lands.
"""

NOTE = (
    "What this part answered when driven through the exchanges real cartridges make."
    " The payloads were generated from the seed named here, so nothing any cartridge"
    " carries is needed to reproduce this and none of it is stored. The digest is of"
    " the microcode that answered: a corpus taken against one image says nothing"
    " about another, so a check against a different image refuses rather than"
    " reporting a disagreement."
)


class Malformed(Exception):
    pass


class WrongImage(Exception):
    pass


class Checked:
    """What a corpus and the part on this machine had to say to each other."""

    def __init__(
        self,
        part: str,
        disagreements: Iterable[tuple[str, list[str], list[str]]],
        unrecorded: Iterable[str],
        vanished: Iterable[str],
        checked: int,
    ) -> None:
        self.part = part
        self.disagreements = tuple(disagreements)
        self.unrecorded = tuple(unrecorded)
        self.vanished = tuple(vanished)
        self.checked = checked

    @property
    def agrees(self) -> bool:
        """Whether the part still answers what it answered, and still answers it all.

        An exchange that has gone missing counts against agreement. It means the
        cartridge corpus lost a shape the part used to be driven through, and a
        smaller sweep passing is not the same thing as the same sweep passing.
        """
        return not self.disagreements and not self.vanished

    @override
    def __repr__(self) -> str:
        return f"<Checked {self.part}, {self.checked} exchanges, {len(self.disagreements)} wrong>"


def _default_build(part: str) -> Watched:  # pragma: no cover
    return snesdsp.Dsp(part)


def _default_digest(part: str) -> str:  # pragma: no cover
    """The digest of the image that will answer, taken from the file itself."""
    wanted = silicon.SHARES_IMAGE.get(part, part)
    held = silicon.available()
    if wanted not in held:
        raise WrongImage(f"no image for {wanted} is on this machine")
    return hashlib.sha256(Path(held[wanted][1]).read_bytes()).hexdigest()


def shapes_named(part: str) -> str:
    """Whose shapes drive that part, which is its own unless it shares a protocol."""
    return DRIVEN_LIKE.get(part, part)


def _default_shapes(part: str) -> list[dict[str, Any]]:
    path = ROOT / f"{shapes_named(part)}shapes.json"
    if not path.exists():
        return []
    held = json.loads(path.read_text())
    assert isinstance(held, dict), f"{path} does not hold an object"
    named = held["shapes"]
    assert isinstance(named, list), f"{path} does not hold a list of shapes"
    return named


def _exchanges(
    part: str, build: BuildWatched, held: Iterable[Mapping[str, Any]], chance: random.Random
) -> list[dict[str, Any]]:
    """Every shape that both gives and takes, played once at a freshly started part."""
    found: list[dict[str, Any]] = []
    for one in held:
        steps = shapes_module.parse(one["shape"])
        writes = any(step.what == shapes_module.WRITE for step in steps)
        takes = any(step.what == shapes_module.READ for step in steps)
        if not writes or not takes:
            continue
        payload = shapes_module.payload_for(steps, chance)
        said = shapes_module.drive(build(part), steps, payload)
        found.append({"shape": one["shape"], "said": [bytes(run).hex() for run in said]})
    return found


def take(
    part: str,
    build: BuildWatched = _default_build,
    shapes: Iterable[Mapping[str, Any]] | None = None,
    seed: int = shapes_module.DEFAULT_SEED,
    digest: Callable[[str], str] = _default_digest,
    rolls: Callable[[int], random.Random] = shapes_module.rolls,
) -> dict[str, Any]:
    """Everything that part answers today, in a form that can be written down."""
    held = _default_shapes(part) if shapes is None else shapes
    return {
        "note": NOTE,
        "part": part,
        "seed": seed,
        "image": {"sha256": digest(part)},
        "exchanges": _exchanges(part, build, held, rolls(seed)),
    }


def check(
    corpus: Mapping[str, Any],
    build: BuildWatched = _default_build,
    shapes: Iterable[Mapping[str, Any]] | None = None,
    digest: Callable[[str], str] = _default_digest,
    rolls: Callable[[int], random.Random] = shapes_module.rolls,
) -> "Checked":
    """A corpus against the part on this machine, refusing if the image differs."""
    part = corpus["part"]
    wanted = corpus["image"]["sha256"]
    found = digest(part)
    if found != wanted:
        raise WrongImage(
            f"the {part} answers here were taken from the image {wanted} and this"
            f" machine holds {found}. Two different images are entitled to answer"
            " differently, so there is nothing to compare"
        )

    held = _default_shapes(part) if shapes is None else shapes
    now = {
        one["shape"]: one["said"] for one in _exchanges(part, build, held, rolls(corpus["seed"]))
    }
    before = {one["shape"]: one["said"] for one in corpus["exchanges"]}

    return Checked(
        part=part,
        disagreements=[
            (shape, said, now[shape])
            for shape, said in before.items()
            if shape in now and now[shape] != said
        ],
        unrecorded=sorted(set(now) - set(before)),
        vanished=sorted(set(before) - set(now)),
        checked=len(set(now) & set(before)),
    )


def store(corpus: Mapping[str, Any], where: Path = ROOT) -> Path:
    """One corpus written where its part names."""
    path = Path(where) / f"{corpus['part']}answers.json"
    path.write_text(json.dumps(corpus, indent=2) + "\n")
    return path


def load(part: str, where: Path = ROOT) -> dict[str, Any] | None:
    """That part's corpus, or nothing when none has been taken."""
    path = Path(where) / f"{part}answers.json"
    if not path.exists():
        return None
    held = json.loads(path.read_text())
    assert isinstance(held, dict), f"{path} does not hold an object"
    if held.get("part") != part:
        raise Malformed(f"{path} holds answers for {held.get('part')}, not for {part}")
    return held


def lines_for(found: "Checked") -> list[str]:
    """What a comparison found, in the order somebody reading it wants it."""
    said = [f"  {found.part}: {found.checked} exchanges re-derived and compared"]
    for shape, wanted, got in found.disagreements:
        said.append(f"       ! {shape}")
        said.append(f"           recorded {wanted}")
        said.append(f"           answered {got}")
    for shape in found.vanished:
        said.append(f"       ! {shape}: recorded, and no longer among the shapes swept")
    for shape in found.unrecorded:
        said.append(f"         {shape}: swept, and not yet recorded. Take the corpus again")
    return said


def main(
    argv: Sequence[str] = (),
    why_not: Callable[[], str | None] = silicon.why_not,
    build: BuildWatched = _default_build,
    shapes_for: Callable[[str], list[dict[str, Any]]] = _default_shapes,
    digest: Callable[[str], str] = _default_digest,
    where: Path = ROOT,
    parts: Sequence[str] = PARTS,
    say: Callable[[str], object] = print,
) -> int:
    """Take a corpus, or check one, depending on what was asked for."""
    reason = why_not()
    if reason:
        say(f"  nothing to run: {reason}")
        return 2

    taking = "--take" in argv
    wanted = [one for one in argv if one != "--take"] or list(parts)

    if taking:
        for part in wanted:
            corpus = take(part, build, shapes_for(part), digest=digest)
            path = store(corpus, where)
            say(f"  wrote {path.name}: {len(corpus['exchanges'])} exchanges from {part}")
        return 0

    unwell = False
    for part in wanted:
        recorded = load(part, where)
        if recorded is None:
            say(f"  {part}: no answers are recorded. Take them with --take {part}")
            unwell = True
            continue
        try:
            found = check(recorded, build, shapes_for(part), digest=digest)
        except WrongImage as wrong:
            say(f"  {part}: {wrong}")
            return 2
        for line in lines_for(found):
            say(line)
        unwell = unwell or not found.agrees
    return 1 if unwell else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
