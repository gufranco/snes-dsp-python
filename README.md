<div align="center">

<h1>SNES DSP Family</h1>

<strong>The NEC uPD77C25 as Nintendo shipped it, with its commands proved rather than sampled.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#models">The family</a> &nbsp;|&nbsp;
  <a href="#the-dsp-2-commands">Commands</a> &nbsp;|&nbsp;
  <a href="#how-this-is-proved">How this is proved</a> &nbsp;|&nbsp;
  <a href="#the-corpus-and-why-it-can-ship">Why the corpus is legal</a> &nbsp;|&nbsp;
  <a href="#the-rescale-reads-past-its-own-data">The rescale</a> &nbsp;|&nbsp;
  <a href="#models">The DSP-4</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/snes-dsp-python/issues">Issues</a>
</p>

**4** microcodes · **5** models, counting both masks of the DSP-1 · **65** commands · **7** renderers that suspend and resume · **1** exhaustively proved bit permutation · shapes from **1,804,133** real cartridge commands · **851,132** bytes agreeing with snes9x · **500** tests · **100%** statement and branch coverage

```python
from snesdsp import Dsp

chip = Dsp(model="dsp2")

chip.write(0x09)
for byte in (0x02, 0x00, 0x03, 0x00):
    chip.write(byte)

[chip.read() for _ in range(4)]
# [6, 0, 0, 0]
```

```python
from snesdsp import Dsp

road = Dsp(model="dsp4")

road.write(0x01)
road.write(0x00)
for byte in opening_stretch:
    road.write(byte)

road.out_count
# how many bytes of scanline this stretch produced
```

---

## The problem

None of these chips has a published per-instruction test suite the way a 6502 or a Z80 does, and none ever will. They are one NEC uPD77C25 with Nintendo's microcode masked into it, and the microcode is what makes each of them a different chip. The DSP-2 modelled here shipped in exactly one cartridge, so its sample size is one game.

The usual answer is to record the real chip and replay the recording. That works, and it has a ceiling. A recording only covers what that one game happened to ask for, so the moment you use the model for anything else, you are outside what was ever tested. It is also the game's own artwork, which makes shipping it a redistribution problem rather than a testing one.

## The solution

Separate what each command computes from the protocol that feeds it, then prove the commands directly.

Five of the six commands are pure functions of their input, and each one has an input space small enough or structured enough to be settled rather than sampled. The tile conversion is a permutation of the 256 bits it is given, so 256 single-bit inputs pin where every bit lands and nothing can be hiding. The merge is a per-nibble rule, so every combination of colour and byte it accepts is checked. The multiply is checked against arithmetic. That is a stronger claim than any recording supports.

The recording still has a job, and it is kept: this model agrees byte for byte with a reference that reproduced **71,970,987 bytes** of real recorded traffic with zero errors, over 1,139,246 reads of randomised command streams that reach lengths the game never used.

The DSP-4 does not fit that argument, and gets a different one. It is a renderer rather than a calculator: nothing it does is a small pure function, and several of its commands cannot finish in one go. So it is held to a corpus of roads generated from seeds and answered by the chip's own reference, 140 of them and 725,032 bytes, covering every one of its seven renderers. That comparison found two defects in this model and one in the reference.

Those corpora are recordings. They were taken from the reference implementations once and are replayed here forever after, which is why this repository is Python throughout and needs nothing else installed to check itself. New evidence now comes from a stronger direction: the microcode the cartridge itself carries, run on a model of the processor it is masked into.

<table>
<tr>
<td width="50%" valign="top">

### Proved, not sampled

The bit permutation is settled by 256 one-hot inputs. The merge is checked over every input it accepts. Neither is a spot check.

</td>
<td width="50%" valign="top">

### Nothing starts clean

The parameter RAM is scrambled by default, because the chip never clears it and one command reads straight into whatever is there.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### Commands split from protocol

The five transforms are plain functions with no notion of a port. That separation is what makes them provable at all.

</td>
<td width="50%" valign="top">

### It never redistributes a game

No recording ships here, and none ever will. The bytes this chip returns are the artwork.

