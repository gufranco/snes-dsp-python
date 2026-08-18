import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsp2 import chip as unit
from dsp2.memory import PARAMETER_BYTES


def clean_chip():
    return unit.Chip(fill=0)


def feed(machine, values):
    for value in values:
        machine.write(value)
    return machine


def drain(machine, count):
    return bytes(machine.read() for _ in range(count))


class StartTest(unittest.TestCase):
    def test_the_parameter_ram_is_not_assumed_clear(self):
        machine = unit.Chip()

        self.assertNotEqual(machine.parameter_ram, bytearray(PARAMETER_BYTES))

    def test_a_clean_parameter_ram_is_a_decision_a_caller_can_make(self):
        self.assertEqual(clean_chip().parameter_ram, bytearray(PARAMETER_BYTES))

    def test_a_chip_repeats_for_one_seed(self):
        self.assertEqual(unit.Chip(seed=5).parameter_ram, unit.Chip(seed=5).parameter_ram)

    def test_a_chip_reads_as_idle_before_anything_is_asked_of_it(self):
        self.assertEqual(clean_chip().read(), unit.IDLE_BYTE)

    def test_the_transparent_colour_starts_somewhere_defined(self):
        self.assertIn(clean_chip().transparent, range(16))


class TransparentTest(unittest.TestCase):
    def test_setting_the_colour_takes_one_byte(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0x07])

        self.assertEqual(machine.transparent, 0x07)

    def test_the_whole_byte_of_the_colour_is_kept(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0xF3])

        self.assertEqual(machine.transparent, 0xF3)

    def test_only_the_low_nibble_of_the_colour_decides_transparency(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0xF2])

        feed(machine, [unit.COMMAND_MERGE, 0x01, 0x11, 0x22])

        self.assertEqual(drain(machine, 1), bytes([0x11]))

    def test_setting_the_colour_produces_nothing_to_read(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0x07])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)

    def test_the_colour_survives_the_next_command(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0x05])

        feed(machine, [unit.COMMAND_MULTIPLY, 0x02, 0x00, 0x03, 0x00])

        self.assertEqual(machine.transparent, 0x05)


class MultiplyTest(unittest.TestCase):
    def test_a_multiply_gives_four_bytes_back(self):
        machine = feed(clean_chip(), [unit.COMMAND_MULTIPLY, 0x02, 0x00, 0x03, 0x00])

        self.assertEqual(drain(machine, 4), (6).to_bytes(4, "little"))

    def test_a_multiply_reports_what_is_waiting(self):
        machine = feed(clean_chip(), [unit.COMMAND_MULTIPLY, 0x02, 0x00, 0x03, 0x00])

        self.assertEqual(machine.pending_output, 4)

    def test_reading_the_result_spends_it(self):
        machine = feed(clean_chip(), [unit.COMMAND_MULTIPLY, 0x02, 0x00, 0x03, 0x00])

        drain(machine, 4)

        self.assertEqual(machine.read(), unit.IDLE_BYTE)

    def test_a_result_read_only_in_part_is_still_waiting(self):
        machine = feed(clean_chip(), [unit.COMMAND_MULTIPLY, 0x02, 0x00, 0x03, 0x00])

        machine.read()

        self.assertEqual(machine.pending_output, 3)


class TileTest(unittest.TestCase):
    def test_a_tile_gives_thirty_two_bytes_back(self):
        machine = feed(clean_chip(), [unit.COMMAND_TILE, *range(32)])

        self.assertEqual(len(drain(machine, 32)), 32)

    def test_a_tile_needs_all_thirty_two_bytes_before_it_runs(self):
        machine = feed(clean_chip(), [unit.COMMAND_TILE, *range(31)])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)


class MirrorTest(unittest.TestCase):
    def test_a_mirror_takes_a_length_then_that_many_bytes(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x02, 0x12, 0x34])

        self.assertEqual(drain(machine, 2), bytes([0x43, 0x21]))

    def test_a_mirror_does_not_run_before_its_payload_arrives(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x02, 0x12])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)


class MergeTest(unittest.TestCase):
    def test_a_merge_takes_two_runs_of_the_length(self):
        machine = feed(clean_chip(), [unit.COMMAND_MERGE, 0x01, 0x11, 0x22])

        self.assertEqual(drain(machine, 1), bytes([0x22]))

    def test_a_merge_uses_the_colour_that_was_set(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0x02])

        feed(machine, [unit.COMMAND_MERGE, 0x01, 0x11, 0x22])

        self.assertEqual(drain(machine, 1), bytes([0x11]))


