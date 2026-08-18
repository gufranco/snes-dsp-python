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

corpus = importlib.import_module("corpus")


class DefinitionTest(unittest.TestCase):
    def test_the_repository_ships_a_corpus(self):
        self.assertTrue(corpus.load()["exchanges"])

    def test_the_corpus_names_the_chip_its_answers_came_from(self):
        self.assertIn("snes9x", corpus.load()["reference"])

    def test_the_corpus_carries_the_shapes_it_was_built_from(self):
        found = corpus.load()["shapes"]

        self.assertTrue(found["commands"])
        self.assertTrue(found["lengths"])

    def test_a_corpus_is_read_from_where_it_is_asked_for(self):
        with tempfile.TemporaryDirectory() as where:
            path = Path(where) / "c.json"
            path.write_text(json.dumps({"exchanges": [], "reference": "x", "shapes": {}}))

            self.assertEqual(corpus.load(path)["reference"], "x")


class ShapeTest(unittest.TestCase):
    def test_every_command_the_cartridge_issued_appears_in_an_exchange(self):
        found = corpus.load()
        measured = {int(command) for command in found["shapes"]["commands"]}

        exercised = {
            command for exchange in found["exchanges"] for command, _ in exchange["sequence"]
        }

        self.assertEqual(measured, exercised)

    def test_every_length_the_cartridge_used_appears_in_an_exchange(self):
        found = corpus.load()
        measured = {
            (int(command), tuple(lengths))
            for command, shapes in found["shapes"]["lengths"].items()
            for lengths in shapes
        }

        exercised = {
            (command, tuple(lengths))
            for exchange in found["exchanges"]
            for command, lengths in exchange["sequence"]
        }

        self.assertTrue(measured <= exercised)

    def test_the_shapes_hold_no_payload_byte(self):
        found = corpus.load()["shapes"]

        self.assertEqual(sorted(found), ["commands", "lengths", "transitions"])


class PortTest(unittest.TestCase):
    def test_a_sequence_becomes_port_traffic(self):
        port = corpus.port_for([(0x09, ())], 1)

        self.assertEqual(port[0], ("w", 0x09))

    def test_a_fixed_length_command_takes_the_bytes_it_wants(self):
        port = corpus.port_for([(0x09, ())], 1)

        self.assertEqual(sum(1 for kind, _ in port if kind == "w"), 5)

    def test_a_length_carrying_command_writes_its_length_first(self):
        port = corpus.port_for([(0x06, (4,))], 1)

        self.assertEqual(port[1], ("w", 4))

    def test_a_rescale_writes_both_of_its_lengths(self):
        port = corpus.port_for([(0x0D, (8, 4))], 1)

        self.assertEqual([port[1], port[2]], [("w", 8), ("w", 4)])

    def test_the_same_seed_gives_the_same_traffic(self):
        self.assertEqual(corpus.port_for([(0x01, ())], 7), corpus.port_for([(0x01, ())], 7))

    def test_a_different_seed_gives_different_payload(self):
        self.assertNotEqual(corpus.port_for([(0x01, ())], 7), corpus.port_for([(0x01, ())], 8))


class ReplayTest(unittest.TestCase):
    def test_a_recorded_exchange_is_answered_the_same_way(self):
        exchange = corpus.load()["exchanges"][0]

        self.assertIsNone(corpus.check(exchange))

    def test_a_disagreement_names_the_exchange(self):
        wrong = dict(corpus.load()["exchanges"][0], output_sha256="0" * 64)

        self.assertIn(wrong["name"], corpus.check(wrong))

    def test_an_exchange_that_cannot_run_is_reported_rather_than_raising(self):
        broken = dict(corpus.load()["exchanges"][0], sequence="not a list of pairs")

        self.assertIsNotNone(corpus.check(broken))


class RunTest(unittest.TestCase):
    def test_the_whole_shipped_corpus_agrees(self):
        found = corpus.load()

        passed, failed, examples = corpus.run(found["exchanges"])

        self.assertEqual(failed, 0)
        self.assertEqual(examples, [])
        self.assertEqual(passed, len(found["exchanges"]))

    def test_a_disagreeing_exchange_is_counted_and_kept(self):
        wrong = dict(corpus.load()["exchanges"][0], output_sha256="0" * 64)

        passed, failed, examples = corpus.run([wrong])

        self.assertEqual((passed, failed), (0, 1))
        self.assertEqual(len(examples), 1)

    def test_only_a_few_examples_are_kept(self):
        wrong = dict(corpus.load()["exchanges"][0], output_sha256="0" * 64)

        _, _, examples = corpus.run([wrong] * 50)

        self.assertLessEqual(len(examples), corpus.EXAMPLE_LIMIT)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="corpus-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_main(self, argv):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = corpus.main(argv)
        return code, captured.getvalue()

    def test_no_arguments_runs_the_corpus_that_ships(self):
        code, output = self.run_main([])

        self.assertEqual(code, 0)
        self.assertIn("agreed", output)

    def test_a_corpus_that_is_not_there_is_reported(self):
        code, output = self.run_main([str(Path(self.root) / "absent.json")])

        self.assertEqual(code, 2)
        self.assertIn("no corpus at", output)

    def test_a_disagreeing_corpus_fails_and_names_the_exchange(self):
        found = corpus.load()
        broken = dict(found, exchanges=[dict(found["exchanges"][0], output_sha256="0" * 64)])
        path = Path(self.root) / "broken.json"
        path.write_text(json.dumps(broken))

        code, output = self.run_main([str(path)])

        self.assertEqual(code, 1)
        self.assertIn("1 did not", output)


if __name__ == "__main__":
    unittest.main()
