import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dsp3corpus

FIRST, SECOND = dsp3corpus.buildable_seeds(2)


class SessionTest(unittest.TestCase):
    def test_a_session_is_a_run_of_writes_and_reads(self):
        steps = dsp3corpus.steps_for(FIRST)

        self.assertTrue(all(kind in (dsp3corpus.WRITE, dsp3corpus.READ) for kind, _ in steps))

    def test_a_session_opens_by_telling_the_chip_how_big_the_grid_is(self):
        self.assertEqual(dsp3corpus.steps_for(FIRST)[0], (dsp3corpus.WRITE, dsp3corpus.SET_WINDOW))

    def test_the_same_seed_builds_the_same_session(self):
        self.assertEqual(dsp3corpus.steps_for(FIRST), dsp3corpus.steps_for(FIRST))

    def test_different_seeds_build_different_sessions(self):
        self.assertNotEqual(dsp3corpus.steps_for(FIRST), dsp3corpus.steps_for(SECOND))

    def test_every_session_reaches_every_job_the_chip_does(self):
        written = [value for kind, value in dsp3corpus.steps_for(FIRST) if kind == dsp3corpus.WRITE]

        for command in dsp3corpus.EXERCISED:
            self.assertIn(command, written)


class CorpusTest(unittest.TestCase):
    def test_the_corpus_that_ships_holds_sessions(self):
        self.assertTrue(dsp3corpus.load()["cases"])

    def test_every_case_names_its_seed_and_its_expected_answer(self):
        for case in dsp3corpus.load()["cases"]:
            self.assertIn("seed", case)
            self.assertIn("expected", case)

    def test_the_corpus_says_where_its_answers_came_from(self):
        self.assertIn("reference", dsp3corpus.load())

    def test_a_corpus_can_be_read_from_somewhere_else(self):
        where = Path(tempfile.mkdtemp()) / "other.json"
        where.write_text(json.dumps({"reference": "x", "cases": []}))

        self.assertEqual(dsp3corpus.load(where)["cases"], [])


class ReplayTest(unittest.TestCase):
    def test_replaying_a_session_answers_bytes(self):
        found = dsp3corpus.replay(dsp3corpus.steps_for(FIRST))

        self.assertTrue(all(0 <= value <= 0xFF for value in found))

    def test_the_same_session_replays_the_same_way(self):
        self.assertEqual(
            dsp3corpus.replay(dsp3corpus.steps_for(FIRST)),
            dsp3corpus.replay(dsp3corpus.steps_for(FIRST)),
        )


class ComparisonTest(unittest.TestCase):
    def test_two_identical_answers_report_nothing(self):
        self.assertIsNone(dsp3corpus.disagreement([1, 2], [1, 2]))

    def test_a_byte_that_differs_is_named_with_its_position(self):
        self.assertEqual(dsp3corpus.disagreement([1, 2], [1, 3]), (1, 2, 3))

    def test_an_answer_that_stops_early_is_reported(self):
        self.assertEqual(dsp3corpus.disagreement([1, 2], [1])[0], 1)


class AgainstCorpusTest(unittest.TestCase):
    def test_the_model_reproduces_every_answer_the_reference_gave(self):
        for case in dsp3corpus.load()["cases"]:
            found = dsp3corpus.disagreement(
                dsp3corpus.expected_of(case), dsp3corpus.replay(dsp3corpus.steps_for(case["seed"]))
            )

            self.assertIsNone(found, f"seed {case['seed']}")


class RunTest(unittest.TestCase):
    def test_a_full_run_reports_clean(self):
        self.assertEqual(dsp3corpus.run([]), 0)

    def test_a_corpus_whose_answers_are_wrong_makes_the_run_fail(self):
        where = Path(tempfile.mkdtemp()) / "wrong.json"
        where.write_text(
            json.dumps(
                {"reference": "x", "cases": [{"seed": FIRST, "expected": dsp3corpus.encode([0])}]}
            )
        )

        self.assertEqual(dsp3corpus.run(["--corpus", str(where)]), 1)

    def test_an_option_it_does_not_know_is_refused(self):
        with self.assertRaises(dsp3corpus.Usage):
            dsp3corpus.options(["--nonsense"])

    def test_an_option_with_no_value_is_refused(self):
        with self.assertRaises(dsp3corpus.Usage):
            dsp3corpus.options(["--corpus"])

    def test_the_number_of_cases_can_be_set(self):
        self.assertEqual(dsp3corpus.options(["--cases", "7"]).cases, 7)


class OverrunTest(unittest.TestCase):
    """A stream of noise can walk past the table it built, and that is the reference's memory."""

    def test_a_seed_that_walks_past_the_table_does_not_build(self):
        overrunning = [seed for seed in range(60) if not dsp3corpus.buildable(seed)]

        self.assertTrue(overrunning)

    def test_and_the_model_says_so_rather_than_answering_from_somewhere_else(self):
        overrunning = next(seed for seed in range(60) if not dsp3corpus.buildable(seed))

        with self.assertRaises(dsp3corpus.dsp3.TableOverrun):
            dsp3corpus.steps_for(overrunning)

    def test_a_corpus_naming_one_of_them_fails_the_run(self):
        overrunning = next(seed for seed in range(60) if not dsp3corpus.buildable(seed))
        where = Path(tempfile.mkdtemp()) / "stale.json"
        where.write_text(
            json.dumps(
                {
                    "reference": "x",
                    "cases": [{"seed": overrunning, "expected": dsp3corpus.encode([0])}],
                }
            )
        )

        self.assertEqual(dsp3corpus.run(["--corpus", str(where)]), 1)

    def test_a_corpus_of_many_of_them_stops_reporting_after_a_handful(self):
        overrunning = [seed for seed in range(200) if not dsp3corpus.buildable(seed)]
        where = Path(tempfile.mkdtemp()) / "stale.json"
        cases = [
            {"seed": seed, "expected": dsp3corpus.encode([0])}
            for seed in overrunning[: dsp3corpus.REPORT_LIMIT + 3]
        ]
        where.write_text(json.dumps({"reference": "x", "cases": cases}))

        self.assertEqual(dsp3corpus.run(["--corpus", str(where)]), 1)

    def test_the_seeds_that_build_are_the_ones_recorded(self):
        recorded = {case["seed"] for case in dsp3corpus.load()["cases"]}

        for seed in recorded:
            self.assertTrue(dsp3corpus.buildable(seed))


class EncodingTest(unittest.TestCase):
    def test_an_answer_survives_being_written_down_and_read_back(self):
        self.assertEqual(
            dsp3corpus.expected_of({"expected": dsp3corpus.encode([1, 2, 3])}), [1, 2, 3]
        )


class ReportLimitTest(unittest.TestCase):
    def test_a_corpus_of_many_wrong_answers_stops_reporting_after_a_handful(self):
        where = Path(tempfile.mkdtemp()) / "wrong.json"
        cases = [
            {"seed": seed, "expected": dsp3corpus.encode([0])}
            for seed in dsp3corpus.buildable_seeds(8)
        ]
        where.write_text(json.dumps({"reference": "x", "cases": cases}))

        self.assertEqual(dsp3corpus.run(["--corpus", str(where)]), 1)


class EntryTest(unittest.TestCase):
    def test_a_run_from_the_command_line_returns_what_the_run_returned(self):
        self.assertEqual(dsp3corpus.main([]), 0)

    def test_an_option_it_does_not_know_is_reported(self):
        self.assertEqual(dsp3corpus.main(["--nonsense"]), 2)


if __name__ == "__main__":
    unittest.main()
