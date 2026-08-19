import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import commands


class TileTest(unittest.TestCase):
    def test_a_conversion_takes_thirty_two_bytes(self):
        with self.assertRaises(ValueError):
            commands.tile(bytes(31))

    def test_a_conversion_gives_thirty_two_bytes_back(self):
        self.assertEqual(len(commands.tile(bytes(32))), 32)

    def test_an_empty_tile_stays_empty(self):
        self.assertEqual(commands.tile(bytes(32)), bytes(32))

    def test_the_conversion_moves_every_bit_and_loses_none(self):
        landed = set()
        for index in range(32):
            for bit in range(8):
                payload = bytearray(32)
                payload[index] = 1 << bit

                result = commands.tile(bytes(payload))

                lit = [
                    (position, held)
                    for position, byte in enumerate(result)
                    for held in range(8)
                    if byte & (1 << held)
                ]
                self.assertEqual(len(lit), 1)
                landed.add(lit[0])

        self.assertEqual(len(landed), 256)

    def test_the_conversion_adds_nothing_of_its_own(self):
        for index in range(32):
            for bit in range(8):
                payload = bytearray(32)
                payload[index] = 1 << bit

                self.assertEqual(sum(bin(b).count("1") for b in commands.tile(bytes(payload))), 1)


class MergeTest(unittest.TestCase):
    def test_a_merge_takes_two_runs_of_the_length(self):
        with self.assertRaises(ValueError):
            commands.merge(0x00, bytes(3), 2)

    def test_a_merge_gives_the_length_back(self):
        self.assertEqual(len(commands.merge(0x00, bytes(8), 4)), 4)

    def test_the_over_run_wins_where_it_is_not_transparent(self):
        self.assertEqual(commands.merge(0x00, bytes([0x11, 0x22]), 1), bytes([0x22]))

    def test_the_under_run_shows_through_where_the_over_run_is_transparent(self):
        self.assertEqual(commands.merge(0x00, bytes([0x11, 0x00]), 1), bytes([0x11]))

    def test_each_nibble_is_decided_on_its_own(self):
        self.assertEqual(commands.merge(0x00, bytes([0x12, 0x30]), 1), bytes([0x32]))

    def test_the_transparent_colour_is_the_one_that_was_set(self):
        self.assertEqual(commands.merge(0x0F, bytes([0x11, 0xFF]), 1), bytes([0x11]))

    def test_every_combination_picks_the_nibble_the_rule_names(self):
        for colour in range(16):
            for under in range(256):
                for over in (0x00, 0x0F, 0xF0, 0xFF, under, (under ^ 0xFF)):
                    expected_high = under & 0xF0 if (over >> 4) == colour else over & 0xF0
                    expected_low = under & 0x0F if (over & 0x0F) == colour else over & 0x0F

                    found = commands.merge(colour, bytes([under, over]), 1)

                    self.assertEqual(found[0], expected_high | expected_low)


class MirrorTest(unittest.TestCase):
    def test_a_mirror_needs_at_least_the_length(self):
        with self.assertRaises(ValueError):
            commands.mirror(bytes(3), 4)

    def test_a_mirror_gives_the_length_back(self):
        self.assertEqual(len(commands.mirror(bytes(4), 4)), 4)

    def test_a_mirror_reverses_the_run(self):
        found = commands.mirror(bytes([0x10, 0x20, 0x30, 0x40]), 4)

        self.assertEqual(found, bytes([0x04, 0x03, 0x02, 0x01]))

    def test_a_mirror_swaps_the_nibbles_of_each_byte(self):
        self.assertEqual(commands.mirror(bytes([0xAB]), 1), bytes([0xBA]))

    def test_mirroring_twice_gives_the_run_back(self):
        for length in range(1, 9):
            original = bytes(range(0x10, 0x10 + length))

            self.assertEqual(commands.mirror(commands.mirror(original, length), length), original)

    def test_extra_bytes_past_the_length_are_ignored(self):
        self.assertEqual(commands.mirror(bytes([0x12, 0x34, 0x56]), 2), bytes([0x43, 0x21]))


class MultiplyTest(unittest.TestCase):
    def test_a_multiply_takes_four_bytes(self):
        with self.assertRaises(ValueError):
            commands.multiply(bytes(3))

    def test_a_multiply_gives_four_bytes_back(self):
        self.assertEqual(len(commands.multiply(bytes(4))), 4)

    def test_a_multiply_is_the_product_of_two_words(self):
        found = commands.multiply(bytes([0x02, 0x00, 0x03, 0x00]))

        self.assertEqual(int.from_bytes(found, "little"), 6)

    def test_a_multiply_reads_both_words_low_byte_first(self):
        found = commands.multiply(bytes([0x00, 0x01, 0x00, 0x01]))

        self.assertEqual(int.from_bytes(found, "little"), 0x100 * 0x100)

    def test_the_widest_product_still_fits(self):
        found = commands.multiply(bytes([0xFF, 0xFF, 0xFF, 0xFF]))

        self.assertEqual(int.from_bytes(found, "little"), 0xFFFF * 0xFFFF)

    def test_the_product_matches_arithmetic_across_the_range(self):
        for first in range(0, 0x10000, 0x321):
            for second in range(0, 0x10000, 0x765):
                payload = first.to_bytes(2, "little") + second.to_bytes(2, "little")

                found = commands.multiply(payload)

                self.assertEqual(int.from_bytes(found, "little"), first * second)


class ScaleTest(unittest.TestCase):
    def test_the_parameter_ram_must_be_whole(self):
        with self.assertRaises(ValueError):
            commands.scale(bytes(16), 4, 4)

    def test_a_scale_gives_the_output_length_back(self):
        self.assertEqual(len(commands.scale(bytes(512), 4, 8)), 8)

    def test_growing_a_run_repeats_its_nibbles(self):
        parameters = bytearray(512)
        parameters[0] = 0x12

        found = commands.scale(bytes(parameters), 2, 4)

        self.assertEqual(found[0], 0x12)

    def test_shrinking_a_run_skips_nibbles(self):
        parameters = bytearray(512)
        parameters[:4] = bytes([0x12, 0x34, 0x56, 0x78])

        found = commands.scale(bytes(parameters), 8, 4)

        self.assertEqual(len(found), 4)

    def test_a_scale_that_neither_grows_nor_shrinks_copies(self):
        parameters = bytearray(512)
        parameters[:4] = bytes([0x12, 0x34, 0x56, 0x78])

        found = commands.scale(bytes(parameters), 8, 8)

        self.assertEqual(found[:4], bytes([0x12, 0x34, 0x56, 0x78]))

    def test_the_walk_reads_past_the_payload_rather_than_stopping(self):
        parameters = bytearray(512)
        parameters[0] = 0x12
        parameters[60] = 0xAB

        found = commands.scale(bytes(parameters), 120, 120)

        self.assertEqual(found[60], 0xAB)

    def test_the_walk_wraps_inside_the_parameter_ram(self):
        parameters = bytearray(range(256)) * 2

        found = commands.scale(bytes(parameters), 2048, 1024)

        self.assertEqual(len(found), 1024)

    def test_the_ratio_shrinks_as_the_output_grows(self):
        self.assertGreater(commands.ratio(16, 4), commands.ratio(16, 8))

    def test_the_ratio_of_equal_lengths_is_about_one_unit(self):
        self.assertAlmostEqual(commands.ratio(64, 64) / commands.UNIT, 1.0, places=1)


if __name__ == "__main__":
    unittest.main()
