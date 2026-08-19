import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp.memory import PARAMETER_BYTES, UNSET_SEED, parameter_ram, scramble


class ScrambleTest(unittest.TestCase):
    def test_gives_the_requested_length(self):
        self.assertEqual(len(scramble(64)), 64)

    def test_repeats_for_one_seed(self):
        self.assertEqual(scramble(256, seed=7), scramble(256, seed=7))

    def test_differs_between_seeds(self):
        self.assertNotEqual(scramble(256, seed=7), scramble(256, seed=8))

    def test_is_not_a_cleared_machine(self):
        self.assertNotEqual(scramble(4096), bytearray(4096))

    def test_covers_most_of_the_byte_range(self):
        self.assertGreater(len(set(scramble(4096))), 200)

    def test_gives_nothing_for_no_length(self):
        self.assertEqual(scramble(0), bytearray())

    def test_the_default_seed_is_shared(self):
        self.assertEqual(scramble(16), scramble(16, seed=UNSET_SEED))


class ParameterRamTest(unittest.TestCase):
    def test_the_ram_is_five_hundred_and_twelve_bytes(self):
        self.assertEqual(PARAMETER_BYTES, 512)

    def test_it_is_that_long_however_it_is_built(self):
        for fill in (None, 0, 0xFF, b"\x01\x02"):
            self.assertEqual(len(parameter_ram(fill=fill)), PARAMETER_BYTES)

    def test_it_is_scrambled_when_nothing_is_asked_for(self):
        self.assertNotEqual(parameter_ram(), bytearray(PARAMETER_BYTES))

    def test_zero_is_a_decision_a_caller_can_make(self):
        self.assertEqual(parameter_ram(fill=0), bytearray(PARAMETER_BYTES))

    def test_it_fills_with_a_byte(self):
        self.assertEqual(set(parameter_ram(fill=0xAA)), {0xAA})

    def test_it_keeps_only_the_low_byte_of_the_fill(self):
        self.assertEqual(set(parameter_ram(fill=0x1BB)), {0xBB})

    def test_it_takes_an_image_at_the_bottom(self):
        held = parameter_ram(fill=b"\x01\x02\x03")

        self.assertEqual(bytes(held[:3]), b"\x01\x02\x03")

    def test_an_image_longer_than_the_ram_is_cut_to_fit(self):
        held = parameter_ram(fill=bytes(range(256)) * 4)

        self.assertEqual(len(held), PARAMETER_BYTES)

    def test_it_repeats_for_one_seed(self):
        self.assertEqual(parameter_ram(seed=3), parameter_ram(seed=3))


if __name__ == "__main__":
    unittest.main()
