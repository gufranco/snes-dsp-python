import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import answers


class Complaint(Exception):
    pass


class Puppet:
    """A part that answers by counting, so a corpus can be checked without one."""

    def __init__(self, first: int = 0x10) -> None:
        self.next = first
        self.written: list[int] = []

    def write(self, value: int) -> None:
        self.written.append(value)

    def read(self) -> int:
        self.next = (self.next + 1) & 0xFF
        return self.next

    def read_status(self) -> int:
        return 0x80


def puppets(first: int = 0x10) -> Any:
    def build(_part: str) -> Any:
        return Puppet(first)

    return build


def a_digest(_part: str) -> str:
    """A digest that names no real image.

    Every test supplies one. Reaching for the digest of a file on disk would make
    the test pass on a machine holding that file and fail on one that does not,
    which is not a test of anything in this module.
    """
    return "abc123"


def a_shape(shape: str = "write1 read1", seen: int = 3, cartridges: int = 1) -> dict[str, Any]:
    return {"shape": shape, "seen": seen, "cartridges": cartridges}


def some_shapes(*held: Any) -> list[dict[str, Any]]:
    return list(held) or [a_shape()]


class TakingTest(unittest.TestCase):
    """What a part said, taken in a form that can be written down and compared."""

    def test_every_exchange_is_recorded_under_its_shape(self) -> None:
        found = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(found["exchanges"][0]["shape"], "write1 read1")

    def test_and_what_came_back_is_recorded_as_hex(self) -> None:
        found = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(found["exchanges"][0]["said"], ["11"])

    def test_a_two_byte_read_is_one_run_of_two_bytes(self) -> None:
        found = answers.take(
            "dsp1", puppets(), shapes=some_shapes(a_shape("write1 read2")), digest=a_digest
        )

        self.assertEqual(found["exchanges"][0]["said"], ["1112"])

    def test_a_poll_is_recorded_beside_the_reads(self) -> None:
        found = answers.take(
            "dsp1", puppets(), shapes=some_shapes(a_shape("write1 poll1 read1")), digest=a_digest
        )

        self.assertEqual(found["exchanges"][0]["said"], ["80", "11"])

    def test_the_seed_the_payloads_came_from_is_recorded(self) -> None:
        found = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest, seed=1234)

        self.assertEqual(found["seed"], 1234)

    def test_and_the_part_it_was_taken_from(self) -> None:
        self.assertEqual(
            answers.take("dsp2", puppets(), shapes=some_shapes(), digest=a_digest)["part"], "dsp2"
        )

    def test_the_digest_of_the_image_that_answered_is_recorded(self) -> None:
        found = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(found["image"]["sha256"], "abc123")

    def test_a_shape_that_reads_nothing_is_left_out(self) -> None:
        found = answers.take(
            "dsp1", puppets(), shapes=some_shapes(a_shape("write1 write1")), digest=a_digest
        )

        self.assertEqual(found["exchanges"], [])

    def test_and_so_is_one_that_writes_nothing(self) -> None:
        found = answers.take(
            "dsp1", puppets(), shapes=some_shapes(a_shape("read1 read1")), digest=a_digest
        )

        self.assertEqual(found["exchanges"], [])

    def test_the_same_seed_takes_the_same_answers_twice(self) -> None:
        first = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)
        second = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(first, second)

    def test_and_a_part_that_answers_differently_is_recorded_differently(self) -> None:
        first = answers.take("dsp1", puppets(first=0x10), shapes=some_shapes(), digest=a_digest)
        second = answers.take("dsp1", puppets(first=0x20), shapes=some_shapes(), digest=a_digest)

        self.assertNotEqual(first["exchanges"], second["exchanges"])


class FamilyTest(unittest.TestCase):
    """Which part's shapes drive another, and why that is what finds a divergence."""

    def test_a_part_with_its_own_shapes_uses_them(self) -> None:
        self.assertEqual(answers.shapes_named("dsp2"), "dsp2")

    def test_the_die_shrink_is_driven_by_the_part_it_shrank(self) -> None:
        self.assertEqual(answers.shapes_named("dsp1a"), "dsp1")

    def test_and_so_is_the_later_mask(self) -> None:
        self.assertEqual(answers.shapes_named("dsp1b"), "dsp1")

    def test_every_part_that_shares_shapes_is_a_part_this_covers(self) -> None:
        from snesdsp import models

        for part, like in answers.DRIVEN_LIKE.items():
            self.assertIn(part, models.MODELS)
            self.assertIn(like, models.MODELS)

    def test_a_part_reads_the_shapes_of_whoever_drives_it(self) -> None:
        found = answers._default_shapes("dsp1a")
        wanted = answers._default_shapes("dsp1")

        self.assertEqual(found, wanted)

    def test_and_a_part_with_no_shapes_recorded_reads_none(self) -> None:
        original = answers.ROOT
        answers.ROOT = Path(tempfile.mkdtemp())
        self.addCleanup(setattr, answers, "ROOT", original)

        self.assertEqual(answers._default_shapes("dsp1"), [])


