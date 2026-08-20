import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dsp3corpus

STEPS = [[dsp3corpus.WRITE, 0x02], [dsp3corpus.READ, 0]]


def a_corpus(cases, gaps=()):
    return {"part": "dsp3", "cases": list(cases), "knownGaps": list(gaps)}


def a_case(seed, script, answers, command=0x02):
    return {
        "seed": seed,
        "command": command,
        "script": script,
        "expected": base64.b64encode(bytes(answers)).decode("ascii"),
    }


def a_file(held):
    where = Path(tempfile.mkdtemp()) / "made-up.json"
    where.write_text(json.dumps(held))
    return where


def clean(seed=0):
    return a_case(seed, STEPS, dsp3corpus.replay(STEPS))


def dirty(seed=1):
    return a_case(seed, STEPS, [0xEE])


class LoadTest(unittest.TestCase):
    def test_the_corpus_that_ships_has_cases_in_it(self):
        self.assertTrue(dsp3corpus.load()["cases"])

    def test_it_says_which_part_it_describes(self):
        self.assertEqual(dsp3corpus.load()["part"], "dsp3")

    def test_and_that_the_answers_came_from_the_part(self):
        self.assertIn("microcode", dsp3corpus.load()["recordedFrom"])

    def test_a_corpus_can_be_read_from_somewhere_else(self):
        where = a_file(a_corpus([clean()]))

        self.assertEqual(len(dsp3corpus.load(where)["cases"]), 1)

    def test_every_case_carries_the_script_it_was_asked(self):
        for case in dsp3corpus.load()["cases"]:
            self.assertTrue(case["script"], case["seed"])

    def test_and_the_answers_that_came_back(self):
        for case in dsp3corpus.load()["cases"]:
            self.assertTrue(dsp3corpus.expected_of(case), case["seed"])

    def test_no_two_cases_ask_the_same_command_with_the_same_seed(self):
        held = [(case["seed"], case["command"]) for case in dsp3corpus.load()["cases"]]

        self.assertEqual(len(held), len(set(held)))

    def test_every_command_the_part_has_is_covered(self):
        found = {case["command"] for case in dsp3corpus.load()["cases"]}

        self.assertGreaterEqual(len(found), 12)


class ReplayTest(unittest.TestCase):
    def test_a_script_that_only_writes_produces_no_answers(self):
        self.assertEqual(dsp3corpus.replay([[dsp3corpus.WRITE, 0x02]]), [])

    def test_one_answer_comes_back_per_read(self):
        steps = [[dsp3corpus.WRITE, 0x02], [dsp3corpus.READ, 0], [dsp3corpus.READ, 0]]

        self.assertEqual(len(dsp3corpus.replay(steps)), 2)

    def test_every_answer_is_a_byte(self):
        steps = [[dsp3corpus.WRITE, 0x02]] + [[dsp3corpus.READ, 0]] * 4

        for value in dsp3corpus.replay(steps):
            self.assertTrue(0 <= value <= 0xFF)

    def test_a_script_replays_the_same_way_every_time(self):
        steps = dsp3corpus.load()["cases"][0]["script"]

        self.assertEqual(dsp3corpus.replay(steps), dsp3corpus.replay(steps))


class DisagreementTest(unittest.TestCase):
    def test_two_identical_answers_do_not_disagree(self):
        self.assertIsNone(dsp3corpus.disagreement([1, 2, 3], [1, 2, 3]))

    def test_the_first_byte_that_differs_is_named(self):
        self.assertEqual(dsp3corpus.disagreement([1, 2, 3], [1, 9, 3]), (1, 2, 9))

    def test_an_answer_that_stops_early_disagrees_where_it_stopped(self):
        self.assertEqual(dsp3corpus.disagreement([1, 2], [1]), (1, 2, None))

    def test_and_one_that_runs_long_disagrees_where_it_carried_on(self):
        self.assertEqual(dsp3corpus.disagreement([1], [1, 2]), (1, None, 2))


