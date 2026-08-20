import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import against_part


class Echo:
    """A stand-in part that hands back whatever it was last written."""

    def __init__(self):
        self.held = 0
        self.given = []

    def write(self, byte):
        self.held = byte
        self.given.append(byte)

    def read(self):
        return self.held


def a_case(part, command, seed, script, answers):
    return {
        "part": part,
        "command": command,
        "seed": seed,
        "script": script,
        "expected": base64.b64encode(bytes(answers)).decode("ascii"),
    }


def a_corpus(cases, gaps=()):
    return {"cases": list(cases), "knownGaps": list(gaps)}


def a_file(held):
    where = Path(tempfile.mkdtemp()) / "made-up.json"
    where.write_text(json.dumps(held))
    return where


SIMPLE = [[against_part.WRITE, 0x02], [against_part.READ, 0]]


class ProfileTest(unittest.TestCase):
    def test_every_part_the_package_models_has_a_profile(self):
        for part in ("dsp1", "dsp1b", "dsp2", "dsp3", "dsp4"):
            self.assertIn(part, against_part.PROFILES, part)

    def test_each_profile_names_commands_the_part_answers(self):
        for name, profile in against_part.PROFILES.items():
            self.assertTrue(profile.commands, name)

    def test_a_command_is_one_byte_wide_unless_the_part_says_otherwise(self):
        self.assertEqual(against_part.PROFILES["dsp3"].command_width, 1)

    def test_and_the_part_that_takes_a_word_says_so(self):
        self.assertEqual(against_part.PROFILES["dsp4"].command_width, 2)

    def test_every_profile_knows_how_much_to_feed_each_command(self):
        for name, profile in against_part.PROFILES.items():
            for command in profile.commands:
                self.assertIsInstance(profile.argument_bytes(command), int, (name, command))

    def test_a_profile_is_named_after_the_part_it_describes(self):
        for name, profile in against_part.PROFILES.items():
            self.assertEqual(profile.part, name)

    def test_an_unknown_part_has_no_profile(self):
        with self.assertRaises(against_part.Unknown):
            against_part.profile_for("nonsense")

    def test_a_known_one_comes_back(self):
        self.assertIs(against_part.profile_for("dsp3"), against_part.PROFILES["dsp3"])


class ScriptTest(unittest.TestCase):
    def test_a_script_opens_with_the_command(self):
        found = against_part.script_for("dsp3", 0x02, seed=0)

        self.assertEqual(found[0], [against_part.WRITE, 0x02])

    def test_a_part_whose_command_is_a_word_writes_both_halves(self):
        found = against_part.script_for("dsp4", 0x0A, seed=0)

        self.assertEqual(found[0], [against_part.WRITE, 0x0A])
        self.assertEqual(found[1], [against_part.WRITE, 0x00])

    def test_every_byte_in_a_script_is_a_byte(self):
        for kind, value in against_part.script_for("dsp1", 0x14, seed=0):
            self.assertTrue(0 <= value <= 0xFF, (kind, value))

    def test_a_script_feeds_what_the_profile_says_the_command_takes(self):
        profile = against_part.profile_for("dsp1")
        found = against_part.script_for("dsp1", 0x14, seed=0)
        writes = sum(1 for kind, _ in found if kind == against_part.WRITE)

        self.assertEqual(writes, profile.command_width + profile.argument_bytes(0x14))

    def test_and_reads_what_the_profile_asks_for(self):
        profile = against_part.profile_for("dsp2")
        found = against_part.script_for("dsp2", 0x01, seed=0)
        reads = sum(1 for kind, _ in found if kind == against_part.READ)

        self.assertEqual(reads, profile.reads_for(0x01))

    def test_a_command_that_answers_more_is_read_more(self):
        profile = against_part.profile_for("dsp2")

        self.assertGreater(profile.reads_for(0x01), profile.reads)

    def test_a_length_a_command_reads_before_its_payload_is_pinned(self):
        self.assertTrue(against_part.profile_for("dsp2").pinned_bytes(0x05))

    def test_and_the_pinned_byte_is_what_the_script_writes(self):
        found = against_part.script_for("dsp2", 0x05, seed=0)
        pinned = against_part.profile_for("dsp2").pinned_bytes(0x05)

        self.assertEqual(found[1][1], pinned[0])

    def test_the_same_seed_gives_the_same_script(self):
        self.assertEqual(
            against_part.script_for("dsp3", 0x02, 7), against_part.script_for("dsp3", 0x02, 7)
        )

    def test_and_a_different_seed_does_not(self):
        self.assertNotEqual(
            against_part.script_for("dsp3", 0x02, 7), against_part.script_for("dsp3", 0x02, 8)
        )


