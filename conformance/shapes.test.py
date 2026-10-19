import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import snesdsp
from conformance import shapes


def a_file(held: Any) -> Path:
    where = Path(tempfile.mkdtemp()) / "made-up.json"
    where.write_text(json.dumps(held))
    return where


class ParseTest(unittest.TestCase):
    def test_a_write_is_read_as_a_write(self) -> None:
        self.assertEqual(shapes.parse("write1")[0].what, shapes.WRITE)

    def test_a_read_is_read_as_a_read(self) -> None:
        self.assertEqual(shapes.parse("read2")[0].what, shapes.READ)

    def test_a_poll_is_read_as_a_poll(self) -> None:
        self.assertEqual(shapes.parse("poll1")[0].what, shapes.POLL)

    def test_the_width_comes_back_as_a_number(self) -> None:
        self.assertEqual(shapes.parse("write2")[0].width, 2)

    def test_every_step_of_a_long_shape_is_read(self) -> None:
        found = shapes.parse("write1 write2 poll2 read2 read2")

        self.assertEqual(len(found), 5)

    def test_an_empty_shape_has_no_steps(self) -> None:
        self.assertEqual(shapes.parse(""), ())

    def test_a_word_naming_no_access_is_refused(self) -> None:
        with self.assertRaises(shapes.Malformed) as raised:
            shapes.parse("nonsense1")

        self.assertIn("nonsense1", str(raised.exception))

    def test_a_width_that_is_not_one_or_two_is_refused(self) -> None:
        with self.assertRaises(shapes.Malformed):
            shapes.parse("write3")

    def test_a_step_with_no_width_at_all_is_refused(self) -> None:
        with self.assertRaises(shapes.Malformed):
            shapes.parse("write")

    def test_a_step_prints_as_what_it_is_and_how_wide(self) -> None:
        self.assertIn("write", repr(shapes.parse("write2")[0]))
        self.assertIn("2", repr(shapes.parse("write2")[0]))

    def test_two_steps_describing_the_same_access_are_the_same_step(self) -> None:
        self.assertEqual(shapes.parse("write2")[0], shapes.parse("write2")[0])

    def test_and_two_describing_different_ones_are_not(self) -> None:
        self.assertNotEqual(shapes.parse("write2")[0], shapes.parse("write1")[0])

    def test_a_step_is_not_equal_to_something_that_is_not_a_step(self) -> None:
        self.assertNotEqual(shapes.parse("write2")[0], "write2")

    def test_steps_can_be_counted_by_kind(self) -> None:
        found = set(shapes.parse("write1 write1 read2"))

        self.assertEqual(len(found), 2)

    def test_a_write_and_a_read_carry_a_payload(self) -> None:
        self.assertTrue(shapes.parse("write1")[0].moves)
        self.assertTrue(shapes.parse("read1")[0].moves)

    def test_and_a_poll_does_not(self) -> None:
        self.assertFalse(shapes.parse("poll1")[0].moves)


class RecordedTest(unittest.TestCase):
    def test_the_shapes_read_from_a_cartridge_come_back(self) -> None:
        self.assertTrue(shapes.recorded("dsp3"))

    def test_each_one_is_a_run_of_steps_and_how_often_it_was_seen(self) -> None:
        steps, seen = shapes.recorded("dsp3")[0]

        self.assertTrue(steps)
        self.assertGreater(seen, 0)

    def test_the_longest_shape_comes_first(self) -> None:
        found = shapes.recorded("dsp3")

        self.assertEqual(len(found[0][0]), max(len(steps) for steps, _ in found))

    def test_a_file_holding_another_part_is_refused(self) -> None:
        where = a_file({"part": "dsp4", "shapes": []})

        with self.assertRaises(shapes.Malformed) as raised:
            shapes.recorded("dsp3", where)

        self.assertIn("dsp4", str(raised.exception))

    def test_a_file_can_be_read_from_somewhere_else(self) -> None:
        where = a_file({"part": "dsp3", "shapes": [{"shape": "write1 read1", "seen": 1}]})

        self.assertEqual(len(shapes.recorded("dsp3", where)), 1)

    def test_every_cartridge_the_shapes_came_from_is_named_with_its_digests(self) -> None:
        held = json.loads((shapes.ROOT / "dsp1shapes.json").read_text())

        self.assertTrue(held["readFrom"])
        for source in held["readFrom"]:
            for name in ("name", "crc32", "md5", "sha1", "sha256"):
                self.assertIn(name, source, name)

    def test_no_byte_of_any_cartridge_is_in_the_file(self) -> None:
        held = json.loads((shapes.ROOT / "dsp1shapes.json").read_text())

        for one in held["shapes"]:
            self.assertEqual(set(one) - {"shape", "seen", "cartridges"}, set())

    def test_a_shape_says_how_many_of_those_cartridges_use_it(self) -> None:
        held = json.loads((shapes.ROOT / "dsp1shapes.json").read_text())
        sources = len(held["readFrom"])

        for one in held["shapes"]:
            self.assertGreaterEqual(one["cartridges"], 1)
            self.assertLessEqual(one["cartridges"], sources)

    def test_the_dsp1_shapes_come_from_more_than_one_game(self) -> None:
        held = json.loads((shapes.ROOT / "dsp1shapes.json").read_text())

        self.assertGreater(len(held["readFrom"]), 1)


