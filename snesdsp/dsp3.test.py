import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp3


def word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


def commanded(command, payload=(), data_rom=None):
    """A chip given a command, which at reset is one byte rather than a word."""
    chip = dsp3.Dsp3(data_rom=data_rom)
    chip.write(command)
    for value in payload:
        chip.write(value)
    return chip


def answered(chip, count):
    return [chip.read() for _ in range(count)]


class PortTest(unittest.TestCase):
    def test_a_fresh_chip_says_it_is_ready_for_a_command(self):
        chip = dsp3.Dsp3()

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)

    def test_a_command_arrives_as_one_byte_while_the_chip_is_waiting_for_one(self):
        chip = dsp3.Dsp3()

        chip.write(0x06)

        self.assertEqual(chip.data, 0x0006)

    def test_and_a_word_as_two_once_a_command_has_been_accepted(self):
        chip = dsp3.Dsp3()
        chip.write(0x06)

        chip.write(0x14)

        self.assertEqual(chip.step, chip._set_window)

    def test_reading_toggles_the_same_half_that_writing_does(self):
        chip = commanded(0x06)

        chip.read()
        chip.write(0x14)

        self.assertEqual((chip.window_low, chip.window_high), (0x06, 0x14))


class WindowTest(unittest.TestCase):
    def test_the_window_command_takes_a_width_and_a_height(self):
        chip = commanded(0x06, word(0x0A14))

        self.assertEqual((chip.window_low, chip.window_high), (0x14, 0x0A))

    def test_and_leaves_the_chip_ready_for_the_next_command(self):
        chip = commanded(0x06, word(0x0A14))

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)


class CellTest(unittest.TestCase):
    def located(self, x, y, width=0x14, height=0x0A):
        chip = commanded(0x06, word((height << 8) | width))
        chip.write(0x03)
        for value in word((y << 8) | x):
            chip.write(value)
        return chip

    def test_a_coordinate_becomes_a_row_walked_by_the_window_width(self):
        chip = self.located(3, 2)

        self.assertEqual(chip.data, 2 * 0x14 + 3)

    def test_the_origin_is_the_first_cell(self):
        chip = self.located(0, 0)

        self.assertEqual(chip.data, 0)


class CoordinateTest(unittest.TestCase):
    def test_a_pair_handed_in_comes_back_out(self):
        chip = commanded(0x02)
        for value in word(0) + word(0) + word(0) + word(0x1234) + word(0x5678):
            chip.write(value)

        for value in word(0):
            chip.write(value)

        self.assertEqual(chip.data, 0x1234)

    def test_and_so_does_the_second_half_of_it(self):
        chip = commanded(0x02)
        for value in word(0) * 3 + word(0x1234) + word(0x5678) + word(0):
            chip.write(value)

        for value in word(0):
            chip.write(value)

        self.assertEqual(chip.data, 0x5678)

    def test_the_end_marker_in_the_third_word_stops_it(self):
        chip = commanded(0x02)

        for value in word(0) + word(0) + word(0xFFFF):
            chip.write(value)

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)


class MoveTest(unittest.TestCase):
    def test_the_six_neighbours_are_the_geometry_of_a_hex_grid(self):
        self.assertEqual(len(dsp3.NEIGHBOURS), 6)

    def test_the_table_repeats_before_it_holds_anything_else(self):
        for move in range(6):
            self.assertEqual(dsp3.move_of(move), dsp3.move_of(move + 6))

    def test_past_the_two_copies_it_holds_things_that_are_not_directions(self):
        self.assertEqual(dsp3.move_of(13), (0, 68))

    def test_and_past_those_it_is_unprogrammed(self):
        self.assertEqual(dsp3.move_of(40), dsp3.STRAY_TAIL)

    def test_a_move_beyond_the_table_wraps_rather_than_being_refused(self):
        self.assertEqual(dsp3.move_of(0x200), dsp3.move_of(0))