class AnswersTest(unittest.TestCase):
    def test_one_answer_comes_back_per_read(self):
        steps = against_part.script_for("dsp3", 0x02, 0)
        reads = sum(1 for kind, _ in steps if kind == against_part.READ)

        self.assertEqual(len(against_part.answers_of(steps, Echo())), reads)

    def test_every_written_byte_reaches_the_part_in_order(self):
        chip = Echo()

        against_part.answers_of([[against_part.WRITE, 0x11], [against_part.WRITE, 0x22]], chip)

        self.assertEqual(chip.given, [0x11, 0x22])

    def test_what_the_part_says_is_what_comes_back(self):
        steps = [[against_part.WRITE, 0x42], [against_part.READ, 0]]

        self.assertEqual(against_part.answers_of(steps, Echo()), [0x42])


class ReplayTest(unittest.TestCase):
    def test_a_script_replays_through_the_model_of_its_part(self):
        steps = against_part.script_for("dsp3", 0x02, 0)

        self.assertTrue(against_part.replay("dsp3", steps))

    def test_the_same_script_replays_the_same_way_twice(self):
        steps = against_part.script_for("dsp1", 0x14, 0)

        self.assertEqual(against_part.replay("dsp1", steps), against_part.replay("dsp1", steps))

    def test_every_part_can_be_replayed(self):
        for name, profile in against_part.PROFILES.items():
            steps = against_part.script_for(name, profile.commands[0], 0)

            wanted = profile.reads_for(profile.commands[0])

            self.assertEqual(len(against_part.replay(name, steps)), wanted, name)


class RecordTest(unittest.TestCase):
    def test_one_case_per_command_and_seed(self):
        found = against_part.record("dsp3", [0, 1], commands=(0x02, 0x1C), build=lambda _: Echo())

        self.assertEqual(len(found), 4)

    def test_each_case_says_which_part_and_command_it_asked(self):
        found = against_part.record("dsp3", [0], commands=(0x02,), build=lambda _: Echo())

        self.assertEqual(found[0]["part"], "dsp3")
        self.assertEqual(found[0]["command"], 0x02)

    def test_and_carries_the_script_and_the_answers(self):
        found = against_part.record("dsp3", [0], commands=(0x02,), build=lambda _: Echo())

        self.assertTrue(found[0]["script"])
        self.assertTrue(base64.b64decode(found[0]["expected"]))

    def test_a_fresh_part_is_built_for_every_script(self):
        seen = []

        def build(_part):
            chip = Echo()
            seen.append(chip)
            return chip

        against_part.record("dsp3", [0, 1, 2], commands=(0x02,), build=build)

        self.assertEqual(len(seen), 3)


class DifferenceTest(unittest.TestCase):
    def test_a_case_the_model_answers_exactly_has_none(self):
        steps = against_part.script_for("dsp3", 0x02, 0)
        case = a_case("dsp3", 0x02, 0, steps, against_part.replay("dsp3", steps))

        self.assertEqual(against_part.differences(case), ())

    def test_and_one_it_does_not_names_every_index(self):
        case = a_case("dsp3", 0x02, 0, SIMPLE, [0xEE])

        self.assertEqual(against_part.differences(case), (0,))

    def test_an_answer_that_stops_short_counts_as_a_difference(self):
        case = a_case("dsp3", 0x02, 0, SIMPLE, [])

        self.assertEqual(against_part.differences(case), (0,))


class GateTest(unittest.TestCase):
    def _clean(self):
        steps = against_part.script_for("dsp3", 0x02, 0)
        return a_case("dsp3", 0x02, 0, steps, against_part.replay("dsp3", steps))

    def _dirty(self, command=0x02):
        return a_case("dsp3", command, 1, SIMPLE, [0xEE])

    def test_a_corpus_the_model_answers_exactly_measures_nothing(self):
        self.assertEqual(against_part.measured(a_corpus([self._clean()])), {})

    def test_one_it_does_not_is_measured_by_part_command_and_seed(self):
        found = against_part.measured(a_corpus([self._dirty()]))

        self.assertEqual(found, {("dsp3", 0x02, 1): (0,)})

    def test_two_commands_sharing_a_seed_are_kept_apart(self):
        found = against_part.measured(a_corpus([self._dirty(0x02), self._dirty(0x1C)]))

        self.assertEqual(len(found), 2)

    def test_a_gap_that_was_written_down_is_not_drift(self):
        held = a_corpus(
            [self._dirty()],
            gaps=[{"part": "dsp3", "command": 0x02, "seed": 1, "indices": [0], "note": "x"}],
        )

        self.assertEqual(against_part.drifted(held), {})

    def test_one_that_was_not_is_drift(self):
        self.assertTrue(against_part.drifted(a_corpus([self._dirty()])))

    def test_a_gap_that_has_gone_is_also_drift(self):
        held = a_corpus(
            [self._clean()],
            gaps=[{"part": "dsp3", "command": 0x02, "seed": 0, "indices": [0], "note": "x"}],
        )

        self.assertTrue(against_part.drifted(held))


