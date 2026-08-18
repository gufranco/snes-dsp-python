"""Replay a corpus shaped by a real cartridge against this model.

The DSP-2 has no published per-instruction suite, so the evidence here is a
recording of a real cartridge driving a real chip. What is recorded, and what is
shipped, are deliberately not the same thing.

**What a recording contains, and what leaves the machine.** A recording holds two
separable things. The payload bytes are the game's graphics, encoded; they are the
protected work and they never leave. The *shape* of the traffic is which commands
the program issued, in what order, and with which lengths. That is a description
of how a program drives a peripheral: functional, dictated by the chip's
interface rather than authored, and the kind of thing copyright does not reach
(17 U.S.C. 102(b), and Feist for facts). `capture.py` produces the shape and
never writes a payload byte.

**How this corpus was built.** The shapes in `corpus.json` were measured from
1.8 million real commands issued by a cartridge. Every command it uses, every
length it asks for, and every transition between commands is reproduced here.
The payload bytes filling those shapes are generated from a seed by `port_for`
below, so they are arithmetic rather than artwork. The expected answers were then
computed by the reference chip, not by this implementation, which is what makes
agreement a cross-check rather than a restatement.

So the corpus is real in the way that matters and synthetic in the way that must
be. A bug that only shows up on a length the cartridge actually uses is caught
here; a byte of the game is not.

**Running the full check on your own cartridge.** Nothing above replaces
decoding real payloads. If you own the game, `capture.py` records your own
traffic and this replays it. That check stays on your machine, which is the whole
reason the shipped corpus is built the way it is.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsp2 import Chip

EXAMPLE_LIMIT = 5

DEFAULT_CORPUS = Path(__file__).resolve().parent / "corpus.json"

WRITE = "w"
READ = "r"

FIXED_PAYLOAD = {0x01: 32, 0x03: 1, 0x09: 4}
FIXED_OUTPUT = {0x01: 32, 0x09: 4}

TRAILING_READS = 2
"""Reads taken past the end of each result, to see the chip report itself idle."""


def load(path=None):
    """The corpus, from where it was asked for or from the one that ships."""
    with Path(path or DEFAULT_CORPUS).open() as handle:
        return json.load(handle)


def port_for(sequence, seed):
    """The port traffic one sequence of real command shapes produces.

    The commands and lengths come from the cartridge. The payload bytes come from
    the seed, which is what keeps the game's data out of this repository while
    leaving the traffic the same shape the hardware saw.
    """
    rng = random.Random(seed)
    port = []
    for command, lengths in sequence:
        port.append((WRITE, command))

        if command in FIXED_PAYLOAD:
            payload = FIXED_PAYLOAD[command]
        elif command == 0x05:
            port.append((WRITE, lengths[0]))
            payload = 2 * lengths[0]
        elif command == 0x06:
            port.append((WRITE, lengths[0]))
            payload = lengths[0]
        elif command == 0x0D:
            port.append((WRITE, lengths[0]))
            port.append((WRITE, lengths[1]))
            payload = (lengths[0] + 1) >> 1
        else:
            payload = 0

        for _ in range(payload):
            port.append((WRITE, rng.randrange(256)))

        produced = FIXED_OUTPUT.get(command, lengths[-1] if lengths else 0)
        for _ in range(produced + TRAILING_READS):
            port.append((READ, 0))
    return port


def replay(exchange):
    """What this model answers for one exchange, byte for byte."""
    chip = Chip(fill=bytes(random.Random(exchange["ram_seed"]).randbytes(512)))
    chip.transparent = exchange["transparent"]

    answered = []
    for kind, value in port_for(
        [(command, tuple(lengths)) for command, lengths in exchange["sequence"]],
        exchange["payload_seed"],
    ):
        if kind == WRITE:
            chip.write(value)
        else:
            answered.append(chip.read())
    return bytes(answered)


def check(exchange):
    """What went wrong with one exchange, or nothing when it agreed."""
    try:
        answered = replay(exchange)
    except Exception as error:  # noqa: BLE001
        return f"{exchange.get('name', '?')}: {type(error).__name__}"

    digest = hashlib.sha256(answered).hexdigest()
    if digest == exchange["output_sha256"]:
        return None
    return (
        f"{exchange['name']}: want {exchange['output_sha256'][:16]} "
        f"got {digest[:16]}, {len(answered)} bytes read"
    )


def run(exchanges):
    """How many exchanges agreed, how many did not, and a few that did not."""
    passed = failed = 0
    examples = []
    for exchange in exchanges:
        wrong = check(exchange)
        if wrong is None:
            passed += 1
        else:
            failed += 1
            if len(examples) < EXAMPLE_LIMIT:
                examples.append(wrong)
    return passed, failed, examples


def main(argv):
    path = Path(argv[0]) if argv else DEFAULT_CORPUS
    if not path.is_file():
        print(f"  no corpus at {path}")
        return 2

    found = load(path)
    passed, failed, examples = run(found["exchanges"])
    commands = sum(int(count) for count in found["shapes"]["commands"].values())
    print(f"  {passed + failed} exchanges from {path}, against {found['reference']}")
    print(f"  shapes measured from {commands} real commands")
    print(f"  {passed} agreed, {failed} did not")
    for line in examples:
        print(f"    {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
