import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dsp1corpus

FIRST, SECOND = 0, 1


class SessionTest(unittest.TestCase):
    def test_a_session_is_a_run_of_writes_and_reads(self):
        steps = dsp1corpus.steps_for(FIRST)

        self.assertTrue(all(kind in (dsp1corpus.WRITE, dsp1corpus.READ) for kind, _ in steps))

    def test_a_session_opens_by_placing_the_camera(self):
        self.assertEqual(dsp1corpus.steps_for(FIRST)[0], (dsp1corpus.WRITE, dsp1corpus.SET_CAMERA))

    def test_the_same_seed_builds_the_same_session(self):
        self.assertEqual(dsp1corpus.steps_for(FIRST), dsp1corpus.steps_for(FIRST))

    def test_different_seeds_build_different_sessions(self):
        self.assertNotEqual(dsp1corpus.steps_for(FIRST), dsp1corpus.steps_for(SECOND))

    def test_every_session_asks_every_question_the_chip_answers(self):
        written = [value for kind, value in dsp1corpus.steps_for(FIRST) if kind == dsp1corpus.WRITE]

        for command, _, _ in dsp1corpus.QUESTIONS:
            self.assertIn(command, written)

    def test_and_builds_all_three_attitude_matrices_first(self):
        written = [value for kind, value in dsp1corpus.steps_for(FIRST) if kind == dsp1corpus.WRITE]

        for command in dsp1corpus.MATRIX_COMMANDS:
            self.assertIn(command, written)


class CorpusTest(unittest.TestCase):
    def test_the_corpus_that_ships_holds_sessions(self):
        self.assertTrue(dsp1corpus.load()["cases"])

    def test_every_case_names_its_seed_and_its_expected_answer(self):
        for case in dsp1corpus.load()["cases"]:
            self.assertIn("seed", case)
            self.assertIn("expected", case)

    def test_the_corpus_says_where_its_answers_came_from(self):
        self.assertIn("reference", dsp1corpus.load())

    def test_a_corpus_can_be_read_from_somewhere_else(self):
        where = Path(tempfile.mkdtemp()) / "other.json"
        where.write_text(json.dumps({"reference": "x", "cases": []}))

        self.assertEqual(dsp1corpus.load(where)["cases"], [])


class ReplayTest(unittest.TestCase):
    def test_replaying_a_session_answers_bytes(self):
        found = dsp1corpus.replay(dsp1corpus.steps_for(FIRST))

        self.assertTrue(all(0 <= value <= 0xFF for value in found))

    def test_the_same_session_replays_the_same_way(self):
        self.assertEqual(
            dsp1corpus.replay(dsp1corpus.steps_for(FIRST)),
            dsp1corpus.replay(dsp1corpus.steps_for(FIRST)),
        )


class ComparisonTest(unittest.TestCase):
    def test_two_identical_answers_report_nothing(self):
        self.assertIsNone(dsp1corpus.disagreement([1, 2], [1, 2]))

    def test_a_byte_that_differs_is_named_with_its_position(self):
        self.assertEqual(dsp1corpus.disagreement([1, 2], [1, 3]), (1, 2, 3))

    def test_an_answer_that_stops_early_is_reported(self):
        self.assertEqual(dsp1corpus.disagreement([1, 2], [1])[0], 1)


class AgainstCorpusTest(unittest.TestCase):
    def test_the_model_reproduces_every_answer_the_reference_gave(self):
        for case in dsp1corpus.load()["cases"]:
            found = dsp1corpus.disagreement(
                dsp1corpus.expected_of(case), dsp1corpus.replay(dsp1corpus.steps_for(case["seed"]))
            )

            self.assertIsNone(found, f"seed {case['seed']}")


class RunTest(unittest.TestCase):
    def test_a_full_run_reports_clean(self):
        self.assertEqual(dsp1corpus.run([]), 0)

    def test_a_corpus_whose_answers_are_wrong_makes_the_run_fail(self):
        where = Path(tempfile.mkdtemp()) / "wrong.json"
        where.write_text(
            json.dumps(
                {"reference": "x", "cases": [{"seed": FIRST, "expected": dsp1corpus.encode([0])}]}
            )
        )

        self.assertEqual(dsp1corpus.run(["--corpus", str(where)]), 1)

    def test_an_option_it_does_not_know_is_refused(self):
        with self.assertRaises(dsp1corpus.Usage):
            dsp1corpus.options(["--nonsense"])

    def test_an_option_with_no_value_is_refused(self):
        with self.assertRaises(dsp1corpus.Usage):
            dsp1corpus.options(["--corpus"])


class EncodingTest(unittest.TestCase):
    def test_an_answer_survives_being_written_down_and_read_back(self):
        self.assertEqual(
            dsp1corpus.expected_of({"expected": dsp1corpus.encode([1, 2, 3])}), [1, 2, 3]
        )


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

        with self.assertRaises(dsp1corpus.Usage):
            dsp1corpus.ask(dsp1corpus.steps_for(FIRST), str(wrong))

    def test_asking_a_driver_returns_what_it_said_past_the_count(self):
        found = dsp1corpus.ask(dsp1corpus.steps_for(FIRST), str(self.answering()))

        self.assertEqual(found, [ord("?")] * 4)

    def test_recording_asks_the_driver_for_every_session(self):
        found = dsp1corpus.record(str(self.answering()), 3)

        self.assertEqual(len(found["cases"]), 3)

    def test_and_says_where_the_answers_came_from(self):
        found = dsp1corpus.record(str(self.answering()), 1)

        self.assertIn("reference", found)

    def test_recording_writes_the_corpus_where_it_was_asked(self):
        where = Path(tempfile.mkdtemp()) / "recorded.json"

        answered = dsp1corpus.run(
            ["--record", "--driver", str(self.answering()), "--corpus", str(where), "--cases", "2"]
        )

        self.assertEqual(answered, 0)
        self.assertEqual(len(json.loads(where.read_text())["cases"]), 2)

    def test_recording_without_a_driver_says_so(self):
        self.assertEqual(dsp1corpus.run(["--record"]), 2)


class ReportLimitTest(unittest.TestCase):
    def test_a_corpus_of_many_wrong_answers_stops_reporting_after_a_handful(self):
        where = Path(tempfile.mkdtemp()) / "wrong.json"
        cases = [{"seed": seed, "expected": dsp1corpus.encode([0])} for seed in range(8)]
        where.write_text(json.dumps({"reference": "x", "cases": cases}))

        self.assertEqual(dsp1corpus.run(["--corpus", str(where)]), 1)


class EntryTest(unittest.TestCase):
    def test_a_run_from_the_command_line_returns_what_the_run_returned(self):
        self.assertEqual(dsp1corpus.main([]), 0)

    def test_an_option_it_does_not_know_is_reported(self):
        self.assertEqual(dsp1corpus.main(["--nonsense"]), 2)


if __name__ == "__main__":
    unittest.main()
