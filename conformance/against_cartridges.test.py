import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import against_cartridges, shapes


class Talkative:
    """A stand-in part that always has something to say."""

    def __init__(self, part: str = "dsp3") -> None:
        self.part = part
        self.given: list[int] = []

    def write(self, byte: int) -> None:
        self.given.append(byte)

    def read(self) -> int:
        return 0x5A

    def read_status(self) -> int:
        return 0x80


class Mute:
    """A stand-in part that answers every read with a zero."""

    def __init__(self, part: str = "dsp3") -> None:
        self.part = part

    def write(self, byte: int) -> None:
        return None

    def read(self) -> int:
        return 0

    def read_status(self) -> int:
        return 0x80


def build(part: str) -> Any:
    return Talkative(part)


class OnlyForOneCommand:
    """A stand-in that answers only when the first byte it was given is that one."""

    def __init__(self, part: str = "dsp3", speaks_on: int = 0x0B) -> None:
        self.part = part
        self.speaks_on = speaks_on
        self.given: list[int] = []

    def write(self, byte: int) -> None:
        self.given.append(byte)

    def read(self) -> int:
        return 0x5A if self.given and self.given[0] == self.speaks_on else 0

    def read_status(self) -> int:
        return 0x80


def _spoke(found: "against_cartridges.Spoke | None") -> "against_cartridges.Spoke":
    """The command that answered, insisting that one did."""
    assert found is not None, "no command byte got an answer"
    return found


class CommandSweepTest(unittest.TestCase):
    """A shape that answered nothing, tried again across every command byte.

    A payload is random bytes, so the first one is a random command, and on these
    parts most of the 256 possible bytes are not commands at all. A shape that
    says nothing under a random command has not been shown to say nothing: it has
    been asked a question the part does not have. Only a shape that stays silent
    for all 256 is silent.
    """

    def _steps(self) -> Any:
        return shapes.parse("write1 write2 poll1 read2")

    def test_a_part_that_answers_under_one_command_is_found_under_it(self) -> None:
        found = against_cartridges.speaking(
            lambda part: OnlyForOneCommand(part, 0x0B), "dsp3", self._steps(), [[0x00], [1, 2]]
        )

        self.assertEqual(_spoke(found).command, 0x0B)

    def test_and_what_it_said_under_that_command_is_carried(self) -> None:
        found = against_cartridges.speaking(
            lambda part: OnlyForOneCommand(part, 0x0B), "dsp3", self._steps(), [[0x00], [1, 2]]
        )

        self.assertEqual(_spoke(found).said, [[0x80], [0x5A, 0x5A]])

    def test_a_part_that_answers_under_none_of_them_is_not_found(self) -> None:
        found = against_cartridges.speaking(Mute, "dsp3", self._steps(), [[0x00], [1, 2]])

        self.assertIsNone(found)

    def test_a_narrower_sweep_can_miss_a_command_that_would_have_answered(self) -> None:
        found = against_cartridges.speaking(
            lambda part: OnlyForOneCommand(part, 0x0B),
            "dsp3",
            self._steps(),
            [[0x00], [1, 2]],
            commands=range(4),
        )

        self.assertIsNone(found)

    def test_a_shape_with_nothing_to_write_cannot_be_given_a_command(self) -> None:
        found = against_cartridges.speaking(
            lambda part: OnlyForOneCommand(part, 0x0B), "dsp3", shapes.parse("read1"), []
        )

        self.assertIsNone(found)


class SweepInsideARunTest(unittest.TestCase):
    """A run that meets a silent shape and asks again under every command."""

    def test_a_shape_silent_under_its_random_command_is_recovered(self) -> None:
        found = against_cartridges.driven(
            "dsp3", build=lambda part: OnlyForOneCommand(part, 0x0B), seed=7
        )

        self.assertTrue(all(one.answered for one in found if not one.unprompted))

    def test_and_the_command_that_recovered_it_is_recorded(self) -> None:
        found = against_cartridges.driven(
            "dsp3", build=lambda part: OnlyForOneCommand(part, 0x0B), seed=7
        )

        self.assertIn(0x0B, [one.command for one in found])

    def test_a_part_silent_under_every_command_stays_silent(self) -> None:
        found = against_cartridges.driven("dsp3", build=Mute, seed=7)

        self.assertEqual(
            against_cartridges.silent(found),
            [one for one in found if not one.unprompted],
        )


