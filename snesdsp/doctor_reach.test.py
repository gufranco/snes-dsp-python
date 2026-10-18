import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from snesdsp import doctor  # noqa: E402

PROCESSOR = str(ROOT / "nec-upd7725-96050-python")


class Complaint(Exception):
    pass


def advice_from(found: doctor.Finding) -> str:
    assert found.advice is not None, f"{found.name} failed without saying what to do"
    return found.advice


def a_folder(**files: str) -> Path:
    where = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (where / name).write_text(text)
    return where


class BeneathTest(unittest.TestCase):
    def test_the_processor_underneath_is_examined_as_well(self) -> None:
        # Arrange
        prefix = f"{doctor.PROCESSOR_NAME} / "

        # Act
        names = [one.name for one in doctor.examine()]

        # Assert
        self.assertIn(f"{prefix}python", names)

    def test_its_findings_keep_their_verdict_and_detail_under_its_name(self) -> None:
        # Arrange
        def beneath() -> list[doctor.Finding]:
            return [doctor.Finding("image dsp1", False, "sha256 abc", "go and look")]

        # Act
        found = doctor.examine(beneath=beneath)[-1]

        # Assert
        self.assertEqual(
            (found.name, found.ok, found.detail, found.advice),
            (f"{doctor.PROCESSOR_NAME} / image dsp1", False, "sha256 abc", "go and look"),
        )

    def test_a_project_underneath_that_cannot_be_asked_says_so(self) -> None:
        # Arrange
        def beneath() -> list[doctor.Finding]:
            raise Complaint("no doctor down there")

        # Act
        found = doctor.examine(beneath=beneath)[-1]

        # Assert
        self.assertEqual((found.name, found.ok), (doctor.PROCESSOR_NAME, False))
        self.assertEqual(found.detail, "Complaint: no doctor down there")
        self.assertIn("older than this package expects", advice_from(found))

    def test_nothing_underneath_at_all_adds_no_finding(self) -> None:
        # Arrange
        prefix = doctor.PROCESSOR_NAME

        # Act
        found = doctor.examine(beneath=list)

        # Assert
        self.assertEqual([one.name for one in found if one.name.startswith(prefix)], [])


class ReachTest(unittest.TestCase):
    def test_a_path_without_the_processor_gains_it_first(self) -> None:
        # Arrange
        path = ["somewhere else"]

        # Act
        found = doctor.reach_processor(path)

        # Assert
        self.assertEqual(found, [PROCESSOR, "somewhere else"])

    def test_a_path_that_already_has_it_is_left_alone(self) -> None:
        # Arrange
        path = ["somewhere else", PROCESSOR]

        # Act
        found = doctor.reach_processor(path)

        # Assert
        self.assertEqual(found, ["somewhere else", PROCESSOR])

    def test_by_default_it_works_on_the_real_one(self) -> None:
        # Arrange
        expected = sys.path

        # Act
        found = doctor.reach_processor()

        # Assert
        self.assertIs(found, expected)
        self.assertIn(PROCESSOR, sys.path)


class CorpusTest(unittest.TestCase):
    def test_the_shapes_say_how_many_cartridges_each_part_was_read_from(self) -> None:
        # Arrange
        where = a_folder(
            **{
                "dsp2shapes.json": json.dumps({"readFrom": ["a", "b"]}),
                "dsp3shapes.json": json.dumps({"readFrom": "a"}),
            }
        )

        # Act
        found = doctor.check_exchanges(where)

        # Assert
        self.assertEqual(found.detail, "dsp2 from 2 cartridges, dsp3 from 1 cartridge")

    def test_a_shapes_file_that_is_damaged_is_reported_as_damaged(self) -> None:
        # Arrange
        where = a_folder(**{"dsp1shapes.json": "{ not json at all"})

        # Act
        found = doctor.check_exchanges(where)

        # Assert
        self.assertTrue(found.detail.startswith("dsp1 is damaged: "))

    def test_no_shapes_at_all_is_a_failure_that_says_where_they_go(self) -> None:
        # Arrange
        where = a_folder()

        # Act
        found = doctor.check_exchanges(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "none recorded"))
        self.assertIn("conformance/", advice_from(found))

    def test_the_recorded_answers_are_named_by_part(self) -> None:
        # Arrange
        where = a_folder(**{"dsp2answers.json": "{}", "dsp1answers.json": "{}"})

        # Act
        found = doctor.check_answers(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (True, "pinned for dsp1, dsp2"))

    def test_no_recorded_answers_says_how_to_take_them(self) -> None:
        # Arrange
        where = a_folder()

        # Act
        found = doctor.check_answers(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "none pinned"))
        self.assertIn("--take", advice_from(found))

    def test_the_mask_divergence_says_how_wide_the_sweep_was(self) -> None:
        # Arrange
        held = {"divergences": [1, 2], "swept": {"commands": 256, "argumentSets": 16}}
        where = a_folder(**{"dsp1masks.json": json.dumps(held)})

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertEqual(
            found.detail,
            "2 inputs where the DSP-1 and DSP-1B differ, found across 256 commands x 16 argument sets",
        )

    def test_a_sweep_that_was_never_run_says_how_to_run_it(self) -> None:
        # Arrange
        where = a_folder()

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "not swept"))
        self.assertIn("--sweep", advice_from(found))

    def test_a_swept_file_that_is_damaged_is_reported_as_damaged(self) -> None:
        # Arrange
        where = a_folder(**{"dsp1masks.json": "{ not json at all"})

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertFalse(found.ok)
        self.assertTrue(found.detail.startswith("is damaged: "))

    def test_a_sweep_that_found_no_divergence_is_a_failure(self) -> None:
        # Arrange
        where = a_folder(**{"dsp1masks.json": json.dumps({"divergences": [], "swept": {}})})

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertFalse(found.ok)
        self.assertIn("one image under two names", advice_from(found))


if __name__ == "__main__":
    unittest.main()
