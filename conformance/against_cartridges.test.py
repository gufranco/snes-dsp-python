import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import against_cartridges
import shapes


class Talkative:
    """A stand-in part that always has something to say."""

    def __init__(self, part="dsp3"):
        self.part = part
        self.given = []

    def write(self, byte):
        self.given.append(byte)

    def read(self):
        return 0x5A

    def read_status(self):
        return 0x80


class Mute:
    """A stand-in part that answers every read with a zero."""

    def __init__(self, part="dsp3"):
        self.part = part

    def write(self, byte):
        return None

    def read(self):
        return 0

    def read_status(self):
        return 0x80


def build(part):
    return Talkative(part)


class DrivenTest(unittest.TestCase):
    def test_a_part_is_driven_through_every_shape_its_cartridge_uses(self):
        found = against_cartridges.driven("dsp3", build=build)

        self.assertEqual(len(found), len(shapes.interesting(shapes.recorded("dsp3"))))

    def test_each_one_reports_the_shape_and_what_came_back(self):
        first = against_cartridges.driven("dsp3", build=build)[0]

        self.assertTrue(first.shape)
        self.assertTrue(first.said)

    def test_a_run_prints_as_the_shape_it_drove(self):
        first = against_cartridges.driven("dsp3", build=build)[0]

        self.assertIn("write", repr(first))

    def test_a_part_that_answered_something_is_not_silent(self):
        first = against_cartridges.driven("dsp3", build=build)[0]

        self.assertTrue(first.answered)

    def test_a_part_that_answered_nothing_but_zeroes_is_silent(self):
        found = against_cartridges.Driven("write1 read1", [[0]], [shapes.READ])

        self.assertFalse(found.answered)

    def test_a_status_register_that_reads_as_ready_is_not_an_answer(self):
        found = against_cartridges.Driven("write1 poll1", [[0x80]], [shapes.POLL])

        self.assertFalse(found.answered)


class ReportTest(unittest.TestCase):
    def test_every_shape_makes_a_line(self):
        lines = against_cartridges.report(against_cartridges.driven("dsp3", build=build))

        self.assertTrue(lines)

    def test_a_line_names_the_shape(self):
        lines = against_cartridges.report(against_cartridges.driven("dsp3", build=build))

        self.assertIn("write", lines[0])

    def test_the_report_counts_what_it_drove(self):
        found = against_cartridges.driven("dsp3", build=build)

        self.assertIn(str(len(found)), " ".join(against_cartridges.lines_for(found, "dsp3")))


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_microcode_says_so(self):
        found = against_cartridges.main([], why_not=lambda: "no image here", say=lambda _: None)

        self.assertEqual(found, 2)

    def test_a_run_with_microcode_drives_the_part(self):
        said = []

        found = against_cartridges.main(
            ["dsp3"], why_not=lambda: None, build=build, say=said.append
        )

        self.assertEqual(found, 0)
        self.assertTrue(said)

    def test_a_part_with_no_recorded_shapes_is_refused(self):
        with self.assertRaises(against_cartridges.Usage):
            against_cartridges.main(["dsp2"], why_not=lambda: None, build=build, say=lambda _: None)

    def test_a_part_that_says_nothing_at_all_is_a_failure(self):
        found = against_cartridges.main(
            ["dsp3"], why_not=lambda: None, build=Mute, say=lambda _: None
        )

        self.assertEqual(found, 1)


if __name__ == "__main__":
    unittest.main()