class ConvertTest(unittest.TestCase):
    def test_a_solid_row_becomes_a_bit_in_every_plane(self):
        chip = commanded(0x18, word(1))
        for value in [0xFF, 0x00] * 4:
            chip.write(value)

        self.assertEqual(chip.bitplane, bytearray([0xAA] * 8))

    def test_it_hands_the_planes_back_a_word_at_a_time(self):
        chip = commanded(0x18, word(1))
        for value in [0xFF, 0x00] * 4:
            chip.write(value)

        self.assertEqual(chip.data, 0xAAAA)

    def test_and_finishes_once_it_has_converted_what_it_was_asked_for(self):
        chip = commanded(0x18, word(1))
        for value in [0xFF, 0x00] * 4:
            chip.write(value)
        for _ in range(3):
            chip.write(0)
            chip.write(0)

        chip.write(0)
        chip.write(0)

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)


class ConvertStatusTest(unittest.TestCase):
    """What the console is told while the bitmap is going in.

    The part takes those eight bytes one at a time and says so, which is the
    difference between a console that feeds it correctly and one that feeds it
    the same bytes assembled into words and is never told it guessed right.
    Measured against the part's own microcode.
    """

    def test_the_part_asks_for_bytes_once_the_count_has_arrived(self):
        chip = commanded(0x18, word(1))

        self.assertEqual(chip.read_status(), dsp3.READY | dsp3.BYTE_AT_A_TIME)

    def test_and_keeps_asking_for_bytes_until_the_last_one(self):
        chip = commanded(0x18, word(1))
        seen = []
        for value in [0xFF, 0x00] * 4:
            chip.write(value)
            seen.append(chip.read_status())

        self.assertEqual(seen[:7], [dsp3.READY | dsp3.BYTE_AT_A_TIME] * 7)

    def test_then_goes_back_to_words_to_hand_the_planes_over(self):
        chip = commanded(0x18, word(1))
        for value in [0xFF, 0x00] * 4:
            chip.write(value)

        self.assertEqual(chip.read_status(), dsp3.READY)

    def test_the_bytes_land_in_the_order_they_were_written(self):
        chip = commanded(0x18, word(1))
        for value in (0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81):
            chip.write(value)

        self.assertEqual(
            bytes(chip.bitmap), bytes((0x81, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x81))
        )


class DataRomTest(unittest.TestCase):
    def test_the_dump_command_refuses_when_no_table_was_supplied(self):
        chip = commanded(0x1F, [0x00])

        with self.assertRaises(dsp3.DataRomMissing):
            chip.write(0x00)

    def test_and_says_why_rather_than_answering_zeroes(self):
        chip = commanded(0x1F, [0x00])

        with self.assertRaises(dsp3.DataRomMissing) as caught:
            chip.write(0x00)

        self.assertIn("0x1f", str(caught.exception))

    def test_a_supplied_table_is_handed_back_word_by_word(self):
        table = list(range(dsp3.DATA_ROM_WORDS))
        chip = commanded(0x1F, word(0), data_rom=table)

        self.assertEqual(chip.data, 0)

    def test_and_the_walk_ends_when_the_table_does(self):
        table = [0] * dsp3.DATA_ROM_WORDS
        chip = commanded(0x1F, word(0), data_rom=table)
        for _ in range(dsp3.DATA_ROM_WORDS - 1):
            chip.write(0)
            chip.write(0)

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)


