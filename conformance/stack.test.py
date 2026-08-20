import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shapes
import stack


class Calling:
    """A part whose stack pointer walks up to a chosen depth and back."""

    def __init__(self, part: str = "dsp1", deepest: int = 2) -> None:
        self.part = part
        self.deepest = deepest
        self.registers = _Registers()
        self._walk = [deepest, 0]
        self._at = 0

    def step(self) -> None:
        self.registers.sp = self._walk[self._at % len(self._walk)]
        self._at += 1

    def write(self, value: int) -> None:
        self.step()

    def read(self) -> int:
        self.step()
        return 0

    def read_status(self) -> int:
        self.step()
        return 0x80


class _Registers:
    def __init__(self) -> None:
        self.sp = 0


class _Flat:
    """A part whose stack never moves at all."""

    def __init__(self, part: str = "dsp1") -> None:
        self.part = part
        self.registers = _Registers()

    def step(self) -> None:
        return None

    def write(self, value: int) -> None:
        self.step()

    def read(self) -> int:
        self.step()
        return 0

    def read_status(self) -> int:
        return 0x80


def a_shape(shape: str = "write1 read1") -> Any:
    return shapes.parse(shape)


class WatchingTest(unittest.TestCase):
    """Following the pointer while a part is driven."""

    def test_a_part_whose_pointer_never_moves_reports_no_movement(self) -> None:
        found = stack.watched(_Flat, "dsp1", a_shape(), [[1]])

        self.assertEqual(found.moves, 0)
        self.assertEqual(found.deepest, 0)

    def test_a_part_that_calls_reports_the_deepest_slot_it_reached(self) -> None:
        found = stack.watched(lambda part: Calling(part, deepest=2), "dsp1", a_shape(), [[1]])

        self.assertEqual(found.deepest, 2)

    def test_and_counts_every_time_the_pointer_moved(self) -> None:
        found = stack.watched(lambda part: Calling(part, deepest=2), "dsp1", a_shape(), [[1]])

        self.assertGreater(found.moves, 0)

    def test_a_shape_that_polls_the_register_is_watched_the_same_way(self) -> None:
        found = stack.watched(
            lambda part: Calling(part, deepest=2), "dsp1", a_shape("write1 poll1 read1"), [[1]]
        )

        self.assertEqual(found.deepest, 2)

    def test_and_a_part_that_never_calls_reports_nothing_through_a_poll(self) -> None:
        found = stack.watched(_Flat, "dsp1", a_shape("write1 poll1 read1"), [[1]])

        self.assertEqual(found.deepest, 0)

    def test_a_deeper_part_reports_deeper(self) -> None:
        found = stack.watched(lambda part: Calling(part, deepest=3), "dsp1", a_shape(), [[1]])

        self.assertEqual(found.deepest, 3)


class SweepTest(unittest.TestCase):
    """Every shape a cartridge uses, under every command byte."""

    def test_a_sweep_reports_the_deepest_slot_across_every_command(self) -> None:
        found = stack.sweep(
            "dsp1",
            build=lambda part: Calling(part, deepest=2),
            held=((a_shape(), 1),),
            commands=range(4),
        )

        self.assertEqual(found.deepest, 2)

    def test_and_how_many_exchanges_it_played(self) -> None:
        found = stack.sweep(
            "dsp1",
            build=lambda part: Calling(part, deepest=1),
            held=((a_shape(), 1), (a_shape("write1 read2"), 1)),
            commands=range(4),
        )

        self.assertEqual(found.exchanges, 8)

    def test_a_sweep_told_nothing_reads_the_recorded_shapes_itself(self) -> None:
        found = stack.sweep(
            "dsp1",
            build=lambda part: Calling(part, deepest=1),
            held=None,
            commands=range(1),
            shapes_for=lambda _part: ((a_shape(), 1),),
        )

        self.assertEqual(found.exchanges, 1)

    def test_a_sweep_given_a_seed_repeats(self) -> None:
        first = stack.sweep(
            "dsp1",
            build=lambda part: Calling(part, deepest=2),
            held=((a_shape(), 1),),
            commands=range(2),
            seed=7,
        )
        second = stack.sweep(
            "dsp1",
            build=lambda part: Calling(part, deepest=2),
            held=((a_shape(), 1),),
            commands=range(2),
            seed=7,
        )

        self.assertEqual((first.deepest, first.moves), (second.deepest, second.moves))

    def test_a_part_with_no_recorded_shapes_plays_nothing(self) -> None:
        found = stack.sweep("dsp1", build=_Flat, held=(), commands=range(4))

        self.assertEqual(found.exchanges, 0)
        self.assertEqual(found.deepest, 0)


