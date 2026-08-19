import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import models


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_model_it_covers(self):
        self.assertEqual(set(models.MODELS), {"dsp1", "dsp1a", "dsp1b", "dsp2", "dsp3", "dsp4"})

    def test_a_model_says_what_it_is_and_what_it_holds(self):
        found = models.describe("dsp2")

        self.assertTrue(found.summary)
        self.assertEqual(found.parameter_bytes, 512)

    def test_a_model_name_is_matched_however_it_is_written(self):
        for written in ("DSP2", "dsp-2", "DSP_2", "nintendo-dsp2"):
            self.assertEqual(models.describe(written).name, "dsp2")

    def test_the_projector_answers_to_its_own_names(self):
        for written in ("DSP1", "dsp-1", "DSP_1", "nintendo-dsp1"):
            self.assertEqual(models.describe(written).name, "dsp1")

    def test_the_later_mask_is_a_model_of_its_own(self):
        for written in ("DSP1B", "dsp-1b", "DSP_1B"):
            self.assertEqual(models.describe(written).name, "dsp1b")

    def test_the_middle_mask_is_a_part_in_its_own_right(self):
        self.assertIn("dsp1a", models.MODELS)

    def test_the_middle_mask_runs_the_first_mask_program(self):
        self.assertEqual(models.SHARES_MICROCODE["dsp1a"], "dsp1")

    def test_and_the_last_mask_shares_nobody_else_program(self):
        self.assertNotIn("dsp1b", models.SHARES_MICROCODE)

    def test_the_two_masks_are_not_the_same_model(self):
        self.assertIsNot(models.describe("dsp1"), models.describe("dsp1b"))

    def test_and_they_do_not_answer_the_same_way(self):
        first = snesdsp.Dsp(model="dsp1", backend="modelled", fill=0)
        later = snesdsp.Dsp(model="dsp1b", backend="modelled", fill=0)

        for chip in (first, later):
            chip.write(0x2F)
            chip.write(0x00)
            chip.write(0x00)

        self.assertNotEqual((first.read(), first.read()), (later.read(), later.read()))

    def test_nothing_is_refused_now_that_every_mask_is_covered(self):
        self.assertEqual(models.NOT_MODELLED, {})

    def test_a_name_the_package_deliberately_refuses_says_why(self):
        models.NOT_MODELLED["dsp9"] = "there is no such part"

        try:
            with self.assertRaises(models.UnknownModelError) as raised:
                models.describe("dsp9")

            self.assertIn("no such part", str(raised.exception))
        finally:
            del models.NOT_MODELLED["dsp9"]

    def test_the_searcher_answers_to_its_own_names(self):
        for written in ("DSP3", "dsp-3", "DSP_3", "nintendo-dsp3"):
            self.assertEqual(models.describe(written).name, "dsp3")

    def test_a_model_with_no_parameter_ram_says_so_rather_than_guessing(self):
        self.assertEqual(models.describe("dsp3").parameter_bytes, 0)

    def test_the_renderer_answers_to_its_own_names(self):
        for written in ("DSP4", "dsp-4", "DSP_4", "nintendo-dsp4"):
            self.assertEqual(models.describe(written).name, "dsp4")

    def test_a_model_the_package_does_not_have_is_refused_by_name(self):
        with self.assertRaises(models.UnknownModelError):
            models.describe("dsp5")

    def test_the_refusal_lists_what_is_available(self):
        with self.assertRaises(models.UnknownModelError) as raised:
            models.describe("nonsense")

        self.assertIn("dsp1", str(raised.exception))

    def test_a_model_prints_as_its_name_and_size(self):
        printed = repr(models.describe("dsp2"))

        self.assertIn("dsp2", printed)
        self.assertIn("512", printed)


class BuildTest(unittest.TestCase):
    def test_a_chip_is_built_from_its_model_name(self):
        self.assertEqual(snesdsp.Dsp(model="dsp2", backend="modelled", fill=0).model, "dsp2")

    def test_the_default_model_is_the_one_the_cartridge_carries(self):
        self.assertEqual(snesdsp.Dsp(backend="modelled", fill=0).model, "dsp2")

    def test_options_reach_the_chip_that_gets_built(self):
        self.assertEqual(
            snesdsp.Dsp(model="dsp2", backend="modelled", fill=0xAA).parameter_ram[0], 0xAA
        )

    def test_the_renderer_is_built_from_its_model_name_too(self):
        self.assertEqual(snesdsp.Dsp(model="dsp4", backend="modelled", fill=0).model, "dsp4")

    def test_the_projector_is_built_from_its_model_name_too(self):
        self.assertEqual(snesdsp.Dsp(model="dsp1", backend="modelled", fill=0).model, "dsp1")

    def test_and_so_is_its_later_mask(self):
        self.assertEqual(snesdsp.Dsp(model="dsp1b", backend="modelled", fill=0).model, "dsp1b")

    def test_a_built_chip_carries_the_mask_it_was_asked_for(self):
        self.assertEqual(snesdsp.Dsp(model="dsp1b", backend="modelled", fill=0).revision, "dsp1b")

    def test_the_searcher_is_built_from_its_model_name_too(self):
        self.assertEqual(snesdsp.Dsp(model="dsp3").model, "dsp3")

    def test_a_model_the_package_does_not_have_is_refused_at_construction(self):
        with self.assertRaises(models.UnknownModelError):
            snesdsp.Dsp(model="dsp5")


if __name__ == "__main__":
    unittest.main()