class UnpromptedTest(unittest.TestCase):
    """A shape that reads before it writes, played at a part that has just booted.

    On a console that read follows an earlier exchange, and it is answered by what
    that exchange left behind. Played on its own at a fresh part there is nothing
    behind it, so nothing comes back, and no command byte can change that: the
    read happens before the command does. Counting that as the part failing to
    answer would be counting the harness asking out of order.
    """

    def test_a_shape_that_writes_first_is_prompted(self) -> None:
        found = against_cartridges.Played("write1 read1", [[1]], [shapes.READ])

        self.assertFalse(found.unprompted)

    def test_one_that_reads_first_is_not(self) -> None:
        found = against_cartridges.Played("read1 write1", [[0]], [shapes.READ])

        self.assertTrue(found.unprompted)

    def test_one_that_polls_before_writing_is_still_prompted(self) -> None:
        found = against_cartridges.Played(
            "poll1 write1 read1", [[0x80], [1]], [shapes.POLL, shapes.READ]
        )

        self.assertFalse(found.unprompted)

    def test_a_silent_shape_that_read_first_is_not_counted_as_silence(self) -> None:
        found = [against_cartridges.Played("read1 write1", [[0]], [shapes.READ])]

        self.assertEqual(against_cartridges.silent(found), [])

    def test_a_silent_shape_that_wrote_first_is(self) -> None:
        found = [against_cartridges.Played("write1 read1", [[0]], [shapes.READ])]

        self.assertEqual(
            against_cartridges.silent(found),
            [one for one in found if not one.unprompted],
        )

    def test_a_shape_that_only_polls_is_neither_prompted_nor_not(self) -> None:
        found = against_cartridges.Played("poll1 poll1", [[0x80], [0x80]], [shapes.POLL] * 2)

        self.assertFalse(found.unprompted)

    def test_a_run_with_silence_and_nothing_out_of_order_says_only_the_silence(self) -> None:
        found = [against_cartridges.Played("write1 read1", [[0]], [shapes.READ])]

        lines = " ".join(against_cartridges.lines_for(found, "dsp3"))

        self.assertIn("nothing back", lines)
        self.assertNotIn("before writing", lines)

    def test_a_run_says_how_many_were_asked_out_of_order(self) -> None:
        found = [against_cartridges.Played("read1 write1", [[0]], [shapes.READ])]

        lines = " ".join(against_cartridges.lines_for(found, "dsp3"))

        self.assertIn("before writing", lines)


class PrintingTest(unittest.TestCase):
    def test_a_command_that_answered_prints_as_the_byte_it_was(self) -> None:
        self.assertIn("0x0b", repr(against_cartridges.Spoke(0x0B, [[1]])))


class DrivenTest(unittest.TestCase):
    def test_a_part_is_driven_through_every_shape_its_cartridge_uses(self) -> None:
        found = against_cartridges.driven("dsp3", build=build)

        self.assertEqual(len(found), len(shapes.interesting(shapes.recorded("dsp3"))))

    def test_each_one_reports_the_shape_and_what_came_back(self) -> None:
        first = against_cartridges.driven("dsp3", build=build)[0]

        self.assertTrue(first.shape)
        self.assertTrue(first.said)

    def test_a_run_prints_as_the_shape_it_drove(self) -> None:
        first = against_cartridges.driven("dsp3", build=build)[0]

        self.assertIn("write", repr(first))

    def test_a_part_that_answered_something_is_not_silent(self) -> None:
        first = against_cartridges.driven("dsp3", build=build)[0]

        self.assertTrue(first.answered)

    def test_a_part_that_answered_nothing_but_zeroes_is_silent(self) -> None:
        found = against_cartridges.Played("write1 read1", [[0]], [shapes.READ])

        self.assertFalse(found.answered)

    def test_a_status_register_that_reads_as_ready_is_not_an_answer(self) -> None:
        found = against_cartridges.Played("write1 poll1", [[0x80]], [shapes.POLL])

        self.assertFalse(found.answered)


class ReportTest(unittest.TestCase):
    def test_every_shape_makes_a_line(self) -> None:
        lines = against_cartridges.report(against_cartridges.driven("dsp3", build=build))

        self.assertTrue(lines)

    def test_a_line_names_the_shape(self) -> None:
        lines = against_cartridges.report(against_cartridges.driven("dsp3", build=build))

        self.assertIn("write", lines[0])

    def test_the_report_counts_what_it_drove(self) -> None:
        found = against_cartridges.driven("dsp3", build=build)

        self.assertIn(str(len(found)), " ".join(against_cartridges.lines_for(found, "dsp3")))


class EntryTest(unittest.TestCase):
    def test_a_run_with_no_microcode_says_so(self) -> None:
        found = against_cartridges.main([], why_not=lambda: "no image here", say=lambda _: None)

        self.assertEqual(found, 2)

    def test_a_run_with_microcode_drives_the_part(self) -> None:
        said: list[str] = []

        found = against_cartridges.main(
            ["dsp3"], why_not=lambda: None, build=build, say=said.append
        )

        self.assertEqual(found, 0)
        self.assertTrue(said)

    def test_a_part_with_no_recorded_shapes_is_refused(self) -> None:
        with self.assertRaises(against_cartridges.Usage):
            against_cartridges.main(
                ["dsp1a"], why_not=lambda: None, build=build, say=lambda _: None
            )

    def test_every_part_with_its_own_image_has_exchanges_recorded(self) -> None:
        from conformance import shapes as recorded

        for part in ("dsp1", "dsp2", "dsp3", "dsp4"):
            self.assertTrue(recorded.interesting(recorded.recorded(part)), part)

    def test_each_recording_names_every_cartridge_it_came_from(self) -> None:
        import json

        for part in ("dsp1", "dsp2", "dsp3", "dsp4"):
            where = Path(__file__).resolve().parent / f"{part}shapes.json"
            held = json.loads(where.read_text())

            self.assertTrue(held["readFrom"], part)
            for source in held["readFrom"]:
                for digest in ("name", "crc32", "md5", "sha1", "sha256"):
                    self.assertIn(digest, source, part)

    def test_and_carries_no_byte_of_any_of_them(self) -> None:
        import json

        for part in ("dsp1", "dsp2", "dsp3", "dsp4"):
            where = Path(__file__).resolve().parent / f"{part}shapes.json"
            for one in json.loads(where.read_text())["shapes"]:
                self.assertEqual(set(one) - {"shape", "seen", "cartridges"}, set(), part)

    def test_a_part_that_says_nothing_at_all_is_a_failure(self) -> None:
        found = against_cartridges.main(
            ["dsp3"], why_not=lambda: None, build=Mute, say=lambda _: None
        )

        self.assertEqual(found, 1)


if __name__ == "__main__":
    unittest.main()
