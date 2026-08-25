"""Read what every cartridge on this machine says to its part, and write it down.

A shape is the sequence of accesses one routine makes and how wide each one was.
Nothing derives it: it is ordinary 65816 code sitting in the game, and the tool
that reads it is a submodule at the root of this repository.

One cartridge per part is not enough, and that is the reason this exists. The
DSP-1 shipped in more than twenty games and each driver asks differently: Super
Mario Kart takes a command and a burst, Pilotwings polls between words, Suzuka 8
Hours writes three words before it reads one. A part settled against one of those
is settled against one driver, not against the part. So every cartridge present is
read, the shapes are pooled per part, and each one records how many cartridges
used it. A shape two dozen games agree on is the part's protocol. A shape one game
uses is that game's corner, and it is exactly where a model is likely to be wrong.

Nothing a cartridge carries is written out. A shape names accesses and widths, and
carries no byte of the payload that travelled through them, so no set of shapes
reconstructs anything. Every cartridge is confirmed against all four of its
published digests before a byte of it is disassembled, because a file that is not
the one it claims to be would be read anyway and would describe a protocol
nobody's hardware has.
"""

import json
import sys
from collections.abc import Callable, Collection, Iterable, Mapping
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent

DRIVER = ROOT / "snes-driver-python"

CARTRIDGES = ROOT / "cartridges"

MANIFEST = ROOT / "cartridges.manifest.json"

PRODUCED_BY = "https://github.com/gufranco/snes-driver-python"

PART_FAMILY = "dsp"
"""What the reading tool calls this family, which is what decides the window."""

NOTE = (
    "The shapes real cartridges use to drive this part: which accesses each routine"
    " makes, in what order, and how wide each one was. No byte any cartridge carries"
    " is recorded here and none can be recovered from this. Read out of the games"
    " named below, every one of them confirmed against all four of its digests first."
)


class Recorded:
    """Everything read for one part, and where each shape came from."""

    def __init__(self, part: str) -> None:
        self.part = part
        self.counted: dict[str, int] = {}
        self.cartridges: dict[str, int] = {}
        self.sources: list[dict[str, Any]] = []
        self.silent: list[str] = []

    def add(self, identity: Mapping[str, Any], layout: str, shapes: Mapping[str, int]) -> None:
        """One cartridge's shapes pooled into this part's."""
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
        """Longest shape first, and the busier of two equal lengths before the other.

        Longest first because a long shape exercises more of the part than a short
        one, and a sweep that runs out of budget should have spent it on those.
        """
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


def _default_shapes(image: bytes, window: object) -> dict[str, int]:  # pragma: no cover
    _reach()
    from snesdriver import conversation

    found = conversation.shapes(image, window)
    assert isinstance(found, dict)
    return found


def _default_window(layout: str) -> object:  # pragma: no cover
    _reach()
    from snesdriver import windows

    return windows.window_for(PART_FAMILY, layout)


def _reach() -> None:
    """Put the reading tool and the mapper it uses where they can be imported."""
    for where in (DRIVER, DRIVER / "snes-mapper-python"):
        if str(where) not in sys.path:
            sys.path.insert(0, str(where))


Reading = Callable[[str], tuple[str, dict[str, int]] | None]
"""How one cartridge is read, so a test can hand over something already read."""


def reading(
    name: str,
    where: Path = CARTRIDGES,
    confirm: Callable[[bytes], object] = _default_confirm,
    layout_of: Callable[[bytes], str] = _default_layout,
    shapes_of: Callable[[bytes, Any], dict[str, int]] = _default_shapes,
    window_of: Callable[[str], object] = _default_window,
) -> tuple[str, dict[str, int]] | None:
    """What one cartridge says, or nothing when it is not on this machine.

    The confirmation runs before the disassembly rather than after it. A file that
    is not the one it is named as would be read anyway, and the shapes would then
    describe somebody's edit rather than a shipped protocol.
    """
    path = Path(where) / name
    if not path.exists():
        return None
    image = path.read_bytes()
    confirm(image)
    layout = layout_of(image)
    return layout, shapes_of(image, window_of(layout))


def gather(
    manifest: Mapping[str, Any],
    reading: Reading = reading,
    keep_silent: bool = False,
) -> dict[str, "Recorded"]:
    """Every cartridge present, read and pooled under the part it drives."""
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
    """One file per part, each naming every cartridge it was read from."""
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


def lines_for(recorded: Mapping[str, "Recorded"], written: Collection[Path]) -> list[str]:
    """What was read and what was written, in the order a reader wants it."""
    said = []
    for part, held in sorted(recorded.items()):
        said.append(
            f"  {part}: {len(held.counted)} shapes from {len(held.sources)} cartridges"
            f", {sum(held.counted.values())} sites"
        )
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
    """Read every cartridge on this machine and write the shapes it says."""
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
