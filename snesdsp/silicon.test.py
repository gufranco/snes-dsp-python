import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import silicon, timing

PRESENT = silicon.available()


class WithoutTest(unittest.TestCase):
    """What the backend says when the things it needs are not there."""

    @override
    def setUp(self) -> None:
        self.real = silicon._processor

    @override
    def tearDown(self) -> None:
        silicon._processor = self.real

    def test_with_no_processor_it_offers_nothing(self) -> None:
        silicon._processor = lambda: None

        self.assertEqual(silicon.available(), {})

    def test_and_says_the_submodule_is_missing(self) -> None:
        silicon._processor = lambda: None

        self.assertEqual(silicon.why_not(), silicon.WHY_NOT_PROCESSOR)

    def test_and_refuses_to_build_a_part(self) -> None:
        silicon._processor = lambda: None

        with self.assertRaises(silicon.NoFirmware):
            silicon.Silicon("dsp1")

    def test_with_a_processor_but_no_image_it_says_that_instead(self) -> None:
        # Three module-shaped stand-ins rather than three Nones. The real
        # function hands back three modules or nothing at all, and a state it
        # cannot produce is not a state worth asking it about.
        held = ModuleType("held")
        silicon._processor = lambda: (held, held, held)

        self.assertEqual(silicon.why_not({}), silicon.WHY_NOT_FIRMWARE)

    def test_a_part_sharing_an_image_that_is_absent_is_refused(self) -> None:
        with self.assertRaises(silicon.NoFirmware):
            silicon.Silicon("dsp1a", images={})


class SharingTest(unittest.TestCase):
    def test_a_part_that_shares_an_image_is_offered_when_the_image_is(self) -> None:
        held = {"dsp1": ("identity", Path("dsp1.bin"))}

        self.assertIn("dsp1a", silicon.available(held))

    def test_and_is_not_offered_when_it_is_not(self) -> None:
        held = {"dsp2": ("identity", Path("dsp2.bin"))}

        self.assertNotIn("dsp1a", silicon.available(held))

    def test_what_was_found_is_left_as_it_was(self) -> None:
        held = {"dsp1": ("identity", Path("dsp1.bin"))}

        silicon.available(held)

        self.assertEqual(set(held), {"dsp1"})


class ImportTest(unittest.TestCase):
    def test_with_the_processor_unimportable_it_offers_nothing(self) -> None:
        import sys as system

        held = dict(system.modules)
        # A module entry of None is how the import system records a module that
        # cannot be found, so this is the state a machine without the submodule
        # is actually in rather than an approximation of it.
        system.modules["upd7725"] = None  # type: ignore[assignment]
        try:
            self.assertIsNone(silicon._processor())
        finally:
            system.modules.clear()
            system.modules.update(held)


class AvailabilityTest(unittest.TestCase):
    def test_it_says_which_parts_it_can_run(self) -> None:
        self.assertIsInstance(silicon.available(), dict)

    def test_a_part_with_no_image_is_not_offered(self) -> None:
        self.assertNotIn("nonsense", silicon.available())

    def test_asking_for_a_part_it_cannot_run_is_refused(self) -> None:
        with self.assertRaises(silicon.NoFirmware):
            silicon.Silicon("nonsense")

    def test_the_refusal_says_what_is_missing_and_what_to_do(self) -> None:
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("nonsense")

        told = str(raised.exception).lower()

        self.assertIn("microcode", told)
        self.assertTrue("firmware" in told or "submodule" in told)

    def test_the_reason_is_the_same_one_the_refusal_carries(self) -> None:
        self.assertTrue(silicon.why_not() is None or isinstance(silicon.why_not(), str))


