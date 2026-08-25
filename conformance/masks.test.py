import sys
import tempfile
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance import masks


def loaded(where: Path) -> dict[str, Any]:
    """What was pinned there, insisting that something was.

    A store that wrote nothing reads back as None, and indexing that would fail
    somewhere further down with a message about the wrong thing.
    """
    held = masks.load(where)
    assert held is not None, f"nothing was written to {where}"
    return held


def a_finding(
    command: int = 0x04,
    args: Sequence[int] = (0x1234,),
    first: str = "11" * 8,
    second: str = "22" * 8,
    at: int = 0,
) -> dict[str, Any]:
    return {
        "command": command,
        "arguments": list(args),
        "answers": {"dsp1": first, "dsp1b": second},
        "firstDifferingByte": at,
    }


class SweepTest(unittest.TestCase):
    """Searching for arguments where two masks of one part disagree."""

    def _build(self, differ_on: int | None = None) -> Any:
        def build(part: str) -> Any:
            return _Fixed(part, differ_on)

        return build

    def test_two_masks_that_answer_alike_have_no_divergence(self) -> None:
        found = masks.sweep(self._build(), commands=(0x04,), arguments=((0x01,),))

        self.assertEqual(found, [])

    def test_a_command_where_they_disagree_is_found(self) -> None:
        found = masks.sweep(self._build(differ_on=0x04), commands=(0x04,), arguments=((0x01,),))

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["command"], 0x04)

    def test_and_carries_the_arguments_that_produced_it(self) -> None:
        found = masks.sweep(
            self._build(differ_on=0x04), commands=(0x04,), arguments=((0x1234, 0x5678),)
        )

        self.assertEqual(found[0]["arguments"], [0x1234, 0x5678])

    def test_and_what_each_mask_answered(self) -> None:
        found = masks.sweep(self._build(differ_on=0x04), commands=(0x04,), arguments=((0x01,),))

        self.assertNotEqual(found[0]["answers"]["dsp1"], found[0]["answers"]["dsp1b"])

    def test_and_where_the_two_answers_first_part_company(self) -> None:
        found = masks.sweep(self._build(differ_on=0x04), commands=(0x04,), arguments=((0x01,),))

        self.assertEqual(found[0]["firstDifferingByte"], 0)

    def test_a_command_that_agrees_is_not_reported_beside_one_that_does_not(self) -> None:
        found = masks.sweep(
            self._build(differ_on=0x04), commands=(0x03, 0x04), arguments=((0x01,),)
        )

        self.assertEqual([one["command"] for one in found], [0x04])

    def test_the_sweep_reads_as_many_bytes_as_it_was_told_to(self) -> None:
        found = masks.sweep(
            self._build(differ_on=0x04), commands=(0x04,), arguments=((0x01,),), reads=4
        )

        self.assertEqual(len(found[0]["answers"]["dsp1"]), 8)


class _Fixed:
    """A part whose answers depend on which mask it is, for one chosen command."""

    def __init__(self, part: str, differ_on: int | None) -> None:
        self.part = part
        self.differ_on = differ_on
        self.written: list[int] = []

    def write(self, value: int) -> None:
        self.written.append(value)

    def read(self) -> int:
        if self.differ_on is not None and self.written and self.written[0] == self.differ_on:
            return 0x11 if self.part == "dsp1" else 0x22
        return 0x33


