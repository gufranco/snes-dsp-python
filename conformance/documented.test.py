import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import documented


class Puppet:
    """A part that answers whatever it was handed, so the plumbing can be checked."""

    def __init__(self, answers: Sequence[int] = (), part: str = "dsp1") -> None:
        self.answers = list(answers)
        self.written: list[int] = []
        self.identity = type("Identity", (), {"part": part})()

    def write(self, value: int) -> None:
        self.written.append(value)

    def read(self) -> int:
        return self.answers.pop(0) if self.answers else 0


def puppets(**answers: Any) -> Any:
    def build(name: str) -> Any:
        return Puppet(answers.get(name, ()), part=answers.get("identity", name))

    return build


class ShapeTest(unittest.TestCase):
    def test_every_documented_example_carries_a_name(self) -> None:
        for name, _, _ in documented.DOCUMENTED:
            self.assertTrue(name)

    def test_and_the_answer_the_readme_prints(self) -> None:
        for _, _, wanted in documented.DOCUMENTED:
            self.assertTrue(wanted)

    def test_and_something_to_run(self) -> None:
        for _, example, _ in documented.DOCUMENTED:
            self.assertTrue(callable(example))

    def test_there_is_one_for_every_part(self) -> None:
        from snesdsp import models

        named = " ".join(name for name, _, _ in documented.DOCUMENTED)

        for part in models.MODELS:
            self.assertIn(part, named, part)


class RunTest(unittest.TestCase):
    def test_a_run_reports_one_row_per_example(self) -> None:
        found = documented.run(build=puppets())

        self.assertEqual(len(found), len(documented.DOCUMENTED))

    def test_each_row_carries_what_the_readme_says_and_what_happened(self) -> None:
        found = documented.run(build=puppets())

        for name, wanted, got in found:
            self.assertTrue(name)
            self.assertTrue(wanted)
            self.assertIsInstance(got, str)

    def test_a_part_that_answers_something_else_is_a_disagreement(self) -> None:
        found = documented.run(build=puppets())

        self.assertTrue(documented.disagreements(found))

    def test_and_the_lines_say_which_and_what_both_sides_had(self) -> None:
        found = documented.run(build=puppets())

        text = "\n".join(documented.lines_for(found))
        self.assertIn("README says", text)
        self.assertIn("do not give what the README says", text)

    def test_a_run_where_everything_agrees_says_so(self) -> None:
        found = (("something", "0x1000", "0x1000"),)

        self.assertIn("every one gives", "\n".join(documented.lines_for(found)))

    def test_and_reports_no_disagreements(self) -> None:
        self.assertEqual(documented.disagreements((("something", "a", "a"),)), ())


class EntryTest(unittest.TestCase):
    def test_a_machine_with_no_microcode_says_so_rather_than_passing(self) -> None:
        said: list[str] = []

        code = documented.main([], why_not=lambda: "no image is here", say=said.append)

        self.assertEqual(code, 2)
        self.assertIn("nothing to run", " ".join(said))

    def test_a_disagreement_is_reported_as_a_failure(self) -> None:
        said: list[str] = []

        code = documented.main([], why_not=lambda: None, build=puppets(), say=said.append)

        self.assertEqual(code, 1)
        self.assertTrue(said)

    def test_and_agreement_as_a_pass(self) -> None:
        agreeing = (("something", lambda _build: "0x1000", "0x1000"),)
        said: list[str] = []

        code = documented.main(
            [],
            why_not=lambda: None,
            build=puppets(),
            documented=agreeing,
            say=said.append,
        )

        self.assertEqual(code, 0)
        self.assertIn("every one gives", " ".join(said))


if __name__ == "__main__":
    unittest.main()
