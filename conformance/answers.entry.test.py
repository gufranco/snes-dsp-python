import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from conformance import answers  # noqa: E402


class Puppet:
    def __init__(self, first: int = 0x10) -> None:
        self.next = first
        self.written: list[int] = []

    def write(self, value: int) -> None:
        self.written.append(value)

    def read(self) -> int:
        self.next = (self.next + 1) & 0xFF
        return self.next


def puppets(first: int = 0x10) -> Any:
    def build(_part: str) -> Any:
        return Puppet(first)

    return build


def a_digest(_part: str) -> str:
    return "abc123"


def a_shape(shape: str = "write1 read1", seen: int = 3, cartridges: int = 1) -> dict[str, Any]:
    return {"shape": shape, "seen": seen, "cartridges": cartridges}


def some_shapes(*held: Any) -> list[dict[str, Any]]:
    return list(held) or [a_shape()]


class EntryTest(unittest.TestCase):
    def test_a_machine_with_no_microcode_says_so_rather_than_passing(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = answers.main([], why_not=lambda: "no image is here", say=said.append)

        # Assert
        self.assertEqual(code, 2)
        self.assertIn("nothing to run", " ".join(said))

    def test_taking_a_corpus_writes_one_and_reports_it(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        said: list[str] = []

        # Act
        code = answers.main(
            ["--take", "dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 0)
        self.assertTrue((where / "dsp1answers.json").exists())
        self.assertIn("wrote", " ".join(said))

    def test_a_part_with_no_corpus_yet_is_reported_rather_than_passed(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=Path(tempfile.mkdtemp()),
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertIn("no answers are recorded", " ".join(said))

    def test_a_run_that_agrees_passes(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            say=lambda _l: None,
        )

        # Assert
        self.assertEqual(code, 0)

    def test_and_one_that_disagrees_fails(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(first=0x30),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertIn("write1 read1", " ".join(said))

    def test_a_corpus_from_another_image_stops_the_run_rather_than_failing_it(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=lambda _part: "something else",
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 2)
        self.assertIn("image", " ".join(said))

    def test_taking_a_corpus_with_no_microcode_writes_nothing(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        said: list[str] = []

        # Act
        code = answers.main(
            ["--take", "dsp1"], why_not=lambda: "no image is here", where=where, say=said.append
        )

        # Assert
        self.assertEqual(code, 2)
        self.assertEqual(said, ["  nothing to run: no image is here"])
        self.assertEqual(list(where.iterdir()), [])

    def test_every_recorded_corpus_was_taken_over_the_shapes_swept_today(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = answers.main([], why_not=lambda: "no image is here", say=said.append)

        # Assert
        self.assertEqual(said, ["  nothing to run: no image is here"])
        self.assertEqual(code, 2)

    def test_a_shape_swept_but_not_recorded_fails_with_no_microcode(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: "no image is here",
            shapes_for=lambda _part: some_shapes(a_shape(), a_shape("write1 read2")),
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertIn("write1 read2: swept, and not yet recorded", " ".join(said))

    def test_a_shape_recorded_but_no_longer_swept_fails_with_no_microcode(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        held = some_shapes(a_shape(), a_shape("write1 read2"))
        answers.store(answers.take("dsp1", puppets(), shapes=held, digest=a_digest), where)
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: "no image is here",
            shapes_for=lambda _part: some_shapes(),
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertIn("write1 read2: recorded, and no longer among", " ".join(said))

    def test_the_same_shapes_swept_in_another_order_fail_with_no_microcode(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        held = some_shapes(a_shape(), a_shape("write1 read2"))
        answers.store(answers.take("dsp1", puppets(), shapes=held, digest=a_digest), where)
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: "no image is here",
            shapes_for=lambda _part: list(reversed(held)),
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertIn("another order", " ".join(said))

    def test_a_missing_corpus_fails_with_no_microcode(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: "no image is here",
            shapes_for=lambda _part: some_shapes(),
            where=Path(tempfile.mkdtemp()),
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertIn("no answers are recorded", " ".join(said))

    def test_a_stale_corpus_is_not_re_derived_against_the_microcode(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        answers.store(answers.take("dsp1", puppets(), shapes=some_shapes(), digest=a_digest), where)
        said: list[str] = []

        # Act
        code = answers.main(
            ["dsp1"],
            why_not=lambda: None,
            build=puppets(first=0x30),
            shapes_for=lambda _part: some_shapes(a_shape(), a_shape("write1 read2")),
            digest=a_digest,
            where=where,
            say=said.append,
        )

        # Assert
        self.assertEqual(code, 1)
        self.assertNotIn("re-derived", " ".join(said))

    def test_with_no_part_named_every_part_is_checked(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        for part in ("dsp1", "dsp2"):
            answers.store(
                answers.take(part, puppets(), shapes=some_shapes(), digest=a_digest), where
            )
        said: list[str] = []

        # Act
        code = answers.main(
            [],
            why_not=lambda: None,
            build=puppets(),
            shapes_for=lambda _part: some_shapes(),
            digest=a_digest,
            where=where,
            parts=("dsp1", "dsp2"),
            say=said.append,
        )

        # Assert
        text = " ".join(said)
        self.assertEqual(code, 0)
        self.assertIn("dsp1", text)
        self.assertIn("dsp2", text)


if __name__ == "__main__":
    unittest.main()
