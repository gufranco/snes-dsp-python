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


def an_exchange(**changes):
    found = {
        "name": "multiply 2 by 3",
        "ram": 0,
        "transparent": 0,
        "port": [
            ["w", 0x09],
            ["w", 0x02],
            ["w", 0x00],
            ["w", 0x03],
            ["w", 0x00],
            ["r", 0x06],
            ["r", 0x00],
            ["r", 0x00],
            ["r", 0x00],
        ],
    }
    found.update(changes)
    return found


class ReplayTest(unittest.TestCase):
    def test_a_recorded_exchange_is_answered_the_same_way(self):
        self.assertEqual(corpus.replay(an_exchange()), [0x06, 0x00, 0x00, 0x00])

    def test_the_transparent_colour_is_taken_from_the_recording(self):
        exchange = an_exchange(
            transparent=0x02,
            port=[["w", 0x05], ["w", 0x01], ["w", 0x11], ["w", 0x22], ["r", 0x11]],
        )

        self.assertEqual(corpus.replay(exchange), [0x11])

    def test_a_recording_without_a_colour_still_replays(self):
        exchange = an_exchange()
        del exchange["transparent"]

        self.assertEqual(corpus.replay(exchange), [0x06, 0x00, 0x00, 0x00])

    def test_a_recording_without_a_parameter_ram_starts_from_zeroes(self):
        exchange = an_exchange()
        del exchange["ram"]

        self.assertEqual(corpus.replay(exchange), [0x06, 0x00, 0x00, 0x00])


class CheckTest(unittest.TestCase):
    def test_a_matching_exchange_reports_nothing(self):
        self.assertEqual(corpus.check(an_exchange()), [])

    def test_a_disagreement_names_the_read_that_differs(self):
        wrong = an_exchange()
        wrong["port"][5] = ["r", 0x99]

        self.assertEqual(corpus.check(wrong), [(0, 0x99, 0x06)])


class RunTest(unittest.TestCase):
    def test_a_run_counts_what_agreed_and_what_did_not(self):
        passed, failed, examples = corpus.run([an_exchange(), an_exchange()])

        self.assertEqual((passed, failed), (2, 0))
        self.assertEqual(examples, [])

    def test_a_failing_exchange_is_kept_as_an_example(self):
        wrong = an_exchange()
        wrong["port"][5] = ["r", 0x99]

        passed, failed, examples = corpus.run([wrong])

        self.assertEqual((passed, failed), (0, 1))
        self.assertEqual(examples[0][0], "multiply 2 by 3")

    def test_only_a_few_examples_are_kept(self):
        wrong = an_exchange()
        wrong["port"][5] = ["r", 0x99]

        _, _, examples = corpus.run([wrong] * 50)

        self.assertLessEqual(len(examples), corpus.EXAMPLE_LIMIT)

    def test_an_exchange_that_raises_is_counted_rather_than_ending_the_run(self):
        broken = an_exchange(port="not a list of pairs")

        passed, failed, examples = corpus.run([broken, an_exchange()])

        self.assertEqual((passed, failed), (1, 1))
        self.assertEqual(examples[0][1][0], -1)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="corpus-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, exchanges):
        path = Path(self.root) / "corpus.json"
        path.write_text(json.dumps({"transactions": exchanges}))
        return path

    def run_main(self, argv):
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            code = corpus.main(argv)
        return code, captured.getvalue()

    def test_no_arguments_explains_how_to_call_it(self):
        code, output = self.run_main([])

        self.assertEqual(code, 2)
        self.assertIn("usage", output)

    def test_a_corpus_that_is_not_there_says_so_without_failing_the_build(self):
        code, output = self.run_main([str(Path(self.root) / "absent.json")])

        self.assertEqual(code, 0)
        self.assertIn("no corpus at", output)

    def test_a_matching_corpus_reports_success(self):
        path = self.write([an_exchange(), an_exchange()])

        code, output = self.run_main([str(path)])

        self.assertEqual(code, 0)
        self.assertIn("2 agreed, 0 did not", output)

    def test_a_disagreeing_corpus_names_the_exchange(self):
        wrong = an_exchange()
        wrong["port"][5] = ["r", 0x99]
        path = self.write([wrong])

        code, output = self.run_main([str(path)])

        self.assertEqual(code, 1)
        self.assertIn("multiply 2 by 3", output)

    def test_the_transactions_are_read_from_the_file(self):
        path = self.write([an_exchange()])

        self.assertEqual(len(corpus.transactions(path)), 1)


if __name__ == "__main__":
    unittest.main()
