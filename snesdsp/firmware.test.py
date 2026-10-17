import hashlib
import json
import sys
import tomllib
import unittest
import zlib
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

sys.path.append(str(ROOT / "nec-upd7725-96050-python"))

from upd7725 import MODELS as PROCESSORS  # noqa: E402

PACKAGE = ROOT / "snesdsp"

MANIFEST = PACKAGE / "artifacts.manifest.json"

DIGEST_WIDTHS = {"crc32": 8, "md5": 32, "sha1": 40, "sha256": 64}

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024


def shipped() -> dict[str, Any]:
    held = json.loads(MANIFEST.read_text())
    assert isinstance(held, dict), f"{MANIFEST} does not hold an object"
    return held


def every_accepted() -> Iterator[tuple[str, dict[str, Any]]]:
    for entry in shipped()["artifacts"]:
        for accepted in entry["accepted"]:
            yield entry["part"], accepted


def an_image(filler: int = 0xAB) -> bytes:
    return bytes([filler]) * (PROGRAM_WORDS * 3 + TABLE_WORDS * 2)


def a_catalogue(image: bytes, part: str = "made-up", **extra: object) -> dict[str, Any]:
    accepted = {"revision": "one", "sha256": hashlib.sha256(image).hexdigest(), **extra}
    return {
        "artifacts": [
            {
                "part": part,
                "processor": "upd7725",
                "bytes": len(image),
                "programWords": PROGRAM_WORDS,
                "dataWords": TABLE_WORDS,
                "accepted": [accepted],
                "badDumps": [],
            }
        ]
    }


def with_bad_dumps(image: bytes, part: str, broken: bytes) -> dict[str, Any]:
    held = a_catalogue(image, part)
    held["artifacts"][0]["badDumps"] = [{"sha256": hashlib.sha256(broken).hexdigest()}]
    return held


def an_identity() -> SimpleNamespace:
    return SimpleNamespace(
        part="dsp1",
        processor="upd7725",
        revision="MADE UP",
        program_words=PROGRAM_WORDS,
        data_words=TABLE_WORDS,
    )


class RefusalCase(unittest.TestCase):
    def refusal(self, image: bytes, catalogue: dict[str, Any]) -> str:
        with self.assertRaises(snesdsp.Unrecognised) as refused:
            snesdsp.identify(image, catalogue)
        return str(refused.exception)


class ShippedManifestTest(RefusalCase):
    def test_the_manifest_lives_inside_the_package(self) -> None:
        # Arrange
        package = Path(snesdsp.__file__).resolve().parent

        # Act
        found = (package / MANIFEST.name).is_file()

        # Assert
        self.assertTrue(found)

    def test_and_the_packaging_declares_it_as_package_data(self) -> None:
        # Arrange
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

        # Act
        declared = pyproject["tool"]["setuptools"]["package-data"]["snesdsp"]

        # Assert
        self.assertEqual(declared, [MANIFEST.name])

    def test_and_identify_reads_it_with_no_catalogue_handed_in(self) -> None:
        # Arrange
        image = b"\x00" * 7
        expected = self.refusal(image, shipped())

        # Act
        with self.assertRaises(snesdsp.Unrecognised) as refused:
            snesdsp.identify(image)

        # Assert
        self.assertEqual(str(refused.exception), expected)


class ManifestTest(unittest.TestCase):
    def test_the_manifest_names_every_image_the_parts_run(self) -> None:
        # Arrange
        images = {model.image for model in snesdsp.MODELS.values()}

        # Act
        named = {entry["part"] for entry in shipped()["artifacts"]}

        # Assert
        self.assertEqual(named, images)
        self.assertEqual(named, {"dsp1", "dsp1b", "dsp2", "dsp3", "dsp4"})

    def test_each_part_names_a_processor_that_exists(self) -> None:
        # Arrange
        entries = shipped()["artifacts"]

        # Act
        named = {entry["processor"] for entry in entries}

        # Assert
        self.assertEqual(named - set(PROCESSORS), set())

    def test_each_part_names_a_size_its_two_stores_add_up_to(self) -> None:
        # Arrange
        entries = shipped()["artifacts"]

        # Act
        wrong = [
            entry["part"]
            for entry in entries
            if entry["programWords"] * 3 + entry["dataWords"] * 2 != entry["bytes"]
        ]

        # Assert
        self.assertEqual(wrong, [])

    def test_every_accepted_image_carries_all_four_digests_at_their_widths(self) -> None:
        # Arrange
        accepted = list(every_accepted())

        # Act
        widths = {
            (part, name): len(one.get(name, "")) for part, one in accepted for name in DIGEST_WIDTHS
        }

        # Assert
        self.assertEqual(
            widths,
            {(part, name): width for part, _ in accepted for name, width in DIGEST_WIDTHS.items()},
        )

    def test_the_manifest_carries_no_run_of_hex_longer_than_a_digest(self) -> None:
        # Arrange
        text = MANIFEST.read_text()

        # Act
        runs = [
            word
            for word in text.replace('"', " ").split()
            if len(word) > 64 and all(letter in "0123456789abcdefABCDEF" for letter in word)
        ]

        # Assert
        self.assertEqual(runs, [])

    def test_every_part_declares_its_bad_dumps_and_its_provenance(self) -> None:
        # Arrange
        held = shipped()
        kinds = held["provenance"]["kinds"]

        # Act
        missing = [
            part
            for part, one in every_accepted()
            if one["provenance"]["kind"] not in kinds or "verifiedOn" not in one["provenance"]
        ] + [entry["part"] for entry in held["artifacts"] if "badDumps" not in entry]

        # Assert
        self.assertEqual(missing, [])

    def test_the_weakest_kind_says_that_it_is_the_weakest(self) -> None:
        # Arrange
        kinds = shipped()["provenance"]["kinds"]

        # Act
        local = kinds["localCopy"]

        # Assert
        self.assertIn("weakest", local)

    def test_the_manifest_names_sha256_as_the_digest_that_decides(self) -> None:
        # Arrange
        held = str(shipped()["decides"])

        # Act
        named = ("sha256" in held, "decides anything on its own" in held)

        # Assert
        self.assertEqual(named, (True, True))


