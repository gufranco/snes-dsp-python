import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp4


def started(command, payload=()):
    chip = dsp4.Dsp4()
    chip.write(command & 0xFF)
    chip.write(command >> 8)
    for value in payload:
        chip.write(value)
    return chip


def word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


def answered(chip, count):
    return [chip.read() for _ in range(count)]


class ProtocolTest(unittest.TestCase):
    def test_a_command_is_two_bytes_low_first(self):
        chip = dsp4.Dsp4()

        chip.write(0x11)
        chip.write(0x00)

        self.assertEqual(chip.command, 0x0011)

    def test_a_chip_waits_for_the_second_half_before_deciding_anything(self):
        chip = dsp4.Dsp4()

        chip.write(0x11)

        self.assertTrue(chip.waiting)

    def test_a_command_the_chip_does_not_know_leaves_it_waiting_again(self):
        chip = started(0x00FF)

        self.assertTrue(chip.waiting)

    def test_a_command_that_needs_no_input_runs_at_once(self):
        chip = started(0x0005)

        self.assertEqual(chip.sprite_count, 0)

    def test_a_command_that_needs_input_waits_for_all_of_it(self):
        chip = started(0x0000, word(2))

        self.assertEqual(chip.out_count, 0)

    def test_and_runs_when_the_last_byte_arrives(self):
        chip = started(0x0000, word(2) + word(3))

        self.assertGreater(chip.out_count, 0)

    def test_reading_with_nothing_to_give_answers_the_idle_value(self):
        self.assertEqual(dsp4.Dsp4().read(), 0xFF)

    def test_reading_walks_the_output_and_then_stops(self):
        chip = started(0x0000, word(2) + word(3))

        answered(chip, 4)

        self.assertEqual(chip.read(), 0xFF)


class MultiplyTest(unittest.TestCase):
    def test_two_small_numbers_multiply(self):
        chip = started(0x0000, word(3) + word(5))

        self.assertEqual(answered(chip, 4), [15, 0, 0, 0])

    def test_a_negative_multiplicand_gives_a_negative_product(self):
        chip = started(0x0000, word(0xFFFF) + word(2))

        self.assertEqual(answered(chip, 4), [0xFE, 0xFF, 0xFF, 0xFF])

    def test_multiplying_by_nothing_gives_nothing(self):
        chip = started(0x0000, word(0) + word(0x7FFF))

        self.assertEqual(answered(chip, 4), [0, 0, 0, 0])


class MappingTest(unittest.TestCase):
    def test_the_mapping_command_packs_four_values_into_one_word(self):
        chip = started(0x0011, word(1) + word(1) + word(1) + word(1))

        self.assertEqual(len(answered(chip, 2)), 2)

    def test_four_zeroes_map_to_zero(self):
        chip = started(0x0011, word(0) * 4)

        self.assertEqual(answered(chip, 2), [0, 0])


class LookupTest(unittest.TestCase):
    def test_the_lookup_command_answers_four_words(self):
        chip = started(0x000A, word(0) + word(0x0123) + word(0))

        self.assertEqual(len(answered(chip, 8)), 8)

    def test_each_nibble_chooses_its_own_entry(self):
        chip = started(0x000A, word(0) + word(0x0000) + word(0))

        self.assertEqual(answered(chip, 8), [0] * 8)

    def test_the_answers_come_back_in_the_order_the_caller_reads_them(self):
        chip = started(0x000A, word(0) + word(0x1234) + word(0))

        self.assertEqual(answered(chip, 8), [0x60, 0, 0x30, 0, 0xC0, 0, 0x90, 0])