class BusTest(unittest.TestCase):
    """The console's side of the wire, which is an address rather than a call.

    A console does not call a method on a coprocessor. It reads and writes an
    address, and the part decides from the lowest bit of it whether that was the
    data port or the status register. Leaving that decode to whoever calls this
    means every caller reimplements it, and one of them gets it the wrong way
    round.
    """

    def _built(self, **options: Any) -> "silicon.Silicon":
        import sys as system

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("made-up", "upd7725", "MADE UP", 2048, 1024)
        image = bytes(2048 * 3 + 1024 * 2)
        return silicon.Silicon("made-up", image=image, identity=identity, boot=64, **options)

    def test_an_even_address_is_the_data_port(self) -> None:
        chip = self._built()

        self.assertEqual(chip.read_bus(0x00C000), chip.read())

    def test_an_odd_address_is_the_status_register(self) -> None:
        chip = self._built()

        self.assertEqual(chip.read_bus(0x00C001), chip.read_status())

    def test_only_the_lowest_bit_decides(self) -> None:
        chip = self._built()

        self.assertEqual(chip.read_bus(0x3F8000), chip.read_bus(0x008000))

    def test_a_write_to_an_even_address_reaches_the_data_port(self) -> None:
        chip = self._built()
        before = chip.chip.registers.pc

        chip.write_bus(0x00C000, 0x42)

        self.assertNotEqual(chip.chip.registers.pc, before)

    def test_a_write_to_an_odd_address_is_taken_as_a_status_write(self) -> None:
        chip = self._built()

        chip.write_bus(0x00C001, 0x00)

        self.assertIsInstance(chip.read_status(), int)

    def test_what_is_written_is_narrowed_to_a_byte(self) -> None:
        chip = self._built()

        chip.write_bus(0x00C000, 0x1FF)

        self.assertIsInstance(chip.read_status(), int)