class FamilyTest(unittest.TestCase):
    def test_a_part_with_its_own_shapes_uses_them(self) -> None:
        # Arrange
        part = "dsp2"

        # Act
        found = shapes.named(part)

        # Assert
        self.assertEqual(found, "dsp2")

    def test_the_die_shrink_is_driven_by_the_part_it_shrank(self) -> None:
        # Arrange
        part = "dsp1a"

        # Act
        found = shapes.named(part)

        # Assert
        self.assertEqual(found, "dsp1")

    def test_and_so_is_the_later_mask(self) -> None:
        # Arrange
        part = "dsp1b"

        # Act
        found = shapes.named(part)

        # Assert
        self.assertEqual(found, "dsp1")

    def test_every_part_that_shares_shapes_is_a_part_this_covers(self) -> None:
        # Arrange
        catalogue = set(snesdsp.MODELS)

        # Act
        named = set(shapes.DRIVEN_LIKE) | set(shapes.DRIVEN_LIKE.values())

        # Assert
        self.assertEqual(named - catalogue, set())

    def test_a_later_mask_reads_the_shapes_of_the_part_it_follows(self) -> None:
        # Arrange
        expected = shapes.recorded("dsp1")

        # Act
        found = shapes.recorded("dsp1b")

        # Assert
        self.assertEqual(found, expected)


class InterestingTest(unittest.TestCase):
    def test_a_shape_that_gives_and_takes_is_kept(self) -> None:
        found = shapes.interesting(((shapes.parse("write1 read1"), 1),))

        self.assertEqual(len(found), 1)

    def test_a_shape_that_only_writes_is_dropped(self) -> None:
        self.assertEqual(shapes.interesting(((shapes.parse("write1 write2"), 1),)), ())

    def test_a_shape_that_only_reads_is_dropped(self) -> None:
        self.assertEqual(shapes.interesting(((shapes.parse("read1 read1"), 1),)), ())

    def test_a_shape_that_only_polls_is_dropped(self) -> None:
        self.assertEqual(shapes.interesting(((shapes.parse("poll1"), 1),)), ())

    def test_the_cartridge_has_shapes_worth_sweeping(self) -> None:
        self.assertTrue(shapes.interesting(shapes.recorded("dsp3")))


class PayloadTest(unittest.TestCase):
    def test_one_run_of_bytes_is_made_per_write(self) -> None:
        steps = shapes.parse("write1 read2 write2")

        self.assertEqual(len(shapes.payload_for(steps, shapes.rolls())), 2)

    def test_each_run_is_as_wide_as_the_write_it_fills(self) -> None:
        steps = shapes.parse("write1 write2")

        found = shapes.payload_for(steps, shapes.rolls())

        self.assertEqual([len(one) for one in found], [1, 2])

    def test_every_byte_is_a_byte(self) -> None:
        steps = shapes.parse("write2 write2")

        for run in shapes.payload_for(steps, shapes.rolls()):
            for byte in run:
                self.assertTrue(0 <= byte <= 0xFF)

    def test_the_same_seed_produces_the_same_payload(self) -> None:
        steps = shapes.parse("write2 write2")

        one = shapes.payload_for(steps, shapes.rolls(7))
        two = shapes.payload_for(steps, shapes.rolls(7))

        self.assertEqual(one, two)

    def test_and_a_different_seed_does_not(self) -> None:
        steps = shapes.parse("write2 write2 write2 write2")

        one = shapes.payload_for(steps, shapes.rolls(7))
        two = shapes.payload_for(steps, shapes.rolls(8))

        self.assertNotEqual(one, two)


