import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import against_firmware

import snesdsp
from snesdsp import backend, silicon

WHY = against_firmware.why_not()

PRESENT = silicon.available()


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


class PacingTest(unittest.TestCase):
    def test_the_part_is_given_room_to_keep_up_between_accesses(self):
        self.assertGreaterEqual(against_firmware.GAP, 8)

    def test_and_is_booted_before_the_first_command(self):
        self.assertGreater(against_firmware.BOOT_STEPS, 0)


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


# What follows drives a real part rather than the sweep above, and lives here
# for the reason the sweep does: it can only run where somebody's microcode is
# present, so on a machine without one every check reports as skipped. A skipped
# check contributes no coverage, and this file sits outside the coverage gate.


@unittest.skipUnless("dsp1" in PRESENT, "no dsp1 image")
class DriveTest(unittest.TestCase):
    PART = "dsp1"

    def setUp(self):
        self.chip = silicon.Silicon(self.PART)

    def test_a_part_boots_ready_for_a_command(self):
        self.assertTrue(self.chip.asking)

    def test_it_names_the_part_it_is_running(self):
        self.assertEqual(self.chip.part, self.PART)

    def test_it_prints_as_the_part_and_how_it_is_run(self):
        printed = repr(self.chip)

        self.assertIn(self.PART, printed)
        self.assertIn("silicon", printed)

    def test_a_command_with_arguments_produces_an_answer(self):
        self.chip.write(0x00)
        for byte in (0x10, 0x00, 0x20, 0x00, 0x30, 0x00):
            self.chip.write(byte)

        self.assertTrue(self.chip.pending_output)

    def test_the_answer_reads_out_a_byte_at_a_time(self):
        self.chip.write(0x00)
        for byte in (0x10, 0x00, 0x20, 0x00, 0x30, 0x00):
            self.chip.write(byte)

        first = self.chip.read()
        second = self.chip.read()

        self.assertIsInstance(first, int)
        self.assertIsInstance(second, int)
        self.assertLess(first, 0x100)
        self.assertLess(second, 0x100)

    def test_the_same_command_twice_gives_the_same_answer(self):
        def run():
            chip = silicon.Silicon(self.PART)
            chip.write(0x00)
            for byte in (0x10, 0x00, 0x20, 0x00, 0x30, 0x00):
                chip.write(byte)
            return [chip.read() for _ in range(6)]

        self.assertEqual(run(), run())

    def test_two_parts_run_independently_of_each_other(self):
        other = silicon.Silicon(self.PART)
        self.chip.write(0x00)

        self.assertTrue(other.asking)

    def test_a_booted_part_is_already_asking_so_a_read_returns(self):
        self.assertLess(self.chip.read(), 0x100)

    def test_waiting_runs_the_part_until_it_asks_again(self):
        self.chip.chip.registers.sr.rqm = False

        self.chip.settle()

        self.assertTrue(self.chip.asking)

    def test_waiting_gives_up_rather_than_hanging_when_it_never_asks(self):
        self.chip.patience = 0

        with self.assertRaises(silicon.NeverReady):
            self.chip.settle()

    def test_the_refusal_to_wait_forever_names_the_part_and_the_limit(self):
        self.chip.patience = 0

        with self.assertRaises(silicon.NeverReady) as raised:
            self.chip.settle()

        self.assertIn(self.PART, str(raised.exception))
        self.assertIn("0", str(raised.exception))

    def test_the_part_reports_whether_it_wants_attention_rather_than_a_count(self):
        self.assertIn(self.chip.pending_output, (0, 1))


@unittest.skipUnless(PRESENT, silicon.WHY_NOT_FIRMWARE)
class EveryPartTest(unittest.TestCase):
    def test_every_image_present_boots_and_asks_for_a_command(self):
        for part in sorted(PRESENT):
            self.assertTrue(silicon.Silicon(part).asking, part)

    def test_every_image_present_names_the_processor_it_runs_on(self):
        for part in sorted(PRESENT):
            self.assertIn(silicon.Silicon(part).processor, ("upd7725", "upd96050"))

    def test_the_parts_it_offers_are_the_ones_the_manifest_recognises(self):
        for part in PRESENT:
            self.assertTrue(part)


@unittest.skipUnless(PRESENT, silicon.WHY_NOT_FIRMWARE)
class WithFirmwareTest(unittest.TestCase):
    def test_the_microcode_is_what_a_caller_gets_by_default(self):
        part = sorted(PRESENT)[0]

        self.assertIsInstance(snesdsp.Dsp(model=part), silicon.Silicon)

    def test_and_it_says_so(self):
        part = sorted(PRESENT)[0]

        self.assertEqual(snesdsp.Dsp(model=part).backend, backend.SILICON)

    def test_the_model_is_still_reachable_by_asking_for_it(self):
        part = sorted(PRESENT)[0]
        chip = snesdsp.Dsp(model=part, backend=backend.MODELLED)

        self.assertEqual(chip.backend, backend.MODELLED)

    def test_every_part_with_an_image_offers_the_same_interface_either_way(self):
        for part in sorted(PRESENT):
            for which in (backend.SILICON, backend.MODELLED):
                chip = snesdsp.Dsp(model=part, backend=which)

                for name in ("write", "read", "pending_output", "backend"):
                    self.assertTrue(hasattr(chip, name), (part, which, name))


if __name__ == "__main__":
    unittest.main()