class SpriteTest(unittest.TestCase):
    def test_clearing_the_table_forgets_every_sprite(self):
        chip = started(0x0005)

        self.assertEqual((chip.oam_index, chip.oam_bits, chip.sprite_count), (0, 0, 0))

    def test_the_selection_command_sets_the_row_limit(self):
        chip = started(0x0003)

        self.assertEqual(chip.oam_row_max, 33)

    def test_and_empties_every_row(self):
        chip = started(0x0003)

        self.assertEqual(list(chip.oam_row), [0] * 32)

    def test_transferring_the_table_hands_back_thirty_two_bytes(self):
        chip = started(0x0006)

        self.assertEqual(chip.out_count, 32)

    def test_setting_a_sprite_inside_the_screen_draws_it(self):
        started(0x0005)
        chip = started(0x0003)
        chip.write(0x0B)
        chip.write(0x00)
        for value in word(100) + word(50) + word(0x1234):
            chip.write(value)

        self.assertEqual(chip.read(), 1)

    def test_a_sprite_below_the_screen_says_so_rather_than_going_quiet(self):
        chip = started(0x0003)
        chip.write(0x0B)
        chip.write(0x00)
        for value in word(100) + word(0x00F0) + word(0x1234):
            chip.write(value)

        self.assertEqual(answered(chip, 2), [0, 0])


class AcknowledgementTest(unittest.TestCase):
    def test_a_write_while_output_is_pending_steps_past_it(self):
        chip = started(0x0000, word(3) + word(5))

        chip.write(0x00)

        self.assertEqual(chip.out_index, 1)

    def test_and_does_not_start_a_new_command(self):
        chip = started(0x0000, word(3) + word(5))

        chip.write(0x11)

        self.assertEqual(chip.command, 0x0000)


class CrowdingTest(unittest.TestCase):
    def place(self, chip, x, y):
        chip.write(0x0B)
        chip.write(0x00)
        for value in word(x) + word(y) + word(0):
            chip.write(value)
        drained = [chip.read() for _ in range(8)]
        return drained[0]

    def test_a_row_that_is_full_refuses_the_next_sprite(self):
        chip = started(0x0003)
        chip.oam_row_max = 1

        self.place(chip, 10, 8)

        self.assertEqual(self.place(chip, 20, 8), 0)

    def test_the_chip_stops_once_it_has_a_full_table_of_sprites(self):
        chip = started(0x0003)
        chip.sprite_count = 128

        self.assertEqual(self.place(chip, 10, 8), 0)

    def test_eight_sprites_fill_the_first_word_of_the_table(self):
        chip = started(0x0003)
        started(0x0005)
        chip.oam_index = 0
        chip.oam_bits = 0

        for at in range(8):
            self.place(chip, 10, at * 8)

        self.assertEqual((chip.oam_index, chip.oam_bits), (1, 0))

    def test_a_sprite_off_the_side_is_marked_in_the_table(self):
        chip = started(0x0003)
        chip.oam_index = 0
        chip.oam_bits = 0

        self.place(chip, 300, 8)

        self.assertEqual(chip.oam_attr[0] & 1, 1)


class UnfinishedTest(unittest.TestCase):
    """The renderers are not modelled, and saying nothing would be a real answer."""

    def test_a_renderer_says_it_is_not_here_rather_than_going_quiet(self):
        chip = dsp4.Dsp4()
        chip.write(0x0E)

        with self.assertRaises(dsp4.Unimplemented):
            chip.write(0x00)

    def test_and_the_refusal_names_the_command(self):
        chip = dsp4.Dsp4()
        chip.write(0x09)
        chip.write(0x00)
        for _ in range(13):
            chip.write(0)

        with self.assertRaises(dsp4.Unimplemented) as caught:
            chip.write(0)

        self.assertIn("0x0009", str(caught.exception))


