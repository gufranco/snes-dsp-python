"""Ask every part its own questions once, and write down what it said.

This needs an image of each part's microcode and is therefore run by hand, on a
machine that holds them, whenever the questions change. What it produces runs
everywhere: `conformance/against_part.py` replays it against the models on
machines that will never hold an image.

Nothing it writes belongs to anybody. The questions are arithmetic from a seed,
and the answers are a handful of bytes each part produced from them.

Usage:
    python3 conformance/record_parts.py <corpus.json> [seeds]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import against_part

from snesdsp import silicon

RECORDED_FROM = "each part's own microcode, run on the processor it is masked into"


class Usage(Exception):
    pass


def record_all(seeds, parts=None, build=against_part._silicon, say=print):
    """Every part, every command, every seed."""
    cases = []
    for part in parts if parts is not None else sorted(against_part.PROFILES):
        say(f"  {part}...")
        cases.extend(against_part.record(part, seeds, build=build))
    return cases


def gaps_of(cases):
    """Where the models do not answer what the parts answered, one line each."""
    found = against_part.measured({"cases": cases})
    return [
        {
            "part": part,
            "command": command,
            "seed": seed,
            "indices": list(indices),
            "note": (
                f"{part} command {command:#04x}: the model does not yet answer what"
                " the part answers here"
            ),
        }
        for (part, command, seed), indices in sorted(found.items())
    ]


def write_out(where, seeds, build=against_part._silicon, say=print):
    """The corpus file, with what it is and where its answers came from."""
    cases = record_all(seeds, build=build, say=say)
    held = {
        "note": (
            "Recorded from the parts themselves, which are the authority on what"
            " they answer. The scripts are arithmetic from a seed and carry nothing"
            " belonging to anybody."
        ),
        "recordedFrom": RECORDED_FROM,
        "cases": cases,
        "knownGapsNote": (
            "Every byte named here is a place a model does not yet answer what its"
            " part answered. It is a gate rather than an excuse: fixing one removes"
            " a line, breaking one adds a line, and either way the check fails until"
            " the change is written down."
        ),
        "knownGaps": gaps_of(cases),
    }
    Path(where).write_text(json.dumps(held, indent=2) + "\n")
    return held


def main(argv, why_not=silicon.why_not, build=against_part._silicon, say=print):
    if not argv:
        raise Usage("usage: record_parts.py <corpus.json> [seeds]")

    reason = why_not()
    if reason:
        say(f"  nothing was recorded: {reason}")
        return 2

    where = argv[0]
    count = argv[1] if len(argv) > 1 else str(against_part.DEFAULT_SEEDS)
    if not count.isdigit():
        raise Usage(f"{count} is not a number of seeds")

    held = write_out(Path(where), range(int(count)), build=build, say=say)
    say(f"  {len(held['cases'])} scripts recorded, {len(held['knownGaps'])} gaps written down")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Usage as refusal:
        print(refusal)
        sys.exit(2)
