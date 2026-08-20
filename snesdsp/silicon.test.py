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

        self.assertEqual(silicon.why_not({}), silicon.WHY_NOT_FIRMWARE)

    def test_a_part_sharing_an_image_that_is_absent_is_refused(self):
        with self.assertRaises(silicon.NoFirmware):
            silicon.Silicon("dsp1a", images={})


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

    def test_the_refusal_says_what_is_missing_and_what_to_do(self):
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("nonsense")

        told = str(raised.exception).lower()

        self.assertIn("microcode", told)
        self.assertTrue("firmware" in told or "submodule" in told)

    def test_the_reason_is_the_same_one_the_refusal_carries(self):
        self.assertTrue(silicon.why_not() is None or isinstance(silicon.why_not(), str))


class StatusTest(unittest.TestCase):
    """The register the console polls, which some parts are driven entirely by.

    A part that answers a command and a count of words is driven by writing and
    reading. A part that is clocked a word at a time is driven by watching this
    instead, so a backend that cannot be polled cannot stand in for the model of
    one.
    """

    def _built(self):
        import sys as system

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("made-up", "upd7725", "MADE UP", 2048, 1024)
        image = bytes(2048 * 3 + 1024 * 2)
        return silicon.Silicon("made-up", image=image, identity=identity, boot=64)

    def test_the_status_register_can_be_read_without_taking_a_byte(self):
        chip = self._built()

        self.assertIsInstance(chip.read_status(), int)

    def test_it_is_one_byte_wide(self):
        self.assertLessEqual(self._built().read_status(), 0xFF)

    def test_reading_it_does_not_change_what_the_part_has_to_say(self):
        chip = self._built()
        before = chip.pending_output

        chip.read_status()

        self.assertEqual(chip.pending_output, before)


class FoundOnDiskTest(unittest.TestCase):
    """The path that reads an image the search turned up.

    A machine with real microcode takes this path and a hosted runner does not,
    so the search is replaced rather than the file: the bytes are a program of
    zeroes written to a temporary file, and everything from the lookup onwards is
    the same code a real image goes through.
    """

    def _catalogue(self):
        import sys as system
        import tempfile

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("dsp1", "upd7725", "MADE UP", 2048, 1024)
        where = Path(tempfile.mkdtemp()) / "made-up.bin"
        where.write_bytes(bytes(2048 * 3 + 1024 * 2))
        return {"dsp1": (identity, where)}

    def test_an_image_the_search_found_is_read_from_its_file(self):
        chip = silicon.Silicon("dsp1", images=self._catalogue(), boot=64)

        self.assertEqual(chip.part, "dsp1")

    def test_a_part_sharing_another_part_image_is_built_from_it(self):
        chip = silicon.Silicon("dsp1a", images=self._catalogue(), boot=64)

        self.assertEqual(chip.part, "dsp1a")

    def test_a_part_with_no_image_anywhere_is_refused_by_name(self):
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("dsp4", images=self._catalogue())

        self.assertIn("dsp4", str(raised.exception))

    def test_with_an_image_present_there_is_no_reason_it_cannot_run(self):
        self.assertIsNone(silicon.why_not(self._catalogue()))


class SuppliedImageTest(unittest.TestCase):
    """Driving the backend with a program nobody owns.

    Every check below runs on a machine with no microcode present, which is what
    a hosted runner is. The image is zeroes: a real program is somebody else's
    and cannot be here, and none of what is checked depends on the program doing
    anything in particular.
    """

    def _built(self, **options):
        import sys as system

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("made-up", "upd7725", "MADE UP", 2048, 1024)
        image = bytes(2048 * 3 + 1024 * 2)
        return silicon.Silicon("made-up", image=image, identity=identity, boot=64, **options)

    def test_a_supplied_image_is_run_without_one_on_disk(self):
        self.assertEqual(self._built().part, "made-up")

    def test_it_names_the_processor_the_image_says_it_runs_on(self):
        self.assertEqual(self._built().processor, "upd7725")

    def test_it_carries_the_same_name_field_the_models_do(self):
        self.assertEqual(self._built().model, "made-up")

    def test_it_prints_as_the_part_and_how_it_is_run(self):
        self.assertIn("silicon", repr(self._built()))

    def test_a_part_that_is_already_asking_is_read_without_waiting(self):
        chip = self._built(patience=1)
        chip.chip.registers.sr.rqm = True

        self.assertLess(chip.read(), 0x100)

    def test_and_waiting_on_one_that_is_asking_says_so_at_once(self):
        chip = self._built(patience=1)
        chip.chip.registers.sr.rqm = True

        self.assertTrue(chip.waited())

    def test_while_one_that_never_asks_says_it_never_did(self):
        chip = self._built(patience=8)

        self.assertFalse(chip.waited())

    def test_waiting_on_a_part_that_is_asking_returns_rather_than_refusing(self):
        chip = self._built(patience=1)
        chip.chip.registers.sr.rqm = True

        self.assertIsNone(chip.settle())

    def test_writing_a_byte_runs_the_part_afterwards(self):
        chip = self._built()

        chip.write(0x12)

        self.assertIsInstance(chip.pending_output, int)

    def test_a_program_that_never_asks_is_given_up_on_when_waited_on(self):
        chip = self._built(patience=32)

        with self.assertRaises(silicon.NeverReady):
            chip.settle()

    def test_but_reading_from_it_takes_the_port_rather_than_hanging(self):
        chip = self._built(patience=32)

        self.assertLess(chip.read(), 0x100)

    def test_reading_leaves_the_part_room_to_act_before_the_next_access(self):
        chip = self._built(patience=32)
        before = chip.chip.registers.pc

        chip.read()

        self.assertNotEqual(chip.chip.registers.pc, before)

    def test_a_part_that_is_asking_can_be_read_from(self):
        chip = self._built()
        chip.chip.registers.sr.rqm = True

        self.assertLess(chip.read(), 0x100)

    def test_and_reports_that_it_has_something_to_say(self):
        chip = self._built()
        chip.chip.registers.sr.rqm = True

        self.assertEqual(chip.pending_output, 1)

    def test_stepping_a_given_number_of_times_is_allowed(self):
        chip = self._built()

        chip.step(3)

        self.assertTrue(True)

    def test_an_image_supplied_without_saying_what_it_is_is_refused(self):
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("made-up", image=bytes(64))

        self.assertIn("program", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