class IdentifyTest(RefusalCase):
    def test_an_image_the_catalogue_knows_is_named_with_its_revision(self) -> None:
        # Arrange
        image = an_image()

        # Act
        found = snesdsp.identify(image, a_catalogue(image))

        # Assert
        self.assertEqual(
            (found.part, found.revision, found.processor, found.program_words, found.data_words),
            ("made-up", "one", "upd7725", PROGRAM_WORDS, TABLE_WORDS),
        )

    def test_an_identity_prints_as_the_part_and_revision_it_names(self) -> None:
        # Arrange
        image = an_image()
        found = snesdsp.identify(image, a_catalogue(image))

        # Act
        printed = repr(found)

        # Assert
        self.assertEqual(printed, "<Identity made-up one on upd7725>")

    def test_an_image_of_a_known_length_and_the_wrong_content_says_so(self) -> None:
        # Arrange
        catalogue = a_catalogue(an_image())

        # Act
        said = self.refusal(an_image(0xCD), catalogue)

        # Assert
        self.assertIn("8192 bytes, the length of made-up, but its content is altered", said)

    def test_an_image_of_no_length_the_catalogue_knows_says_that_instead(self) -> None:
        # Arrange
        catalogue = a_catalogue(an_image())

        # Act
        said = self.refusal(b"\x00" * 7, catalogue)

        # Assert
        self.assertIn("7 bytes, and the manifest knows no part of that length", said)
        self.assertIn("(it knows 8192)", said)

    def test_an_empty_catalogue_says_it_knows_no_length_at_all(self) -> None:
        # Arrange
        catalogue: dict[str, Any] = {"artifacts": []}

        # Act
        said = self.refusal(b"\x00" * 7, catalogue)

        # Assert
        self.assertIn("(it knows none)", said)

    def test_the_refusal_always_carries_the_digest_that_was_computed(self) -> None:
        # Arrange
        image = b"\x00" * 7

        # Act
        said = self.refusal(image, {"artifacts": []})

        # Assert
        self.assertIn(hashlib.sha256(image).hexdigest(), said)


class RepairTest(RefusalCase):
    def test_a_file_carrying_a_copier_header_is_told_to_strip_it(self) -> None:
        # Arrange
        image = an_image()

        # Act
        said = self.refusal(b"H" * 512 + image, a_catalogue(image, "dsp9"))

        # Assert
        self.assertIn("strip the first 512 bytes, which is a copier header", said)
        self.assertIn("turns it into dsp9", said)
        self.assertIn("checked rather than guessed", said)

    def test_a_file_with_a_trailer_is_told_to_strip_the_end(self) -> None:
        # Arrange
        image = an_image()

        # Act
        said = self.refusal(image + b"T" * 512, a_catalogue(image))

        # Assert
        self.assertIn("strip the last 512 bytes", said)

    def test_a_file_with_its_bytes_in_the_wrong_order_is_told_to_swap_them(self) -> None:
        # Arrange
        image = bytes(range(256)) * 32
        swapped = bytes(image[at ^ 1] for at in range(len(image)))

        # Act
        said = self.refusal(swapped, a_catalogue(image))

        # Assert
        self.assertIn("swap every pair of bytes", said)

    def test_a_file_nothing_helps_is_offered_no_repair(self) -> None:
        # Arrange
        image = an_image()

        # Act
        said = self.refusal(b"Z" * len(image), a_catalogue(image))

        # Assert
        self.assertNotIn("checked rather than guessed", said)

    def test_a_file_too_short_to_strip_is_offered_no_repair(self) -> None:
        # Arrange
        image = an_image()

        # Act
        said = self.refusal(b"Z" * 8, a_catalogue(image))

        # Assert
        self.assertIn("8 bytes, and the manifest knows no part of that length", said)