class WithinTest(unittest.TestCase):
    """Whether what was measured fits the depth the manufacturer gives."""

    def test_a_sweep_that_stays_inside_the_depth_fits(self) -> None:
        found = stack.Measured("dsp1", deepest=3, moves=10, exchanges=4)

        self.assertTrue(found.within(4))

    def test_one_that_reaches_the_last_slot_still_fits(self) -> None:
        found = stack.Measured("dsp1", deepest=3, moves=10, exchanges=4)

        self.assertTrue(found.within(4))

    def test_one_that_reaches_past_it_does_not(self) -> None:
        found = stack.Measured("dsp1", deepest=4, moves=10, exchanges=4)

        self.assertFalse(found.within(4))

    def test_a_measurement_prints_as_what_it_found(self) -> None:
        found = stack.Measured("dsp3", deepest=3, moves=10, exchanges=4)

        self.assertIn("dsp3", repr(found))
        self.assertIn("3", repr(found))


class ReportTest(unittest.TestCase):
    def test_a_run_names_each_part_and_the_slot_it_reached(self) -> None:
        found = [stack.Measured("dsp1", deepest=2, moves=99, exchanges=7)]

        lines = " ".join(stack.lines_for(found, levels=4))

        self.assertIn("dsp1", lines)
        self.assertIn("2", lines)

    def test_and_says_it_fits_when_everything_did(self) -> None:
        found = [stack.Measured("dsp1", deepest=2, moves=99, exchanges=7)]

        self.assertIn("within", " ".join(stack.lines_for(found, levels=4)))

    def test_and_says_which_part_did_not_when_one_did_not(self) -> None:
        found = [
            stack.Measured("dsp1", deepest=2, moves=9, exchanges=7),
            stack.Measured("dsp4", deepest=6, moves=9, exchanges=7),
        ]

        lines = " ".join(stack.lines_for(found, levels=4))

        self.assertIn("dsp4", lines)
        self.assertIn("past", lines)


class EntryTest(unittest.TestCase):
    def _run(self, **held: Any) -> tuple[int, str]:
        said: list[str] = []
        code = stack.main([], say=said.append, **held)
        return code, " ".join(said)

    def test_a_machine_with_no_microcode_says_so_and_stops(self) -> None:
        code, said = self._run(why_not=lambda: "no image is here")

        self.assertEqual(code, 2)
        self.assertIn("no image is here", said)

    def test_a_run_that_fits_the_documented_depth_passes(self) -> None:
        code, said = self._run(
            why_not=lambda: None,
            build=lambda part: Calling(part, deepest=2),
            shapes_for=lambda _part: ((a_shape(), 1),),
            commands=range(2),
            parts=("dsp1",),
        )

        self.assertEqual(code, 0)
        self.assertIn("within", said)

    def test_a_run_that_goes_past_it_fails_and_names_the_part(self) -> None:
        code, said = self._run(
            why_not=lambda: None,
            build=lambda part: Calling(part, deepest=5),
            shapes_for=lambda _part: ((a_shape(), 1),),
            commands=range(2),
            parts=("dsp2",),
        )

        self.assertEqual(code, 1)
        self.assertIn("dsp2", said)


class RealPartTest(unittest.TestCase):  # pragma: no cover
    """The real microcode, on a machine that has it.

    Small on purpose. The full sweep is the runner, and it takes minutes; what
    this pins is that the runner is wired to real parts rather than to stand-ins.

    Outside the coverage gate, and it is the only thing here that is. A test whose
    subject is a file nobody can distribute runs on one machine and not another,
    so counting it would make the number mean something different depending on who
    ran it. Everything it exercises is covered by the stand-ins as well; what this
    adds is that the wiring reaches a real part, which no stand-in can show.
    """

    def test_a_real_part_stays_inside_the_documented_depth(self) -> None:
        if stack.why_not() is not None:
            self.skipTest("no microcode on this machine")

        found = stack.sweep("dsp1", held=shapes.interesting(shapes.recorded("dsp1"))[:1])

        self.assertTrue(found.within(stack.LEVELS))


if __name__ == "__main__":
    unittest.main()
