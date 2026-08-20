import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dsp3record


class Echo:
    """A stand-in part that hands back whatever it was last written."""

    def __init__(self):
        self.held = 0
        self.given = []

    def write(self, byte):
        self.held = byte
        self.given.append(byte)

    def read(self):
        return self.held


class ScriptTest(unittest.TestCase):
    def test_a_script_is_a_run_of_steps(self):
        self.assertTrue(dsp3record.script_for(0, 0x02))

    def test_every_step_says_whether_it_gives_or_takes(self):
        for kind, _ in dsp3record.script_for(0, 0x02):
            self.assertIn(kind, (dsp3record.WRITE, dsp3record.READ))

    def test_every_byte_written_is_a_byte(self):
        for kind, value in dsp3record.script_for(0, 0x02):
            if kind == dsp3record.WRITE:
                self.assertTrue(0 <= value <= 0xFF)

    def test_the_command_asked_for_is_the_one_written_first(self):
        first = dsp3record.script_for(0, 0x1C)[0]

        self.assertEqual(first, [dsp3record.WRITE, 0x1C])

    def test_every_command_the_part_has_is_recorded(self):
        found = dsp3record.record([0], build=Echo)

        self.assertEqual(sorted({one["command"] for one in found}), sorted(dsp3record.COMMANDS))

    def test_the_same_seed_gives_the_same_script(self):
        self.assertEqual(dsp3record.script_for(7, 0x02), dsp3record.script_for(7, 0x02))

    def test_and_a_different_seed_does_not(self):
        self.assertNotEqual(dsp3record.script_for(7, 0x02), dsp3record.script_for(8, 0x02))

    def test_a_script_asks_for_as_many_answers_as_it_says(self):
        reads = [one for one in dsp3record.script_for(0, 0x02) if one[0] == dsp3record.READ]

        self.assertEqual(len(reads), dsp3record.READS_PER_COMMAND)

    def test_two_commands_with_the_same_seed_carry_the_same_words(self):
        one = dsp3record.script_for(0, 0x02)[1:]
        two = dsp3record.script_for(0, 0x1C)[1:]

        self.assertEqual(one, two)


class AnswersTest(unittest.TestCase):
    def test_one_answer_comes_back_per_read(self):
        steps = dsp3record.script_for(0, 0x02)
        reads = sum(1 for kind, _ in steps if kind == dsp3record.READ)

        self.assertEqual(len(dsp3record.answers_of(steps, Echo())), reads)

    def test_every_written_byte_reaches_the_part(self):
        steps = dsp3record.script_for(0, 0x02)
        chip = Echo()

        dsp3record.answers_of(steps, chip)

        self.assertEqual(len(chip.given), sum(1 for kind, _ in steps if kind == dsp3record.WRITE))

    def test_what_the_part_says_is_what_is_written_down(self):
        steps = [[dsp3record.WRITE, 0x42], [dsp3record.READ, 0]]

        self.assertEqual(dsp3record.answers_of(steps, Echo()), [0x42])


class RecordTest(unittest.TestCase):
    def test_one_case_is_recorded_per_seed_and_command(self):
        found = dsp3record.record([0, 1], commands=(0x02, 0x1C), build=Echo)

        self.assertEqual(len(found), 4)

    def test_each_case_carries_the_script_it_was_asked(self):
        found = dsp3record.record([0], commands=(0x02,), build=Echo)

        self.assertEqual(found[0]["script"], dsp3record.script_for(0, 0x02))

    def test_and_the_answers_as_something_a_file_can_hold(self):
        found = dsp3record.record([0], commands=(0x02,), build=Echo)

        self.assertTrue(base64.b64decode(found[0]["expected"]))

    def test_a_fresh_part_is_used_for_every_case(self):
        seen = []

        def build(_part=None):
            chip = Echo()
            seen.append(chip)
            return chip

        dsp3record.record([0, 1, 2], commands=(0x02,), build=build)

        self.assertEqual(len(seen), 3)


class WriteOutTest(unittest.TestCase):
    def test_a_corpus_is_written_where_it_was_asked_for(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        dsp3record.write_out(where, [0, 1], build=Echo)

        self.assertTrue(where.exists())

    def test_it_names_the_part_it_describes(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        dsp3record.write_out(where, [0], build=Echo)

        self.assertEqual(json.loads(where.read_text())["part"], "dsp3")

    def test_and_says_where_the_answers_came_from(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        dsp3record.write_out(where, [0], build=Echo)

        self.assertIn("microcode", json.loads(where.read_text())["recordedFrom"])

    def test_every_case_asked_for_is_in_it(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        dsp3record.write_out(where, [0, 1, 2], build=Echo)

        self.assertEqual(len(json.loads(where.read_text())["cases"]), 3 * len(dsp3record.COMMANDS))


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_microcode_says_so_and_records_nothing(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        found = dsp3record.main([str(where), "2"], why_not=lambda: "no image here")

        self.assertEqual(found, 2)
        self.assertFalse(where.exists())

    def test_a_run_with_one_records_what_it_was_asked_for(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        found = dsp3record.main([str(where), "2"], why_not=lambda: None, build=Echo)

        self.assertEqual(found, 0)
        self.assertEqual(len(json.loads(where.read_text())["cases"]), 2 * len(dsp3record.COMMANDS))

    def test_a_count_that_is_not_a_number_is_refused(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        with self.assertRaises(dsp3record.Usage):
            dsp3record.main([str(where), "many"], why_not=lambda: None, build=Echo)

    def test_a_run_with_no_arguments_at_all_is_refused(self):
        with self.assertRaises(dsp3record.Usage):
            dsp3record.main([], why_not=lambda: None, build=Echo)


if __name__ == "__main__":
    unittest.main()
