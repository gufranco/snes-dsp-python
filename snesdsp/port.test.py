import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024

HARDWARE = ROOT / "conformance" / "hardware.json"

BLANK = bytes(PROGRAM_WORDS * 3 + TABLE_WORDS * 2)

BOOT = 64

DOCUMENTED_GAP = 14

SLOW_ACCESS = 8

A_SIXTIETH_OF_A_SECOND = 126666


def an_identity(part: str = "dsp1") -> SimpleNamespace:
    return SimpleNamespace(
        part=part,
        processor="upd7725",
        revision="MADE UP",
        program_words=PROGRAM_WORDS,
        data_words=TABLE_WORDS,
    )


def a_part(model: str = "dsp1", **options: Any) -> Any:
    return snesdsp.Chip(model, image=BLANK, identity=an_identity(), boot=BOOT, **options)


def spent(part: Any, act: Any) -> int:
    before = int(part.core.cycles)
    act()
    return int(part.core.cycles) - before


def window(name: str) -> dict[str, Any]:
    held = json.loads(HARDWARE.read_text())["facts"][name]
    assert isinstance(held, dict), f"{name} is not recorded"
    return held


def edges(name: str) -> tuple[int, int, int, int]:
    rows = {row["register"].split()[0]: row for row in window(name)["rows"]}
    status, data = rows["STATUS"], rows["DATA"]
    bank = int(status["banks"].split()[-1], 16)
    return (
        bank,
        int(data["from"][:-1], 16),
        int(status["from"][:-1], 16),
        int(status["to"][:-1], 16),
    )


def banks(name: str) -> list[int]:
    printed = window(name)["rows"][0]["banks"].replace("(", "").replace(")", "").split()
    mirrors = [int(one, 16) for one in window(name)["mirrorBanks"]]
    return [int(one, 16) for one in printed] + mirrors


def landed(address: int) -> str:
    part = a_part()
    part.core.registers.sr.rqm = True
    part.core.registers.dr = 0x5A5A
    found = part.read_bus(address)
    return "status" if found == part.read_status() and found != 0x5A else "data"


class BusTest(unittest.TestCase):
    def test_mode_20_selects_the_status_register_with_address_line_14(self) -> None:
        # Arrange
        bank, data, status, end = edges("mode20Window")

        # Act
        found = [landed(bank << 16 | one) for one in (data, status - 1, status, end)]

        # Assert
        self.assertEqual(
            (found, data ^ status),
            (["data", "data", "status", "status"], 1 << window("mode20Window")["selectLine"]),
        )

    def test_mode_21_selects_the_status_register_with_address_line_12(self) -> None:
        # Arrange
        bank, data, status, end = edges("mode21Window")

        # Act
        found = [landed(bank << 16 | one) for one in (data, status - 1, status, end)]

        # Assert
        self.assertEqual(
            (found, data ^ status),
            (["data", "data", "status", "status"], 1 << window("mode21Window")["selectLine"]),
        )

    def test_every_bank_of_each_window_and_its_mirror_reaches_the_part(self) -> None:
        # Arrange
        names = ("mode20Window", "mode21Window")

        # Act
        found = {landed(bank << 16 | edges(name)[2]) for name in names for bank in banks(name)}

        # Assert
        self.assertEqual(found, {"status"})

    def test_the_lowest_address_bit_no_longer_picks_the_port(self) -> None:
        # Arrange
        address = 0x3F8001

        # Act
        found = landed(address)

        # Assert
        self.assertEqual(found, "data")

    def test_an_address_outside_both_windows_is_refused(self) -> None:
        # Arrange
        part = a_part()

        # Act
        with self.assertRaises(snesdsp.NotDecoded) as refused:
            part.read_bus(0x00C000)

        # Assert
        self.assertTrue(str(refused.exception).startswith("00C000 is in neither window"))

    def test_and_a_write_there_is_refused_too(self) -> None:
        # Arrange
        part = a_part()

        # Act
        with self.assertRaises(snesdsp.NotDecoded) as refused:
            part.write_bus(0x406000, 0x42)

        # Assert
        self.assertTrue(str(refused.exception).startswith("406000 is in neither window"))

    def test_a_write_to_the_data_range_reaches_the_data_port(self) -> None:
        # Arrange
        part = a_part()

        # Act
        part.write_bus(0x3F8000, 0x42)

        # Assert
        self.assertEqual(part.core.registers.dr & 0xFF, 0x42)

    def test_a_write_to_the_read_only_status_range_leaves_the_data_port_alone(self) -> None:
        # Arrange
        part = a_part()
        before = part.core.registers.dr

        # Act
        handed = part.write_bus(0x007000, 0x42)

        # Assert
        self.assertEqual((handed, part.core.registers.dr), (part, before))

    def test_what_is_written_is_narrowed_to_a_byte(self) -> None:
        # Arrange
        part = a_part()

        # Act
        part.write_bus(0x006000, 0x1FF)

        # Assert
        self.assertEqual(part.core.registers.dr & 0xFF, 0xFF)


