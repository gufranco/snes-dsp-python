import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import dsp1


def word(value):
    return [value & 0xFF, (value >> 8) & 0xFF]


def asked(command, payload=(), data_rom=None, revision=None):
    chip = dsp1.Dsp1(data_rom=data_rom, **({"revision": revision} if revision else {}))
    chip.write(command)
    for value in payload:
        chip.write(value)
    return chip


def answered(chip, count):
    return [chip.read() for _ in range(count)]


def read_word(chip):
    low, high = answered(chip, 2)
    return dsp1.signed16(low | (high << 8))


class ProtocolTest(unittest.TestCase):
    def test_a_fresh_chip_is_waiting_for_a_command(self):
        self.assertTrue(dsp1.Dsp1().waiting)

    def test_a_command_names_how_many_bytes_it_wants(self):
        chip = asked(0x00)

        self.assertEqual(chip.in_count, 4)

    def test_and_runs_when_the_last_one_arrives(self):
        chip = asked(0x00, word(2) + word(3))

        self.assertTrue(chip.waiting)

    def test_a_command_the_chip_does_not_know_leaves_it_waiting(self):
        chip = asked(0x80)

        self.assertTrue(chip.waiting)
        self.assertEqual(chip.in_count, 0)

    def test_reading_with_nothing_to_give_answers_the_idle_value(self):
        self.assertEqual(dsp1.Dsp1().read(), dsp1.IDLE)

    def test_reading_walks_the_output_and_then_stops(self):
        chip = asked(0x00, word(0x4000) + word(0x4000))

        answered(chip, 2)

        self.assertEqual(chip.read(), dsp1.IDLE)


class ArithmeticTest(unittest.TestCase):
    """The pieces every command is built from, at the values that are not arithmetic."""

    def test_the_sine_of_the_angle_a_word_cannot_negate_is_nothing(self):
        self.assertEqual(dsp1.sine(-0x8000), 0)

    def test_and_its_cosine_is_the_value_a_word_cannot_negate(self):
        self.assertEqual(dsp1.cosine(-0x8000), -0x8000)

    def test_narrowing_nothing_leaves_it_alone_however_far_it_is_shifted(self):
        self.assertEqual(dsp1.narrowed(0, 4), 0)

    def test_narrowing_by_nothing_leaves_a_value_alone(self):
        self.assertEqual(dsp1.narrowed(0x1234, 0), 0x1234)

    def test_one_over_a_negative_half_answers_a_different_exponent(self):
        positive = dsp1.inverse(0x4000, 0)
        negative = dsp1.inverse(-0x4000, 0)

        self.assertEqual(negative[0], -0x4000)
        self.assertEqual(negative[1], positive[1] + 1)

    def test_a_value_a_word_cannot_negate_is_halved_before_it_is_negated(self):
        self.assertEqual(dsp1.halved_if_unnegatable(-0x8000, 3), (-0x4000, 4))

    def test_and_anything_else_is_left_where_it_was(self):
        self.assertEqual(dsp1.halved_if_unnegatable(-0x4000, 3), (-0x4000, 3))


class OddMultiplyTest(unittest.TestCase):
    def test_the_second_multiply_forces_its_answer_odd(self):
        for first, second in ((0x0100, 0x8000), (0x1234, 0x4000), (0x7FFF, 0x7FFF)):
            chip = asked(0x20, word(first) + word(second))

            self.assertEqual(read_word(chip) & 1, 1, (first, second))

    def test_and_leaves_an_answer_that_is_already_odd_alone(self):
        plain = asked(0x00, word(0x3508) + word(0x00A0))
        odd = asked(0x20, word(0x3508) + word(0x00A0))

        self.assertEqual(read_word(odd), read_word(plain) | 1)

    def test_it_is_the_plain_multiply_with_one_bit_forced(self):
        for first, second in ((0x756B, 0xE445), (0xE425, 0xBCB8), (0x3508, 0x00A0)):
            plain = read_word(asked(0x00, word(first) + word(second)))
            odd = read_word(asked(0x20, word(first) + word(second)))

            self.assertEqual(odd, dsp1.signed16((plain | 1) & 0xFFFF), (first, second))


