"""Replay a corpus of real chip traffic against this model.

The DSP-2 has no published per-instruction suite, so the oracle here is a
recording of a real cartridge talking to a real chip: every byte written, every
byte read back. Replaying it proves the model answers what the hardware answered
for the traffic that was recorded.

A corpus is not distributed with this repository and never will be. The bytes a
DSP-2 returns are the game's own graphics, and shipping a recording of them ships
the artwork. A corpus is made from a cartridge the person running it already
owns, and the file stays on their machine. When none is present the run says so
and passes, because a missing recording is not a failing model.

That leaves a gap this file is honest about. A recording only covers what the
game happened to ask for. The exhaustive checks beside the commands cover the
rest, and they are the stronger of the two: a bit permutation proved over all 256
of its inputs is not improved by watching a game use it.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsp2 import Chip

EXAMPLE_LIMIT = 5

WRITE = "w"
READ = "r"


def transactions(path):
    """Every recorded exchange in a corpus file, in the order it happened."""
    with Path(path).open() as handle:
        return json.load(handle)["transactions"]


def replay(exchange, fill=0):
    """Run one recorded exchange, returning what this model answered.

    The parameter RAM starts from the state the recording captured, because the
    rescale reads past its payload into whatever the previous command left there.
    A corpus that did not record it gets zeroes, and says so by omission.
    """
    machine = Chip(fill=exchange.get("ram", fill))
    if "transparent" in exchange:
        machine.transparent = exchange["transparent"]

    answered = []
    for kind, value in exchange["port"]:
        if kind == WRITE:
            machine.write(value)
        else:
            answered.append(machine.read())
    return answered


def check(exchange):
    """Where this model and the recording disagree, byte by byte."""
    answered = replay(exchange)
    expected = [value for kind, value in exchange["port"] if kind == READ]
    return [
        (index, want, got)
        for index, (want, got) in enumerate(zip(expected, answered, strict=False))
        if want != got
    ]


def run(recorded):
    """How many exchanges agreed, how many did not, and a few that did not."""
    passed = failed = 0
    examples = []
    for exchange in recorded:
        try:
            wrong = check(exchange)
        except Exception as error:  # noqa: BLE001
            wrong = [(-1, type(error).__name__, str(error)[:60])]
        if wrong:
            failed += 1
            if len(examples) < EXAMPLE_LIMIT:
                examples.append((exchange.get("name", "?"), wrong[0]))
        else:
            passed += 1
    return passed, failed, examples


def main(argv):
    if not argv:
        print("usage: corpus.py <corpus file>")
        return 2

    path = Path(argv[0])
    if not path.is_file():
        print(f"  no corpus at {path}; make one from a cartridge you own")
        return 0

    passed, failed, examples = run(transactions(path))
    print(f"  {passed + failed} exchanges from {path}")
    print(f"  {passed} agreed, {failed} did not")
    for name, (index, want, got) in examples:
        print(f"    {name}: first at read {index}, want {want} got {got}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
