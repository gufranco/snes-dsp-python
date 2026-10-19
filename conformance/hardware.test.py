import json
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp

HARDWARE = Path(__file__).resolve().parent / "hardware.json"

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024

LAST_WORD = b"\x12\x34\x56"

STEPS = 50

PROGRAM_BYTES_PER_WORD = 3

TABLE_BYTES_PER_WORD = 2

LONG_STORE_CYCLES = 5


def declared() -> dict[str, Any]:
    held = json.loads(HARDWARE.read_text())
    assert isinstance(held, dict), f"{HARDWARE} does not hold an object"
    return held


def words_of(part: Any) -> list[int]:
    store = part.core.stores.program
    return [store[at] for at in range(len(store))]


def a_part() -> Any:
    identity = SimpleNamespace(
        part="dsp1",
        processor="upd7725",
        revision="MADE UP",
        program_words=PROGRAM_WORDS,
        data_words=TABLE_WORDS,
    )
    program = bytes(PROGRAM_WORDS * PROGRAM_BYTES_PER_WORD - len(LAST_WORD)) + LAST_WORD
    table = bytes(TABLE_WORDS * TABLE_BYTES_PER_WORD)
    return snesdsp.Chip("dsp1", image=program + table, identity=identity, boot=0)


def printed_megahertz(quote: str) -> int:
    found = re.search(r"\(([\d.]+) MHz maximum\)", quote)
    assert found is not None, f"no ceiling in {quote!r}"
    return round(float(found.group(1)) * 1_000_000)


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
        # Arrange
        rated = self.facts["ratedClock"]

        # Act
        printed = printed_megahertz(rated["quote"])

        # Assert
        self.assertEqual((rated["value"], rated["verified"]), (printed, True))

    def test_the_cartridge_oscillator_is_the_one_the_part_runs_at(self) -> None:
        # Arrange
        crystal = self.facts["cartridgeOscillatorHz"]

        # Act
        rate = a_part().clock

        # Assert
        self.assertEqual(crystal["value"], rate)

    def test_and_it_is_marked_unverified_because_no_document_carries_it(self) -> None:
        # Arrange
        crystal = self.facts["cartridgeOscillatorHz"]

        # Act
        verified = crystal["verified"]

        # Assert
        self.assertFalse(verified)

    def test_the_oscillator_stays_under_the_ceiling_the_data_sheet_gives(self) -> None:
        # Arrange
        ceiling = self.facts["ratedClock"]["value"]

        # Act
        rate = a_part().clock

        # Assert
        self.assertLess(rate, ceiling)

    def test_the_master_clock_is_the_one_the_console_time_is_counted_in(self) -> None:
        # Arrange
        master = self.facts["masterClockHz"]

        # Act
        a_second = snesdsp.steps_for(master["value"])

        # Assert
        self.assertEqual((a_second, master["verified"]), (a_part().clock, False))

    def test_the_slow_access_cost_is_what_sets_the_gap_and_the_fast_one_is_not(self) -> None:
        # Arrange
        access = self.facts["accessCostMasterCycles"]

        # Act
        slow, fast = (snesdsp.steps_for(LONG_STORE_CYCLES * access[k]) for k in ("slow", "fast"))

        # Assert
        self.assertEqual(slow, a_part().gap)
        self.assertLess(fast, a_part().gap)

    def test_the_unverified_access_count_is_not_used_here(self) -> None:
        # Arrange
        access = self.facts["accessCostMasterCycles"]

        # Act
        extra = set(access) & {"extraSlow", "extra_slow"}

        # Assert
        self.assertEqual(extra, set())


class PrintedBehaviourTest(unittest.TestCase):
    def test_a_second_of_console_time_never_runs_the_part_past_its_rated_ceiling(self) -> None:
        # Arrange
        ceiling = declared()["facts"]["ratedClock"]["value"]
        part = a_part()

        # Act
        run = snesdsp.steps_for(snesdsp.MASTER_CLOCK, part.clock)

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
        # Arrange
        crystal = declared()["facts"]["cartridgeOscillatorHz"]

        # Act
        why = crystal["why"]

        # Assert
        self.assertIn("load-bearing", why)

    def test_six_of_the_nine_facts_are_documented(self) -> None:
        # Arrange
        facts = declared()["facts"]

        # Act
        verified = [name for name, fact in facts.items() if fact["verified"]]

        # Assert
        self.assertEqual(len(verified), 6)

    def test_a_faster_oscillator_would_change_what_the_part_gets_done(self) -> None:
        # Arrange
        part = a_part()
        slow = declared()["facts"]["accessCostMasterCycles"]["slow"]

        # Act
        doubled = snesdsp.steps_for(LONG_STORE_CYCLES * slow, clock=part.clock * 2)

        # Assert
        self.assertGreater(doubled, part.gap)


if __name__ == "__main__":
    unittest.main(verbosity=1)