class CheckTest(unittest.TestCase):
    """A pinned divergence against the parts on this machine."""

    def _build(self, first: int = 0x11, second: int = 0x22) -> Any:
        def build(part: str) -> Any:
            return _Answers(first if part == "dsp1" else second)

        return build

    def test_a_divergence_the_parts_still_show_agrees(self) -> None:
        pinned = [a_finding()]

        found = masks.check(pinned, self._build())

        self.assertTrue(found.agrees)

    def test_one_the_parts_no_longer_show_is_a_disagreement(self) -> None:
        pinned = [a_finding(second="99" * 8)]

        found = masks.check(pinned, self._build())

        self.assertFalse(found.agrees)
        self.assertEqual(len(found.disagreements), 1)

    def test_and_the_disagreement_names_the_mask_and_both_answers(self) -> None:
        pinned = [a_finding(second="99" * 8)]

        found = masks.check(pinned, self._build())

        command, mask, wanted, got = found.disagreements[0]
        self.assertEqual(command, 0x04)
        self.assertEqual(mask, "dsp1b")
        self.assertEqual(wanted, "99" * 8)
        self.assertEqual(got, "22" * 8)

    def test_a_divergence_that_has_become_agreement_is_reported_as_that(self) -> None:
        pinned = [a_finding()]

        found = masks.check(pinned, self._build(second=0x11))

        self.assertFalse(found.agrees)
        self.assertEqual(found.converged, (0x04,))

    def test_every_pinned_case_is_counted(self) -> None:
        pinned = [a_finding(command=0x04), a_finding(command=0x0B)]

        found = masks.check(pinned, self._build())

        self.assertEqual(found.checked, 2)


class _Answers:
    def __init__(self, byte: int) -> None:
        self.byte = byte
        self.written: list[int] = []

    def write(self, value: int) -> None:
        self.written.append(value)

    def read(self) -> int:
        return self.byte


class PrintingTest(unittest.TestCase):
    def test_a_comparison_prints_as_what_it_found(self) -> None:
        found = masks.Checked(disagreements=((0x04, "dsp1b", "a", "b"),), converged=(), checked=6)

        self.assertIn("6 cases", repr(found))
        self.assertIn("1 wrong", repr(found))


class FirstDifferenceTest(unittest.TestCase):
    """Where two answers part company, which is what a reader looks at first."""

    def test_two_answers_that_differ_at_the_front_part_company_there(self) -> None:
        self.assertEqual(masks._first_difference(b"\x01\x02", b"\x99\x02"), 0)

    def test_and_two_that_differ_later_part_company_later(self) -> None:
        self.assertEqual(masks._first_difference(b"\x01\x02", b"\x01\x99"), 1)

    def test_two_answers_that_agree_part_company_at_neither_end(self) -> None:
        self.assertEqual(masks._first_difference(b"\x01\x02", b"\x01\x02"), 2)

    def test_and_one_shorter_than_the_other_parts_company_where_it_stops(self) -> None:
        self.assertEqual(masks._first_difference(b"\x01", b"\x01\x02"), 1)


class StoringTest(unittest.TestCase):
    def test_a_sweep_is_written_where_it_can_be_read_back(self) -> None:
        where = Path(tempfile.mkdtemp())

        masks.store([a_finding()], where)

        self.assertEqual(loaded(where)["divergences"], [a_finding()])

    def test_it_names_which_masks_were_compared(self) -> None:
        where = Path(tempfile.mkdtemp())

        masks.store([a_finding()], where)

        self.assertEqual(loaded(where)["compared"], list(masks.MASKS))

    def test_and_the_digest_of_each_image_that_answered(self) -> None:
        where = Path(tempfile.mkdtemp())

        masks.store([a_finding()], where, digest=lambda part: f"digest-of-{part}")

        self.assertEqual(loaded(where)["images"]["dsp1"], "digest-of-dsp1")

    def test_nothing_written_reads_back_as_nothing(self) -> None:
        self.assertIsNone(masks.load(Path(tempfile.mkdtemp())))

    def test_a_sweep_that_found_nothing_still_writes_a_file(self) -> None:
        where = Path(tempfile.mkdtemp())

        masks.store([], where)

        self.assertEqual(loaded(where)["divergences"], [])


