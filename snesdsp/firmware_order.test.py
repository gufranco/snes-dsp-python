import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024


def an_image(filler: int = 0xAB) -> bytes:
    return bytes([filler]) * (PROGRAM_WORDS * 3 + TABLE_WORDS * 2)


def a_catalogue(image: bytes, part: str = "made-up") -> dict[str, Any]:
    return {
        "artifacts": [
            {
                "part": part,
                "processor": "upd7725",
                "bytes": len(image),
                "programWords": PROGRAM_WORDS,
                "dataWords": TABLE_WORDS,
                "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                "badDumps": [],
            }
        ]
    }


def stored_low_byte_first(image: bytes) -> bytes:
    split = PROGRAM_WORDS * 3
    program = b"".join(image[at : at + 3][::-1] for at in range(0, split, 3))
    table = b"".join(image[at : at + 2][::-1] for at in range(split, len(image), 2))
    return program + table


def a_varied_image(seed: int = 7) -> bytes:
    return bytes((seed * 131 + at * 29 + (at >> 3)) & 0xFF for at in range(len(an_image())))


class LowByteFirstTest(unittest.TestCase):
    def test_a_dump_storing_each_word_low_byte_first_is_the_image_it_reorders_to(self) -> None:
        # Arrange
        image = a_varied_image()

        # Act
        found = snesdsp.identify(stored_low_byte_first(image), a_catalogue(image))

        # Assert
        self.assertEqual((found.part, found.order), ("made-up", snesdsp.LOW_BYTE_FIRST))

    def test_an_image_in_the_published_order_says_so(self) -> None:
        # Arrange
        image = a_varied_image()

        # Act
        found = snesdsp.identify(image, a_catalogue(image))

        # Assert
        self.assertEqual(found.order, snesdsp.HIGH_BYTE_FIRST)

    def test_a_dump_is_put_back_in_the_published_order_before_it_is_run(self) -> None:
        # Arrange
        image = a_varied_image()
        dumped = stored_low_byte_first(image)
        identity = snesdsp.identify(dumped, a_catalogue(image))

        # Act
        found = snesdsp.canonical(dumped, identity)

        # Assert
        self.assertEqual(found, image)

    def test_an_image_already_in_the_published_order_is_left_alone(self) -> None:
        # Arrange
        image = a_varied_image()
        identity = snesdsp.identify(image, a_catalogue(image))

        # Act
        found = snesdsp.canonical(image, identity)

        # Assert
        self.assertEqual(found, image)

    def test_a_folder_holding_only_the_dump_counts_the_part_as_present(self) -> None:
        # Arrange
        image = a_varied_image()
        where = Path(tempfile.mkdtemp())
        (where / "dump.bin").write_bytes(stored_low_byte_first(image))

        # Act
        found = [identity.part for identity, _path in snesdsp.search([where], a_catalogue(image))]

        # Assert
        self.assertEqual(found, ["made-up"])


if __name__ == "__main__":
    unittest.main()
