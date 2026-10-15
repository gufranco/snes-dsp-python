from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402
from conformance import speed  # noqa: E402


class TimedTest(unittest.TestCase):
    def test_the_median_is_the_middle_reading(self) -> None:
        found = speed.Timed("step", 100, [0.4, 0.1, 0.2])

        self.assertEqual(found.median(), 0.2)

    def test_the_rate_is_calls_over_that_median(self) -> None:
        found = speed.Timed("step", 100, [0.5, 0.5, 0.5])

        self.assertEqual(found.rate(), 200.0)

    def test_a_run_above_the_floor_beats_it(self) -> None:
        found = speed.Timed("step", 1000, [0.001])

        self.assertTrue(found.beats(1000))

    def test_and_one_below_it_does_not(self) -> None:
        found = speed.Timed("step", 1, [1.0])

        self.assertFalse(found.beats(1000))

    def test_a_run_that_took_no_time_is_not_read_as_infinitely_fast(self) -> None:
        found = speed.Timed("step", 100, [0.0])

        self.assertEqual(found.rate(), 0.0)
        self.assertFalse(found.beats(1))


class ReportTest(unittest.TestCase):
    def test_the_report_names_the_rate_the_floor_and_the_runtime(self) -> None:
        lines = speed.lines_for(speed.Timed("step", 1000, [0.001]), floor=1000)
        held = "\n".join(lines)

        self.assertIn("step", held)
        self.assertIn("floor", held)
        self.assertIn(f"{sys.version_info.major}.{sys.version_info.minor}", held)

    def test_a_run_under_the_floor_says_so(self) -> None:
        lines = speed.lines_for(speed.Timed("step", 1, [1.0]), floor=1_000_000)

        self.assertTrue(any("below" in one for one in lines), lines)


class MainTest(unittest.TestCase):
    def run_main(self, **changes: object) -> tuple[int, str]:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = speed.main(**changes)  # type: ignore[arg-type]
        return code, captured.getvalue()

    def measuring(self, rate: float) -> object:
        return lambda calls, repeats: speed.Timed("step", int(rate), [1.0])

    def test_a_run_that_beats_the_floor_reports_success(self) -> None:
        code, output = self.run_main(floor=1, taken=self.measuring(1_000))

        self.assertEqual(code, 0)
        self.assertIn("step", output)

    def test_a_machine_with_no_microcode_measures_nothing_and_says_so(self) -> None:
        real = snesdsp.why_not
        snesdsp.why_not = lambda *_, **__: "no image is on this machine"
        try:
            code, output = self.run_main(repeats=1, calls=200, floor=1)
        finally:
            snesdsp.why_not = real

        self.assertEqual(code, 0)
        self.assertIn("nothing measured", output)

    def test_a_floor_nothing_could_beat_fails_the_run(self) -> None:
        code, output = self.run_main(floor=10**12, taken=self.measuring(1_000))

        self.assertEqual(code, 1)
        self.assertIn("below", output)

    def test_a_run_at_exactly_the_shipped_floor_is_not_below_it(self) -> None:
        exactly = speed.Timed("at the floor", speed.FLOOR, [1.0])

        self.assertGreater(speed.FLOOR, 0)
        self.assertTrue(exactly.beats(speed.FLOOR))
        self.assertIn(f"{speed.FLOOR:,}", "\n".join(speed.lines_for(exactly, speed.FLOOR)))


class OnThisMachineTest(unittest.TestCase):
    def test_a_run_with_nothing_handed_in_reports_and_succeeds(self) -> None:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = speed.main(calls=200, repeats=1, floor=1)

        self.assertEqual(code, 0)
        self.assertTrue(captured.getvalue().strip())


if __name__ == "__main__":
    unittest.main()