</td>
</tr>
</table>

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | >= 3.12 | [python.org](https://www.python.org/downloads/) |

### Setup

```bash
git clone https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
```

### Verify

```bash
python3 snesdsp/commands.test.py
# Ran 33 tests in 0.03s
# OK
```

## The DSP-2 commands

Everything reaches the chip through one byte-wide port: a command, then any lengths it needs, then its data. Results leave the same way, a byte at a time, and reading past the end gives `$FF`.

| Command | Byte | Takes | Gives |
|:--------|:----:|:------|:------|
| Tile conversion | `$01` | 32 bytes | 32 bytes, rearranged into bit planes |
| Transparent colour | `$03` | 1 byte | nothing; it sets state the merge reads |
| Merge | `$05` | a length, then two runs of it | one run, overlaid |
| Mirror | `$06` | a length, then that many bytes | the run reversed, with each byte's pixels swapped |
| Multiply | `$09` | 4 bytes | a 32-bit product |
| Rescale | `$0D` | two lengths, then half the input | the output length, resampled |
| Sync | `$0F` | nothing | nothing |

A command the chip does not recognise produces nothing and leaves it ready for the next one.

## The rescale reads past its own data

This is the behaviour that makes the parameter RAM part of the model rather than an implementation detail.

```python
from snesdsp import Dsp

chip = Dsp(fill=0)
chip.parameter_ram[60] = 0xAB

chip.write(0x0D)
chip.write(120)
chip.write(120)
for _ in range(60):
    chip.write(0x00)

bytes(chip.read() for _ in range(120))[60]
# 0xAB, which was never sent as part of this command
```

The walk is bounded by the **output** length, not by the data it was given. With the step at one unit, which is every case where the input is no longer than the output, it reads 120 bytes from a 60-byte payload. What it finds past the payload is whatever the previous command left behind, because the chip never clears its RAM.

> [!IMPORTANT]
> An earlier implementation padded with zeroes and agreed with every recorded run anyway, because in those runs the reads past the payload happened to land on bytes that were still zero. It disagreed everywhere else. This is exactly the class of bug that a clean-start model hides and a scrambled one exposes.

## How this is proved

| Command | Oracle | Strength |
|:--------|:-------|:---------|
| Tile conversion | 256 one-hot inputs, one per bit | Exhaustive. A bit permutation is fully determined by where each single bit lands |
| Merge | Every colour against a spread of byte pairs, checked against the nibble rule | Exhaustive over the rule's inputs |
| Multiply | Compared against arithmetic across the 16-bit range | Settled |
| Mirror | Reversal and nibble-swap properties, plus its own inverse | Settled |
| Rescale | Fixed-point walk, including reads past the payload and wrapping in RAM | Behavioural |
| Whole chip | 95,784 reads against snes9x's own `dsp2.cpp` | Differential, independent implementation |
| Real command shapes | Every command, length and transition a cartridge actually uses | Measured from 1,804,133 real commands |

The differential is the one that ties this to real hardware, and it found a real bug. The chip latches per command whether a length has already been given, and decides whether data follows by looking at the length byte itself. A length of zero therefore does not cancel a command; it arms one, and the next byte on the port is read as a new command. A tidier model that resets on a zero length passes every ordinary test and answers differently here.

### The corpus, and why it can ship

The DSP-2 has no published per-instruction suite, so the evidence is a recording of a real cartridge driving a real chip. A recording holds two separable things, and only one of them can leave your machine.

| Part of a recording | What it is | Ships? |
|:--------------------|:-----------|:-------|
| Payload bytes | The game's graphics, encoded | Never |
| Which commands were issued | How a program drives a peripheral | Yes |
| The lengths asked for | Interface parameters | Yes |
| The order commands came in | Program behaviour | Yes |

The second group is functional rather than authored. It is dictated by the chip's interface, not chosen by an artist, and that is the distinction copyright draws in [17 U.S.C. 102(b)](https://www.law.cornell.edu/uscode/text/17/102) and in `Feist` for facts. [`conformance/capture.py`](conformance/capture.py) produces exactly that and never writes a payload byte.

So [`conformance/corpus.json`](conformance/corpus.json) is built in three steps:

1. **Shapes measured from real hardware.** `1,804,133 commands issued by a cartridge to its DSP-2. Every command it uses, every length it asks for, and every transition between commands is reproduced.
2. **Payloads generated from a seed.** The bytes filling those shapes are arithmetic, not artwork, produced by `port_for` in [`conformance/corpus.py`](conformance/corpus.py).
3. **Answers computed by the reference chip.** Expected outputs come from snes9x's `dsp2.cpp`, not from this implementation, so agreement is a cross-check rather than a restatement.

The result is real in the way that matters and synthetic in the way it must be. A bug that only appears on a length the cartridge actually uses is caught; a byte of the game is not shipped.

```bash
python3 conformance/corpus.py
#   257 exchanges from conformance/corpus.json, against snes9x 1.63 dsp2.cpp
#   shapes measured from 1804133 real commands
#   257 agreed, 0 did not
```

> [!IMPORTANT]
> This reasoning is how the repository is built, not legal advice. If you plan to redistribute anything derived from a cartridge, the safe rule is the one used here: publish behaviour, never content.

### Recording your own cartridge

None of the above replaces decoding real payloads. If you own the game, record its port traffic and turn it into a shape profile:

```bash
python3 conformance/capture.py trace.bin shapes.json 28 12 13
#   1804133 commands, 7 kinds, from trace.bin
#   16 distinct length shapes
```

The log format is deliberately dumb: fixed-size records with a kind byte and a value byte at offsets you name, so a trace from any emulator or logic capture is read by pointing the offsets at the right columns rather than by writing a parser. The trailing arguments above are record size, kind offset and value offset.

That profile stays on your machine, and so does any corpus built from it with real payloads. The shipped corpus is what the reasoning above allows to travel.

## Models

Nintendo shipped one part four times. The DSP-1, DSP-2, DSP-3 and DSP-4 are the
same NEC uPD77C25 with different microcode masked into it, which is why they
share a port interface and a parameter RAM and answer completely different
commands through them. A package named after one of them could not grow into the
others, so this one is named after the family and the microcode is a construction
argument.

```python
from snesdsp import Dsp, describe

describe("dsp-2").parameter_bytes
# 512

chip = Dsp(model="dsp2")
```

| Model | State | Parameter RAM | Notes |
|:------|:------|:-------------:|:------|
| `dsp1` | modelled | 512 bytes | The first mask, in Pilotwings alone, with its own vector length and its own version word. Thirty one commands: a camera, three attitude matrices, and the projections that ask questions of them. Aliases: `dsp-1`, `upd77c25dsp1`, `nintendodsp1` |
| `dsp1b` | modelled | 512 bytes | The last mask, in nearly every other cartridge of the family. It corrects the first mask's vector length. Aliases: `dsp-1b`, `upd77c25dsp1b`, `nintendodsp1b` |
| `dsp2` | modelled | 512 bytes | Six commands. Aliases: `dsp-2`, `upd77c25dsp2`, `nintendodsp2` |
| `dsp3` | modelled | none | Thirteen commands: a decompressor, a bit plane converter, a hex grid search. Aliases: `dsp-3`, `upd77c25dsp3`, `nintendodsp3` |
| `dsp4` | modelled | 512 bytes | Fifteen commands, seven of them renderers. Aliases: `dsp-4`, `upd77c25dsp4`, `nintendodsp4` |
| `dsp1a` | refused by name | | The middle mask. No image of it has been measured here |

Each of the four has its own recorded corpus, replayed by its own runner, and none
of them needs anything installed to run.

### The DSP-1 was masked three times

The DSP-1, the DSP-1A and the DSP-1B are three microcodes rather than three
spellings of one, and the last corrected the first. Nearly half the program
differs between the first and the last: 993 of 2,048 instruction words and 537 of
1,024 table words.

Two of the three are modelled here as separate parts, because two of the three
were measured. Both images were run on the processor they are masked into, in the
`processor` submodule, and asked the same questions. They answer command `0x2F`
differently on every input tried:

```python
from snesdsp import Dsp


def names_itself(model):
    chip = Dsp(model=model, fill=0)
    for byte in (0x2F, 0x00, 0x00):
        chip.write(byte)
    return chip.read() | chip.read() << 8


hex(names_itself("dsp1"))  # '0x100'
hex(names_itself("dsp1b"))  # '0x101'
```

It is a version word: the part names its own mask.

The second difference is the one that matters, and it is a real fault. Between two
nodes of its root curve the part blends by a fraction taken from a normalised
coefficient. The last mask reads nine bits of that fraction, unsigned, which is what
the blend wants. **The first mask reads ten and treats the tenth as a sign**, so
whenever that bit is set it blends the wrong way: instead of moving from the lower
node towards the higher one it moves the same distance below the lower node.

```python
from snesdsp import Dsp


def length(model, x, y, z):
    chip = Dsp(model=model, fill=0)
    chip.write(0x28)
    for value in (x, y, z):
        chip.write(value & 0xFF)
        chip.write(value >> 8)
    return chip.read() | chip.read() << 8


length("dsp1", 0x15B9, 0x0AA7, 0x1A44)  # 8908
length("dsp1b", 0x15B9, 0x0AA7, 0x1A44)  # 9140
```

The two agree on exactly the half of all inputs where that bit is clear, which is
why the fault survived long enough to need a mask revision. Both readings were
measured against their own image: over 200 random vectors the signed reading
matches the first mask on every one, and the unsigned reading matches the last on
every one.

Every command of both masks now matches its own microcode: **365 of 365 each**.

The middle mask is refused by name, because no image of it has been measured:

```python
Dsp(model="dsp1a")
# UnknownModelError: dsp1a is not modelled here: the DSP-1A is the middle mask of
# the three, and no image of it has been measured here; the first and the last
# both have one, so they are modelled and this one is not rather than being
# assumed to match either
```

The DSP-4 is the odd one in the family. It draws rather than answers: a command
hands it a viewpoint and a stretch of track and it walks that track outwards from
the viewer, producing scanline segments and sprite entries until it runs out of
either. Seven of its commands cannot finish in one go. They consume a batch of
input, produce output, and then wait for the next batch, resuming exactly where
they stopped, and the resumption point is state. Two of them suspend in places
that ask for the same number of bytes, so which one it is cannot be recovered
from what arrives next.

The reference implements that by jumping back into the middle of a function. Here
each such command is a generator, which resumes where it yielded for the same
reason and without the jump.

Three things the comparison settled that reading the code would not have.

The reciprocal table holds one over one as a value the lookup hands back signed,
so a run of a single scanline steps the wrong way. Every caller then negates that
step again, so the two mistakes cancel where they meet and neither is visible on
its own. Ten single-line runs in the corpus pin it.

A fork in the road does not interrupt the wait for the next distance, it restarts
it. The two bytes after one are a distance in their own right and may be another
fork, or the marker that ends the track. Reading them as the curvature that
normally follows bends the road by whatever the caller meant as an ending. Nine of
the twelve forked cases catch it.

And the chip's output buffer is 512 bytes, so a stretch that would produce more
than that cannot be expressed through the interface: there is nowhere for the
bytes to go. The reference does not notice. It writes past the end of its own
buffer and over the variables that follow, one of which is the loop counter, so
the loop stops at a length decided by the layout of a C struct. That is a property
of that program rather than of the chip, so those cases are not in the corpus, and
the corpus says so.

The DSP-3 is three unrelated chips sharing one port. It decompresses tile data,
it converts a bitmap into bit planes, and it walks a hex grid working out what a
unit can reach and what each step there costs. The three have nothing to do with
each other beyond arriving through the same two registers.

What makes it awkward is that it has no framing at all. There is no length, no
command envelope, and no way to ask it what it is doing. A command sets the state
machine's next step, and every word after it is handed to whatever step is
current, which sets the next one. So a byte means whatever the step holding it
decides, and the step is state that outlives the byte. A corpus of single
commands would prove nothing; each case here is a whole session.

Three things the comparison settled. One command is accepted without the chip
also saying it is busy, so the byte after it arrives on its own rather than as
half of a word, and nothing about the command says so. Another takes four steps
to swallow two words and answer two zeroes, and a model that zeroes its answer a
step early hands back the second word instead of the first zero. And the ring
walk hands the caller a cell, takes two single-byte answers about it, and hands
over the next, which is a protocol nothing in the command names.

All four are in the catalogue now, because all four have a corpus behind them. A
model with nothing behind it would make its fidelity a claim rather than a
measurement, and listing one would have been worse than the gap.

### The DSP-1

The microcode that shipped in the most cartridges, and the only one in the family
whose commands are recognisably arithmetic. A camera is placed, three attitude
matrices are built, and everything else asks questions of them: where a point in
the world lands on the screen, where a screen position lands in the world, how
long a vector is, where an aircraft ends up after a moment of flying the way it
is pointed.

None of it is floating point. Every value is a word with a separate exponent, and
the chip carries its own normalise, its own reciprocal and its own saturating
narrow to move between them. Four defects in this model came from getting those
wrong rather than from getting the geometry wrong, and each was found by the
reference rather than by reading:

- The reciprocal narrows its Newton step to a word one operation too early, which
  is invisible until the value being inverted is large enough for the product to
  matter.
- The wide normalise takes the complement of an already complemented value on its
  second pass, so an exponent past fifteen comes back shifted the wrong way.
- The three squared sums wrap at thirty two bits, and a vector long enough to wrap
  them makes the length command read its own square root curve backwards, landing
  in the reciprocal seeds instead. That is not a bug to be guarded against; it is
  what the chip does, and the model reproduces it.
- The size a projected thing comes back at continues the exponent the reciprocal
  produced. Starting it from nothing halves every answer, and nothing else about
  the projection changes.

### The mask ROM no chip here ships

The DSP-1 and DSP-3 each carry a thousand-entry table masked into the silicon.
That is chip content rather than a description of behaviour, so it is not here.

For the DSP-1 that turned out to cost nothing at all. Everything its arithmetic
reads out of that table is stated as the formula that produces it, and every one
of them agrees exactly with the table across its whole range:

| What the chip reads | What it is |
|:--------------------|:-----------|
| A sine over 256 steps | The truncation of a word times the sine, clamped where one does not fit |
| The line it interpolates along between two steps | Not pi. Three hundred and fifty five over one hundred and thirteen |
| A ladder of powers of two, read from four different offsets | One run that rises to a saturated word and falls away again |
| One hundred and twenty eight reciprocal seeds | One over where the value sits, rounded |
| A square root curve | A scale a hair above a saturated word, times the root of the step |

Two things are carried as measurements rather than as formulas, and both are
numbers rather than expression: five coefficients of the curve that bends the
horizon once the view is clipped, and one word of the ladder that holds one where
the run says sixteen. That last is what a slip in transcribing a table looks
like, it is reachable from three different directions, and it is reproduced
rather than quietly corrected.

For the DSP-3 the cost is almost as small. Only one part of its table is reachable
by anything other than the command that dumps it: six pairs naming the neighbours
of a cell on a hex grid, which are the grid's own geometry. Those are modelled.
The dump command answers from a table you supply and refuses clearly when you
have not supplied one, because a table that is absent is not a table of zeroes.

```python
from snesdsp import Dsp

chip = Dsp(model="dsp3")
chip.write(0x1F)
chip.write(0x00)
chip.write(0x00)
# DataRomMissing: command 0x1f hands back this chip's mask ROM word by word,
# which is content rather than behaviour and is not shipped here
```

One more thing the corpus had to decide. A stream of noise can ask the
decompressor for a symbol past the end of the table it just built, and what
happens there is a property of whichever memory the reference keeps after its own
array rather than of the chip. Those sessions are refused rather than guessed at,
and the corpus records only the seeds that stay inside.

## Project structure

```
snesdsp/
  __init__.py     the package, and the model chosen at construction
  chip.py         the DSP-2 port protocol, and nothing else
  commands.py     what each DSP-2 command computes, as functions of their input
  dsp1.py         the DSP-1: its port, its fixed point arithmetic, and its projections
  dsp1tables.py   what its arithmetic reads out of the mask ROM, as the formulas
  dsp3.py         the DSP-3: its port, its decompressor, and its grid search
  dsp4.py         the DSP-4: its port, its commands, and its seven renderers
  memory.py       parameter RAM that holds what it held
  models.py       what each part is
  version.py      rewritten by the release job and by nothing else
conformance/
  corpus.py       replays a DSP-2 recording you captured yourself
  capture.py      turns a recording into shapes, and never into payload
  dsp1corpus.py   whole sessions generated from seeds, answered by the reference
  dsp3corpus.py   whole sessions generated from seeds, answered by the reference
  dsp4corpus.py   roads generated from seeds, answered by the reference
```

Each module has its tests beside it as `<module>.test.py`, so a module and the cases that pin its behaviour are read together.

## Tests

```bash
for f in snesdsp/*.test.py conformance/*.test.py; do python3 "$f"; done
```

| Suite | File | Covers |
|:------|:-----|:-------|
| Commands | [`snesdsp/commands.test.py`](snesdsp/commands.test.py) | The exhaustive bit permutation, the merge rule, the product, the mirror, the rescale walk |
| Protocol | [`snesdsp/chip.test.py`](snesdsp/chip.test.py) | Command framing, lengths, payload assembly, result readout, unknown commands |
| Parameter RAM | [`snesdsp/memory.test.py`](snesdsp/memory.test.py) | Scrambled fills, explicit zeroes, seeding, size |
| Models | [`snesdsp/models.test.py`](snesdsp/models.test.py) | The catalogue, alias matching, construction |
| DSP-1 | [`snesdsp/dsp1.test.py`](snesdsp/dsp1.test.py) | The port, the thirty one commands, the reciprocal, the normalise, the saturating narrow |
| DSP-1 tables | [`snesdsp/dsp1tables.test.py`](snesdsp/dsp1tables.test.py) | Every formula against the range the chip reads, including the word that breaks the run |
| DSP-3 | [`snesdsp/dsp3.test.py`](snesdsp/dsp3.test.py) | The port and its half-word toggle, the thirteen commands, the decompressor, the ring walk, the cost spread |
| DSP-4 | [`snesdsp/dsp4.test.py`](snesdsp/dsp4.test.py) | The port, the eight single-shot commands, all seven renderers, the sprite packer, the reciprocal table |
| Corpus harness | [`conformance/corpus.test.py`](conformance/corpus.test.py) | Replay, comparison, reporting, the command line |
| DSP-1 corpus | [`conformance/dsp1corpus.test.py`](conformance/dsp1corpus.test.py) | Session generation, recording, replay against 80 recorded sessions |
| DSP-3 corpus | [`conformance/dsp3corpus.test.py`](conformance/dsp3corpus.test.py) | Session generation, the table-overrun exclusion, recording, replay against 60 recorded sessions |
| DSP-4 corpus | [`conformance/dsp4corpus.test.py`](conformance/dsp4corpus.test.py) | Case generation, the buffer-overrun exclusion, recording, replay against 140 recorded roads |

Coverage is enforced at 100% of statements and branches by [`pyproject.toml`](pyproject.toml), so a new branch without a test fails the build rather than quietly lowering the number.

## Development

| Command | Description |
|:--------|:------------|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage run -a <file>` | Run one test file under coverage |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 conformance/corpus.py <file>` | Replay a DSP-2 recording |
| `python3 conformance/dsp1corpus.py` | Replay the 80 recorded DSP-1 sessions |
| `python3 conformance/dsp3corpus.py` | Replay the 60 recorded DSP-3 sessions |
| `python3 conformance/dsp4corpus.py` | Replay the 140 recorded roads |
| `pnpm install` | Install the JSON formatter |
| `pnpm run format` | Format every JSON file |
| `pnpm run format:check` | Check that every JSON file is formatted, which CI also does |

## Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/), driven by [`.releaserc.json`](.releaserc.json) |
| Lint and format | [Ruff](https://docs.astral.sh/ruff/), configured in [`pyproject.toml`](pyproject.toml) |
| JSON formatting | [Prettier](https://prettier.io/), configured in [`.prettierrc.json`](.prettierrc.json). Re-recording a corpus writes it plainly; `pnpm run format` settles it |
| Test layout | `<module>.test.py` beside the module it covers |

## Versioning

This project follows [Semantic Versioning](https://semver.org/), and every release is tagged from `main` by semantic-release. See [releases](https://github.com/gufranco/snes-dsp-python/releases).

> [!IMPORTANT]
> While the version is below `1.0.0`, the public interface may change on a minor release. Pin an exact version if that matters to you.

## FAQ

<details>
<summary><strong>Why is there no test suite shipped with this, like the CPU repositories have?</strong></summary>
<br>

Because none exists to ship. SingleStepTests covers processors with published instruction sets and many implementations to compare against. The DSP-2 is one microcode mask in one cartridge. What replaces the suite here is proving the commands directly, which for a bit permutation and a per-nibble rule is available and is stronger than any suite would be.

</details>

<details>
<summary><strong>Could you not just include a recording of the real chip?</strong></summary>
<br>

No. What a DSP-2 returns is the game's graphics, tile by tile. A recording of its output is the artwork in a different container, so distributing one is distributing the game. The tooling to make your own from a cartridge you own is here; the recording stays on your machine.

</details>

<details>
<summary><strong>Why does the parameter RAM start scrambled instead of zeroed?</strong></summary>
<br>

Because the chip never clears it, and one command reads past its own data straight into it. Zeroing makes those reads look deliberate and stable, which is precisely how a real bug in that path passed every recorded test before being caught. Pass `fill=0` when you want zeroes, and the decision is then recorded in the code.

</details>

<details>
<summary><strong>Does this emulate the uPD77C25 processor itself?</strong></summary>
<br>

No. This models each chip at its port: the commands the cartridge sends and the bytes that come back. Emulating the uPD77C25 core and running Nintendo's microcode on it would need that microcode, which is copyrighted and not distributable, so it would not be a package anyone could use.

</details>

## License

[MIT](LICENSE)
