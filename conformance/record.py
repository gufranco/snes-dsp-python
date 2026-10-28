import collections
import hashlib
import json
import sys
from collections.abc import Callable, Collection, Iterable, Mapping
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import shapes

ROOT = Path(__file__).resolve().parent.parent

DRIVER = ROOT / "snes-driver-python"

CARTRIDGES = ROOT / "external" / "cartridges"

MANIFEST = ROOT / "cartridges.manifest.json"

TRACED = DRIVER / "conformance" / "traced.json"

LABELS = ("known", "executed", "traced", "assumed")

PRODUCED_BY = "https://github.com/gufranco/snes-driver-python"

PART_FAMILY = "dsp"

NOTE = (
    "The shapes real cartridges use to drive this part: which accesses each routine"
    " makes, in what order, and how wide each one was. No byte any cartridge carries"
    " is recorded here and none can be recovered from this. Read out of the games"
    " named below, every one of them confirmed against all four of its digests first."
)


class Recorded:
    def __init__(self, part: str) -> None:
        self.part = part
        self.counted: dict[str, int] = {}
        self.cartridges: dict[str, int] = {}
        self.sources: list[dict[str, Any]] = []
        self.silent: list[str] = []

    def add(self, identity: Mapping[str, Any], layout: str, shapes: Mapping[str, int]) -> None:
        for shape, seen in shapes.items():
            self.counted[shape] = self.counted.get(shape, 0) + seen
            self.cartridges[shape] = self.cartridges.get(shape, 0) + 1
        self.sources.append(
            {
                "name": identity["name"],
                "title": identity["title"],
                "why": identity["why"],
                "bytes": identity["bytes"],
                "layout": layout,
                "shapes": len(shapes),
                "crc32": identity["crc32"],
                "md5": identity["md5"],
                "sha1": identity["sha1"],
                "sha256": identity["sha256"],
            }
        )

    def ordered(self) -> list[dict[str, Any]]:
        return [
            {"shape": shape, "seen": self.counted[shape], "cartridges": self.cartridges[shape]}
            for shape in sorted(
                self.counted, key=lambda one: (-len(one.split()), -self.counted[one], one)
            )
        ]

    @override
    def __repr__(self) -> str:
        return f"<Recorded {self.part}, {len(self.counted)} shapes from {len(self.sources)}>"


def _default_confirm(image: bytes) -> object:  # pragma: no cover
    from conformance import cartridges

    return cartridges.identify(image)


def _default_layout(image: bytes) -> str:  # pragma: no cover
    _reach()
    from mapper import header

    layout = header.read(image).layout
    assert isinstance(layout, str)
    return layout


def digest_of(image: bytes) -> str:
    return hashlib.sha256(image).hexdigest()


def traced_widths(image: bytes, corpus: Path = TRACED) -> dict[int, int]:
    if not corpus.is_file():
        return {}
    held = json.loads(corpus.read_text())["cartridges"].get(digest_of(image))
    if held is None:
        return {}
    return {
        int(site["offset"], 16): site["widths"][0]
        for site in held["sites"]
        if len(site["widths"]) == 1 and not site["disputed"]
    }


def _default_shapes(
    image: bytes, window: object, layout: str
) -> dict[str, int]:  # pragma: no cover
    _reach()
    from snesdriver import conversation

    found = conversation.shapes(image, window, kind=layout, traced=traced_widths(image))
    assert isinstance(found, dict)
    return found


def _default_window(layout: str) -> object:  # pragma: no cover
    _reach()
    from snesdriver import windows

    return windows.window_for(PART_FAMILY, layout)


def _reach() -> None:
    for where in (DRIVER, DRIVER / "snes-mapper-python"):
        if str(where) not in sys.path:
            sys.path.insert(0, str(where))


Reading = Callable[[str], tuple[str, dict[str, int]] | None]


def reading(
    name: str,
    where: Path = CARTRIDGES,
    confirm: Callable[[bytes], object] = _default_confirm,
    layout_of: Callable[[bytes], str] = _default_layout,
    shapes_of: Callable[[bytes, Any, str], dict[str, int]] = _default_shapes,
    window_of: Callable[[str], object] = _default_window,
) -> tuple[str, dict[str, int]] | None:
    path = Path(where) / name
    if not path.exists():
        return None
    image = path.read_bytes()
    confirm(image)
    layout = layout_of(image)
    return layout, shapes_of(image, window_of(layout), layout)


def gather(
    manifest: Mapping[str, Any],
    reading: Reading = reading,
    keep_silent: bool = False,
) -> dict[str, "Recorded"]:
    found: dict[str, Recorded] = {}
    for identity in manifest["cartridges"]:
        said = reading(identity["name"])
        if said is None:
            continue
        layout, shapes = said
        part = identity["part"]
        if not shapes:
            if keep_silent:
                found.setdefault(part, Recorded(part)).silent.append(identity["name"])
            continue
        found.setdefault(part, Recorded(part)).add(identity, layout, shapes)
    return {part: held for part, held in found.items() if held.sources or held.silent}


def write(recorded: Mapping[str, "Recorded"], where: Path) -> list[Path]:
    written = []
    for part, held in sorted(recorded.items()):
        if not held.sources:
            continue
        path = Path(where) / f"{part}shapes.json"
        path.write_text(
            json.dumps(
                {
                    "note": NOTE,
                    "part": part,
                    "producedBy": PRODUCED_BY,
                    "readFrom": held.sources,
                    "shapes": held.ordered(),
                },
                indent=2,
            )
            + "\n"
        )
        written.append(path)
    return written


def labelled(counted: Mapping[str, int]) -> str:
    tally: collections.Counter[str] = collections.Counter()
    for shape, seen in counted.items():
        for step in shapes.parse(shape):
            tally[step.label] += seen
    return ", ".join(f"{tally[label]} {label}" for label in LABELS)


def lines_for(recorded: Mapping[str, "Recorded"], written: Collection[Path]) -> list[str]:
    said = []
    for part, held in sorted(recorded.items()):
        said.append(
            f"  {part}: {len(held.counted)} shapes from {len(held.sources)} cartridges"
            f", {sum(held.counted.values())} sites"
        )
        said.append(f"      accesses by width: {labelled(held.counted)}")
        for one in held.sources:
            said.append(f"      {one['name']}  {one['layout']}, {one['shapes']} shapes")
        for name in held.silent:
            said.append(f"      {name}  said nothing to the {part}")
    said.append(f"  wrote {len(written)} files")
    return said


def main(
    argv: Iterable[str] = (),
    manifest: Mapping[str, Any] | None = None,
    reading: Reading = reading,
    where: Path | str | None = None,
    say: Callable[[str], object] = print,
) -> int:
    if manifest is None:
        held = json.loads(MANIFEST.read_text())
        assert isinstance(held, dict), f"{MANIFEST} does not hold an object"
        manifest = held
    where = Path(__file__).resolve().parent if where is None else Path(where)

    recorded = gather(manifest, reading, keep_silent=True)
    if not recorded:
        say(
            "  nothing to read: no cartridge named in the manifest is on this machine."
            " A copy you already own goes in cartridges/, or wherever"
            " SNES_CARTRIDGE_DIR points"
        )
        return 2

    written = write(recorded, where)
    for line in lines_for(recorded, written):
        say(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