class DifferencesTest(unittest.TestCase):
    def test_a_case_the_model_answers_exactly_has_none(self):
        self.assertEqual(dsp3corpus.differences(clean()), ())

    def test_and_one_it_does_not_names_every_index(self):
        steps = [[dsp3corpus.WRITE, 0x02], [dsp3corpus.READ, 0], [dsp3corpus.READ, 0]]

        self.assertEqual(dsp3corpus.differences(a_case(0, steps, [0xEE, 0xEE])), (0, 1))

    def test_an_answer_shorter_than_the_reads_counts_as_a_difference(self):
        self.assertEqual(dsp3corpus.differences(a_case(0, STEPS, [])), (0,))


class GapTest(unittest.TestCase):
    def test_a_corpus_the_model_answers_exactly_measures_nothing(self):
        self.assertEqual(dsp3corpus.measured(a_corpus([clean()])), {})

    def test_a_case_it_does_not_is_measured(self):
        self.assertEqual(dsp3corpus.measured(a_corpus([dirty()])), {(1, 0x02): (0,)})

    def test_what_the_file_wrote_down_is_read_back(self):
        held = a_corpus([clean()], gaps=[{"seed": 1, "command": 0x02, "indices": [0], "note": "x"}])

        self.assertEqual(dsp3corpus.recorded(held), {(1, 0x02): (0,)})

    def test_a_gap_that_was_written_down_is_not_drift(self):
        held = a_corpus([dirty()], gaps=[{"seed": 1, "command": 0x02, "indices": [0], "note": "x"}])

        self.assertEqual(dsp3corpus.drifted(held), {})

    def test_a_gap_that_was_not_written_down_is_drift(self):
        self.assertEqual(dsp3corpus.drifted(a_corpus([dirty()])), {(1, 0x02): ((), (0,))})

    def test_a_gap_written_down_that_has_gone_is_also_drift(self):
        held = a_corpus([clean()], gaps=[{"seed": 0, "command": 0x02, "indices": [0], "note": "x"}])

        self.assertEqual(dsp3corpus.drifted(held), {(0, 0x02): ((0,), ())})

    def test_a_gap_that_moved_is_drift(self):
        held = a_corpus([dirty()], gaps=[{"seed": 1, "command": 0x02, "indices": [3], "note": "x"}])

        self.assertEqual(dsp3corpus.drifted(held), {(1, 0x02): ((3,), (0,))})


class ShippedCorpusTest(unittest.TestCase):
    def test_the_model_answers_what_the_part_answered_except_where_recorded(self):
        self.assertEqual(dsp3corpus.drifted(dsp3corpus.load()), {})

    def test_every_recorded_gap_names_the_command_behind_it(self):
        for one in dsp3corpus.load().get("knownGaps", ()):
            self.assertTrue(one.get("note"), one["seed"])


class ReportTest(unittest.TestCase):
    def test_a_clean_corpus_says_nothing_has_drifted(self):
        held = a_corpus([clean()])

        self.assertIn("nothing has drifted", " ".join(dsp3corpus.lines_for(held)))

    def test_a_drifted_one_names_the_sessions(self):
        held = a_corpus([a_case(7, STEPS, [0xEE])])

        self.assertIn("seed 7", " ".join(dsp3corpus.lines_for(held)))

    def test_the_report_says_how_much_was_compared(self):
        self.assertIn("bytes compared", " ".join(dsp3corpus.lines_for(dsp3corpus.load())))

    def test_a_long_list_of_drift_is_cut_short(self):
        held = a_corpus([a_case(seed, STEPS, [0xEE]) for seed in range(20)])

        self.assertLessEqual(len(dsp3corpus.lines_for(held)), dsp3corpus.REPORT_LIMIT + 3)


class EntryTest(unittest.TestCase):
    def test_a_clean_corpus_reports_success(self):
        where = a_file(a_corpus([clean()]))

        self.assertEqual(dsp3corpus.main([str(where)]), 0)

    def test_a_drifted_one_reports_failure(self):
        where = a_file(a_corpus([a_case(0, STEPS, [0xEE])]))

        self.assertEqual(dsp3corpus.main([str(where)]), 1)

    def test_a_run_with_no_argument_reads_the_one_that_ships(self):
        self.assertEqual(dsp3corpus.main([]), 0)


if __name__ == "__main__":
    unittest.main()