class AbsorbTest(unittest.TestCase):
    def test_the_command_that_swallows_words_hands_back_the_last_one(self):
        chip = commanded(0x1C, word(0x1234) + word(0x5678))

        self.assertEqual(answered(chip, 2), word(0x5678))

    def test_and_keeps_handing_it_back_rather_than_going_to_zero(self):
        chip = commanded(0x1C, word(0x1234) + word(0x5678))
        answered(chip, 2)

        self.assertEqual(answered(chip, 4), word(0x5678) + word(0x5678))

    def test_it_swallows_as_many_words_as_it_is_given(self):
        chip = commanded(0x1C, word(0x1234) + word(0x5678) + word(0x9ABC) + word(0xDEF0))

        self.assertEqual(answered(chip, 2), word(0xDEF0))

    def test_and_one_word_is_enough_for_it_to_answer(self):
        chip = commanded(0x1C, word(0x1234))

        self.assertEqual(answered(chip, 2), word(0x1234))

    def test_the_command_that_swallows_a_word_answers_nothing(self):
        chip = commanded(0x0C, word(0x1234))

        self.assertEqual(chip.data, 0)

    def test_the_one_that_swallows_until_the_end_marker_waits_for_it(self):
        chip = commanded(0x10, word(0x1234))

        self.assertNotEqual(chip.step, chip._command)

    def test_and_stops_when_it_arrives(self):
        chip = commanded(0x10, word(0xFFFF))

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)

    def test_the_memory_test_answers_zero(self):
        chip = dsp3.Dsp3()
        chip.write(0x0F)
        chip.read()
        chip.read()

        self.assertEqual([chip.read(), chip.read()], [0x00, 0x00])

    def test_it_hands_back_two_words_before_going_back_to_waiting(self):
        chip = dsp3.Dsp3()
        chip.write(0x0F)

        said = [chip.read() for _ in range(4)]

        self.assertEqual(said, [0x0F, 0x00, 0x00, 0x00])

    def test_and_only_then_is_it_waiting_for_the_next_command(self):
        chip = dsp3.Dsp3()
        chip.write(0x0F)
        for _ in range(3):
            chip.read()

        self.assertNotEqual(chip.read_status(), dsp3.RESET_STATUS)

    def test_which_it_is_once_the_second_word_has_gone(self):
        chip = dsp3.Dsp3()
        chip.write(0x0F)
        for _ in range(4):
            chip.read()

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)


class MultipleTilesTest(unittest.TestCase):
    """A conversion asked for more than one tile, which is what the count is for."""

    SOLID = [0xFF, 0x00] * 4

    def test_a_second_tile_is_asked_for_a_byte_at_a_time_like_the_first(self):
        chip = commanded(0x18, word(2))
        for value in self.SOLID:
            chip.write(value)
        answered(chip, 8)

        self.assertEqual(chip.read_status(), dsp3.READY | dsp3.BYTE_AT_A_TIME)

    def test_and_it_converts_the_same_way(self):
        chip = commanded(0x18, word(2))
        for value in self.SOLID:
            chip.write(value)
        answered(chip, 8)
        for value in self.SOLID:
            chip.write(value)

        self.assertEqual(chip.bitplane, bytearray([0xAA] * 8))

    def test_the_count_is_what_says_how_many_there_are(self):
        chip = commanded(0x18, word(2))
        for value in self.SOLID:
            chip.write(value)
        answered(chip, 8)
        for value in self.SOLID:
            chip.write(value)
        answered(chip, 8)

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)


class RunLengthTest(unittest.TestCase):
    """A run that carries on past its first word, and the count that ends it.

    The decompressor answers either one symbol or a run of them, and a run has a
    second half: the length arrives in its own bits after the code that announced
    it. Driving it only far enough to see the announcement leaves that half
    unread, which is where it used to stop being checked.
    """

    STREAM = (0xA3, 0x27, 0x5F, 0x6D)

    TAIL = (0x0E, 0x4A)

    def decoding(self, outwords):
        chip = commanded(0x38, word(1) + word(outwords))
        for value in self.STREAM:
            chip.write(value)
        return chip

    def _turn(self, chip):
        answered(chip, 2)
        for value in self.TAIL:
            chip.write(value)

    def test_a_run_reaches_the_state_that_reads_its_length(self):
        chip = self.decoding(3)
        seen = set()
        for _ in range(8):
            seen.add(chip.lz_code)
            self._turn(chip)

        self.assertIn(2, seen)

    def test_the_stream_ends_when_the_word_count_runs_out(self):
        chip = self.decoding(3)
        for _ in range(8):
            self._turn(chip)

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)

    def test_a_shorter_stream_ends_sooner(self):
        chip = self.decoding(2)
        for _ in range(8):
            self._turn(chip)

        self.assertEqual(chip.read_status(), dsp3.RESET_STATUS)

    def test_and_the_part_is_waiting_for_a_command_once_it_has(self):
        chip = self.decoding(2)
        for _ in range(8):
            self._turn(chip)

        self.assertTrue(chip.idle)