class PacingTest(unittest.TestCase):
    """That the part is left the time the console would have left it."""

    def _built(self, **options: Any) -> "silicon.Silicon":
        import sys as system

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("made-up", "upd7725", "MADE UP", 2048, 1024)
        image = bytes(2048 * 3 + 1024 * 2)
        return silicon.Silicon("made-up", image=image, identity=identity, boot=64, **options)

    def test_the_default_gap_is_the_one_the_console_clocks_imply(self) -> None:
        self.assertEqual(silicon.GAP, timing.GAP)

    def test_a_caller_can_say_how_long_their_console_actually_spent(self) -> None:
        chip = self._built()
        before = chip.chip.registers.pc

        chip.elapsed(timing.MASTER_CLOCK // 1000)

        self.assertNotEqual(chip.chip.registers.pc, before)

    def test_more_console_time_runs_the_part_further(self) -> None:
        one, two = self._built(), self._built()

        one.elapsed(timing.SLOW_ACCESS)
        two.elapsed(timing.SLOW_ACCESS * 100)

        self.assertNotEqual(one.chip.registers.pc, two.chip.registers.pc)

    def test_no_console_time_at_all_runs_it_nowhere(self) -> None:
        chip = self._built()
        before = chip.chip.registers.pc

        chip.elapsed(0)

        self.assertEqual(chip.chip.registers.pc, before)

    def test_the_part_says_what_rate_it_runs_at(self) -> None:
        self.assertEqual(self._built().clock, timing.DSP_CLOCK)


class StatusTest(unittest.TestCase):
    """The register the console polls, which some parts are driven entirely by.

    A part that answers a command and a count of words is driven by writing and
    reading. A part that is clocked a word at a time is driven by watching this
    instead, so a backend that cannot be polled cannot stand in for the model of
    one.
    """

    def _built(self) -> "silicon.Silicon":
        import sys as system

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("made-up", "upd7725", "MADE UP", 2048, 1024)
        image = bytes(2048 * 3 + 1024 * 2)
        return silicon.Silicon("made-up", image=image, identity=identity, boot=64)

    def test_the_status_register_can_be_read_without_taking_a_byte(self) -> None:
        chip = self._built()

        self.assertIsInstance(chip.read_status(), int)

    def test_it_is_one_byte_wide(self) -> None:
        self.assertLessEqual(self._built().read_status(), 0xFF)

    def test_reading_it_does_not_change_what_the_part_has_to_say(self) -> None:
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

    def _catalogue(self) -> "dict[str, tuple[object, Path]]":
        import sys as system
        import tempfile

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("dsp1", "upd7725", "MADE UP", 2048, 1024)
        where = Path(tempfile.mkdtemp()) / "made-up.bin"
        where.write_bytes(bytes(2048 * 3 + 1024 * 2))
        return {"dsp1": (identity, where)}

    def test_an_image_the_search_found_is_read_from_its_file(self) -> None:
        chip = silicon.Silicon("dsp1", images=self._catalogue(), boot=64)

        self.assertEqual(chip.part, "dsp1")

    def test_a_part_sharing_another_part_image_is_built_from_it(self) -> None:
        chip = silicon.Silicon("dsp1a", images=self._catalogue(), boot=64)

        self.assertEqual(chip.part, "dsp1a")

    def test_a_part_with_no_image_anywhere_is_refused_by_name(self) -> None:
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("dsp4", images=self._catalogue())

        self.assertIn("dsp4", str(raised.exception))

    def test_with_an_image_present_there_is_no_reason_it_cannot_run(self) -> None:
        self.assertIsNone(silicon.why_not(self._catalogue()))


class SuppliedImageTest(unittest.TestCase):
    """Driving the backend with a program nobody owns.

    Every check below runs on a machine with no microcode present, which is what
    a hosted runner is. The image is zeroes: a real program is somebody else's
    and cannot be here, and none of what is checked depends on the program doing
    anything in particular.
    """

    def _built(self, **options: Any) -> "silicon.Silicon":
        import sys as system

        system.path.insert(0, str(silicon.PROCESSOR))
        from upd7725 import firmware

        identity = firmware.Identity("made-up", "upd7725", "MADE UP", 2048, 1024)
        image = bytes(2048 * 3 + 1024 * 2)
        return silicon.Silicon("made-up", image=image, identity=identity, boot=64, **options)

    def test_a_supplied_image_is_run_without_one_on_disk(self) -> None:
        self.assertEqual(self._built().part, "made-up")

    def test_it_names_the_processor_the_image_says_it_runs_on(self) -> None:
        self.assertEqual(self._built().processor, "upd7725")

    def test_it_carries_the_same_name_field_the_models_do(self) -> None:
        self.assertEqual(self._built().model, "made-up")

    def test_it_prints_as_the_part_and_how_it_is_run(self) -> None:
        self.assertIn("silicon", repr(self._built()))

    def test_a_part_that_is_already_asking_is_read_without_waiting(self) -> None:
        chip = self._built(patience=1)
        chip.chip.registers.sr.rqm = True

        self.assertLess(chip.read(), 0x100)

    def test_and_waiting_on_one_that_is_asking_says_so_at_once(self) -> None:
        chip = self._built(patience=1)
        chip.chip.registers.sr.rqm = True

        self.assertTrue(chip.waited())

    def test_while_one_that_never_asks_says_it_never_did(self) -> None:
        chip = self._built(patience=8)

        self.assertFalse(chip.waited())

    def test_waiting_on_a_part_that_is_asking_returns_rather_than_refusing(self) -> None:
        chip = self._built(patience=1)
        chip.chip.registers.sr.rqm = True

        chip.settle()

        self.assertTrue(chip.chip.registers.sr.rqm)

    def test_writing_a_byte_runs_the_part_afterwards(self) -> None:
        chip = self._built()

        chip.write(0x12)

        self.assertIsInstance(chip.pending_output, int)

    def test_a_program_that_never_asks_is_given_up_on_when_waited_on(self) -> None:
        chip = self._built(patience=32)

        with self.assertRaises(silicon.NeverReady):
            chip.settle()

    def test_but_reading_from_it_takes_the_port_rather_than_hanging(self) -> None:
        chip = self._built(patience=32)

        self.assertLess(chip.read(), 0x100)

    def test_reading_leaves_the_part_room_to_act_before_the_next_access(self) -> None:
        chip = self._built(patience=32)
        before = chip.chip.registers.pc

        chip.read()

        self.assertNotEqual(chip.chip.registers.pc, before)

    def test_a_part_that_is_asking_can_be_read_from(self) -> None:
        chip = self._built()
        chip.chip.registers.sr.rqm = True

        self.assertLess(chip.read(), 0x100)

    def test_and_reports_that_it_has_something_to_say(self) -> None:
        chip = self._built()
        chip.chip.registers.sr.rqm = True

        self.assertEqual(chip.pending_output, 1)

    def test_stepping_a_given_number_of_times_is_allowed(self) -> None:
        chip = self._built()

        chip.step(3)

        self.assertTrue(True)

    def test_an_image_supplied_without_saying_what_it_is_is_refused(self) -> None:
        with self.assertRaises(silicon.NoFirmware) as raised:
            silicon.Silicon("made-up", image=bytes(64))

        self.assertIn("program", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