class ScaleTest(unittest.TestCase):
    def test_a_scale_takes_two_lengths_then_half_the_input(self):
        machine = feed(clean_chip(), [unit.COMMAND_SCALE, 0x04, 0x04, 0x12, 0x34])

        self.assertEqual(len(drain(machine, 4)), 4)

    def test_a_scale_reads_the_parameter_ram_past_its_payload(self):
        machine = unit.Chip(fill=0)
        machine.parameter_ram[60] = 0xAB

        feed(machine, [unit.COMMAND_SCALE, 120, 120, *([0x00] * 60)])

        self.assertEqual(drain(machine, 120)[60], 0xAB)

    def test_a_scale_of_an_odd_length_rounds_its_payload_up(self):
        machine = feed(clean_chip(), [unit.COMMAND_SCALE, 0x03, 0x04, 0x12, 0x34])

        self.assertEqual(len(drain(machine, 4)), 4)


class SyncTest(unittest.TestCase):
    def test_a_sync_produces_nothing_to_read(self):
        machine = feed(clean_chip(), [unit.COMMAND_SYNC])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)

    def test_a_sync_does_not_disturb_the_transparent_colour(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0x09])

        feed(machine, [unit.COMMAND_SYNC])

        self.assertEqual(machine.transparent, 0x09)

    def test_a_command_the_chip_does_not_know_produces_nothing(self):
        machine = feed(clean_chip(), [0xAA])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)

    def test_a_command_the_chip_does_not_know_leaves_it_ready(self):
        machine = feed(clean_chip(), [0xAA])

        feed(machine, [unit.COMMAND_MULTIPLY, 0x02, 0x00, 0x02, 0x00])

        self.assertEqual(drain(machine, 4), (4).to_bytes(4, "little"))


class ProtocolTest(unittest.TestCase):
    def test_a_write_keeps_only_the_low_byte(self):
        machine = feed(clean_chip(), [unit.COMMAND_TRANSPARENT, 0x1FF])

        self.assertEqual(machine.transparent, 0xFF)

    def test_no_command_can_ask_for_more_than_the_ram_holds(self):
        self.assertLessEqual(unit.LARGEST_PAYLOAD, PARAMETER_BYTES)

    def test_the_hungriest_command_still_fits(self):
        machine = clean_chip()

        feed(machine, [unit.COMMAND_MERGE, 0xFF, *([0x11] * 510)])

        self.assertEqual(machine.in_index, unit.LARGEST_PAYLOAD)

    def test_a_rescale_of_no_input_leaves_the_chip_taking_bytes_forever(self):
        machine = feed(clean_chip(), [unit.COMMAND_SCALE, 0x00, 0x04])

        feed(machine, [0x11] * (PARAMETER_BYTES + 8))

        self.assertGreater(machine.in_index, PARAMETER_BYTES)

    def test_that_stuck_state_never_writes_past_the_parameter_ram(self):
        machine = feed(clean_chip(), [unit.COMMAND_SCALE, 0x00, 0x04])

        feed(machine, [0x11] * (PARAMETER_BYTES + 8))

        self.assertEqual(len(machine.parameter_ram), PARAMETER_BYTES)

    def test_a_length_of_zero_produces_nothing(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x00])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)

    def test_a_length_of_zero_leaves_the_chip_waiting_for_a_command(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x00])

        self.assertTrue(machine.waiting_for_command)

    def test_a_length_of_zero_arms_the_command_rather_than_cancelling_it(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x00])

        self.assertTrue(machine.mirror_armed)

    def test_an_armed_command_runs_at_once_with_the_length_it_was_given(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x00])

        feed(machine, [unit.COMMAND_MIRROR, 0x02, 0xAB, 0xCD])

        self.assertEqual(machine.read(), unit.IDLE_BYTE)

    def test_a_length_of_zero_still_leaves_the_chip_ready_for_other_commands(self):
        machine = feed(clean_chip(), [unit.COMMAND_MIRROR, 0x00])

        feed(machine, [unit.COMMAND_MULTIPLY, 0x03, 0x00, 0x03, 0x00])

        self.assertEqual(drain(machine, 4), (9).to_bytes(4, "little"))

    def test_one_command_leaves_its_data_behind_for_the_next(self):
        machine = clean_chip()

        feed(machine, [unit.COMMAND_MIRROR, 0x02, 0xAB, 0xCD])

        self.assertEqual(machine.parameter_ram[0], 0xAB)

    def test_a_result_can_be_read_back_a_byte_at_a_time(self):
        machine = feed(clean_chip(), [unit.COMMAND_MULTIPLY, 0x04, 0x00, 0x02, 0x00])

        self.assertEqual([machine.read(), machine.read()], [0x08, 0x00])

    def test_nothing_pending_reports_none(self):
        self.assertEqual(clean_chip().pending_output, 0)


if __name__ == "__main__":
    unittest.main()