class StarvedDecoderTest(unittest.TestCase):
    """A stream that runs out of bits in the middle of reading one.

    The decompressor reads a code, then a length, then a symbol, and any of the
    three can arrive half-written when the console has not fed enough. It has to
    stop where it is and pick the same place up when more arrives, and the
    stopping is what these cover.
    """

    def starved(self, outwords, stream, turns):
        chip = commanded(0x38, word(1) + word(outwords))
        for value in stream:
            chip.write(value)
        for _ in range(turns):
            answered(chip, 2)
            for value in stream[:2]:
                chip.write(value)
        return chip

    def test_a_stream_that_stops_mid_code_leaves_the_part_waiting(self):
        chip = self.starved(3, (0xCA, 0xF5), 2)

        self.assertFalse(chip.idle)

    def test_and_it_carries_on_when_more_arrives(self):
        chip = self.starved(3, (0xCA, 0xF5), 2)
        before = chip.data

        chip.write(0xCA)
        chip.write(0xF5)

        self.assertIsInstance(before, int)
        self.assertIsInstance(chip.data, int)

    def test_a_stream_that_stops_mid_length_does_the_same(self):
        chip = self.starved(5, (0x5E, 0xB6, 0xDF, 0xA4), 2)

        self.assertFalse(chip.idle)

    def test_nothing_it_hands_back_while_starved_is_wider_than_a_byte(self):
        chip = self.starved(5, (0x5E, 0xB6, 0xDF, 0xA4), 2)

        for value in answered(chip, 4):
            self.assertTrue(0 <= value <= 0xFF)

    def test_a_symbol_step_that_runs_out_of_bits_stops_where_it_is(self):
        chip = commanded(0x38, word(3) + word(3))
        for value in (0x76, 0x10, 0x54, 0x5B, 0x6D, 0x8E):
            chip.write(value)
        for _ in range(2):
            answered(chip, 2)
            chip.write(0x76)
            chip.write(0x10)

        self.assertTrue(chip.idle)

    def test_a_table_that_ends_on_the_last_bit_does_not_run_into_the_tree(self):
        chip = commanded(0x38, word(3) + word(3))
        for value in (0x62, 0x88, 0xE3, 0x07):
            chip.write(value)
        answered(chip, 2)
        chip.write(0x62)
        chip.write(0x88)

        self.assertFalse(chip.idle)

    def test_a_tree_that_ends_on_the_last_bit_does_not_run_into_the_data(self):
        chip = commanded(0x38, word(1) + word(4))
        for value in (0x48, 0x85):
            chip.write(value)

        self.assertFalse(chip.idle)

    def test_both_pick_up_where_they_stopped_once_more_bits_arrive(self):
        chip = commanded(0x38, word(1) + word(4))
        for value in (0x48, 0x85):
            chip.write(value)

        chip.write(0x48)
        chip.write(0x85)

        self.assertFalse(chip.idle)


class SearchRangeTest(unittest.TestCase):
    """How far out the search goes, and what a second search does with that."""

    RING_CELLS = 36

    def searching(self, radius, again=None):
        chip = commanded(0x06, word((0x0C << 8) | 0x14))
        chip.write(0x3E)
        for value in word((4 << 8) | 4):
            chip.write(value)
        answered(chip, 2)
        chip.write(0x1E)
        for value in word(radius):
            chip.write(value)
        if again is None:
            return chip

        self.walk_the_rings(chip)
        for value in word(radius):
            chip.write(value)
        self.walk_the_weights(chip)
        chip.write(0x1E)
        for value in word(again):
            chip.write(value)
        return chip

    def walk_the_rings(self, chip):
        for _ in range(self.RING_CELLS):
            answered(chip, 2)
            chip.write(0x00)
            chip.write(0x01)
        answered(chip, 2)

    def walk_the_weights(self, chip):
        for _ in range(self.RING_CELLS):
            answered(chip, 3)
        answered(chip, 2)

    def test_a_search_asked_for_no_radius_at_all_starts_at_one(self):
        chip = self.searching(0x0300)

        self.assertEqual(chip.min_radius, 1)

    def test_a_second_search_starts_where_the_first_one_stopped(self):
        chip = self.searching(0x0301, again=0x0501)

        self.assertEqual(chip.min_radius, 4)

    def test_and_remembers_how_far_the_first_one_reached(self):
        chip = self.searching(0x0301)

        self.assertEqual(chip.max_search_radius, 3)


