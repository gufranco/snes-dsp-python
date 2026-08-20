import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import snesdsp
from snesdsp import silicon

RECORDED = Path(__file__).resolve().parent / "divergences.json"


def declared() -> dict[str, Any]:
    held = json.loads(RECORDED.read_text())
    assert isinstance(held, dict), f"{RECORDED} does not hold an object"
    return held


def entry_for(part: str, command: str) -> dict[str, Any]:
    for one in declared()["divergences"]:
        if one["part"] == part and one["command"] == command:
            assert isinstance(one, dict)
            return one
    raise AssertionError(f"nothing recorded for {part} {command}")


class RecordTest(unittest.TestCase):
    """That a recorded divergence says enough for somebody to check it."""

    def test_every_entry_names_both_sides(self) -> None:
        for one in declared()["divergences"]:
            self.assertIn("thisProject", one)
            self.assertIn("otherImplementation", one)

    def test_and_pins_the_other_implementation_to_a_commit(self) -> None:
        for one in declared()["divergences"]:
            other = one["otherImplementation"]
            self.assertEqual(len(other["commit"]), 40, other["name"])

    def test_and_gives_the_bytes_that_produce_it(self) -> None:
        for one in declared()["divergences"]:
            self.assertGreater(len(one["thisProject"]["sends"]), 0)

    def test_and_says_what_it_has_not_established(self) -> None:
        for one in declared()["divergences"]:
            self.assertGreater(len(one["whatIsNotEstablished"]), 0)

    def test_the_file_says_which_side_is_the_authority(self) -> None:
        self.assertIn("microcode is the part", declared()["howToRead"]["authority"])

    def test_and_says_it_is_not_a_bug_report(self) -> None:
        self.assertIn("Not a bug report", declared()["howToRead"]["whatThisIsNot"])


class DivergenceTest(unittest.TestCase):  # pragma: no cover
    """The divergence itself, on a machine holding the microcode.

    Outside the coverage gate for the same reason every other artifact-dependent
    test here is: it runs on one machine and not another. What it adds is that the
    recorded answer is still the answer, so an entry cannot quietly go stale.
    """

    def test_the_part_still_answers_what_was_recorded(self) -> None:
        if silicon.why_not() is not None:
            self.skipTest("no microcode on this machine")

        one = entry_for("dsp3", "0x1c")
        chip = snesdsp.Dsp("dsp3")
        for byte in one["thisProject"]["sends"]:
            chip.write(int(byte, 16))

        said = " ".join(f"{chip.read():02x}" for _ in range(8))

        self.assertEqual(said, "78 56 78 56 78 56 78 56")

    def test_and_echoes_the_last_word_rather_than_a_constant(self) -> None:
        if silicon.why_not() is not None:
            self.skipTest("no microcode on this machine")

        chip = snesdsp.Dsp("dsp3")
        for byte in (0x1C, 0x00, 0xAA, 0xBB, 0xCC, 0xDD):
            chip.write(byte)

        said = " ".join(f"{chip.read():02x}" for _ in range(4))

        self.assertEqual(said, "cc dd cc dd")

    def test_and_does_not_answer_the_zeroes_the_other_one_does(self) -> None:
        if silicon.why_not() is not None:
            self.skipTest("no microcode on this machine")

        chip = snesdsp.Dsp("dsp3")
        for byte in (0x1C, 0x00, 0x34, 0x12, 0x78, 0x56):
            chip.write(byte)

        self.assertNotEqual([chip.read() for _ in range(4)], [0, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