class TrackTest(unittest.TestCase):
    """The one renderer that is here, and the places it stops for more input."""

    def road(self):
        chip = dsp4.Dsp4()
        chip.write(0x01)
        chip.write(0x00)
        for value in (
            word(0)
            + word(0x0002)
            + word(200)
            + word(10)
            + word(0)
            + word(100)
            + word(0)
            + word(0x0001)
            + word(0)
            + word(0x0100)
            + word(0)
            + word(0)
            + word(0)
            + word(0)
            + word(0)
            + word(0x2000)
            + word(0)
            + word(0)
            + word(0)
            + word(0)
            + word(0)
            + word(0)
        ):
            chip.write(value)
        return chip

    def test_the_projection_asks_for_the_next_distance_when_it_has_drawn_one_stretch(self):
        chip = self.road()

        self.assertEqual(chip.in_count, 2)

    def test_and_is_not_waiting_for_a_new_command(self):
        chip = self.road()

        self.assertFalse(chip.waiting)

    def test_it_produces_a_header_before_any_scanline(self):
        chip = self.road()

        self.assertGreaterEqual(chip.out_count, 10)

    def test_the_end_marker_finishes_the_command(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x00)
        chip.write(0x80)

        self.assertTrue(chip.waiting)

    def test_a_fork_in_the_road_asks_for_its_own_six_bytes(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x01)
        chip.write(0x80)

        self.assertEqual(chip.in_count, 6)

    def test_and_then_for_the_next_distance_again(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()
        chip.write(0x01)
        chip.write(0x80)
        for value in word(0x1000) + word(4) + word(1):
            chip.write(value)

        self.assertEqual(chip.in_count, 2)

    def test_a_fork_moves_the_viewer_sideways(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()
        before = chip.view_x1
        chip.write(0x01)
        chip.write(0x80)
        for value in word(0x4000) + word(0x0100) + word(1):
            chip.write(value)

        self.assertNotEqual(chip.view_x1, before)

    def test_an_ordinary_stretch_asks_for_its_curvature(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x00)
        chip.write(0x10)

        self.assertEqual(chip.in_count, 6)


class TurnoffTest(unittest.TestCase):
    """The road that leaves the road, which is told where it is rather than working it out."""

    def branch(self):
        chip = dsp4.Dsp4()
        chip.write(0x07)
        chip.write(0x00)
        for value in (
            word(0)
            + word(0x0002)
            + word(200)
            + word(10)
            + word(0)
            + word(100)
            + word(0)
            + word(0x0001)
            + word(0)
            + word(0x0100)
            + word(0)
            + word(0x2000)
            + word(120)
            + word(2)
            + word(40)
            + word(16)
            + word(0)
        ):
            chip.write(value)
        return chip

    def test_it_asks_for_the_next_distance_once_it_has_drawn_a_stretch(self):
        chip = self.branch()

        self.assertEqual(chip.in_count, 2)

    def test_it_produces_a_header_before_any_scanline(self):
        chip = self.branch()

        self.assertGreaterEqual(chip.out_count, 6)

    def test_the_next_stretch_wants_ten_bytes_rather_than_six(self):
        chip = self.branch()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x00)
        chip.write(0x10)

        self.assertEqual(chip.in_count, 10)

    def test_the_end_marker_finishes_the_command(self):
        chip = self.branch()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x00)
        chip.write(0x80)

        self.assertTrue(chip.waiting)

    def test_a_branch_above_the_window_draws_nothing_below_it(self):
        chip = dsp4.Dsp4()
        chip.write(0x07)
        chip.write(0x00)
        for value in (
            word(0)
            + word(0x0002)
            + word(200)
            + word(100)
            + word(0)
            + word(100)
            + word(0)
            + word(0x0001)
            + word(0)
            + word(0x0100)
            + word(0)
            + word(0x2000)
            + word(0)
            + word(0)
            + word(40)
            + word(0)
            + word(0)
        ):
            chip.write(value)

        self.assertEqual(chip.segments, 0)

    def test_and_flushes_what_is_left_when_the_viewer_is_still_below_it(self):
        chip = dsp4.Dsp4()
        chip.write(0x07)
        chip.write(0x00)
        for value in (
            word(0)
            + word(0x0096)
            + word(200)
            + word(100)
            + word(0)
            + word(100)
            + word(0)
            + word(0x0001)
            + word(0)
            + word(0x0100)
            + word(0)
            + word(0x2000)
            + word(0)
            + word(0)
            + word(40)
            + word(0)
            + word(0)
        ):
            chip.write(value)

        self.assertGreater(chip.segments, 0)

    def test_the_branch_moves_across_the_screen_by_its_own_step(self):
        chip = self.branch()
        first = chip.view_x2
        for _ in range(chip.out_count):
            chip.read()
        chip.write(0x00)
        chip.write(0x10)
        for value in word(120) + word(2) + word(40) + word(16) + word(0):
            chip.write(value)

        self.assertNotEqual(chip.view_x2, first)


class ReadingTest(unittest.TestCase):
    def test_a_chip_prints_as_its_command_and_what_it_is_waiting_for(self):
        self.assertIn("command", repr(dsp4.Dsp4()))


if __name__ == "__main__":
    unittest.main()
