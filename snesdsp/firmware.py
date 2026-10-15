from __future__ import annotations

import hashlib
import json
import os
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from .errors import Corrupt, Unrecognised, WrongShape

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Iterable, Iterator, Mapping
    from typing import Any as Cpu

ROOT = Path(__file__).resolve().parent.parent

MANIFEST = Path(__file__).resolve().parent / "artifacts.manifest.json"

DIRECTORY_VARIABLE = "SNES_DSP_FIRMWARE_DIR"

SHARED_DIRECTORY_VARIABLE = "UPD7725_FIRMWARE_DIR"

DIRECTORY_VARIABLES = (DIRECTORY_VARIABLE, SHARED_DIRECTORY_VARIABLE)

DEFAULT_DIRECTORY = ROOT / "firmware"

ALONGSIDE = ROOT.parent / "firmware"

PROGRAM_BYTES_PER_WORD = 3

TABLE_BYTES_PER_WORD = 2

READABLE_SUFFIXES = (".bin", ".rom")

DIGESTS = ("crc32", "md5", "sha1", "sha256")

DECIDES = "sha256"

DIGEST_WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}


def digests_of(image: bytes) -> dict[str, str]:
    return {
        "crc32": f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }


class Identity:
    __slots__ = ("data_words", "part", "processor", "program_words", "revision")

    def __init__(
        self,
        part: str,
        processor: str,
        revision: str,
        program_words: int,
        data_words: int,
    ) -> None:
        self.part = part
        self.processor = processor
        self.revision = revision
        self.program_words = program_words
        self.data_words = data_words

    @override
    def __repr__(self) -> str:
        return f"<Identity {self.part} {self.revision} on {self.processor}>"


def manifest(path: Path | str | None = None) -> dict[str, Any]:
    with Path(path or MANIFEST).open() as handle:
        held: dict[str, Any] = json.load(handle)
    return held


def directory(environment: Mapping[str, str] | None = None) -> Path:
    return directories(environment)[0]


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


def identify(image: bytes, catalogue: dict[str, Any] | None = None) -> Identity:
    found = digests_of(image)
    entries = (catalogue or manifest())["artifacts"]

    for entry in entries:
        for accepted in entry["accepted"]:
            if accepted[DECIDES] != found[DECIDES]:
                continue
            _confirm(entry, accepted, found)
            return Identity(
                part=entry["part"],
                processor=entry["processor"],
                revision=accepted["revision"],
                program_words=entry["programWords"],
                data_words=entry["dataWords"],
            )

    raise Unrecognised(_diagnosis(image, found[DECIDES], entries))


def _confirm(entry: dict[str, Any], accepted: dict[str, Any], found: dict[str, str]) -> None:
    for name in DIGESTS:
        if name == DECIDES or name not in accepted:
            continue
        if accepted[name].lower() != found[name]:
            raise Corrupt(
                f"{entry['part']} matches on {DECIDES} but not on {name}:"
                f" the manifest says {accepted[name]} and the file gives {found[name]}."
                " A manifest that disagrees with itself was edited by hand or built"
                " from two different copies"
            )


REPAIRS: tuple[tuple[str, Callable[[bytes], bytes]], ...] = (
    (
        "strip the first 512 bytes, which is a copier header",
        lambda image: image[512:],
    ),
    (
        "strip the last 512 bytes",
        lambda image: image[:-512] if len(image) > 512 else image,
    ),
    (
        "swap every pair of bytes, which undoes a byte-order change",
        lambda image: bytes(image[at ^ 1] for at in range(len(image) - len(image) % 2)),
    ),
)


def repairs(image: bytes, entries: Iterable[dict[str, Any]]) -> list[tuple[str, str]]:
    accepted = {one[DECIDES]: entry["part"] for entry in entries for one in entry["accepted"]}
    found = []
    for how, apply in REPAIRS:
        try:
            changed = apply(image)
        except (IndexError, ValueError):  # pragma: no cover
            continue
        if not changed or changed == image:
            continue
        digest = hashlib.sha256(changed).hexdigest()
        if digest in accepted:
            found.append((how, accepted[digest]))
    return found


def _diagnosis(image: bytes, digest: str, entries: list[dict[str, Any]]) -> str:
    fixable = repairs(image, entries)
    if fixable:
        how, part = fixable[0]
        return (
            f"this is not a file the manifest knows, but {how} turns it into"
            f" {part}. That was checked rather than guessed: the change was applied"
            f" and the result matched the published sha256 for {part}. Do it to your"
            " own copy and try again"
        )

    known_bad = [
        entry
        for entry in entries
        for one in entry.get("badDumps", ())
        if one.get(DECIDES) == digest
    ]
    if known_bad:
        return (
            f"this is a known bad dump of {known_bad[0]['part']}: its sha256"
            f" {digest} is recorded in the manifest as damaged rather than as"
            " unrecognised. The copy is the problem, not the name it was given"
        )

    same_length = [entry for entry in entries if entry["bytes"] == len(image)]

    if same_length:
        parts = ", ".join(entry["part"] for entry in same_length)
        return (
            f"this is {len(image)} bytes, the length of {parts}, but its content is altered:"
            f" its sha256 is {digest} and no accepted revision has that."
            " A file of the right length with the wrong content is usually a different"
            " revision than the one it is named after, or a bad dump"
        )

    lengths = ", ".join(sorted({str(entry["bytes"]) for entry in entries})) or "none"
    return (
        f"this is {len(image)} bytes, and the manifest knows no part of that length"
        f" (it knows {lengths}). Its sha256 is {digest}."
        " A file much larger than any of those is usually an archive rather than the"
        " image inside it, and one slightly larger usually carries a header"
    )


def load(chip: Cpu, image: bytes, identity: Identity | None = None) -> Cpu:
    program_words = identity.program_words if identity else len(chip.stores.program)
    data_words = identity.data_words if identity else len(chip.stores.table)
    wanted = program_words * PROGRAM_BYTES_PER_WORD + data_words * TABLE_BYTES_PER_WORD

    if len(image) != wanted:
        raise WrongShape(
            f"a {chip.model.name} takes {wanted} bytes of firmware and this is {len(image)}"
        )

    split = program_words * PROGRAM_BYTES_PER_WORD
    chip.stores.load_program(image[:split])
    chip.stores.load_table(image[split:])
    return chip


def found(
    where: Path | str | None = None, catalogue: dict[str, Any] | None = None
) -> Iterator[tuple[Identity, Path]]:
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


def search(
    places: Iterable[Path] | None = None, catalogue: dict[str, Any] | None = None
) -> Iterator[tuple[Identity, Path]]:
    seen = set()
    for where in places if places is not None else directories():
        for identity, path in found(where, catalogue):
            if identity.part in seen:
                continue
            seen.add(identity.part)
            yield identity, path
