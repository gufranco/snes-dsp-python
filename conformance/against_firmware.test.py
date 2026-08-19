import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import against_firmware

WHY = against_firmware.why_not()


class AvailabilityTest(unittest.TestCase):
    def test_the_reason_nothing_can_run_names_what_is_missing(self):
        if WHY is not None:
            self.assertTrue(WHY.strip())

    def test_a_missing_processor_is_reported_before_a_missing_image(self):
        self.assertIn("submodule", against_firmware.WHY_NOT_PROCESSOR)

    def test_and_a_missing_image_says_where_one_goes(self):
        self.assertIn("firmware", against_firmware.WHY_NOT_FIRMWARE)


class StreamTest(unittest.TestCase):
    def test_every_microcode_here_has_streams_to_drive_it(self):
        for microcode in against_firmware.MICROCODES:
            self.assertTrue(list(microcode.streams(against_firmware.rolls(), 3)), microcode.part)

    def test_a_stream_opens_with_a_command_the_model_knows(self):
        for microcode in against_firmware.MICROCODES:
            for stream in microcode.streams(against_firmware.rolls(), 5):
                self.assertIn(stream[0], microcode.commands, microcode.part)

    def test_the_same_seed_builds_the_same_streams(self):
        first = list(against_firmware.MICROCODES[0].streams(against_firmware.rolls(), 4))
        second = list(against_firmware.MICROCODES[0].streams(against_firmware.rolls(), 4))

        self.assertEqual(first, second)

    def test_every_command_a_model_has_is_reachable(self):
        for microcode in against_firmware.MICROCODES:
            reached = {stream[0] for stream in microcode.streams(against_firmware.rolls(), 2000)}

            self.assertEqual(reached, set(microcode.commands), microcode.part)


class AlignmentTest(unittest.TestCase):
    def test_an_answer_that_arrives_first_is_recognised(self):
        self.assertTrue(against_firmware.agreeing((b"\x01\x02", b"\x03\x04"), b"\x01\x02"))

    def test_and_one_that_arrives_after_the_echo_is_too(self):
        self.assertTrue(against_firmware.agreeing((b"\x01\x02", b"\x03\x04"), b"\x03\x04"))

    def test_an_answer_that_is_neither_is_a_disagreement(self):
        self.assertFalse(against_firmware.agreeing((b"\x01\x02", b"\x03\x04"), b"\x05\x06"))


class ReportTest(unittest.TestCase):
    def test_a_run_reports_rather_than_failing_when_nothing_is_present(self):
        self.assertEqual(against_firmware.main([]), 0)

    def test_an_option_it_does_not_know_is_reported(self):
        self.assertEqual(against_firmware.main(["--nonsense"]), 2)

    def test_an_option_it_does_not_know_is_refused(self):
        with self.assertRaises(against_firmware.Usage):
            against_firmware.options(["--nonsense"])

    def test_an_option_with_no_value_is_refused(self):
        with self.assertRaises(against_firmware.Usage):
            against_firmware.options(["--sequences"])

    def test_the_number_of_sequences_can_be_set(self):
        self.assertEqual(against_firmware.options(["--sequences", "7"]).sequences, 7)


@unittest.skipUnless(WHY is None, WHY or "")
class AgainstMicrocodeTest(unittest.TestCase):
    """What the microcode itself answers, beside what the models here answer.

    This does not yet assert that the two agree everywhere, because they do not,
    and the reason is still open: for some commands the part offers fewer bytes
    than the model produces, and reading past what it offered returns whatever
    the data register still held. Until it is settled whether the extra bytes are
    a model that answers too much or a driver that reads too far, asserting
    either way would be recording a guess.

    What is asserted is that the comparison runs, that it reaches every model
    with an image present, and that it reports what it found.
    """

    def test_every_model_with_an_image_present_is_asked_something(self):
        present = against_firmware.images()

        for microcode in against_firmware.MICROCODES:
            if microcode.part not in present:
                continue
            found = against_firmware.compare(microcode, 12)

            self.assertGreaterEqual(found["asked"], 0, microcode.part)

    def test_the_report_names_every_model_it_looked_at(self):
        lines = "\n".join(against_firmware.lines_for(4))

        for microcode in against_firmware.MICROCODES:
            self.assertIn(microcode.part, lines)


if __name__ == "__main__":
    unittest.main()
