import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

OWN_VARIABLE = "SNES_DSP_FIRMWARE_DIR"

SHARED_VARIABLE = "UPD7725_FIRMWARE_DIR"

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024


def an_image() -> bytes:
    return b"\xab" * (PROGRAM_WORDS * 3 + TABLE_WORDS * 2)


def a_catalogue(image: bytes) -> dict[str, Any]:
    return {
        "artifacts": [
            {
                "part": "made-up",
                "processor": "upd7725",
                "bytes": len(image),
                "programWords": PROGRAM_WORDS,
                "dataWords": TABLE_WORDS,
                "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                "badDumps": [],
            }
        ]
    }


def a_directory_holding(**files: bytes) -> Path:
    where = Path(tempfile.mkdtemp())
    for name, content in files.items():
        (where / name).write_bytes(content)
    return where


class SearchTest(unittest.TestCase):
    def test_a_directory_with_nothing_in_it_yields_nothing(self) -> None:
        # Arrange
        where = a_directory_holding()

        # Act
        found = list(snesdsp.search([where], {"artifacts": []}))

        # Assert
        self.assertEqual(found, [])

    def test_a_directory_that_is_not_there_yields_nothing_either(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "absent"

        # Act
        found = list(snesdsp.search([where], {"artifacts": []}))

        # Assert
        self.assertEqual(found, [])

    def test_a_file_the_catalogue_knows_is_yielded_with_its_path(self) -> None:
        # Arrange
        image = an_image()
        where = a_directory_holding(**{"made-up.ROM": image})

        # Act
        found = [(one.part, path.name) for one, path in snesdsp.search([where], a_catalogue(image))]

        # Assert
        self.assertEqual(found, [("made-up", "made-up.ROM")])

    def test_files_that_are_not_images_or_are_not_known_are_passed_over(self) -> None:
        # Arrange
        image = an_image()
        where = a_directory_holding(
            **{"README.md": b"notes", "made-up.txt": image, "nonsense.bin": b"\x00" * 99}
        )
        (where / "folder.bin").mkdir()

        # Act
        found = list(snesdsp.search([where], a_catalogue(image)))

        # Assert
        self.assertEqual(found, [])

    def test_searching_finds_an_image_in_any_directory(self) -> None:
        # Arrange
        image = an_image()
        places = [a_directory_holding(), a_directory_holding(**{"made-up.bin": image})]

        # Act
        found = [one.part for one, _ in snesdsp.search(places, a_catalogue(image))]

        # Assert
        self.assertEqual(found, ["made-up"])

    def test_a_directory_named_by_a_string_is_searched_too(self) -> None:
        # Arrange
        image = an_image()
        where = str(a_directory_holding(**{"made-up.bin": image}))

        # Act
        found = [one.part for one, _ in snesdsp.search([where], a_catalogue(image))]

        # Assert
        self.assertEqual(found, ["made-up"])

    def test_the_first_directory_holding_a_part_is_the_one_that_answers(self) -> None:
        # Arrange
        image = an_image()
        places = [
            a_directory_holding(**{"from-first.bin": image}),
            a_directory_holding(**{"from-second.bin": image}),
        ]

        # Act
        found = [path.name for _, path in snesdsp.search(places, a_catalogue(image))]

        # Assert
        self.assertEqual(found, ["from-first.bin"])

    def test_with_no_places_named_it_searches_the_directories_in_order(self) -> None:
        # Arrange
        image = an_image()
        where = a_directory_holding(**{"made-up.bin": image})
        named = mock.patch.dict(os.environ, {OWN_VARIABLE: str(where)})
        named.start()
        self.addCleanup(named.stop)

        # Act
        found = [path for _, path in snesdsp.search(catalogue=a_catalogue(image))]

        # Assert
        self.assertEqual(found, [where / "made-up.bin"])


class SearchPathTest(unittest.TestCase):
    def test_with_nothing_named_it_looks_beside_the_checkout_then_inside_it(self) -> None:
        # Arrange
        environment: dict[str, str] = {}

        # Act
        found = snesdsp.directories(environment)

        # Assert
        self.assertEqual(found, (ROOT.parent / "firmware", ROOT / "firmware"))

    def test_a_named_directory_is_looked_at_before_either(self) -> None:
        # Arrange
        environment = {OWN_VARIABLE: "/x"}

        # Act
        found = snesdsp.directories(environment)

        # Assert
        self.assertEqual(found, (Path("/x"), ROOT.parent / "firmware", ROOT / "firmware"))

    def test_more_than_one_can_be_named_and_an_empty_entry_is_passed_over(self) -> None:
        # Arrange
        environment = {OWN_VARIABLE: f"/x{os.pathsep}{os.pathsep}/y"}

        # Act
        found = snesdsp.directories(environment)

        # Assert
        self.assertEqual(found[:3], (Path("/x"), Path("/y"), ROOT.parent / "firmware"))

    def test_no_directory_appears_twice(self) -> None:
        # Arrange
        environment = {OWN_VARIABLE: str(ROOT / "firmware")}

        # Act
        found = snesdsp.directories(environment)

        # Assert
        self.assertEqual(found, (ROOT / "firmware", ROOT.parent / "firmware"))

    def test_the_name_this_member_used_to_share_still_works(self) -> None:
        # Arrange
        environment = {SHARED_VARIABLE: "/x"}

        # Act
        found = snesdsp.directories(environment)

        # Assert
        self.assertEqual(found[0], Path("/x"))

    def test_but_the_members_own_name_is_looked_at_first(self) -> None:
        # Arrange
        environment = {SHARED_VARIABLE: "/shared", OWN_VARIABLE: "/mine"}

        # Act
        found = snesdsp.directories(environment)

        # Assert
        self.assertEqual(found[:2], (Path("/mine"), Path("/shared")))

    def test_with_no_mapping_handed_in_it_reads_the_environment(self) -> None:
        # Arrange
        named = mock.patch.dict(os.environ, {OWN_VARIABLE: "/from-the-environment"})
        named.start()
        self.addCleanup(named.stop)

        # Act
        found = snesdsp.directories()

        # Assert
        self.assertEqual(found[0], Path("/from-the-environment"))


if __name__ == "__main__":
    unittest.main()
