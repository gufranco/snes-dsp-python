import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import against_part
import record_parts


class Echo:
    """A stand-in part that hands back whatever it was last written."""

    def __init__(self):
        self.held = 0

    def write(self, byte):
        self.held = byte

    def read(self):
        return self.held


def quiet(_message):
    return None


def build(_part):
    return Echo()


class RecordAllTest(unittest.TestCase):
    def test_every_part_is_asked(self):
        cases = record_parts.record_all([0], build=build, say=quiet)

        self.assertEqual({case["part"] for case in cases}, set(against_part.PROFILES))

    def test_a_narrower_list_asks_only_those(self):
        cases = record_parts.record_all([0], parts=("dsp3",), build=build, say=quiet)

        self.assertEqual({case["part"] for case in cases}, {"dsp3"})

    def test_every_command_of_a_part_is_asked(self):
        cases = record_parts.record_all([0], parts=("dsp3",), build=build, say=quiet)

        self.assertEqual(
            sorted({case["command"] for case in cases}),
            sorted(against_part.PROFILES["dsp3"].commands),
        )

    def test_one_case_per_seed(self):
        cases = record_parts.record_all([0, 1, 2], parts=("dsp3",), build=build, say=quiet)

        self.assertEqual({case["seed"] for case in cases}, {0, 1, 2})

    def test_the_progress_is_reported_as_it_goes(self):
        said = []

        record_parts.record_all([0], parts=("dsp3",), build=build, say=said.append)

        self.assertTrue(any("dsp3" in line for line in said))


class GapsTest(unittest.TestCase):
    def test_a_recording_the_models_reproduce_has_no_gaps(self):
        cases = [
            {
                "part": "dsp3",
                "command": 0x02,
                "seed": 0,
                "script": against_part.script_for("dsp3", 0x02, 0),
                "expected": "",
            }
        ]
        cases[0]["expected"] = _encoded(against_part.replay("dsp3", cases[0]["script"]))

        self.assertEqual(record_parts.gaps_of(cases), [])

    def test_one_they_do_not_is_written_down_with_its_indices(self):
        cases = record_parts.record_all([0], parts=("dsp3",), build=build, say=quiet)

        found = record_parts.gaps_of(cases)

        self.assertTrue(found)
        self.assertTrue(all(one["indices"] for one in found))

    def test_every_gap_names_its_part_and_command(self):
        cases = record_parts.record_all([0], parts=("dsp3",), build=build, say=quiet)

        for one in record_parts.gaps_of(cases):
            self.assertEqual(one["part"], "dsp3")
            self.assertIn(f"{one['command']:#04x}", one["note"])


class WriteOutTest(unittest.TestCase):
    def _written(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"
        record_parts.write_out(where, [0], build=build, say=quiet)
        return json.loads(where.read_text())

    def test_the_file_says_where_its_answers_came_from(self):
        self.assertIn("microcode", self._written()["recordedFrom"])

    def test_it_carries_a_case_for_every_part(self):
        held = self._written()

        self.assertEqual({case["part"] for case in held["cases"]}, set(against_part.PROFILES))

    def test_and_the_gaps_it_measured_while_recording(self):
        self.assertIn("knownGaps", self._written())

    def test_a_corpus_it_writes_is_one_the_gate_accepts(self):
        held = self._written()

        self.assertEqual(against_part.drifted(held), {})


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_microcode_records_nothing(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        found = record_parts.main([str(where)], why_not=lambda: "no image", say=quiet)

        self.assertEqual(found, 2)
        self.assertFalse(where.exists())

    def test_a_run_says_the_file_still_needs_formatting(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"
        said = []

        record_parts.main([str(where), "1"], why_not=lambda: None, build=build, say=said.append)

        self.assertTrue(any("format" in line for line in said))

    def test_a_run_with_one_writes_the_corpus(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        found = record_parts.main([str(where), "1"], why_not=lambda: None, build=build, say=quiet)

        self.assertEqual(found, 0)
        self.assertTrue(where.exists())

    def test_a_seed_count_that_is_not_a_number_is_refused(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        with self.assertRaises(record_parts.Usage):
            record_parts.main([str(where), "many"], why_not=lambda: None, build=build, say=quiet)

    def test_a_run_with_no_arguments_is_refused(self):
        with self.assertRaises(record_parts.Usage):
            record_parts.main([], why_not=lambda: None, build=build, say=quiet)

    def test_the_default_seed_count_is_used_when_none_is_given(self):
        where = Path(tempfile.mkdtemp()) / "made-up.json"

        record_parts.main([str(where)], why_not=lambda: None, build=build, say=quiet)

        held = json.loads(where.read_text())
        seeds = {case["seed"] for case in held["cases"]}
        self.assertEqual(len(seeds), against_part.DEFAULT_SEEDS)


def _encoded(answers):
    import base64

    return base64.b64encode(bytes(answers)).decode("ascii")


if __name__ == "__main__":
    unittest.main()