class PacingTest(unittest.TestCase):
    def test_the_default_gap_is_the_one_the_readme_derives(self) -> None:
        # Arrange
        part = a_part()

        # Act
        gap = part.gap

        # Assert
        self.assertEqual((gap, snesdsp.GAP), (DOCUMENTED_GAP, DOCUMENTED_GAP))

    def test_a_sixtieth_of_a_second_of_console_time_is_the_worked_example(self) -> None:
        # Arrange
        part = a_part()

        # Act
        run = spent(part, lambda: part.elapsed(snesdsp.MASTER_CLOCK // 60))

        # Assert
        self.assertEqual(run, A_SIXTIETH_OF_A_SECOND)

    def test_more_console_time_runs_the_part_further(self) -> None:
        # Arrange
        part = a_part()

        # Act
        one = spent(part, lambda: part.elapsed(SLOW_ACCESS))
        hundred = spent(part, lambda: part.elapsed(SLOW_ACCESS * 100))

        # Assert
        self.assertGreater(hundred, one)

    def test_no_console_time_at_all_runs_it_nowhere(self) -> None:
        # Arrange
        part = a_part()

        # Act
        run = spent(part, lambda: part.elapsed(0))

        # Assert
        self.assertEqual(run, 0)

    def test_the_part_says_what_rate_it_runs_at(self) -> None:
        # Arrange
        part = a_part()

        # Act
        rate = part.clock

        # Assert
        self.assertEqual(rate, 7_600_000)

    def test_a_write_runs_the_gap_afterwards(self) -> None:
        # Arrange
        part = a_part()

        # Act
        run = spent(part, lambda: part.write(0x12))

        # Assert
        self.assertEqual(run, DOCUMENTED_GAP)

    def test_a_step_with_no_count_runs_the_gap(self) -> None:
        # Arrange
        part = a_part()

        # Act
        run = spent(part, part.step)

        # Assert
        self.assertEqual(run, DOCUMENTED_GAP)

    def test_a_step_with_a_count_runs_that_many(self) -> None:
        # Arrange
        part = a_part()

        # Act
        run = spent(part, lambda: part.step(3))

        # Assert
        self.assertEqual(run, 3)

    def test_a_writable_gap_is_the_one_the_next_access_leaves(self) -> None:
        # Arrange
        part = a_part()
        part.gap = 5

        # Act
        run = spent(part, lambda: part.write(0x12))

        # Assert
        self.assertEqual(run, 5)


class StatusTest(unittest.TestCase):
    def test_a_part_that_has_not_asked_shows_rqm_clear(self) -> None:
        # Arrange
        part = a_part()

        # Act
        status = part.read_status()

        # Assert
        self.assertEqual(status & 0x80, 0)

    def test_a_part_that_asks_shows_rqm_set(self) -> None:
        # Arrange
        part = a_part()
        part.core.registers.sr.rqm = True

        # Act
        status = part.read_status()

        # Assert
        self.assertEqual(status & 0x80, 0x80)

    def test_it_is_one_byte_wide(self) -> None:
        # Arrange
        part = a_part()
        part.core.registers.sr.rqm = True

        # Act
        status = part.read_status()

        # Assert
        self.assertLessEqual(status, 0xFF)

    def test_reading_it_does_not_change_what_the_part_has_to_say(self) -> None:
        # Arrange
        part = a_part()
        part.core.registers.sr.rqm = True

        # Act
        part.read_status()

        # Assert
        self.assertEqual((part.asking, part.pending_output), (True, 1))


class WaitingTest(unittest.TestCase):
    def test_a_part_that_is_already_asking_is_read_without_waiting(self) -> None:
        # Arrange
        part = a_part(patience=1)
        part.core.registers.sr.rqm = True

        # Act
        run = spent(part, part.read)

        # Assert
        self.assertEqual(run, DOCUMENTED_GAP)

    def test_and_waiting_on_one_that_is_asking_says_so_at_once(self) -> None:
        # Arrange
        part = a_part(patience=1)
        part.core.registers.sr.rqm = True

        # Act
        asked = part.waited()

        # Assert
        self.assertTrue(asked)

    def test_while_one_that_never_asks_says_it_never_did(self) -> None:
        # Arrange
        part = a_part(patience=8)

        # Act
        asked = part.waited()

        # Assert
        self.assertFalse(asked)

    def test_settling_a_part_that_is_asking_returns_rather_than_refusing(self) -> None:
        # Arrange
        part = a_part(patience=1)
        part.core.registers.sr.rqm = True

        # Act
        part.settle()

        # Assert
        self.assertTrue(part.asking)

    def test_a_program_that_never_asks_is_given_up_on_when_settled(self) -> None:
        # Arrange
        part = a_part(patience=32)

        # Act
        with self.assertRaises(snesdsp.NeverReady) as refused:
            part.settle()

        # Assert
        self.assertIn("32 instructions", str(refused.exception))

    def test_but_reading_from_it_waits_out_its_patience_and_then_the_gap(self) -> None:
        # Arrange
        part = a_part(patience=32)

        # Act
        run = spent(part, part.read)

        # Assert
        self.assertEqual(run, 32 + DOCUMENTED_GAP)

    def test_a_part_that_is_asking_reports_that_it_has_something_to_say(self) -> None:
        # Arrange
        part = a_part()
        part.core.registers.sr.rqm = True

        # Act
        pending = part.pending_output

        # Assert
        self.assertEqual(pending, 1)

    def test_and_one_that_is_not_reports_nothing(self) -> None:
        # Arrange
        part = a_part()

        # Act
        pending = part.pending_output

        # Assert
        self.assertEqual(pending, 0)


if __name__ == "__main__":
    unittest.main()