class ReportTest(unittest.TestCase):
    def _found(self, **held: Any) -> Any:
        return masks.Checked(**{"disagreements": (), "converged": (), "checked": 2, **held})

    def test_a_run_that_agrees_says_how_many_cases_it_re_derived(self) -> None:
        self.assertIn("2", " ".join(masks.lines_for(self._found())))

    def test_a_disagreement_names_the_command_and_both_answers(self) -> None:
        lines = " ".join(masks.lines_for(self._found(disagreements=((0x04, "dsp1b", "aa", "bb"),))))

        self.assertIn("0x04", lines)
        self.assertIn("aa", lines)
        self.assertIn("bb", lines)

    def test_a_case_that_has_become_agreement_says_which_command(self) -> None:
        lines = " ".join(masks.lines_for(self._found(converged=(0x0B,))))

        self.assertIn("0x0b", lines)
        self.assertIn("no longer", lines)


class EntryTest(unittest.TestCase):
    def test_a_machine_missing_one_of_the_masks_says_which(self) -> None:
        said: list[str] = []

        code = masks.main([], available=lambda: {"dsp1"}, say=said.append)

        self.assertEqual(code, 2)
        self.assertIn("dsp1b", " ".join(said))

    def test_a_sweep_writes_what_it_found_and_says_how_much_it_tried(self) -> None:
        where = Path(tempfile.mkdtemp())
        said: list[str] = []

        code = masks.main(
            ["--sweep"],
            available=lambda: set(masks.MASKS),
            build=lambda part: _Fixed(part, 0x04),
            commands=(0x04,),
            arguments=((0x01,),),
            digest=lambda part: part,
            where=where,
            say=said.append,
        )

        self.assertEqual(code, 0)
        self.assertEqual(len(loaded(where)["divergences"]), 1)
        self.assertIn("1 commands x 1 argument sets", " ".join(said))

    def test_nothing_pinned_yet_is_reported_rather_than_passed(self) -> None:
        said: list[str] = []

        code = masks.main(
            [],
            available=lambda: set(masks.MASKS),
            build=lambda part: _Fixed(part, 0x04),
            where=Path(tempfile.mkdtemp()),
            say=said.append,
        )

        self.assertEqual(code, 1)
        self.assertIn("--sweep", " ".join(said))

    def test_a_pinned_divergence_the_parts_still_show_passes(self) -> None:
        where = Path(tempfile.mkdtemp())
        masks.store(
            masks.sweep(lambda part: _Fixed(part, 0x04), commands=(0x04,), arguments=((0x01,),)),
            where,
            digest=lambda part: part,
        )

        code = masks.main(
            [],
            available=lambda: set(masks.MASKS),
            build=lambda part: _Fixed(part, 0x04),
            where=where,
            say=lambda _l: None,
        )

        self.assertEqual(code, 0)

    def test_and_one_they_no_longer_show_fails(self) -> None:
        where = Path(tempfile.mkdtemp())
        masks.store(
            masks.sweep(lambda part: _Fixed(part, 0x04), commands=(0x04,), arguments=((0x01,),)),
            where,
            digest=lambda part: part,
        )
        said: list[str] = []

        code = masks.main(
            [],
            available=lambda: set(masks.MASKS),
            build=lambda part: _Fixed(part, None),
            where=where,
            say=said.append,
        )

        self.assertEqual(code, 1)
        self.assertIn("no longer", " ".join(said))


class ArgumentTest(unittest.TestCase):
    """What the sweep tries, which decides whether it finds anything."""

    def test_the_edges_of_the_fixed_point_range_are_among_them(self) -> None:
        flat = {value for one in masks.ARGUMENTS for value in one}

        for edge in (0x0000, 0x7FFF, 0x8000, 0xFFFF):
            self.assertIn(edge, flat)

    def test_every_argument_set_is_a_whole_number_of_words(self) -> None:
        for one in masks.ARGUMENTS:
            self.assertEqual(len(one), masks.WORDS)

    def test_every_command_byte_is_swept(self) -> None:
        self.assertEqual(len(masks.COMMANDS), 0x100)

    def test_the_sets_are_the_same_on_every_machine(self) -> None:
        self.assertEqual(masks.ARGUMENTS, masks.argument_sets())


if __name__ == "__main__":
    unittest.main()
