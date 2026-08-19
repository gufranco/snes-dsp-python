import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dsp4corpus


class CaseTest(unittest.TestCase):
    def test_a_case_is_a_run_of_writes_and_reads(self):
        steps = dsp4corpus.steps_for(0)

        self.assertTrue(all(kind in (dsp4corpus.WRITE, dsp4corpus.READ) for kind, _ in steps))

    def test_a_case_starts_by_asking_for_the_track_projection(self):
        self.assertEqual(
            dsp4corpus.steps_for(0)[:2], [(dsp4corpus.WRITE, 0x01), (dsp4corpus.WRITE, 0x00)]
        )

    def test_a_case_ends_by_telling_the_chip_the_track_has_ended(self):
        steps = dsp4corpus.steps_for(0)
        writes = [value for kind, value in steps if kind == dsp4corpus.WRITE]

        self.assertEqual(writes[-2:], [0x00, 0x80])

    def test_the_same_seed_builds_the_same_case(self):
        self.assertEqual(dsp4corpus.steps_for(3), dsp4corpus.steps_for(3))

    def test_different_seeds_build_different_cases(self):
        self.assertNotEqual(dsp4corpus.steps_for(1), dsp4corpus.steps_for(2))


class FitTest(unittest.TestCase):
    def test_a_case_whose_output_the_buffer_can_carry_is_kept(self):
        self.assertTrue(dsp4corpus.fits(dsp4corpus.steps_for(0)))

    def test_one_that_would_overrun_it_is_not(self):
        self.assertFalse(dsp4corpus.fits(dsp4corpus.steps_for(dsp4corpus.OVERRUNNING_SEED)))

    def test_no_recorded_case_is_one_of_those(self):
        recorded = {case["seed"] for case in dsp4corpus.load()["cases"]}

        self.assertNotIn(dsp4corpus.OVERRUNNING_SEED, recorded)


class CorpusTest(unittest.TestCase):
    def test_the_corpus_that_ships_holds_cases(self):
        self.assertTrue(dsp4corpus.load()["cases"])

    def test_every_case_names_its_seed_and_its_expected_answer(self):
        for case in dsp4corpus.load()["cases"]:
            self.assertIn("seed", case)
            self.assertIn("expected", case)

    def test_the_corpus_says_where_its_answers_came_from(self):
        self.assertIn("reference", dsp4corpus.load())

    def test_a_corpus_can_be_read_from_somewhere_else(self):
        where = Path(tempfile.mkdtemp()) / "other.json"
        where.write_text(json.dumps({"reference": "x", "cases": []}))

        self.assertEqual(dsp4corpus.load(where)["cases"], [])


class ReplayTest(unittest.TestCase):
    def test_replaying_a_case_answers_bytes(self):
        found = dsp4corpus.replay(dsp4corpus.steps_for(0))

        self.assertTrue(all(0 <= value <= 0xFF for value in found))

    def test_the_same_case_replays_the_same_way(self):
        self.assertEqual(
            dsp4corpus.replay(dsp4corpus.steps_for(0)), dsp4corpus.replay(dsp4corpus.steps_for(0))
        )


class ComparisonTest(unittest.TestCase):
    def test_two_identical_answers_report_nothing(self):
        self.assertIsNone(dsp4corpus.disagreement([1, 2], [1, 2]))

    def test_a_byte_that_differs_is_named_with_its_position(self):
        self.assertEqual(dsp4corpus.disagreement([1, 2], [1, 3]), (1, 2, 3))

    def test_an_answer_that_stops_early_is_reported(self):
        self.assertEqual(dsp4corpus.disagreement([1, 2], [1])[0], 1)


class AgainstCorpusTest(unittest.TestCase):
    def test_the_model_reproduces_every_answer_the_reference_gave(self):
        for case in dsp4corpus.load()["cases"]:
            found = dsp4corpus.disagreement(
                case["expected"], dsp4corpus.replay(dsp4corpus.steps_for(case["seed"]))
            )

            self.assertIsNone(found, f"seed {case['seed']}")


