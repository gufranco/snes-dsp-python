import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from conformance import driven

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024


def the_real_part() -> type:
    identity = SimpleNamespace(
        part="dsp1",
        processor="upd7725",
        revision="MADE UP",
        program_words=PROGRAM_WORDS,
        data_words=TABLE_WORDS,
    )
    image = bytes(PROGRAM_WORDS * 3 + TABLE_WORDS * 2)
    return type(snesdsp.Chip("dsp1", image=image, identity=identity, boot=0))


class ContractTest(unittest.TestCase):
    def test_the_real_part_is_something_a_console_could_drive(self) -> None:
        # Arrange
        real = the_real_part()

        # Act
        drivable = issubclass(real, driven.Driven)

        # Assert
        self.assertTrue(drivable)

    def test_a_stand_in_that_takes_a_byte_and_gives_one_back_is_too(self) -> None:
        self.assertIsInstance(_Byte(), driven.Driven)

    def test_one_that_can_only_be_written_to_is_not(self) -> None:
        self.assertNotIsInstance(_WriteOnly(), driven.Driven)

    def test_and_one_that_can_only_be_read_from_is_not_either(self) -> None:
        self.assertNotIsInstance(_ReadOnly(), driven.Driven)

    def test_the_contract_is_the_two_ports_and_nothing_else(self) -> None:
        named = {one for one in dir(driven.Driven) if not one.startswith("_")}

        self.assertEqual(named, {"read", "write"})


class PolledTest(unittest.TestCase):
    def test_the_real_part_can_be_polled(self) -> None:
        # Arrange
        real = the_real_part()

        # Act
        polled = issubclass(real, driven.Watched)

        # Assert
        self.assertTrue(polled)

    def test_something_with_two_ports_and_no_register_cannot(self) -> None:
        self.assertNotIsInstance(_Byte(), driven.Watched)

    def test_one_that_carries_the_register_can(self) -> None:
        self.assertIsInstance(_Polled(), driven.Watched)

    def test_being_polled_still_means_being_driven(self) -> None:
        self.assertIsInstance(_Polled(), driven.Driven)


class IdentifiedTest(unittest.TestCase):
    def test_something_with_only_the_two_ports_does_not(self) -> None:
        self.assertNotIsInstance(_Byte(), driven.Identified)

    def test_one_carrying_an_identity_does(self) -> None:
        self.assertIsInstance(_Identified(), driven.Identified)

    def test_the_real_part_is_checked_by_the_type_checker_rather_than_here(self) -> None:
        # Arrange
        real = the_real_part()

        # Act
        with self.assertRaises(TypeError) as refused:
            issubclass(real, driven.Identified)  # type: ignore[misc]

        # Assert
        self.assertIn("non-method members", str(refused.exception))


class StandInTest(unittest.TestCase):
    def test_one_that_is_written_to_holds_what_it_was_given(self) -> None:
        held = _Byte()

        held.write(0x2A)

        self.assertEqual(held.held, 0x2A)

    def test_and_reading_from_it_gives_a_byte(self) -> None:
        self.assertEqual(_Byte().read(), 0)

    def test_a_polled_one_answers_its_register(self) -> None:
        self.assertEqual(_Polled().read_status(), 0)

    def test_a_write_only_one_still_takes_a_byte(self) -> None:
        held = _WriteOnly()

        held.write(0x2A)

        self.assertEqual(held.held, 0x2A)

    def test_a_read_only_one_still_gives_one(self) -> None:
        self.assertEqual(_ReadOnly().read(), 0)

    def test_an_identified_one_names_what_it_runs(self) -> None:
        self.assertEqual(_Identified().identity, "dsp1")


class _Byte:
    def write(self, value: int) -> None:
        self.held = value

    def read(self) -> int:
        return 0


class _Polled(_Byte):
    def read_status(self) -> int:
        return 0


class _Identified(_Byte):
    def __init__(self) -> None:
        self.identity = "dsp1"


class _WriteOnly:
    def write(self, value: int) -> None:
        self.held = value


class _ReadOnly:
    def read(self) -> int:
        return 0


if __name__ == "__main__":
    unittest.main()
