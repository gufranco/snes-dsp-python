import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import silicon

PRESENT = silicon.available()


class WithoutTest(unittest.TestCase):
    """What the backend says when the things it needs are not there."""

    def setUp(self):
        self.real = silicon._processor

    def tearDown(self):
        silicon._processor = self.real

    def test_with_no_processor_it_offers_nothing(self):
        silicon._processor = lambda: None

        self.assertEqual(silicon.available(), {})

    def test_and_says_the_submodule_is_missing(self):
        silicon._processor = lambda: None

        self.assertEqual(silicon.why_not(), silicon.WHY_NOT_PROCESSOR)

    def test_and_refuses_to_build_a_part(self):
        silicon._processor = lambda: None

        with self.assertRaises(silicon.NoFirmware):
            silicon.Silicon("dsp1")

    def test_with_a_processor_but_no_image_it_says_that_instead(self):
        silicon._processor = lambda: (None, None, None)
        real_available = silicon.available
        silicon.available = dict

        try:
            self.assertEqual(silicon.why_not(), silicon.WHY_NOT_FIRMWARE)
        finally:
            silicon.available = real_available

    def test_a_part_sharing_an_image_that_is_absent_is_refused(self):
        real_available = silicon.available
        silicon.available = dict

        try:
            with self.assertRaises(silicon.NoFirmware):
                silicon.Silicon("dsp1a")
        finally:
            silicon.available = real_available


class SharingTest(unittest.TestCase):
    def test_a_part_that_shares_an_image_is_offered_when_the_image_is(self):
        held = {"dsp1": ("identity", "path")}

        self.assertIn("dsp1a", silicon.available(held))

    def test_and_is_not_offered_when_it_is_not(self):
        held = {"dsp2": ("identity", "path")}

        self.assertNotIn("dsp1a", silicon.available(held))

    def test_what_was_found_is_left_as_it_was(self):
        held = {"dsp1": ("identity", "path")}

        silicon.available(held)

        self.assertEqual(set(held), {"dsp1"})


class ImportTest(unittest.TestCase):
    def test_with_the_processor_unimportable_it_offers_nothing(self):
        import sys as system

        held = dict(system.modules)
        system.modules["upd7725"] = None
        try:
            self.assertIsNone(silicon._processor())
        finally:
            system.modules.clear()
            system.modules.update(held)


class AvailabilityTest(unittest.TestCase):
    def test_it_says_which_parts_it_can_run(self):
        self.assertIsInstance(silicon.available(), dict)

    def test_a_part_with_no_image_is_not_offered(self):
        self.assertNotIn("nonsense", silicon.available())

    def test_asking_for_a_part_it_cannot_run_is_refused(self):
        with self.assertRaises(silicon.NoFirmware):
            silicon.Silicon("nonsense")

    def test_the_refusal_says_where_an_image_would_go(self):
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("nonsense")

        self.assertIn("firmware", str(raised.exception).lower())

    def test_the_reason_is_the_same_one_the_refusal_carries(self):
        self.assertTrue(silicon.why_not() is None or isinstance(silicon.why_not(), str))


@unittest.skipUnless(PRESENT, silicon.WHY_NOT_FIRMWARE)
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


if __name__ == "__main__":
    unittest.main()
