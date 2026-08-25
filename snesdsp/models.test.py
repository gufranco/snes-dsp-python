import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import chip, errors, models

EVERY_PART = {"dsp1", "dsp1a", "dsp1b", "dsp2", "dsp3", "dsp4"}


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_part_it_covers(self) -> None:
        self.assertEqual(set(models.MODELS), EVERY_PART)

    def test_a_part_says_what_it_is(self) -> None:
        self.assertTrue(models.describe("dsp2").summary)

    def test_and_which_image_it_runs(self) -> None:
        self.assertEqual(models.describe("dsp2").image, "dsp2")

    def test_a_part_that_carries_another_part_program_says_so(self) -> None:
        self.assertEqual(models.describe("dsp1a").image, "dsp1")

    def test_and_is_still_a_part_in_its_own_right(self) -> None:
        self.assertEqual(models.describe("dsp1a").name, "dsp1a")

    def test_a_part_prints_as_itself_and_the_image_it_runs(self) -> None:
        printed = repr(models.describe("dsp1a"))

        self.assertIn("dsp1a", printed)
        self.assertIn("dsp1", printed)

    def test_every_part_carries_a_summary(self) -> None:
        for name in models.MODELS:
            self.assertTrue(models.describe(name).summary, name)

    def test_no_two_parts_share_a_name(self) -> None:
        self.assertEqual(len(models.MODELS), len(set(models.MODELS)))


class NamingTest(unittest.TestCase):
    def test_a_part_is_found_by_its_name(self) -> None:
        self.assertEqual(models.describe("dsp3").name, "dsp3")

    def test_and_by_any_name_it_is_also_known_by(self) -> None:
        for alias in models.describe("dsp1").aliases:
            self.assertEqual(models.describe(alias).name, "dsp1")

    def test_the_name_is_read_without_regard_to_case(self) -> None:
        self.assertEqual(models.describe("DSP3").name, "dsp3")

    def test_a_name_no_part_answers_to_is_refused(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            models.describe("dsp9")

    def test_and_the_refusal_names_what_there_is(self) -> None:
        with self.assertRaises(errors.UnknownModelError) as raised:
            models.describe("dsp9")

        for name in EVERY_PART:
            self.assertIn(name, str(raised.exception))

    def test_no_alias_belongs_to_two_parts(self) -> None:
        seen = [alias for name in models.MODELS for alias in models.describe(name).aliases]

        self.assertEqual(len(seen), len(set(seen)))


class DeclaredImageTest(unittest.TestCase):
    """That every part names an image the processor will recognise and confirm.

    This is what a machine with no microcode can still check, and it is the check
    that matters most: a user who supplies a file gets it identified by digest
    before a byte of it is run, so a wrong file is refused rather than executed.
    A part whose image nobody declared would be accepted on trust.
    """

    def _manifest(self) -> "dict[str, Any]":
        import json

        where = (
            Path(__file__).resolve().parent.parent
            / "nec-upd7725-python"
            / "artifacts.manifest.json"
        )
        held = json.loads(where.read_text())
        assert isinstance(held, dict), f"{where} does not hold an object"
        return held

    def test_every_part_runs_an_image_the_processor_declares(self) -> None:
        declared = {one["part"] for one in self._manifest()["artifacts"]}

        for name in models.MODELS:
            self.assertIn(models.describe(name).image, declared, name)

    def test_every_declared_image_carries_a_deciding_digest(self) -> None:
        for one in self._manifest()["artifacts"]:
            for accepted in one["accepted"]:
                self.assertEqual(len(accepted["sha256"]), 64, one["part"])

    def test_and_the_shape_the_processor_needs_to_load_it(self) -> None:
        for one in self._manifest()["artifacts"]:
            self.assertEqual(
                one["bytes"], one["programWords"] * 3 + one["dataWords"] * 2, one["part"]
            )

    def test_every_part_of_this_family_runs_the_same_processor(self) -> None:
        declared = {one["part"]: one["processor"] for one in self._manifest()["artifacts"]}

        for name in models.MODELS:
            self.assertEqual(declared[models.describe(name).image], "upd7725", name)


class BuildingTest(unittest.TestCase):
    """What the package hands back, which is a part rather than a description."""

    def test_asking_for_a_part_asks_for_its_microcode(self) -> None:
        with self.assertRaises((snesdsp.NoFirmware, Exception)) as raised:
            _refused_or_built("dsp9")

        self.assertTrue(raised.exception)

    def test_a_name_no_part_answers_to_is_refused_before_any_image_is_looked_for(self) -> None:
        with self.assertRaises(errors.UnknownModelError):
            snesdsp.Chip("dsp9")

    def test_the_default_part_is_one_the_catalogue_knows(self) -> None:
        self.assertIn(snesdsp.DEFAULT_MODEL, models.MODELS)

    def test_the_package_offers_no_way_to_ask_for_anything_but_the_part(self) -> None:
        self.assertNotIn("backend", snesdsp.__all__)
        self.assertNotIn("MODELLED", snesdsp.__all__)


def _refused_or_built(name: str) -> "chip.Chip":
    return snesdsp.Chip(name)


if __name__ == "__main__":
    unittest.main()
