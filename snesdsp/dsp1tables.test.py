import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp1tables


class SineTest(unittest.TestCase):
    def test_the_table_covers_a_whole_turn(self):
        self.assertEqual(len(dsp1tables.SINE), 256)

    def test_it_is_the_sine_of_the_angle_truncated_rather_than_rounded(self):
        for at, value in enumerate(dsp1tables.SINE):
            wanted = int(0x8000 * math.sin(2 * math.pi * at / 256))

            self.assertEqual(value, max(-0x7FFF, min(0x7FFF, wanted)))

    def test_a_quarter_turn_saturates_because_one_does_not_fit(self):
        self.assertEqual(dsp1tables.SINE[64], 0x7FFF)

    def test_and_so_does_three_quarters_of_one(self):
        self.assertEqual(dsp1tables.SINE[192], -0x7FFF)

    def test_the_start_of_a_turn_is_nothing(self):
        self.assertEqual(dsp1tables.SINE[0], 0)


class InterpolationTest(unittest.TestCase):
    def test_the_table_covers_every_step_between_two_angles(self):
        self.assertEqual(len(dsp1tables.INTERPOLATION), 256)

    def test_it_is_a_straight_line_at_the_ratio_that_approximates_pi(self):
        for at, value in enumerate(dsp1tables.INTERPOLATION):
            self.assertEqual(value, 355 * at // 113)

    def test_which_is_not_pi_and_is_what_the_chip_used(self):
        self.assertNotEqual(dsp1tables.INTERPOLATION[113], int(math.pi * 113))


class LadderTest(unittest.TestCase):
    """One run of the mask ROM that four different offsets read as a shift."""

    def test_the_head_of_the_table_is_unprogrammed(self):
        for at in range(0, dsp1tables.LADDER_ZEROES):
            self.assertEqual(dsp1tables.ladder(at), 0)

    def test_it_rises_by_doubling_to_the_middle(self):
        for at in range(dsp1tables.LADDER_ZEROES, dsp1tables.LADDER_ONE):
            self.assertEqual(dsp1tables.ladder(at), 1 << (at - dsp1tables.LADDER_ZEROES))

    def test_the_middle_is_as_close_to_one_as_a_word_gets(self):
        self.assertEqual(dsp1tables.ladder(dsp1tables.LADDER_ONE), 0x7FFF)

    def test_and_it_falls_by_halving_from_there(self):
        for at in range(dsp1tables.LADDER_ONE + 1, dsp1tables.LADDER_END + 1):
            if at == dsp1tables.LADDER_ANOMALY:
                continue

            self.assertEqual(dsp1tables.ladder(at), 1 << (dsp1tables.LADDER_END - at))

    def test_except_at_the_one_word_that_holds_one_instead_of_sixteen(self):
        self.assertEqual(dsp1tables.ladder(dsp1tables.LADDER_ANOMALY), 1)

    def test_past_the_end_it_is_unprogrammed_again(self):
        self.assertEqual(dsp1tables.ladder(dsp1tables.LADDER_END + 1), 0)

    def test_before_the_table_it_says_so_rather_than_guessing(self):
        with self.assertRaises(dsp1tables.BeyondTheTable):
            dsp1tables.ladder(-1)

    def test_and_past_the_ladder_entirely_it_says_so_too(self):
        with self.assertRaises(dsp1tables.BeyondTheTable):
            dsp1tables.ladder(dsp1tables.LADDER_TAIL)

    def test_shifting_up_by_nothing_is_nothing_at_all(self):
        self.assertEqual(dsp1tables.shift_up(0), 0)

    def test_and_by_more_is_a_power_of_two_one_short_of_the_shift(self):
        for shift in range(1, 16):
            self.assertEqual(dsp1tables.shift_up(shift), 1 << (shift - 1))

    def test_shifting_down_by_nothing_is_as_close_to_one_as_a_word_gets(self):
        self.assertEqual(dsp1tables.shift_down(0), 0x7FFF)

    def test_and_by_a_negative_exponent_halves_it_each_time(self):
        for shift in range(1, 16):
            self.assertEqual(dsp1tables.shift_down(-shift), 1 << (15 - shift))

    def test_and_by_a_positive_one_halves_it_the_other_way(self):
        for shift in range(1, 11):
            self.assertEqual(dsp1tables.shift_down(shift), 1 << (15 - shift))

    def test_the_rounding_offset_reads_the_same_run_from_its_far_end(self):
        for shift in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
            self.assertEqual(dsp1tables.round_up(shift), 1 << shift)

    def test_and_lands_on_the_odd_word_at_a_shift_of_four(self):
        self.assertEqual(dsp1tables.round_up(4), 1)

    def test_the_spread_offset_reads_the_rising_half(self):
        for shift in range(16, 31):
            self.assertEqual(dsp1tables.spread(shift), 1 << (shift - 16))


class SeedTest(unittest.TestCase):
    def test_the_seed_for_a_half_saturates_because_two_does_not_fit(self):
        self.assertEqual(dsp1tables.newton_seed(0), 0x7FFF)

    def test_and_every_other_seed_is_one_over_where_it_sits(self):
        for step in range(1, 128):
            wanted = round((1 << 29) / (0x4000 + 128 * step))

            self.assertEqual(dsp1tables.newton_seed(step), wanted)

    def test_the_seeds_fall_as_the_value_they_invert_rises(self):
        self.assertGreater(dsp1tables.newton_seed(1), dsp1tables.newton_seed(127))


class NodeTest(unittest.TestCase):
    def test_a_node_at_the_start_of_the_curve_is_a_half(self):
        self.assertEqual(dsp1tables.node(16), 0x3FFF)

    def test_a_whole_step_along_it_is_as_close_to_one_as_a_word_gets(self):
        self.assertEqual(dsp1tables.node(64), 0x7FFF)

    def test_every_node_on_the_curve_is_the_root_of_its_step(self):
        for step in range(16, 65):
            wanted = int(dsp1tables.ROOT_SCALE * math.sqrt(step / 64))

            self.assertEqual(dsp1tables.node(step), wanted)

    def test_a_node_before_the_curve_lands_among_the_seeds_instead(self):
        self.assertEqual(dsp1tables.node(-1), dsp1tables.newton_seed(0xD4 - 0x65))

    def test_and_the_furthest_one_back_lands_there_too(self):
        self.assertEqual(dsp1tables.node(-64), dsp1tables.newton_seed(0x95 - 0x65))

    def test_the_curve_rises_and_the_seeds_before_it_fall(self):
        self.assertLess(dsp1tables.node(16), dsp1tables.node(64))
        self.assertGreater(dsp1tables.node(-64), dsp1tables.node(-1))


class HorizonTest(unittest.TestCase):
    def test_the_horizon_curve_has_the_coefficients_the_chip_carries(self):
        self.assertEqual(len(dsp1tables.HORIZON), 5)

    def test_and_every_one_of_them_fits_in_a_word(self):
        for value in dsp1tables.HORIZON:
            self.assertTrue(0 <= value <= 0xFFFF)


class ClipTest(unittest.TestCase):
    def test_the_clip_table_has_one_bound_per_exponent(self):
        self.assertEqual(len(dsp1tables.MAX_ZENITH), 16)

    def test_and_the_bounds_rise_with_the_exponent(self):
        self.assertEqual(list(dsp1tables.MAX_ZENITH), sorted(dsp1tables.MAX_ZENITH))


if __name__ == "__main__":
    unittest.main()
