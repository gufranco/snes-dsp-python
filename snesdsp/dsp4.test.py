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

    def test_the_shared_screen_selection_leaves_half_the_room(self):
        chip = started(0x000E)

        self.assertEqual(chip.oam_row_max, 16)

    def test_and_empties_every_row_as_well(self):
        chip = started(0x0003)
        chip.oam_row[3] = 5

        started(0x000E)
        chip = started(0x000E)

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
        chip.write(0x09)
        chip.write(0x00)
        for _ in range(13):
            chip.write(0)

        with self.assertRaises(dsp4.Unimplemented):
            chip.write(0)

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


class SharedTrackTest(unittest.TestCase):
    """The multi-player road, which differs from the other in two places."""

    def road(self, top=10):
        chip = dsp4.Dsp4()
        chip.write(0x0D)
        chip.write(0x00)
        for value in (
            word(0)
            + word(0x0002)
            + word(200)
            + word(top)
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
        ):
            chip.write(value)
        return chip

    def test_it_asks_for_the_next_distance_once_it_has_drawn_a_stretch(self):
        chip = self.road()

        self.assertEqual(chip.in_count, 2)

    def test_its_horizontal_shaping_is_one_word_rather_than_two(self):
        chip = self.road()

        self.assertEqual(chip.in_index, 0)
        self.assertEqual(chip.in_count, 2)

    def test_the_next_stretch_wants_six_bytes(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x00)
        chip.write(0x10)

        self.assertEqual(chip.in_count, 6)

    def test_the_end_marker_finishes_the_command(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x00)
        chip.write(0x80)

        self.assertTrue(chip.waiting)

    def test_a_stretch_that_is_fed_its_curvature_asks_for_the_next_distance(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()
        chip.write(0x00)
        chip.write(0x10)

        for value in word(1) + word(2) + word(3):
            chip.write(value)

        self.assertEqual(chip.in_count, 2)

    def test_a_fork_is_not_something_this_projection_understands(self):
        chip = self.road()
        for _ in range(chip.out_count):
            chip.read()

        chip.write(0x01)
        chip.write(0x80)

        self.assertEqual(chip.in_count, 6)


class SolidRendererTest(unittest.TestCase):
    """Two shapes given as the window edges that carve them out."""

    def opening(self, top=0, left_clip=0, right_clip=255, envelope=(0, 0, 0, 0)):
        clip_right = word(right_clip) * 4
        clip_left = word(left_clip) * 4
        unknown = word(0) * 8
        centre = word(128) * 4
        pointer = word(0x1000) * 4
        bottom = word(200) * 4
        clip_top = word(top) * 4
        return (
            clip_right
            + clip_left
            + unknown
            + centre
            + pointer
            + bottom
            + clip_top
            + word(0) * 4
            + word(0x2000)
            + word(0)
            + word(180)
            + word(0)
            + word(180)
            + word(envelope[0])
            + word(envelope[1])
            + word(envelope[2])
            + word(envelope[3])
        )

    def shape(self, first_y=170, second_y=170, envelope=(0, 0, 0, 0)):
        return (
            word(0)
            + word(first_y)
            + word(0)
            + word(second_y)
            + word(envelope[0])
            + word(envelope[1])
            + word(envelope[2])
            + word(envelope[3])
        )

    def stretch(self, chip, distance=0x2000, **shaping):
        for value in word(distance):
            chip.write(value)
        for value in self.shape(**shaping):
            chip.write(value)
        return chip

    def test_the_opening_hands_back_the_window_the_first_shape_starts_from(self):
        chip = started(0x0008, self.opening())

        self.assertEqual(answered(chip, 2), [128, 128])

    def test_a_window_edge_outside_its_clip_is_pulled_back_to_it(self):
        chip = started(0x0008, self.opening(left_clip=200, right_clip=255))

        self.assertEqual(answered(chip, 2), [200, 200])

    def test_a_clip_whose_edges_are_the_wrong_way_round_settles_on_the_high_one(self):
        chip = started(0x0008, self.opening(left_clip=200, right_clip=100))

        self.assertEqual(answered(chip, 2), [100, 100])

    def test_it_asks_for_two_bytes_once_the_opening_is_in(self):
        chip = started(0x0008, self.opening())

        self.assertEqual(chip.in_count, 2)

    def test_and_for_sixteen_more_once_it_has_a_distance(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)

        for value in word(0x2000):
            chip.write(value)

        self.assertEqual(chip.in_count, 16)

    def test_a_shape_that_has_not_moved_covers_no_scanlines(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)
        self.stretch(chip, second_y=180)

        self.assertEqual(answered(chip, 2), [10, 0])

    def test_a_shape_above_its_top_clip_covers_none_either(self):
        chip = started(0x0008, self.opening(top=200))
        answered(chip, chip.out_count)
        self.stretch(chip)

        self.assertEqual(answered(chip, 2), [0, 0])

    def test_each_scanline_carries_a_pointer_and_two_window_edges(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)
        self.stretch(chip, first_y=178, second_y=180)

        found = answered(chip, 6)

        self.assertEqual(found[:2], [2, 0])
        self.assertEqual(found[2:4], word(0x1000))

    def test_the_pointer_walks_backwards_four_bytes_at_a_time(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)
        self.stretch(chip, first_y=178, second_y=180)
        answered(chip, chip.out_count)
        self.stretch(chip, first_y=176, second_y=180)

        found = answered(chip, 4)

        self.assertEqual(found[2:4], word(0x1000 - 8))

    def test_a_shape_shaped_by_the_fork_word_is_projected_from_the_other_one(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)
        self.stretch(chip, first_y=178, second_y=180, envelope=(-0x3FFF, 0, 0, 0))

        self.assertEqual(chip.solid_start[0], chip.solid_start[1])

    def test_and_so_is_one_shaped_by_the_other_fork_word(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)
        self.stretch(chip, first_y=178, second_y=180, envelope=(0, 0x3FFF, 0, 0))

        self.assertEqual(chip.solid_start[0], chip.solid_start[1])

    def test_the_track_ends_on_a_single_zero_word(self):
        chip = started(0x0008, self.opening())
        answered(chip, chip.out_count)

        for value in word(-0x8000):
            chip.write(value)

        self.assertEqual(answered(chip, 2), [0, 0])
        self.assertTrue(chip.waiting)


class ReciprocalTest(unittest.TestCase):
    def test_one_over_nothing_is_nothing(self):
        self.assertEqual(dsp4.inverse(0), 0)

    def test_one_over_one_comes_back_negative_because_the_table_does_not_fit(self):
        self.assertEqual(dsp4.inverse(1), -0x8000)

    def test_every_other_entry_is_positive(self):
        for value in range(2, 64):
            self.assertGreater(dsp4.inverse(value), 0)

    def test_a_run_longer_than_the_table_reuses_its_last_entry(self):
        self.assertEqual(dsp4.inverse(200), dsp4.inverse(63))

    def test_and_a_negative_run_its_first(self):
        self.assertEqual(dsp4.inverse(-5), dsp4.inverse(0))


class ClampTest(unittest.TestCase):
    def test_a_value_inside_its_window_is_left_alone(self):
        self.assertEqual(dsp4.clamp(50, 0, 100), 50)

    def test_one_below_it_is_pulled_up(self):
        self.assertEqual(dsp4.clamp(-5, 0, 100), 0)

    def test_one_above_it_is_pulled_down(self):
        self.assertEqual(dsp4.clamp(500, 0, 100), 100)

    def test_a_window_the_wrong_way_round_settles_on_the_high_edge(self):
        self.assertEqual(dsp4.clamp(50, 100, 0), 0)


class ReadingTest(unittest.TestCase):
    def test_a_chip_prints_as_its_command_and_what_it_is_waiting_for(self):
        self.assertIn("command", repr(dsp4.Dsp4()))


if __name__ == "__main__":
    unittest.main()