class CheckingTest(unittest.TestCase):
    """A corpus against the part on this machine, which is the whole point."""

    def _corpus(self, **held: Any) -> dict[str, Any]:
        found = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)
        found.update(held)
        return found

    def test_a_part_that_answers_what_was_recorded_agrees(self) -> None:
        found = answers.check(self._corpus(), puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(found.disagreements, ())
        self.assertTrue(found.agrees)

    def test_a_part_that_answers_otherwise_disagrees(self) -> None:
        found = answers.check(
            self._corpus(),
            puppets(first=0x20),
            shapes=some_shapes(),
            digest=a_digest,
        )

        self.assertFalse(found.agrees)
        self.assertEqual(len(found.disagreements), 1)

    def test_and_the_disagreement_carries_both_answers(self) -> None:
        found = answers.check(
            self._corpus(),
            puppets(first=0x20),
            shapes=some_shapes(),
            digest=a_digest,
        )

        shape, wanted, got = found.disagreements[0]
        self.assertEqual(shape, "write1 read1")
        self.assertEqual(wanted, ["11"])
        self.assertEqual(got, ["21"])

    def test_a_corpus_taken_from_another_image_is_refused_rather_than_compared(self) -> None:
        with self.assertRaises(answers.WrongImage) as raised:
            answers.check(
                self._corpus(),
                puppets(),
                shapes=some_shapes(),
                digest=lambda _part: "something else",
            )

        self.assertIn("abc123", str(raised.exception))

    def test_and_the_refusal_says_what_this_machine_holds(self) -> None:
        with self.assertRaises(answers.WrongImage) as raised:
            answers.check(
                self._corpus(),
                puppets(),
                shapes=some_shapes(),
                digest=lambda _part: "something else",
            )

        self.assertIn("something else", str(raised.exception))

    def test_a_shape_the_corpus_does_not_carry_is_reported_as_unrecorded(self) -> None:
        found = answers.check(
            self._corpus(),
            puppets(),
            shapes=some_shapes(a_shape(), a_shape("write1 write1 read1")),
            digest=a_digest,
        )

        self.assertEqual(found.unrecorded, ("write1 write1 read1",))

    def test_and_a_shape_the_corpus_carries_that_is_gone_is_reported_too(self) -> None:
        corpus = self._corpus()
        corpus["exchanges"].append({"shape": "write1 read2", "said": ["1112"]})

        found = answers.check(corpus, puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(found.vanished, ("write1 read2",))

    def test_an_unrecorded_shape_is_not_a_disagreement(self) -> None:
        found = answers.check(
            self._corpus(),
            puppets(),
            shapes=some_shapes(a_shape(), a_shape("write1 write1 read1")),
            digest=a_digest,
        )

        self.assertTrue(found.agrees)

    def test_but_a_vanished_one_is_not_agreement_either(self) -> None:
        corpus = self._corpus()
        corpus["exchanges"].append({"shape": "write1 read2", "said": ["1112"]})

        found = answers.check(corpus, puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertFalse(found.agrees)

    def test_the_seed_the_corpus_names_is_the_seed_the_check_uses(self) -> None:
        corpus = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest, seed=99)
        asked: list[int] = []

        def noting(seed: int) -> random.Random:
            asked.append(seed)
            return random.Random(seed)

        answers.check(
            corpus,
            puppets(),
            shapes=some_shapes(),
            digest=a_digest,
            rolls=noting,
        )

        self.assertEqual(asked, [99])


class StoringTest(unittest.TestCase):
    def test_a_corpus_is_written_where_the_part_names(self) -> None:
        where = Path(tempfile.mkdtemp())

        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)

        self.assertTrue((where / "dsp1answers.json").exists())

    def test_and_reads_back_as_what_was_written(self) -> None:
        where = Path(tempfile.mkdtemp())
        taken = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        answers.store(taken, where)

        self.assertEqual(answers.load("dsp1", where), taken)

    def test_a_part_with_no_corpus_reads_back_as_nothing(self) -> None:
        self.assertIsNone(answers.load("dsp1", Path(tempfile.mkdtemp())))

    def test_a_corpus_holding_another_part_is_refused(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "dsp1answers.json").write_text(json.dumps({"part": "dsp2", "exchanges": []}))

        with self.assertRaises(answers.Malformed):
            answers.load("dsp1", where)

    def test_an_exchange_carries_the_shape_and_the_answer_and_nothing_else(self) -> None:
        taken = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertEqual(sorted(taken["exchanges"][0]), ["said", "shape"])

    def test_so_the_payload_that_was_sent_is_not_stored(self) -> None:
        taken = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)

        self.assertNotIn("payload", json.dumps(taken["exchanges"]))
        self.assertNotIn("wrote", json.dumps(taken["exchanges"]))

    def test_and_the_seed_is_enough_to_send_it_again(self) -> None:
        first = answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest)
        second = answers.take(
            "dsp1", puppets(), shapes=some_shapes(), digest=a_digest, seed=first["seed"]
        )

        self.assertEqual(first["exchanges"], second["exchanges"])


