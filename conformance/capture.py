"""Turn a recording of real chip traffic into a shape profile.

This is the half of the corpus work that can be published. A recording of a
cartridge talking to its DSP-2 contains two very different things, and they have
to be separated before anything leaves your machine.

The payload bytes are the game's artwork. They cannot be distributed, and this
tool never writes one out.

The shape of the traffic is not artwork. Which commands the cartridge issues, in
what order, and with which lengths are functional facts about how a program
drives a peripheral. A profile of those is what this produces, and it is what the
shipped corpus is generated from: real shapes, filled with synthetic payloads,
with expected outputs computed by the reference decoder.

So a recording of a game you own contributes its behaviour to the test suite
without contributing any of its content.

The log format is deliberately dumb. It is a stream of fixed size records, each
carrying a kind byte and a value byte at offsets you name, so a trace from any
emulator or logic capture can be read by pointing the offsets at the right
columns rather than by writing a new parser.
"""

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dsp2 import Chip

WRITE = "w"
READ = "r"

DEFAULT_RECORD_SIZE = 2
DEFAULT_KIND_OFFSET = 0
DEFAULT_VALUE_OFFSET = 1

LENGTH_COMMANDS = (0x05, 0x06, 0x0D)


class TruncatedLog(Exception):
    pass


def events(
    path,
    record_size=DEFAULT_RECORD_SIZE,
    kind_offset=DEFAULT_KIND_OFFSET,
    value_offset=DEFAULT_VALUE_OFFSET,
):
    """Every port event in a log, as a write or a read of one byte."""
    with Path(path).open("rb") as handle:
        while True:
            record = handle.read(record_size)
            if not record:
                return
            if len(record) != record_size:
                raise TruncatedLog(
                    f"{len(record)} trailing bytes, expected a record of {record_size}"
                )
            yield (WRITE if record[kind_offset] == 0 else READ, record[value_offset])


def shapes(port):
    """What the traffic did, with none of what it carried.

    The framing is worked out by driving a real chip, because the framing is not
    something a reader can infer: whether a byte is a command, a length or data
    depends on state the chip is carrying from earlier commands.
    """
    chip = Chip(fill=0)
    commands = collections.Counter()
    lengths = collections.defaultdict(set)
    transitions = collections.Counter()
    previous = None

    for kind, value in port:
        if kind == READ:
            chip.read()
            continue

        starting = chip.waiting_for_command
        chip.write(value)

        if starting:
            commands[value] += 1
            if previous is not None:
                transitions[(previous, value)] += 1
            previous = value
            continue

        if previous == 0x05 and chip.merge_armed and chip.in_index == 0:
            lengths[0x05].add((chip.merge_length,))
        elif previous == 0x06 and chip.mirror_armed and chip.in_index == 0:
            lengths[0x06].add((chip.mirror_length,))
        elif previous == 0x0D and chip.scale_armed and chip.in_index == 0:
            lengths[0x0D].add((chip.scale_in_length, chip.scale_out_length))

    return {
        "comment": (
            "Command shapes measured from real cartridge traffic. Commands, their "
            "order and their lengths are functional facts about how a program drives "
            "the chip. No payload byte is recorded here."
        ),
        "commands": {str(command): count for command, count in sorted(commands.items())},
        "lengths": {
            str(command): [list(found) for found in sorted(lengths[command])]
            for command in sorted(lengths)
        },
        "transitions": sorted([str(first), str(second)] for first, second in transitions),
    }


def main(argv):
    if not argv:
        print("usage: capture.py <port log> <shapes out> [record size] [kind at] [value at]")
        return 2

    path = Path(argv[0])
    if not path.is_file():
        print(f"  no log at {path}")
        return 2

    if len(argv) < 2:
        print("usage: capture.py <port log> <shapes out> [record size] [kind at] [value at]")
        return 2

    record_size = int(argv[2]) if len(argv) > 2 else DEFAULT_RECORD_SIZE
    kind_offset = int(argv[3]) if len(argv) > 3 else DEFAULT_KIND_OFFSET
    value_offset = int(argv[4]) if len(argv) > 4 else DEFAULT_VALUE_OFFSET

    found = shapes(events(path, record_size, kind_offset, value_offset))
    Path(argv[1]).write_text(json.dumps(found, indent=2) + "\n")

    total = sum(found["commands"].values())
    print(f"  {total} commands, {len(found['commands'])} kinds, from {path}")
    print(f"  {sum(len(v) for v in found['lengths'].values())} distinct length shapes")
    print(f"  written to {argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