class WithoutTheTableTest(unittest.TestCase):
    """The commands that read out a part's own table, where the table is absent.

    They can only be checked where the image is, so everywhere else they report
    as a refusal rather than as bytes, and the refusal is what gets checked.
    """

    def setUp(self):
        self.real = against_part.table_of
        against_part.table_of = lambda _part: None

    def tearDown(self):
        against_part.table_of = self.real

    def _dump(self):
        return {
            "part": "dsp3",
            "command": against_part.DSP3_DUMP,
            "seed": 0,
            "script": against_part.script_for("dsp3", against_part.DSP3_DUMP, 0),
            "expectedDigest": "0" * 64,
        }

    def test_a_case_kept_as_a_digest_says_it_is_one(self):
        self.assertTrue(against_part.by_digest(self._dump()))

    def test_and_a_case_kept_as_bytes_says_it_is_not(self):
        self.assertFalse(against_part.by_digest(a_case("dsp3", 0x02, 0, SIMPLE, [1])))

    def test_a_model_with_no_table_refuses_rather_than_answering(self):
        self.assertTrue(against_part.refuses(self._dump()))

    def test_the_refusal_is_what_is_checked_when_no_table_is_here(self):
        self.assertEqual(against_part.differences(self._dump()), ())

    def test_a_model_that_answered_instead_would_be_a_difference(self):
        case = a_case("dsp3", 0x02, 0, SIMPLE, [1])

        self.assertFalse(against_part.refuses(case))

    def test_it_is_counted_as_a_refusal_rather_than_as_matching_bytes(self):
        found = against_part.refusals({"cases": [self._dump()]})

        self.assertEqual(found, {"dsp3": 1})

    def test_and_still_counts_toward_what_was_compared(self):
        self.assertEqual(against_part.per_part({"cases": [self._dump()]}), {"dsp3": (1, 0)})

    def test_the_report_says_the_refusal_is_what_was_checked(self):
        lines = " ".join(against_part.lines_for({"cases": [self._dump()]}))

        self.assertIn("refuses", lines)

    def test_a_table_that_is_not_here_answers_nothing(self):
        self.assertIsNone(against_part.table_of("dsp3"))


class TableTest(unittest.TestCase):
    """Reading a part's table out of an image, using one that belongs to nobody."""

    def _catalogue(self, part="dsp3", words=64):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "processor"))
        from upd7725 import firmware

        where = Path(tempfile.mkdtemp()) / "made-up.bin"
        where.write_bytes(bytes(words * 3) + bytes(range(0, 256)) * 4)
        return {part: (firmware.Identity(part, "upd7725", "MADE UP", words, 512), where)}

    def test_a_part_no_image_names_has_no_table(self):
        self.assertIsNone(against_part.table_of("nonsense"))

    def test_a_catalogue_can_be_handed_in_rather_than_searched_for(self):
        self.assertIsNone(against_part.table_of("dsp3", held={}))

    def test_an_image_that_is_there_is_read_as_words(self):
        found = against_part.table_of("dsp3", held=self._catalogue())

        self.assertTrue(found)
        self.assertTrue(all(0 <= word <= 0xFFFF for word in found))

    def test_the_table_starts_after_the_program(self):
        found = against_part.table_of("dsp3", held=self._catalogue(words=64))

        self.assertEqual(found[0], 0x0001)

    def test_and_reads_two_bytes_per_word(self):
        found = against_part.table_of("dsp3", held=self._catalogue(words=64))

        self.assertEqual(found[1], 0x0203)

    def test_a_dump_case_is_checked_when_a_table_is_handed_in(self):
        case = {
            "part": "dsp3",
            "command": against_part.DSP3_DUMP,
            "seed": 0,
            "script": against_part.script_for("dsp3", against_part.DSP3_DUMP, 0),
            "expectedDigest": "0" * 64,
        }

        self.assertEqual(against_part.differences(case, table=[0] * 2048), (0,))

    def test_and_agrees_when_the_digest_is_the_one_it_produces(self):
        script = against_part.script_for("dsp3", against_part.DSP3_DUMP, 0)
        table = [0] * 2048
        said = against_part.replay("dsp3", script, against_part.DSP3_DUMP, table)
        case = {
            "part": "dsp3",
            "command": against_part.DSP3_DUMP,
            "seed": 0,
            "script": script,
            "expectedDigest": against_part.digest_of(said),
        }

        self.assertEqual(against_part.differences(case, table=table), ())

    def test_a_case_with_a_table_is_compared_by_digest_rather_than_refused(self):
        script = against_part.script_for("dsp3", against_part.DSP3_DUMP, 0)
        table = [0] * 2048
        case = {
            "part": "dsp3",
            "command": against_part.DSP3_DUMP,
            "seed": 0,
            "script": script,
            "expectedDigest": "0" * 64,
        }

        self.assertFalse(against_part.refuses(case, table))
        self.assertEqual(against_part.differences(case, table=table), (0,))