class BadDumpTest(RefusalCase):
    def test_a_declared_bad_dump_is_named_as_damaged_with_its_part(self) -> None:
        # Arrange
        broken = an_image(0x00)
        catalogue = with_bad_dumps(an_image(), "dsp9", broken)

        # Act
        said = self.refusal(broken, catalogue)

        # Assert
        self.assertIn("this is a known bad dump of dsp9", said)

    def test_an_undeclared_file_is_not_called_a_bad_dump(self) -> None:
        # Arrange
        catalogue = with_bad_dumps(an_image(), "dsp9", an_image(0x01))

        # Act
        said = self.refusal(an_image(0x00), catalogue)

        # Assert
        self.assertNotIn("known bad dump", said)


class CrossCheckTest(unittest.TestCase):
    def test_a_crc32_that_disagrees_is_refused_by_name(self) -> None:
        # Arrange
        image = an_image()
        catalogue = a_catalogue(image, crc32="0" * 8)

        # Act
        with self.assertRaises(snesdsp.Corrupt) as refused:
            snesdsp.identify(image, catalogue)

        # Assert
        self.assertIn("matches on sha256 but not on crc32", str(refused.exception))

    def test_an_md5_that_disagrees_is_refused_by_name(self) -> None:
        # Arrange
        image = an_image()
        catalogue = a_catalogue(image, md5="0" * 32)

        # Act
        with self.assertRaises(snesdsp.Corrupt) as refused:
            snesdsp.identify(image, catalogue)

        # Assert
        self.assertIn("not on md5", str(refused.exception))

    def test_a_sha1_that_disagrees_is_refused_by_name(self) -> None:
        # Arrange
        image = an_image()
        catalogue = a_catalogue(image, sha1="0" * 40)

        # Act
        with self.assertRaises(snesdsp.Corrupt) as refused:
            snesdsp.identify(image, catalogue)

        # Assert
        self.assertIn("not on sha1", str(refused.exception))

    def test_an_image_every_digest_agrees_on_is_accepted(self) -> None:
        # Arrange
        image = an_image()
        catalogue = a_catalogue(
            image,
            crc32=f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
            md5=hashlib.md5(image).hexdigest(),
            sha1=hashlib.sha1(image).hexdigest(),
        )

        # Act
        found = snesdsp.identify(image, catalogue)

        # Assert
        self.assertEqual(found.revision, "one")


class DigestTest(unittest.TestCase):
    def test_every_digest_is_the_one_the_standard_library_computes(self) -> None:
        # Arrange
        image = b"nothing anybody owns"

        # Act
        found = snesdsp.digests_of(image)

        # Assert
        self.assertEqual(
            found,
            {
                "crc32": f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
                "md5": hashlib.md5(image).hexdigest(),
                "sha1": hashlib.sha1(image).hexdigest(),
                "sha256": hashlib.sha256(image).hexdigest(),
            },
        )

    def test_a_crc_with_a_leading_zero_keeps_its_eight_digits(self) -> None:
        # Arrange
        image = b"\x00" * 13

        # Act
        crc = snesdsp.digests_of(image)["crc32"]

        # Assert
        self.assertEqual(crc, "0f744682")


class LoadTest(unittest.TestCase):
    def test_a_loaded_image_fills_the_program_store_three_bytes_a_word(self) -> None:
        # Arrange
        image = bytes(range(256)) * 24 + bytes(TABLE_WORDS * 2)

        # Act
        part = snesdsp.Chip("dsp1", image=image, identity=an_identity(), boot=0)

        # Assert
        self.assertEqual(part.core.stores.program[0], 0x000102)

    def test_and_the_table_after_it_two_bytes_a_word(self) -> None:
        # Arrange
        image = bytes(PROGRAM_WORDS * 3) + bytes([0xAA, 0xBB]) * TABLE_WORDS

        # Act
        part = snesdsp.Chip("dsp1", image=image, identity=an_identity(), boot=0)

        # Assert
        self.assertEqual(part.core.stores.table[0], 0xAABB)

    def test_an_image_two_bytes_short_is_refused_as_the_readme_shows(self) -> None:
        # Arrange
        image = an_image()[:-2]

        # Act
        with self.assertRaises(snesdsp.WrongShape) as refused:
            snesdsp.Chip("dsp1", image=image, identity=an_identity())

        # Assert
        self.assertEqual(
            str(refused.exception), "a upd7725 takes 8192 bytes of firmware and this is 8190"
        )


if __name__ == "__main__":
    unittest.main()
