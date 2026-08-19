"""A cartridge its owner supplies, identified before it is read.

The firmware beside this says what the part computes. A cartridge says how it is
asked: how many bytes go each way for each command, in what order, and how wide
each transfer is. None of that is written down anywhere else, because the game and
the part were built together and only ever had to agree with each other.

So the game is the authority on its own protocol, and the way to consult it is to
read the routine inside it that drives the part. That is the only reason a
cartridge is opened here, and no part of one is ever carried.

Every file is checked against all four of its digests rather than only the one
that decides. A file can be the right length under the right name and still be a
bad dump, and a manifest that publishes a crc32 beside a sha256 and then never
looks at the crc32 is publishing decoration.

Only retail releases are listed. A modified release can carry altered code, and a
driver routine read out of one would describe somebody's edit rather than the part.
"""

import hashlib
import json
import os
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MANIFEST = ROOT / "cartridges.manifest.json"

DIRECTORY_VARIABLE = "SNES_CARTRIDGE_DIR"

DEFAULT_DIRECTORY = ROOT / "cartridges"

READABLE_SUFFIXES = (".sfc", ".smc")

DIGESTS = ("crc32", "md5", "sha1", "sha256")

DECIDES = "sha256"

DIGEST_WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}

WHY_NOT = (
    "no cartridge was found: this reads the routine inside a game that drives the"
    " part, and a game belongs to whoever made it, so a copy you already own goes"
    " in the cartridges directory of this repository or wherever"
    f" {DIRECTORY_VARIABLE} points"
)


class Unrecognised(Exception):
    pass


class Corrupt(Exception):
    pass


class Identity:
    """What a cartridge turned out to be."""

    def __init__(self, name, title, size, chipset, sha256):
        self.name = name
        self.title = title
        self.size = size
        self.chipset = chipset
        self.sha256 = sha256

    def __repr__(self):
        return f"<Identity {self.name}, {self.title}, {self.size} bytes>"


def digests_of(image):
    """Every digest this manifest publishes, for one file."""
    return {
        "crc32": f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }


def manifest(path=None):
    with Path(path or MANIFEST).open() as handle:
        return json.load(handle)


def directory(environment=None):
    """Where cartridges are looked for: what was named, or the ignored folder here."""
    named = (environment if environment is not None else os.environ).get(DIRECTORY_VARIABLE)
    return Path(named) if named else DEFAULT_DIRECTORY


def identify(image, catalogue=None):
    """Which cartridge this is, or why it is not one the manifest knows."""
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


def _confirm(entry, found):
    """Every other digest the manifest publishes has to agree as well.

    Reaching here means the deciding digest already matched, so a disagreement is
    not a different file: it is a manifest that contradicts itself, which is worth
    saying out loud rather than passing over.
    """
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


def _diagnosis(image, found, entries):
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


def found(where=None, catalogue=None):
    """Every cartridge on disk the manifest recognises, with the file it came from."""
    where = Path(where) if where is not None else directory()
    if not where.is_dir():
        return

    for path in sorted(where.iterdir()):
        if path.suffix.lower() not in READABLE_SUFFIXES or not path.is_file():
            continue
        try:
            yield identify(path.read_bytes(), catalogue), path
        except Unrecognised:
            continue


def present(where=None, catalogue=None):
    return tuple(found(where, catalogue))