class RunTest(unittest.TestCase):
    def test_a_full_run_reports_clean(self):
        self.assertEqual(dsp4corpus.run([]), 0)

    def test_a_corpus_whose_answers_are_wrong_makes_the_run_fail(self):
        where = Path(tempfile.mkdtemp()) / "wrong.json"
        where.write_text(json.dumps({"reference": "x", "cases": [{"seed": 0, "expected": [0]}]}))

        self.assertEqual(dsp4corpus.run(["--corpus", str(where)]), 1)

    def test_an_option_it_does_not_know_is_refused(self):
        with self.assertRaises(dsp4corpus.Usage):
            dsp4corpus.options(["--nonsense"])

    def test_an_option_with_no_value_is_refused(self):
        with self.assertRaises(dsp4corpus.Usage):
            dsp4corpus.options(["--corpus"])


class RecordTest(unittest.TestCase):
    def scripted(self, body):
        where = Path(tempfile.mkdtemp()) / "fake"
        where.write_text(body)
        where.chmod(where.stat().st_mode | stat.S_IXUSR)
        return where

    def answering(self):
        return self.scripted("#!/bin/sh\ncat > /dev/null\nprintf 'AAAA????'\n")

    def test_a_driver_that_fails_is_reported_rather_than_recorded(self):
        wrong = self.scripted("#!/bin/sh\ncat > /dev/null\nexit 1\n")

        with self.assertRaises(dsp4corpus.Usage):
            dsp4corpus.ask(dsp4corpus.steps_for(0), str(wrong))

    def test_asking_a_driver_returns_what_it_said_past_the_count(self):
        found = dsp4corpus.ask(dsp4corpus.steps_for(0), str(self.answering()))

        self.assertEqual(found, [ord("?")] * 4)

    def test_recording_asks_the_driver_for_every_case_it_keeps(self):
        found = dsp4corpus.record(str(self.answering()), 3)

        self.assertEqual(len(found["cases"]), 3)

    def test_recording_walks_past_the_roads_the_buffer_cannot_carry(self):
        found = dsp4corpus.record(str(self.answering()), dsp4corpus.OVERRUNNING_SEED + 2)
        recorded = {case["seed"] for case in found["cases"]}

        self.assertNotIn(dsp4corpus.OVERRUNNING_SEED, recorded)

    def test_and_says_where_the_answers_came_from(self):
        found = dsp4corpus.record(str(self.answering()), 1)

        self.assertIn("reference", found)

    def test_recording_writes_the_corpus_where_it_was_asked(self):
        where = Path(tempfile.mkdtemp()) / "recorded.json"

        answered = dsp4corpus.run(
            ["--record", "--driver", str(self.answering()), "--corpus", str(where), "--cases", "2"]
        )

        self.assertEqual(answered, 0)
        self.assertEqual(len(json.loads(where.read_text())["cases"]), 2)

    def test_recording_without_a_driver_says_so(self):
        self.assertEqual(dsp4corpus.run(["--record"]), 2)


class ReportLimitTest(unittest.TestCase):
    def test_a_corpus_of_many_wrong_answers_stops_reporting_after_a_handful(self):
        where = Path(tempfile.mkdtemp()) / "wrong.json"
        cases = [{"seed": seed, "expected": [0]} for seed in range(8)]
        where.write_text(json.dumps({"reference": "x", "cases": cases}))

        self.assertEqual(dsp4corpus.run(["--corpus", str(where)]), 1)


class EntryTest(unittest.TestCase):
    def test_a_run_from_the_command_line_returns_what_the_run_returned(self):
        self.assertEqual(dsp4corpus.main([]), 0)

    def test_an_option_it_does_not_know_is_reported(self):
        self.assertEqual(dsp4corpus.main(["--nonsense"]), 2)


if __name__ == "__main__":
    unittest.main()