class CommandedTest(unittest.TestCase):
    def test_the_first_byte_becomes_the_command(self) -> None:
        found = shapes.commanded([[0x11], [0x22, 0x33]], 0x02)

        self.assertEqual(found[0][0], 0x02)

    def test_nothing_after_it_is_disturbed(self) -> None:
        found = shapes.commanded([[0x11, 0x99], [0x22, 0x33]], 0x02)

        self.assertEqual(found[1:], [[0x22, 0x33]])
        self.assertEqual(found[0][1:], [0x99])

    def test_a_payload_with_no_writes_at_all_is_left_alone(self) -> None:
        self.assertEqual(shapes.commanded([], 0x02), [])


class Recorder:
    def __init__(self, answers: Any = None) -> None:
        self.given: list[int] = []
        self.answers = list(answers or [])
        self.polls = 0

    def write(self, byte: int) -> None:
        self.given.append(byte)

    def read(self) -> int:
        return self.answers.pop(0) if self.answers else 0

    def read_status(self) -> int:
        self.polls += 1
        return 0x80


class DriveTest(unittest.TestCase):
    def test_every_written_byte_reaches_the_part_in_order(self) -> None:
        part = Recorder()

        shapes.drive(part, shapes.parse("write1 write2"), [[0x11], [0x22, 0x33]])

        self.assertEqual(part.given, [0x11, 0x22, 0x33])

    def test_a_read_gives_back_as_many_bytes_as_it_is_wide(self) -> None:
        part = Recorder([1, 2, 3])

        said = shapes.drive(part, shapes.parse("write1 read2"), [[0]])

        self.assertEqual(said, [[1, 2]])

    def test_a_poll_reads_the_status_rather_than_taking_a_byte(self) -> None:
        part = Recorder([9])

        said = shapes.drive(part, shapes.parse("write1 poll1"), [[0]])

        self.assertEqual(part.polls, 1)
        self.assertEqual(said, [[0x80]])

    def test_what_comes_back_is_one_run_per_read_and_poll(self) -> None:
        part = Recorder([1, 2, 3, 4])

        said = shapes.drive(part, shapes.parse("write1 read2 poll1 read2"), [[0]])

        self.assertEqual(len(said), 3)

    def test_a_shape_with_nothing_to_say_says_nothing(self) -> None:
        part = Recorder()

        self.assertEqual(shapes.drive(part, shapes.parse("write1"), [[0]]), [])


class Console(Recorder):
    def __init__(self, answers: Any = None) -> None:
        super().__init__(answers)
        self.calls: list[str] = []

    def write_word(self, word: int) -> None:
        self.calls.append(f"write_word {word:#06x}")

    def read_word(self) -> int:
        self.calls.append("read_word")
        return 0xBEEF

    def waited(self) -> bool:
        self.calls.append("waited")
        return True


class WordTest(unittest.TestCase):
    def test_a_word_is_written_as_one_access_low_byte_first(self) -> None:
        # Arrange
        part = Console()

        # Act
        shapes.drive(part, shapes.parse("write1 write2"), [[0x11], [0x22, 0x33]])

        # Assert
        self.assertEqual((part.given, part.calls), ([0x11], ["write_word 0x3322"]))

    def test_and_read_as_one_access(self) -> None:
        # Arrange
        part = Console([7])

        # Act
        said = shapes.drive(part, shapes.parse("write1 read1 read2"), [[0]])

        # Assert
        self.assertEqual((said, part.calls), ([[7], [0xEF, 0xBE]], ["read_word"]))

    def test_a_poll_waits_for_the_part_the_way_a_driver_s_loop_does(self) -> None:
        # Arrange
        part = Console()

        # Act
        said = shapes.drive(part, shapes.parse("write1 poll2"), [[0]])

        # Assert
        self.assertEqual((said, part.calls, part.polls), ([[0x80, 0x80]], ["waited"], 2))


if __name__ == "__main__":
    unittest.main()
