import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

CARTRIDGE_OSCILLATOR = 7_600_000

NTSC_COLOUR_CARRIER = 3_579_545.4545454545

PAL_MASTER_CLOCK = round(4_433_618.75 * 4.8)

SLOW_ACCESS = 8

FAST_ACCESS = 6

LONG_STORE_CYCLES = 5


class ClockTest(unittest.TestCase):
    def test_every_part_runs_at_the_cartridge_oscillator(self) -> None:
        # Arrange
        names = sorted(snesdsp.MODELS)

        # Act
        rates = {name: snesdsp.clock_of(name) for name in names}

        # Assert
        self.assertEqual(rates, dict.fromkeys(names, CARTRIDGE_OSCILLATOR))

    def test_a_model_is_found_by_its_alias_too(self) -> None:
        # Arrange
        alias = "DSP-1"

        # Act
        rate = snesdsp.clock_of(alias)

        # Assert
        self.assertEqual(rate, CARTRIDGE_OSCILLATOR)

    def test_a_part_nobody_names_is_refused(self) -> None:
        # Arrange
        name = "nonsense"

        # Act
        with self.assertRaises(snesdsp.UnknownModelError) as refused:
            snesdsp.clock_of(name)

        # Assert
        self.assertIn("nonsense is not a part this package covers", str(refused.exception))

    def test_the_published_rate_is_the_cartridge_oscillator(self) -> None:
        # Arrange
        expected = CARTRIDGE_OSCILLATOR

        # Act
        rate = snesdsp.DSP_CLOCK

        # Assert
        self.assertEqual(rate, expected)

    def test_the_console_rate_is_six_times_its_colour_carrier(self) -> None:
        # Arrange
        expected = round(NTSC_COLOUR_CARRIER * 6)

        # Act
        rate = snesdsp.MASTER_CLOCK

        # Assert
        self.assertEqual((rate, expected), (21_477_273, 21_477_273))


class ConversionTest(unittest.TestCase):
    def test_one_slow_access_alone_is_two_instructions(self) -> None:
        # Arrange
        master_clocks = SLOW_ACCESS

        # Act
        steps = snesdsp.steps_for(master_clocks)

        # Assert
        self.assertEqual(steps, 2)

    def test_a_longer_wait_gives_the_part_more_to_do(self) -> None:
        # Arrange
        master_clocks = SLOW_ACCESS * 10

        # Act
        steps = snesdsp.steps_for(master_clocks)

        # Assert
        self.assertEqual(steps, 28)

    def test_no_console_time_gives_the_part_none(self) -> None:
        # Arrange
        master_clocks = 0

        # Act
        steps = snesdsp.steps_for(master_clocks)

        # Assert
        self.assertEqual(steps, 0)

    def test_a_second_of_console_time_is_a_second_of_the_part(self) -> None:
        # Arrange
        master_clocks = snesdsp.MASTER_CLOCK

        # Act
        steps = snesdsp.steps_for(master_clocks)

        # Assert
        self.assertEqual(steps, CARTRIDGE_OSCILLATOR)

    def test_a_sixtieth_of_a_second_is_the_worked_example(self) -> None:
        # Arrange
        master_clocks = snesdsp.MASTER_CLOCK // 60

        # Act
        steps = snesdsp.steps_for(master_clocks)

        # Assert
        self.assertEqual(steps, 126_666)

    def test_a_faster_access_leaves_the_part_no_more(self) -> None:
        # Arrange
        slow = snesdsp.steps_for(SLOW_ACCESS)

        # Act
        fast = snesdsp.steps_for(FAST_ACCESS)

        # Assert
        self.assertEqual((fast, slow), (2, 2))

    def test_a_part_that_runs_faster_gets_more_out_of_the_same_wait(self) -> None:
        # Arrange
        slow = snesdsp.steps_for(snesdsp.MASTER_CLOCK, clock=1_000_000)

        # Act
        fast = snesdsp.steps_for(snesdsp.MASTER_CLOCK, clock=2_000_000)

        # Assert
        self.assertEqual((slow, fast), (1_000_000, 2_000_000))

    def test_a_console_that_runs_slower_gives_the_part_more_per_access(self) -> None:
        # Arrange
        ntsc = snesdsp.steps_for(SLOW_ACCESS * 1000)

        # Act
        pal = snesdsp.steps_for(SLOW_ACCESS * 1000, master=PAL_MASTER_CLOCK)

        # Assert
        self.assertEqual((pal, ntsc), (2856, 2830))


class GapTest(unittest.TestCase):
    def test_the_gap_is_what_one_long_store_of_slow_accesses_leaves(self) -> None:
        # Arrange
        master_clocks = LONG_STORE_CYCLES * SLOW_ACCESS

        # Act
        steps = snesdsp.steps_for(master_clocks)

        # Assert
        self.assertEqual((steps, snesdsp.GAP), (14, 14))

    def test_it_is_several_times_what_one_access_alone_leaves(self) -> None:
        # Arrange
        one_access = snesdsp.steps_for(SLOW_ACCESS)

        # Act
        gap = snesdsp.GAP

        # Assert
        self.assertEqual((gap, one_access), (14, 2))


if __name__ == "__main__":
    unittest.main()