class DigestTest(unittest.TestCase):
    def test_two_identical_answers_share_a_digest(self):
        self.assertEqual(against_part.digest_of([1, 2, 3]), against_part.digest_of([1, 2, 3]))

    def test_and_two_different_ones_do_not(self):
        self.assertNotEqual(against_part.digest_of([1, 2, 3]), against_part.digest_of([1, 2, 4]))

    def test_a_digest_is_one_value_rather_than_one_per_word(self):
        self.assertEqual(len(against_part.digest_of(list(range(64)))), 64)

    def test_a_dump_command_is_recognised_as_one(self):
        self.assertTrue(against_part.profile_for("dsp3").dumps_rom(against_part.DSP3_DUMP))

    def test_and_an_ordinary_command_is_not(self):
        self.assertFalse(against_part.profile_for("dsp3").dumps_rom(0x02))

    def test_every_part_that_can_read_out_its_table_says_which_commands_do(self):
        self.assertTrue(against_part.profile_for("dsp1").dumps)

    def test_a_profile_prints_as_the_part_and_how_many_commands_it_has(self):
        printed = repr(against_part.profile_for("dsp3"))

        self.assertIn("dsp3", printed)


class ShippedTest(unittest.TestCase):
    def test_the_corpus_that_ships_covers_every_part(self):
        held = against_part.load()
        found = {case["part"] for case in held["cases"]}

        self.assertEqual(found, set(against_part.PROFILES))

    def test_it_was_recorded_from_the_parts_themselves(self):
        self.assertIn("microcode", against_part.load()["recordedFrom"])

    def test_the_model_answers_what_the_parts_answered_except_where_recorded(self):
        self.assertEqual(against_part.drifted(against_part.load()), {})

    def test_every_recorded_gap_says_what_it_is(self):
        for one in against_part.load().get("knownGaps", ()):
            self.assertTrue(one.get("note"), one)

    def test_no_two_cases_ask_the_same_thing(self):
        held = [
            (case["part"], case["command"], case["seed"]) for case in against_part.load()["cases"]
        ]

        self.assertEqual(len(held), len(set(held)))


class ReportTest(unittest.TestCase):
    def test_a_clean_corpus_says_nothing_has_drifted(self):
        held = a_corpus([GateTest()._clean()])

        self.assertIn("nothing has drifted", " ".join(against_part.lines_for(held)))

    def test_a_drifted_one_names_what_moved(self):
        held = a_corpus([a_case("dsp3", 0x1C, 7, SIMPLE, [0xEE])])

        self.assertIn("0x1c", " ".join(against_part.lines_for(held)))

    def test_the_report_says_how_much_was_compared(self):
        self.assertIn("bytes", " ".join(against_part.lines_for(against_part.load())))

    def test_it_names_every_part_it_covered(self):
        lines = " ".join(against_part.lines_for(against_part.load()))

        for part in against_part.PROFILES:
            self.assertIn(part, lines)

    def test_a_long_list_of_drift_is_cut_short(self):
        held = a_corpus([a_case("dsp3", 0x02, seed, SIMPLE, [0xEE]) for seed in range(20)])

        self.assertLessEqual(
            len(against_part.lines_for(held)),
            against_part.REPORT_LIMIT + len(against_part.PROFILES) + 4,
        )


class EntryTest(unittest.TestCase):
    def test_a_clean_corpus_reports_success(self):
        where = a_file(a_corpus([GateTest()._clean()]))

        self.assertEqual(against_part.main([str(where)]), 0)

    def test_a_drifted_one_reports_failure(self):
        where = a_file(a_corpus([a_case("dsp3", 0x02, 0, SIMPLE, [0xEE])]))

        self.assertEqual(against_part.main([str(where)]), 1)

    def test_a_run_with_no_argument_reads_the_one_that_ships(self):
        self.assertEqual(against_part.main([]), 0)


if __name__ == "__main__":
    unittest.main()
