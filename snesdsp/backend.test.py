import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import backend, silicon

PRESENT = silicon.available()


class ChoiceTest(unittest.TestCase):
    def test_the_two_backends_are_named(self):
        self.assertEqual(set(backend.BACKENDS), {backend.SILICON, backend.MODELLED})

    def test_asking_for_a_backend_that_does_not_exist_is_refused(self):
        with self.assertRaises(backend.UnknownBackend):
            backend.chosen("dsp1", "nonsense")

    def test_the_refusal_names_the_backends_there_are(self):
        with self.assertRaises(backend.UnknownBackend) as raised:
            backend.chosen("dsp1", "nonsense")

        for name in backend.BACKENDS:
            self.assertIn(name, str(raised.exception))

    def test_the_model_can_always_be_asked_for_by_name(self):
        self.assertEqual(backend.chosen("dsp2", backend.MODELLED), backend.MODELLED)

    def test_a_part_with_no_image_falls_back_to_the_model(self):
        self.assertEqual(backend.chosen("dsp1a", None, images={}), backend.MODELLED)

    def test_a_part_with_an_image_prefers_the_microcode(self):
        self.assertEqual(backend.chosen("dsp1", None, images={"dsp1": object()}), backend.SILICON)

    def test_asking_for_the_microcode_without_an_image_is_refused(self):
        with self.assertRaises(silicon.NoFirmware):
            backend.chosen("dsp1", backend.SILICON, images={})

    def test_that_refusal_says_where_an_image_would_go(self):
        with self.assertRaises(silicon.NoFirmware) as raised:
            backend.chosen("dsp1", backend.SILICON, images={})

        self.assertIn("firmware", str(raised.exception).lower())


class BuildTest(unittest.TestCase):
    def test_the_model_is_built_when_it_is_asked_for(self):
        chip = snesdsp.Dsp(model="dsp2", backend=backend.MODELLED)

        self.assertFalse(isinstance(chip, silicon.Silicon))

    def test_a_built_part_says_which_backend_it_is(self):
        chip = snesdsp.Dsp(model="dsp2", backend=backend.MODELLED)

        self.assertEqual(chip.backend, backend.MODELLED)

    def test_both_backends_offer_the_same_interface(self):
        chip = snesdsp.Dsp(model="dsp2", backend=backend.MODELLED)

        for name in ("write", "read", "pending_output", "backend"):
            self.assertTrue(hasattr(chip, name), name)


@unittest.skipUnless(PRESENT, silicon.WHY_NOT_FIRMWARE)
class WithFirmwareTest(unittest.TestCase):
    def test_the_microcode_is_what_a_caller_gets_by_default(self):
        part = sorted(PRESENT)[0]

        self.assertIsInstance(snesdsp.Dsp(model=part), silicon.Silicon)

    def test_and_it_says_so(self):
        part = sorted(PRESENT)[0]

        self.assertEqual(snesdsp.Dsp(model=part).backend, backend.SILICON)

    def test_the_model_is_still_reachable_by_asking_for_it(self):
        part = sorted(PRESENT)[0]
        chip = snesdsp.Dsp(model=part, backend=backend.MODELLED)

        self.assertEqual(chip.backend, backend.MODELLED)

    def test_every_part_with_an_image_offers_the_same_interface_either_way(self):
        for part in sorted(PRESENT):
            for which in (backend.SILICON, backend.MODELLED):
                chip = snesdsp.Dsp(model=part, backend=which)

                for name in ("write", "read", "pending_output", "backend"):
                    self.assertTrue(hasattr(chip, name), (part, which, name))


if __name__ == "__main__":
    unittest.main()
