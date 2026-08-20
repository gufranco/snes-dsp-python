import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import models, timing


class ClockTest(unittest.TestCase):
    def test_every_part_runs_at_a_stated_rate(self):
        for name in models.MODELS:
            self.assertGreater(timing.clock_of(name), 0, name)

    def test_the_family_shares_one_rate(self):
        rates = {timing.clock_of(name) for name in models.MODELS}

        self.assertEqual(rates, {timing.DSP_CLOCK})

    def test_a_part_nobody_names_is_refused(self):
        with self.assertRaises(models.UnknownModelError):
            timing.clock_of("nonsense")

    def test_the_rate_is_the_one_the_cartridge_oscillator_runs_at(self):
        self.assertEqual(timing.DSP_CLOCK, 7_600_000)

    def test_the_console_rate_is_six_times_its_colour_carrier(self):
        self.assertEqual(timing.MASTER_CLOCK, round(timing.NTSC_COLOURBURST * 6))

    def test_a_slower_console_is_also_named(self):
        self.assertLess(timing.PAL_MASTER_CLOCK, timing.MASTER_CLOCK)


class AccessTest(unittest.TestCase):
    def test_a_cartridge_access_costs_the_console_a_stated_number_of_clocks(self):
        self.assertEqual(timing.SLOW_ACCESS, 8)
        self.assertEqual(timing.FAST_ACCESS, 6)

    def test_a_fast_access_costs_less_than_a_slow_one(self):
        self.assertLess(timing.FAST_ACCESS, timing.SLOW_ACCESS)


class ConversionTest(unittest.TestCase):
    def test_console_clocks_become_part_instructions(self):
        self.assertGreater(timing.steps_for(timing.SLOW_ACCESS), 0)

    def test_a_longer_wait_gives_the_part_more_to_do(self):
        self.assertGreater(
            timing.steps_for(timing.SLOW_ACCESS * 10), timing.steps_for(timing.SLOW_ACCESS)
        )

    def test_no_console_time_gives_the_part_none(self):
        self.assertEqual(timing.steps_for(0), 0)

    def test_the_ratio_is_the_two_rates_rather_than_a_number_somebody_picked(self):
        found = timing.steps_for(timing.MASTER_CLOCK)

        self.assertEqual(found, timing.DSP_CLOCK)

    def test_one_bus_access_alone_is_only_a_few_instructions(self):
        self.assertLessEqual(timing.steps_for(timing.SLOW_ACCESS), 4)

    def test_but_the_store_around_it_costs_several_times_that(self):
        self.assertGreater(
            timing.steps_for(timing.LONG_STORE_CYCLES * timing.SLOW_ACCESS),
            timing.steps_for(timing.SLOW_ACCESS) * 4,
        )

    def test_and_a_faster_console_leaves_it_fewer_still(self):
        self.assertLessEqual(
            timing.steps_for(timing.FAST_ACCESS), timing.steps_for(timing.SLOW_ACCESS)
        )

    def test_a_part_that_runs_faster_gets_more_out_of_the_same_wait(self):
        slow = timing.steps_for(timing.MASTER_CLOCK, clock=1_000_000)
        fast = timing.steps_for(timing.MASTER_CLOCK, clock=2_000_000)

        self.assertEqual(fast, 2 * slow)

    def test_a_console_that_runs_slower_gives_the_part_more_per_access(self):
        found = timing.steps_for(timing.SLOW_ACCESS, master=timing.PAL_MASTER_CLOCK)

        self.assertGreaterEqual(found, timing.steps_for(timing.SLOW_ACCESS))


class GapTest(unittest.TestCase):
    def test_the_gap_is_derived_from_the_store_that_reaches_the_port(self):
        self.assertEqual(
            timing.GAP, timing.steps_for(timing.LONG_STORE_CYCLES * timing.SLOW_ACCESS)
        )

    def test_it_is_the_least_a_console_could_leave_rather_than_the_usual_amount(self):
        self.assertGreater(timing.GAP, timing.steps_for(timing.SLOW_ACCESS))

    def test_and_it_is_a_number_of_instructions_the_part_can_get_through(self):
        self.assertGreater(timing.GAP, 0)


if __name__ == "__main__":
    unittest.main()
