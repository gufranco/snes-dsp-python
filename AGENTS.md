# Working in this repository

This file is for a coding agent. A person reading it will not be harmed, but
[README.md](README.md) is the document written for them.

## What this project is, in one paragraph

Six Super Nintendo coprocessors that all turn out to be one NEC part running five
different programs. This package loads the program a user already owns and runs
it on a model of the processor, which lives in
[`nec-upd7725-python`](https://github.com/gufranco/nec-upd7725-python) as a
submodule at the root of this repository. Nothing here describes what a command
does, because the microcode is what a command does.

## The authority ladder

Every factual question is answered by the highest rung that has an answer, and a
lower rung never overrules a higher one.

1. **The manufacturer's document.** Anything NEC printed: widths, memory sizes,
   stack depth, clocks per instruction. Pinned fact by fact, with the sentence it
   came from, in the processor's `conformance/hardware.json`.
2. **The part's own program**, run on a model of that documented processor, and
   measurements of what the shipped programs actually do.
3. **A recording from an independent implementation**, for instruction-level
   behaviour nobody documented.
4. **Nothing else.** An emulator, an FPGA core, a wiki and a forum post are rung 3
   at best and rung 4 for anything the manufacturer printed. Widely used is not
   the same as correct: every implementation of this family in the field gives the
   part a sixteen-level stack, and NEC prints four.

When a lower rung disagrees with a higher one, the higher wins and the lower is
corrected. Say so loudly when it happens.

## The one rule that decides most questions

**The microcode is the behaviour. Nothing here describes it.**

There is no table of commands and no formula for a projection. When a part answers
wrongly, the fault is in the loading, the pacing, the bus decode or the processor,
never in a description that needs correcting. If you find yourself writing what a
command means, stop: that knowledge belongs to the program, and putting a copy of
it in this repository creates a second answer that can drift from the first.

## Every gate, in the order to run them

```bash
ruff format --check .                                  # formatting
ruff check .                                           # lint, zero warnings
mypy                                                   # types, strict
pnpm run format:check                                  # every JSON file
for f in snesdsp/*.test.py conformance/*.test.py; do python3 "$f"; done
python3 -m coverage report                             # fails below 100%
```

Coverage is collected by running each test file under `coverage run -a`, not by a
test runner:

```bash
python3 -m coverage erase
for f in snesdsp/*.test.py conformance/*.test.py; do python3 -m coverage run -a "$f"; done
python3 -m coverage report
```

These need a microcode image and report as skipped rather than passed without one,
which is why they are not in the list above:

```bash
python3 conformance/documented.py                # every README example
python3 conformance/against_cartridges.py dsp1   # real cartridge exchanges
python3 conformance/answers.py                   # what each part answered, still
python3 conformance/masks.py                     # where the DSP-1 masks disagree
python3 conformance/record.py                    # re-read every cartridge present
python3 conformance/stack.py                     # stack depth against the documented one
```

The stack measurement takes about twenty minutes, which is why the schedule runs
it rather than every push.

Exit 2 from any of those means the machine had nothing to run. That is not a
failure and must never be reported as one, in CI or anywhere else.

## Things that will bite you

**Run the suite on the oldest Python supported, not only the newest.** Annotations
are evaluated eagerly before 3.14 and lazily from 3.14 on. A file that names a
type imported only under `TYPE_CHECKING` will import fine on 3.14 and raise
`NameError` on 3.12, and every test will pass locally while the package is broken
for most users. Every file that does this carries
`from __future__ import annotations`. If you add such a file, add the import.

```bash
uvx --python 3.12 python snesdsp/silicon.test.py
```

**Run the suite as a machine that holds nothing.** This is the mistake that has
cost the most time here, twice. A test that reaches a default which opens a real
file passes on a workstation holding that file and fails on a runner that does
not, and the local run gives no hint. Point both directories somewhere empty and
run everything before pushing:

```bash
EMPTY=$(mktemp -d)
for f in snesdsp/*.test.py conformance/*.test.py; do
  UPD7725_FIRMWARE_DIR="$EMPTY" SNES_CARTRIDGE_DIR="$EMPTY" python3 "$f" || echo "FAILED $f"
done
```

Every test that could reach a real image supplies its own digest, its own build,
or its own path. A default is for a person at a command line, never for a test.

**Coverage that depends on what the machine holds is not coverage.** A test that
only runs where a microcode image or a cartridge happens to be present is a test
that reports a pass on a machine that ran nothing. Tests needing a file supply
their own. `conformance/cartridges.py` is the one module deliberately outside the
coverage gate, because finding cartridges runs one set of paths on a machine that
has them and another on a machine that does not, and no single build can exercise
both.

**Never commit a cartridge, an image, or any fragment of one.** Not encoded, not
generated, not as a test fixture. What may be committed is a digest, which
identifies a file and reconstructs nothing, and a shape, which names the accesses
a routine makes without a byte of what travelled through them.

**Confirm before reading, not after.** Every cartridge is checked against all four
of its published digests before a byte of it is disassembled. A file that is not
what it claims would be read anyway, and the shapes would then describe somebody's
edit rather than a shipped protocol.

**A corpus is refused, not failed, when the image differs.** Two different images
are entitled to answer differently. `conformance/answers.py` exits 2 and says so
rather than reporting a disagreement that is not one.

**Do not add hand-written test fixtures for cartridge shapes.** They come out of
real games through
[`snes-driver-python`](https://github.com/gufranco/snes-driver-python), which
disassembles the driver routine. A shape somebody invented asks a question no
hardware has an answer for.

## Conventions that are not negotiable

| Thing | Rule |
|:------|:-----|
| Language | Python only. Nothing else, anywhere in the project |
| Comments | None in source, ever. Docstrings carry the reasoning |
| Test layout | `<module>.test.py` beside the module it covers |
| Test structure | Arrange, blank line, one act, blank line, assert. No section labels |
| Coverage | 100% statements and branches, enforced |
| Types | `mypy` at strict, plus every optional error class the version offers |
| Commits | [Conventional Commits](https://www.conventionalcommits.org/); subject under 50 characters |
| Releases | semantic-release from `main`; never tag by hand |
| Microcode and cartridges | Never committed, never vendored, never encoded, never generated |

Docstrings explain why, not what. A docstring restating the function name is
worse than none, because it takes space a reason could have used.

## Layout

```
snesdsp/
  __init__.py     the package, and the part chosen at construction
  models.py       which parts exist, what they answer to, which image each runs
  silicon.py      loading an image and driving the part it belongs to
  timing.py       the two oscillators, and how long the console leaves the part
  doctor.py       what is actually on this machine, printed for a bug report
  version.py      rewritten by the release job and by nothing else
conformance/
  driven.py              what these runs need a part to be, as a protocol
  shapes.py              reading and replaying a cartridge's exchanges
  cartridges.py          finding and confirming the cartridges, outside the gate
  record.py              re-reading every cartridge present, pooling per part
  against_cartridges.py  driving a part with those exchanges
  answers.py             what each part answered, and whether it still does
  masks.py               where the three masks of the DSP-1 disagree
  documented.py          every example the README prints, run against the parts
nec-upd7725-python/      the processor all of these are, as a submodule
cartridges/              a user's own copies; nothing here is ever committed
firmware/                the same, for microcode images
```

## Adding a part to the family

`snesdsp/models.py` holds the catalogue. A new entry needs the image it runs, the
processor underneath it, and every name the part answers to. If it shares an image
with an existing part, say so through `SHARES_IMAGE` in `silicon.py` rather than
duplicating the entry: that relationship is what lets a machine holding one file
drive both parts, and it is also why a mask comparison between two parts sharing
an image would be meaningless.

The manifest in the processor repository declares the image and its digests. A
part naming an image the manifest does not declare fails
`snesdsp/models.test.py`, which is the intended behaviour.

## What a change is expected to leave behind

A gate that would have caught the bug. A fix with no test that fails without it
is not finished. If the bug was in something a machine without an image cannot
check, say so plainly in the change rather than leaving the gap unmarked.
