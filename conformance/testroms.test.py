import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import snesdsp
from conformance import testroms

DUMP = bytes(range(6)) + bytes(8186)


def an_identity(part: str = "dsp1") -> Any:
    return SimpleNamespace(
        part=part, order=snesdsp.LOW_BYTE_FIRST, program_words=2048, data_words=1024
    )


def checked(disagreements: int = 0) -> Any:
    def check(part: str, identity: Any, path: Path) -> Any:
        return SimpleNamespace(checked=3, disagreements=(None,) * disagreements)

    return check


class Library:
    def __init__(self) -> None:
        self.where = Path(tempfile.mkdtemp())
        self.images = self.where / "images"
        self.images.mkdir()
        (self.images / "dump.bin").write_bytes(DUMP)
        (self.images / "unlisted.bin").write_bytes(b"\x01" * 16)
        self.record = self.where / "testroms.json"
        self.record.write_text(
            json.dumps(
                {
                    "cartridges": [
                        {
                            "id": "made-up",
                            "sha256": hashlib.sha256(DUMP).hexdigest(),
                            "outcome": "run",
                        },
                        {"id": "elsewhere", "sha256": "ab" * 32, "outcome": "hosted"},
                    ]
                }
            )
        )
        self.measured = self.where / "testroms_measured.json"

    def run(self, *argv: str, disagreements: int = 0) -> tuple[int, list[str]]:
        said: list[str] = []
        code = testroms.main(
            list(argv),
            said.append,
            self.record,
            self.measured,
            identify=lambda _image: an_identity(),
            check=checked(disagreements),
        )
        return code, said


A_MEASURE = {
    "part": "dsp1",
    "order": snesdsp.LOW_BYTE_FIRST,
    "canonicalSha256": hashlib.sha256(bytes([2, 1, 0, 5, 4, 3]) + bytes(8186)).hexdigest(),
    "checked": {"dsp1": 3, "dsp1a": 3},
    "disagreements": 0,
}


class MeasureTest(unittest.TestCase):
    def test_a_dump_is_run_as_every_part_that_runs_its_image(self) -> None:
        # Arrange
        identity = an_identity()

        # Act
        found = testroms.measure(DUMP, identity, Path("dump.bin"), checked())

        # Assert
        self.assertEqual(found, A_MEASURE)


class MainTest(unittest.TestCase):
    def test_naming_no_folder_runs_nothing_and_says_so(self) -> None:
        # Arrange
        library = Library()

        # Act
        code, said = library.run()

        # Assert
        self.assertEqual((code, said), (2, ["  0 of 1 runnable images run: no folder was named"]))

    def test_recording_writes_what_each_image_answered(self) -> None:
        # Arrange
        library = Library()

        # Act
        code, _said = library.run(str(library.images), testroms.RECORDING)

        # Assert
        self.assertEqual(
            (code, json.loads(library.measured.read_text())), (0, {"made-up": A_MEASURE})
        )

    def test_a_run_that_still_answers_as_recorded_passes(self) -> None:
        # Arrange
        library = Library()
        library.run(str(library.images), testroms.RECORDING)

        # Act
        code, said = library.run(str(library.images))

        # Assert
        self.assertEqual((code, said), (0, ["  1 of 1 runnable images run"]))

    def test_an_image_that_answers_otherwise_fails_and_says_so(self) -> None:
        # Arrange
        library = Library()
        library.run(str(library.images), testroms.RECORDING)

        # Act
        code, said = library.run(str(library.images), disagreements=2)

        # Assert
        self.assertEqual((code, said[1].startswith("  ! made-up: measured")), (1, True))

    def test_a_folder_holding_none_of_the_images_runs_nothing(self) -> None:
        # Arrange
        library = Library()

        # Act
        code, said = library.run(str(library.where / "absent"))

        # Assert
        self.assertEqual((code, said), (2, ["  0 of 1 runnable images run"]))


class RecordedTest(unittest.TestCase):
    def test_each_dump_on_disk_re_derived_every_recorded_answer(self) -> None:
        # Arrange
        measured = json.loads(testroms.MEASURED.read_text())
        names = [
            "dsp1-91e87d11",
            "dsp1b-d789cb3c",
            "dsp2-03ef4ef2",
            "dsp3-0971b08f",
            "dsp4-752d03b2",
        ]

        # Act
        found = {name: measured[name]["disagreements"] for name in names}

        # Assert
        self.assertEqual(found, dict.fromkeys(names, 0))

    def test_and_each_was_stored_low_byte_first(self) -> None:
        # Arrange
        measured = json.loads(testroms.MEASURED.read_text())

        # Act
        orders = {one["order"] for one in measured.values()}

        # Assert
        self.assertEqual(orders, {snesdsp.LOW_BYTE_FIRST})

    def test_every_measured_image_is_one_the_record_lists(self) -> None:
        # Arrange
        listed = {one["id"] for one in json.loads(testroms.RECORD.read_text())["cartridges"]}

        # Act
        measured = set(json.loads(testroms.MEASURED.read_text()))

        # Assert
        self.assertEqual(measured - listed, set())


if __name__ == "__main__":
    unittest.main()