class MultiplyTest(unittest.TestCase):
    def test_a_product_comes_back_scaled_down_by_a_word(self):
        chip = asked(0x00, word(0x4000) + word(0x4000))

        self.assertEqual(read_word(chip), 0x2000)

    def test_a_negative_multiplicand_gives_a_negative_product(self):
        chip = asked(0x00, word(-0x4000) + word(0x4000))

        self.assertEqual(read_word(chip), -0x2000)

    def test_the_other_multiply_forces_its_answer_odd_rather_than_adding_one(self):
        first = asked(0x00, word(0x1234) + word(0x4321))
        second = asked(0x20, word(0x1234) + word(0x4321))

        self.assertEqual(read_word(second), read_word(first) | 1)


class TrigonometryTest(unittest.TestCase):
    def test_the_sine_of_nothing_is_nothing(self):
        chip = asked(0x04, word(0) + word(0x7FFF))

        self.assertEqual(read_word(chip), 0)

    def test_and_the_cosine_of_nothing_is_the_radius(self):
        chip = asked(0x04, word(0) + word(0x7FFF))
        answered(chip, 2)

        self.assertEqual(read_word(chip), 0x7FFE)

    def test_a_quarter_turn_puts_the_radius_in_the_sine(self):
        chip = asked(0x04, word(0x4000) + word(0x7FFF))

        self.assertEqual(read_word(chip), 0x7FFE)


class InverseTest(unittest.TestCase):
    def test_one_over_nothing_saturates_rather_than_dividing(self):
        chip = asked(0x10, word(0) + word(0))

        self.assertEqual(read_word(chip), 0x7FFF)

    def test_and_says_so_in_the_exponent(self):
        chip = asked(0x10, word(0) + word(0))
        answered(chip, 2)

        self.assertEqual(read_word(chip), 0x2F)

    def test_one_over_a_half_is_as_close_to_two_as_a_word_gets(self):
        chip = asked(0x10, word(0x4000) + word(0))

        self.assertEqual(read_word(chip), 0x7FFF)


class RadiusTest(unittest.TestCase):
    def test_the_squared_length_comes_back_as_two_words(self):
        chip = asked(0x08, word(3) + word(4) + word(0))

        low = read_word(chip)
        high = read_word(chip)

        self.assertEqual((high << 16) | (low & 0xFFFF), (9 + 16) << 1)

    def test_the_range_command_takes_a_radius_off_it(self):
        chip = asked(0x18, word(0x100) + word(0) + word(0) + word(0x100))

        self.assertEqual(read_word(chip), 0)

    def test_and_its_other_form_answers_one_more(self):
        chip = asked(0x38, word(0x100) + word(0) + word(0) + word(0x100))

        self.assertEqual(read_word(chip), 1)


class DistanceTest(unittest.TestCase):
    def test_the_length_of_nothing_is_nothing(self):
        chip = asked(0x28, word(0) + word(0) + word(0))

        self.assertEqual(read_word(chip), 0)

    def test_the_length_of_a_vector_is_near_its_root(self):
        chip = asked(0x28, word(0x2000) + word(0) + word(0))

        self.assertGreater(read_word(chip), 0x1F00)


class RotationTest(unittest.TestCase):
    def test_turning_by_nothing_leaves_a_point_where_it_was(self):
        chip = asked(0x0C, word(0) + word(0x1000) + word(0x2000))

        self.assertEqual(read_word(chip), 0x0FFF)


class PerspectiveTest(unittest.TestCase):
    """The depth a point sits at, which one value the chip refuses to believe."""

    def test_a_depth_of_minus_one_is_read_as_no_depth_at_all(self):
        chip = dsp1.Dsp1(fill=0)

        scale, _, _, _ = chip._perspective(-1, 16)
        cleared, _, _, _ = chip._perspective(0, 16)

        self.assertEqual(scale, cleared)


