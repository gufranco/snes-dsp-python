import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "conformance"))

capture = importlib.import_module("capture")


def a_log(events, record_size=2, kind_offset=0, value_offset=1):
    blob = bytearray()
    for kind, value in events:
        record = bytearray(record_size)
        record[kind_offset] = kind
        record[value_offset] = value
        blob += record
    return bytes(blob)


MULTIPLY = [(0, 0x09), (0, 0x02), (0, 0x00), (0, 0x03), (0, 0x00)] + [(1, 0)] * 4


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="capture-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, blob, name="trace.bin"):
        path = Path(self.root) / name
        path.write_bytes(blob)
        return path

    def test_a_log_of_pairs_reads_back_as_events(self):
        path = self.write(a_log(MULTIPLY))

        found = list(capture.events(path))

        self.assertEqual(len(found), len(MULTIPLY))

    def test_a_write_is_told_apart_from_a_read(self):
        path = self.write(a_log([(0, 0x09), (1, 0x00)]))

        self.assertEqual(list(capture.events(path)), [("w", 0x09), ("r", 0x00)])

    def test_a_wider_record_is_read_at_the_offsets_it_is_given(self):
        path = self.write(a_log([(0, 0x09)], record_size=28, kind_offset=16, value_offset=17))

        found = list(capture.events(path, record_size=28, kind_offset=16, value_offset=17))

        self.assertEqual(found, [("w", 0x09)])

    def test_a_trailing_part_record_is_refused(self):
        path = self.write(a_log(MULTIPLY) + b"\x00")

        with self.assertRaises(capture.TruncatedLog):
            list(capture.events(path))

    def test_an_empty_log_reads_as_nothing(self):
        path = self.write(b"")

        self.assertEqual(list(capture.events(path)), [])


class ShapeTest(unittest.TestCase):
    def test_a_command_is_counted(self):
        found = capture.shapes([("w", 0x09), ("w", 2), ("w", 0), ("w", 3), ("w", 0)])

        self.assertEqual(found["commands"]["9"], 1)

    def test_a_length_is_recorded_with_its_command(self):
        found = capture.shapes([("w", 0x06), ("w", 4), *[("w", 0)] * 4])

        self.assertIn("6", found["lengths"])
        self.assertIn([4], found["lengths"]["6"])

    def test_a_merge_length_is_recorded_with_its_command(self):
        found = capture.shapes([("w", 0x05), ("w", 2), *[("w", 0)] * 4])

        self.assertIn([2], found["lengths"]["5"])

    def test_a_rescale_records_both_of_its_lengths(self):
        found = capture.shapes([("w", 0x0D), ("w", 8), ("w", 4), *[("w", 0)] * 4])

        self.assertIn([8, 4], found["lengths"]["13"])

    def test_a_transition_between_commands_is_recorded(self):
        found = capture.shapes([("w", 0x0F), ("w", 0x09), ("w", 0), ("w", 0), ("w", 0), ("w", 0)])

        self.assertIn(["15", "9"], found["transitions"])

    def test_reads_do_not_disturb_the_framing(self):
        with_reads = capture.shapes([("w", 0x09), ("r", 0), ("w", 2), ("w", 0), ("w", 3), ("w", 0)])

        self.assertEqual(with_reads["commands"]["9"], 1)

    def test_no_payload_byte_is_carried_into_the_shapes(self):
        found = capture.shapes([("w", 0x06), ("w", 2), ("w", 0xAB), ("w", 0xCD)])

        self.assertNotIn("0xAB", json.dumps(found))
        self.assertNotIn("171", json.dumps(found["lengths"]))


class MainTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="capture-main-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_main(self, argv):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = capture.main(argv)
        return code, captured.getvalue()

    def test_no_arguments_explains_how_to_call_it(self):
        code, output = self.run_main([])

        self.assertEqual(code, 2)
        self.assertIn("usage", output)

    def test_a_log_that_is_not_there_is_reported(self):
        code, output = self.run_main([str(Path(self.root) / "absent.bin")])

        self.assertEqual(code, 2)
        self.assertIn("no log at", output)

    def test_a_log_with_nowhere_to_write_explains_how_to_call_it(self):
        path = Path(self.root) / "trace.bin"
        path.write_bytes(a_log(MULTIPLY))

        code, output = self.run_main([str(path)])

        self.assertEqual(code, 2)
        self.assertIn("usage", output)

    def test_a_log_is_turned_into_a_shape_profile(self):
        path = Path(self.root) / "trace.bin"
        path.write_bytes(a_log(MULTIPLY))
        out = Path(self.root) / "shapes.json"

        code, _ = self.run_main([str(path), str(out)])

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.read_text())["commands"]["9"], 1)

    def test_the_profile_reports_what_it_saw(self):
        path = Path(self.root) / "trace.bin"
        path.write_bytes(a_log(MULTIPLY))

        code, output = self.run_main([str(path), str(Path(self.root) / "shapes.json")])

        self.assertEqual(code, 0)
        self.assertIn("1 commands", output)


if __name__ == "__main__":
    unittest.main()
