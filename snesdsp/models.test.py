import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import models


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_model_it_covers(self):
        self.assertIn("dsp2", models.MODELS)

    def test_a_model_says_what_it_is_and_what_it_holds(self):
        found = models.describe("dsp2")

        self.assertTrue(found.summary)
        self.assertEqual(found.parameter_bytes, 512)

    def test_a_model_name_is_matched_however_it_is_written(self):
        for written in ("DSP2", "dsp-2", "DSP_2", "nintendo-dsp2"):
            self.assertEqual(models.describe(written).name, "dsp2")

    def test_a_model_the_package_does_not_have_is_refused_by_name(self):
        with self.assertRaises(models.UnknownModelError):
            models.describe("dsp1")

    def test_the_refusal_lists_what_is_available(self):
        with self.assertRaises(models.UnknownModelError) as raised:
            models.describe("nonsense")

        self.assertIn("dsp2", str(raised.exception))

    def test_a_model_prints_as_its_name_and_size(self):
        printed = repr(models.describe("dsp2"))

        self.assertIn("dsp2", printed)
        self.assertIn("512", printed)


class BuildTest(unittest.TestCase):
    def test_a_chip_is_built_from_its_model_name(self):
        self.assertEqual(snesdsp.Dsp(model="dsp2", fill=0).model, "dsp2")

    def test_the_default_model_is_the_one_the_cartridge_carries(self):
        self.assertEqual(snesdsp.Dsp(fill=0).model, "dsp2")

    def test_options_reach_the_chip_that_gets_built(self):
        self.assertEqual(snesdsp.Dsp(model="dsp2", fill=0xAA).parameter_ram[0], 0xAA)

    def test_a_model_the_package_does_not_have_is_refused_at_construction(self):
        with self.assertRaises(models.UnknownModelError):
            snesdsp.Dsp(model="dsp4")


if __name__ == "__main__":
    unittest.main()