class ReportTest(unittest.TestCase):
    def _found(self, **held: Any) -> Any:
        return answers.Checked(
            **{
                "part": "dsp1",
                "disagreements": (),
                "unrecorded": (),
                "vanished": (),
                "checked": 3,
                **held,
            }
        )

    def test_a_run_that_agrees_says_how_much_it_checked(self) -> None:
        self.assertIn("3", " ".join(answers.lines_for(self._found())))

    def test_a_disagreement_names_the_shape_and_both_answers(self) -> None:
        lines = answers.lines_for(self._found(disagreements=(("write1 read1", ["11"], ["21"]),)))

        text = " ".join(lines)
        self.assertIn("write1 read1", text)
        self.assertIn("11", text)
        self.assertIn("21", text)

    def test_an_unrecorded_shape_is_named_as_something_to_take(self) -> None:
        lines = answers.lines_for(self._found(unrecorded=("write1 read2",)))

        self.assertIn("write1 read2", " ".join(lines))

    def test_and_a_vanished_one_as_something_that_used_to_be_there(self) -> None:
        lines = answers.lines_for(self._found(vanished=("write1 read2",)))

        self.assertIn("no longer", " ".join(lines))


class PrintingTest(unittest.TestCase):
    def test_a_comparison_prints_as_what_it_found(self) -> None:
        found = answers.Checked(
            part="dsp1", disagreements=(("x", ["a"], ["b"]),), unrecorded=(), vanished=(), checked=4
        )

        self.assertIn("dsp1", repr(found))
        self.assertIn("4 exchanges", repr(found))
        self.assertIn("1 wrong", repr(found))


class EntryTest(unittest.TestCase):
    def test_a_machine_with_no_microcode_says_so_rather_than_passing(self) -> None:
        said: list[str] = []

        code = answers.main([], why_not=lambda: "no image is here", say=said.append)

        self.assertEqual(code, 2)
        self.assertIn("nothing to run", " ".join(said))

    def test_taking_a_corpus_writes_one_and_reports_it(self) -> None:
        where = Path(tempfile.mkdtemp())
        said: list[str] = []

        code = answers.main(
            ["--take", "dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            say=said.append,
        )

        self.assertEqual(code, 0)
        self.assertTrue((where / "dsp1answers.json").exists())
        self.assertIn("wrote", " ".join(said))

    def test_a_part_with_no_corpus_yet_is_reported_rather_than_passed(self) -> None:
        said: list[str] = []

        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=Path(tempfile.mkdtemp()),
            say=said.append,
        )

        self.assertEqual(code, 1)
        self.assertIn("no answers are recorded", " ".join(said))

    def test_a_run_that_agrees_passes(self) -> None:
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)

        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            say=lambda _l: None,
        )

        self.assertEqual(code, 0)

    def test_and_one_that_disagrees_fails(self) -> None:
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)
        said: list[str] = []

        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(first=0x30),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            say=said.append,
        )

        self.assertEqual(code, 1)
        self.assertIn("write1 read1", " ".join(said))

    def test_a_corpus_from_another_image_stops_the_run_rather_than_failing_it(self) -> None:
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)
        said: list[str] = []

        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=lambda _part: "something else",
            where=where,
            say=said.append,
        )

        self.assertEqual(code, 2)
        self.assertIn("image", " ".join(said))

    def test_with_no_part_named_every_part_is_checked(self) -> None:
        where = Path(tempfile.mkdtemp())
        for part in ("dsp1", "dsp2"):
            answers.store(
                answers.take(part, puppets(), shapes=some_shapes(), digest=a_digest), where
            )
        said: list[str] = []

        answers.main(
            [],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            parts=("dsp1", "dsp2"),
            say=said.append,
        )

        text = " ".join(said)
        self.assertIn("dsp1", text)
        self.assertIn("dsp2", text)


if __name__ == "__main__":
    unittest.main()
