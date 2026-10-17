import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import chip, firmware, timing

HARDWARE = Path(__file__).resolve().parent / "hardware.json"

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024

LAST_WORD = b"\x12\x34\x56"

STEPS = 50


def declared() -> dict[str, Any]:
    held = json.loads(HARDWARE.read_text())
    assert isinstance(held, dict), f"{HARDWARE} does not hold an object"
    return held


def words_of(part: chip.Chip) -> list[int]:
    store = part.core.stores.program
    return [store[at] for at in range(len(store))]


def a_part() -> chip.Chip:
    sys.path.insert(0, str(chip.PROCESSOR))
    identity = firmware.Identity("made-up", "upd7725", "MADE UP", PROGRAM_WORDS, TABLE_WORDS)
    program = bytes(PROGRAM_WORDS * firmware.PROGRAM_BYTES_PER_WORD - len(LAST_WORD)) + LAST_WORD
    table = bytes(TABLE_WORDS * firmware.TABLE_BYTES_PER_WORD)
    return chip.Chip("made-up", image=program + table, identity=identity, boot=0)


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


class PrintedBehaviourTest(unittest.TestCase):
    def test_a_second_of_console_time_never_runs_the_part_past_its_rated_ceiling(self) -> None:
        # Arrange
        ceiling = declared()["facts"]["ratedClock"]["value"]
        part = a_part()

        # Act
        run = timing.steps_for(timing.MASTER_CLOCK, part.clock)

        # Assert
        self.assertLessEqual(run, ceiling)

    def test_every_instruction_the_part_runs_costs_the_printed_cycle(self) -> None:
        # Arrange
        per_clock = declared()["facts"]["instructionsPerClock"]["value"]
        part = a_part()
        before = part.core.cycles

        # Act
        part.step(STEPS)

        # Assert
        self.assertEqual(part.core.cycles - before, STEPS * per_clock)

    def test_a_reset_restarts_at_address_zero_with_the_program_intact(self) -> None:
        # Arrange
        stated = declared()["facts"]["resetLine"]["value"]
        part = a_part()
        part.step(STEPS)
        program = words_of(part)

        # Act
        part.reset()

        # Assert
        self.assertIn("address zero", stated)
        self.assertEqual((part.core.registers.pc, words_of(part)), (0, program))


class StandingTest(unittest.TestCase):
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