class PrintingTest(unittest.TestCase):
    def test_a_chip_prints_as_its_command_and_whether_it_is_waiting(self):
        printed = repr(dsp1.Dsp1())

        self.assertIn("0x00", printed)
        self.assertIn("True", printed)


class MemoryTest(unittest.TestCase):
    def test_the_memory_test_reports_a_pass(self):
        chip = asked(0x0F, word(0))

        self.assertEqual(read_word(chip), 0)

    def test_the_size_command_answers_the_word_that_names_the_mask(self):
        chip = asked(0x2F, word(0))

        self.assertEqual(read_word(chip), dsp1.VERSION_WORD[dsp1.FIRST_MASK])

    def test_the_later_mask_answers_a_different_word_there(self):
        chip = asked(0x2F, word(0), revision=dsp1.CORRECTED_MASK)

        self.assertEqual(read_word(chip), dsp1.VERSION_WORD[dsp1.CORRECTED_MASK])

    def test_and_the_two_words_are_not_the_same(self):
        self.assertNotEqual(
            dsp1.VERSION_WORD[dsp1.FIRST_MASK], dsp1.VERSION_WORD[dsp1.CORRECTED_MASK]
        )

    def test_every_mask_the_chip_answers_to_has_a_word_of_its_own(self):
        for revision in dsp1.MASKS:
            self.assertIn(revision, dsp1.VERSION_WORD)

    def test_a_mask_the_chip_does_not_have_is_refused(self):
        with self.assertRaises(dsp1.UnknownMask):
            dsp1.Dsp1(revision="dsp1z")

    def test_a_chip_remembers_which_mask_it_is(self):
        self.assertEqual(dsp1.Dsp1(revision=dsp1.CORRECTED_MASK).revision, dsp1.CORRECTED_MASK)

    def test_and_defaults_to_the_first_one(self):
        self.assertEqual(dsp1.Dsp1().revision, dsp1.FIRST_MASK)


class DataRomTest(unittest.TestCase):
    def test_the_dump_command_refuses_when_no_table_was_supplied(self):
        with self.assertRaises(dsp1.DataRomMissing):
            asked(0x1F, word(0))

    def test_and_says_why_rather_than_answering_zeroes(self):
        with self.assertRaises(dsp1.DataRomMissing) as caught:
            asked(0x1F, word(0))

        self.assertIn("0x1f", str(caught.exception))

    def test_a_supplied_table_comes_back_low_byte_first(self):
        table = list(range(dsp1.DATA_ROM_WORDS))
        chip = asked(0x1F, word(0), data_rom=table)

        self.assertEqual(answered(chip, 4), [0, 0, 1, 0])

    def test_and_the_whole_table_is_two_thousand_and_forty_eight_bytes(self):
        table = [0] * dsp1.DATA_ROM_WORDS
        chip = asked(0x1F, word(0), data_rom=table)

        self.assertEqual(chip.out_count, dsp1.DATA_ROM_WORDS * 2)


class RasterTest(unittest.TestCase):
    def parametered(self):
        chip = dsp1.Dsp1()
        chip.write(0x02)
        for value in (
            word(0) + word(0) + word(0x2000) + word(0x1000) + word(0x1000) + word(0) + word(0)
        ):
            chip.write(value)
        answered(chip, 8)
        return chip

    def test_the_raster_command_answers_four_words(self):
        chip = self.parametered()
        chip.write(0x0A)
        for value in word(0):
            chip.write(value)

        self.assertEqual(chip.out_count, 8)

    def test_and_hands_back_another_four_when_those_run_out(self):
        chip = self.parametered()
        chip.write(0x0A)
        for value in word(0):
            chip.write(value)

        answered(chip, 8)

        self.assertEqual(chip.out_count, 8)

    def test_a_write_while_it_still_has_output_is_swallowed(self):
        chip = self.parametered()
        chip.write(0x0A)
        for value in word(0):
            chip.write(value)
        before = chip.out_count

        chip.write(0x00)

        self.assertEqual(chip.out_count, before - 1)


if __name__ == "__main__":
    unittest.main()