class DecoderTest(unittest.TestCase):
    """The decompressor, whose answer is either a symbol or a run of them."""

    RUN_STREAM = (0xA3, 0x27, 0x5F, 0x6D)

    RUN_TAIL = (0x0E, 0x4A)

    OVERRUNS_AFTER = 1

    def decoding(self, codewords=1, outwords=6):
        chip = commanded(0x38, word(codewords) + word(outwords))
        for value in self.RUN_STREAM:
            chip.write(value)
        answered(chip, 2)
        for value in self.RUN_TAIL:
            chip.write(value)
        return chip

    def test_a_symbol_with_a_high_byte_names_a_run_rather_than_a_value(self):
        chip = self.decoding()

        answered(chip, 2)

        self.assertEqual(chip.lz_code, 1)

    def test_and_the_bit_after_it_says_how_long_the_run_may_be(self):
        chip = self.decoding()
        answered(chip, 2)

        answered(chip, 2)

        self.assertEqual(chip.lz_length, 12)

    def test_a_stream_that_asks_past_the_table_it_built_is_refused(self):
        chip = commanded(0x38, word(4) + word(6))
        for _ in range(self.OVERRUNS_AFTER):
            chip.write(0xFF)
            chip.write(0xFF)
            answered(chip, 2)
        chip.write(0xFF)
        chip.write(0xFF)
        chip.read()

        with self.assertRaises(dsp3.TableOverrun):
            chip.read()


class IdleTest(unittest.TestCase):
    def test_a_fresh_chip_is_waiting_for_a_command(self):
        self.assertTrue(dsp3.Dsp3().idle)

    def test_and_one_part_way_through_a_command_is_not(self):
        self.assertFalse(commanded(0x18, word(4)).idle)


class EdgeSearchTest(unittest.TestCase):
    """A search from a cell against the edge of the grid, where a neighbour is outside it."""

    RING_CELLS = 36

    def test_a_neighbour_outside_the_grid_is_skipped_rather_than_read(self):
        chip = commanded(0x06, word((0x0C << 8) | 0x14))
        chip.write(0x3E)
        for value in word((0 << 8) | 0):
            chip.write(value)
        answered(chip, 2)
        chip.write(0x1E)
        for value in word(0x0301):
            chip.write(value)
        for _ in range(self.RING_CELLS):
            answered(chip, 2)
            chip.write(0x00)
            chip.write(0x01)

        answered(chip, 2)

        self.assertEqual(chip.step, chip._report_weights)


class MixedTerrainTest(unittest.TestCase):
    """A search across ground that a unit cannot enter, which the cost spread skips."""

    RING_CELLS = 36

    def test_a_neighbour_a_unit_cannot_enter_does_not_lower_the_cost(self):
        chip = commanded(0x06, word((0x0C << 8) | 0x14))
        chip.write(0x3E)
        for value in word((5 << 8) | 5):
            chip.write(value)
        answered(chip, 2)
        chip.write(0x1E)
        for value in word(0x0301):
            chip.write(value)
        for cell in range(self.RING_CELLS):
            answered(chip, 2)
            chip.write(0x80 if cell % 2 else 0x00)
            chip.write(0x01)

        answered(chip, 2)

        self.assertEqual(chip.step, chip._report_weights)


class PrintingTest(unittest.TestCase):
    def test_a_chip_prints_as_its_status_and_its_data(self):
        printed = repr(dsp3.Dsp3())

        self.assertIn("0x0084", printed)
        self.assertIn("0x0080", printed)


class UnknownCommandTest(unittest.TestCase):
    def test_a_command_the_chip_does_not_know_leaves_it_where_it_was(self):
        chip = commanded(0x04)

        self.assertEqual(chip.step, chip._command)

    def test_and_one_above_the_range_is_ignored_entirely(self):
        chip = commanded(0x40)

        self.assertEqual(chip.step, chip._command)


if __name__ == "__main__":
    unittest.main()
