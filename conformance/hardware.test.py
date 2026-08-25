"""Hold this package's constants to the facts in hardware.json, and to their standing.

Three of the five numbers this package times with are documented, two by NEC's
data sheet through the processor package that pins it and one by Nintendo's own
bus speeds through the mapper. Two are not, and one of those decides how many
instructions the part runs between two console accesses, which is what decides
whether a driver catches it before it has finished.

The point of this file is that a reader cannot pick up the unverified ones as
though they stood beside the others. Each is checked against the constant it
governs, and each is checked against its own mark.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import timing

HARDWARE = Path(__file__).resolve().parent / "hardware.json"


def declared() -> dict[str, Any]:
    held = json.loads(HARDWARE.read_text())
    assert isinstance(held, dict), f"{HARDWARE} does not hold an object"
    return held


class DocumentTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.facts: dict[str, Any] = declared()["facts"]

    def test_every_fact_says_whether_it_is_verified(self) -> None:
        missing = [name for name, fact in self.facts.items() if "verified" not in fact]

        self.assertEqual(missing, [])

    def test_every_verified_fact_names_where_it_came_from(self) -> None:
        missing = [
            name
            for name, fact in self.facts.items()
            if fact["verified"] and not (fact.get("source") or fact.get("quote"))
        ]

        self.assertEqual(missing, [])

    def test_every_unverified_fact_says_what_would_settle_it(self) -> None:
        missing = [
            name
            for name, fact in self.facts.items()
            if not fact["verified"] and not fact.get("howToSettleIt")
        ]

        self.assertEqual(missing, [])

    def test_what_no_document_states_is_recorded_rather_than_filled_in(self) -> None:
        stated = declared()["notStated"]

        self.assertGreaterEqual(len(stated), 4)

    def test_the_authority_puts_the_microcode_first(self) -> None:
        order = declared()["authority"]["order"]

        self.assertIn("the microcode", order[0])


class ConstantTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.facts: dict[str, Any] = declared()["facts"]

    def test_the_rated_ceiling_is_what_the_data_sheet_prints(self) -> None:
        rated = self.facts["ratedClock"]

        self.assertEqual((rated["value"], rated["verified"]), (timing.RATED_CLOCK, True))

    def test_the_cartridge_oscillator_is_the_one_this_package_times_with(self) -> None:
        crystal = self.facts["cartridgeOscillatorHz"]

        self.assertEqual(crystal["value"], timing.DSP_CLOCK)

    def test_and_it_is_marked_unverified_because_no_document_carries_it(self) -> None:
        crystal = self.facts["cartridgeOscillatorHz"]

        self.assertFalse(crystal["verified"])

    def test_the_oscillator_stays_under_the_ceiling_the_data_sheet_gives(self) -> None:
        self.assertLess(timing.DSP_CLOCK, timing.RATED_CLOCK)

    def test_the_master_clock_matches_the_derivation_written_down(self) -> None:
        master = self.facts["masterClockHz"]

        self.assertEqual((master["value"], master["verified"]), (timing.MASTER_CLOCK, False))

    def test_both_access_costs_are_the_ones_the_mapper_derived(self) -> None:
        access = self.facts["accessCostMasterCycles"]

        self.assertEqual((access["slow"], access["fast"]), (timing.SLOW_ACCESS, timing.FAST_ACCESS))

    def test_the_unverified_access_count_is_not_used_here(self) -> None:
        access = self.facts["accessCostMasterCycles"]

        self.assertEqual(set(access) & {"extraSlow", "extra_slow"}, set())


class StandingTest(unittest.TestCase):
    """What rests on a number nobody printed, said out loud rather than implied."""

    def test_the_pacing_rests_on_the_unverified_oscillator(self) -> None:
        crystal = declared()["facts"]["cartridgeOscillatorHz"]

        self.assertIn("load-bearing", crystal["why"])

    def test_four_of_the_six_facts_are_documented(self) -> None:
        facts = declared()["facts"]

        verified = [name for name, fact in facts.items() if fact["verified"]]

        self.assertEqual(len(verified), 4)

    def test_a_faster_oscillator_would_change_what_the_part_gets_done(self) -> None:
        master_clocks = timing.LONG_STORE_CYCLES * timing.SLOW_ACCESS

        doubled = timing.steps_for(master_clocks, clock=timing.DSP_CLOCK * 2)

        self.assertGreater(doubled, timing.GAP)


if __name__ == "__main__":
    unittest.main(verbosity=1)
