"""Every example printed in the README, run against the parts themselves.

A number in a document is a claim about the code, and the only ones worth
printing are the ones something checks. These are the snippets a reader will copy
out of the README, in the order they appear there, each paired with the answer
the README says they give.

Without microcode this reports that it had nothing to run rather than passing,
because a documentation check that quietly skips is how documentation goes stale
in the first place.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import Dsp, silicon


def _word(chip, value):
    chip.write(value & 0xFF)
    chip.write(value >> 8)


def dsp1_multiply(build):
    chip = build("dsp1")
    chip.write(0x00)
    for value in (0x4000, 0x2000):
        _word(chip, value)
    low, high = chip.read(), chip.read()
    return hex(low | (high << 8))


def dsp1a_runs_the_dsp1_image(build):
    return build("dsp1a").identity.part


def dsp1b_runs_its_own(build):
    return build("dsp1b").identity.part


def dsp1b_multiply(build):
    chip = build("dsp1b")
    chip.write(0x00)
    for value in (0x4000, 0x2000):
        _word(chip, value)
    low, high = chip.read(), chip.read()
    return hex(low | (high << 8))


def dsp2_multiply(build):
    chip = build("dsp2")
    chip.write(0x09)
    for value in (0x0002, 0x0003):
        _word(chip, value)
    return str([hex(chip.read()) for _ in range(4)])


def dsp3_echoes_the_last_word(build):
    chip = build("dsp3")
    for byte in (0x1C, 0x00):
        chip.write(byte)
    for byte in (0x34, 0x12, 0x78, 0x56):
        chip.write(byte)
    return " ".join(f"{chip.read():02x}" for _ in range(8))


def dsp4_answers_a_batch(build):
    chip = build("dsp4")
    chip.write(0x01)
    chip.write(0x00)
    for value in (0x0001, 0x0002, 0x0003, 0x0004):
        _word(chip, value)
    return str([hex(chip.read()) for _ in range(6)])


DOCUMENTED = (
    ("dsp1 multiply", dsp1_multiply, "0x1000"),
    ("dsp1a runs the dsp1 image", dsp1a_runs_the_dsp1_image, "dsp1"),
    ("dsp1b runs its own", dsp1b_runs_its_own, "dsp1b"),
    ("dsp1b multiply", dsp1b_multiply, "0x1000"),
    ("dsp2 multiply", dsp2_multiply, "['0x6', '0x0', '0x0', '0x0']"),
    ("dsp3 echoes the last word", dsp3_echoes_the_last_word, "78 56 78 56 78 56 78 56"),
    (
        "dsp4 answers a batch",
        dsp4_answers_a_batch,
        "['0x4', '0x0', '0x4', '0x0', '0x4', '0x0']",
    ),
)


def run(build=Dsp, documented=DOCUMENTED):
    """Each example, what the README says it gives, and what it gave here."""
    return tuple((name, wanted, example(build)) for name, example, wanted in documented)


def disagreements(found):
    """The rows where the document and the part do not say the same thing."""
    return tuple(one for one in found if one[1] != one[2])


def lines_for(found):
    wrong = disagreements(found)
    said = [f"{len(found)} examples from the README, run against the parts"]
    said.extend(
        f"  {'ok  ' if wanted == got else '   !'}  {name}: {got}" for name, wanted, got in found
    )
    if wrong:
        said.append(f"  {len(wrong)} of {len(found)} do not give what the README says")
        said.extend(
            f"    {name}: README says {wanted}, this gave {got}" for name, wanted, got in wrong
        )
    else:
        said.append("  every one gives what the README says it gives")
    return said


def main(argv=(), why_not=silicon.why_not, build=Dsp, documented=DOCUMENTED, say=print):
    reason = why_not()
    if reason:
        say(f"nothing to run: {reason}")
        return 2
    found = run(build, documented)
    for line in lines_for(found):
        say(line)
    return 1 if disagreements(found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
