import hashlib
import json
import os
import zlib
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent

MANIFEST = ROOT / "cartridges.manifest.json"

DIRECTORY_VARIABLE = "SNES_CARTRIDGE_DIR"

DEFAULT_DIRECTORY = ROOT / "external" / "cartridges"

ALONGSIDE = ROOT.parent / "external" / "cartridges"

READABLE_SUFFIXES = (".sfc", ".smc")

DIGESTS = ("crc32", "md5", "sha1", "sha256")

DECIDES = "sha256"

DIGEST_WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}

WHY_NOT = (
    "no cartridge was found: this reads the routine inside a game that drives the"
    " part, and a game belongs to whoever made it, so a copy you already own goes"
    " in the cartridges directory of this repository, or of the project this one"
    f" sits inside, or wherever {DIRECTORY_VARIABLE} points"
)


class Unrecognised(Exception):
    pass


class Corrupt(Exception):
    pass


class Identity:
    def __init__(self, name: str, title: str, size: int, chipset: str, sha256: str) -> None:
        self.name = name
        self.title = title
        self.size = size
        self.chipset = chipset
        self.sha256 = sha256

    @override
    def __repr__(self) -> str:
        return f"<Identity {self.name}, {self.title}, {self.size} bytes>"


def digests_of(image: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def manifest(path: Path | str | None = None) -> dict[str, Any]:
    with Path(path or MANIFEST).open() as handle:
        held = json.load(handle)
    assert isinstance(held, dict), f"{path or MANIFEST} does not hold an object"
    return held


DIRECTORY_VARIABLES = (DIRECTORY_VARIABLE,)


def directories(environment: Mapping[str, str] | None = None) -> tuple[Path, ...]:
    held = environment if environment is not None else os.environ
    wanted = [
        Path(where)
        for variable in DIRECTORY_VARIABLES
        for where in held.get(variable, "").split(os.pathsep)
        if where
    ]
    wanted += [ALONGSIDE, DEFAULT_DIRECTORY]
    seen: list[Path] = []
    for where in wanted:
        if where not in seen:
            seen.append(where)
    return tuple(seen)


def directory(
    environment: Mapping[str, str] | None = None, places: Iterable[Path] | None = None
) -> Path:
    named = (environment if environment is not None else os.environ).get(DIRECTORY_VARIABLE)
    if named:
        return Path(named)
    for place in places if places is not None else directories(environment):
        if place.is_dir():
            return place
    return DEFAULT_DIRECTORY


def identify(image: bytes, catalogue: Mapping[str, Any] | None = None) -> "Identity":
    found = digests_of(image)
    entries = (catalogue or manifest())["cartridges"]

    for entry in entries:
        if entry[DECIDES] != found[DECIDES]:
            continue
        _confirm(entry, found)
        return Identity(
            name=entry["name"],
            title=entry["title"],
            size=entry["bytes"],
            chipset=entry["chipset"],
            sha256=entry[DECIDES],
        )

    raise Unrecognised(_diagnosis(image, found, entries))


def _confirm(entry: Mapping[str, Any], found: Mapping[str, str]) -> None:
    for name in DIGESTS:
        if name == DECIDES or name not in entry:
            continue
        if entry[name].lower() != found[name]:
            raise Corrupt(
                f"{entry['name']} matches on {DECIDES} but not on {name}:"
                f" the manifest says {entry[name]} and the file gives {found[name]}."
                " A manifest that disagrees with itself was edited by hand or built"
                " from two different copies"
            )


def _diagnosis(image: bytes, found: Mapping[str, str], entries: Iterable[Mapping[str, Any]]) -> str:
    same_length = [entry for entry in entries if entry["bytes"] == len(image)]

    if same_length:
        names = ", ".join(entry["name"] for entry in same_length[:3])
        return (
            f"this is {len(image)} bytes, the length of {names}, but its content is"
            f" altered: its sha256 is {found['sha256']} and no cartridge listed has"
            " that. A file of the right length with the wrong content is usually a"
            " modified release, a translation, or a bad dump"
        )

    return (
        f"this is {len(image)} bytes and no cartridge listed has that length."
        f" Its sha256 is {found['sha256']}, its crc32 is {found['crc32']}."
        " A file a few hundred bytes longer than a round number usually carries a"
        " copier header"
    )


def found(
    where: Path | str | None = None, catalogue: Mapping[str, Any] | None = None
) -> "Iterator[tuple[Identity, Path]]":
    at = Path(where) if where is not None else directory()
    if not at.is_dir():
        return

    for path in sorted(at.iterdir()):
        if path.suffix.lower() not in READABLE_SUFFIXES or not path.is_file():
            continue
        try:
            yield identify(path.read_bytes(), catalogue), path
        except Unrecognised:
            continue


def present(
    where: Path | str | None = None, catalogue: Mapping[str, Any] | None = None
) -> "tuple[tuple[Identity, Path], ...]":
    return tuple(found(where, catalogue))
