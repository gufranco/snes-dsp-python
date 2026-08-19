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
  <a href="#the-commands">Commands</a> &nbsp;|&nbsp;
  <a href="#how-this-is-proved">How this is proved</a> &nbsp;|&nbsp;
  <a href="#the-corpus-and-why-it-can-ship">Why the corpus is legal</a> &nbsp;|&nbsp;
  <a href="#the-rescale-reads-past-its-own-data">The rescale</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/snes-dsp-python/issues">Issues</a>
</p>

**4** microcodes carried by the reference driver · **1** modelled so far · **6** commands · **1** exhaustively proved bit permutation · shapes from **1,804,133** real cartridge commands · **95,784** reads agreeing with snes9x · **140** tests · **100%** statement and branch coverage

```python
from snesdsp import Dsp

chip = Dsp(model="dsp2")

chip.write(0x09)
for byte in (0x02, 0x00, 0x03, 0x00):
    chip.write(byte)

[chip.read() for _ in range(4)]
# [6, 0, 0, 0]
```

---

## The problem

None of these chips has a published per-instruction test suite the way a 6502 or a Z80 does, and none ever will. They are one NEC uPD77C25 with Nintendo's microcode masked into it, and the microcode is what makes each of them a different chip. The DSP-2 modelled here shipped in exactly one cartridge, so its sample size is one game.

The usual answer is to record the real chip and replay the recording. That works, and it has a ceiling. A recording only covers what that one game happened to ask for, so the moment you use the model for anything else, you are outside what was ever tested. It is also the game's own artwork, which makes shipping it a redistribution problem rather than a testing one.

## The solution

Separate what each command computes from the protocol that feeds it, then prove the commands directly.

Five of the six commands are pure functions of their input, and each one has an input space small enough or structured enough to be settled rather than sampled. The tile conversion is a permutation of the 256 bits it is given, so 256 single-bit inputs pin where every bit lands and nothing can be hiding. The merge is a per-nibble rule, so every combination of colour and byte it accepts is checked. The multiply is checked against arithmetic. That is a stronger claim than any recording supports.

The recording still has a job, and it is kept: this model agrees byte for byte with a reference that reproduced **71,970,987 bytes** of real recorded traffic with zero errors, over 1,139,246 reads of randomised command streams that reach lengths the game never used.

The same argument is what the other three microcodes will be held to when they are modelled, which is why the reference driver takes the chip as an argument rather than being built around one of them.

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

## The commands

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
| `dsp2` | modelled | 512 bytes | Six commands. Aliases: `dsp-2`, `upd77c25dsp2`, `nintendodsp2` |
| `dsp1` | reference driver only | 512 bytes | Fixed-point 3D maths, used by the most cartridges |
| `dsp3` | reference driver only | n/a | Compression and a coordinate walk |
| `dsp4` | port protocol and seven commands | 512 bytes | The track renderer. The eight renderers themselves are not modelled yet and raise rather than answering |

The reference driver in [`conformance/ref/`](conformance/ref/) already carries all
four and takes the chip as an argument, so adding one is a matter of writing the
model and the corpus rather than of building the evidence first.

The DSP-4 is part way through that. Its port protocol and the seven commands that
finish in one go are modelled and agree with the reference across three hundred
randomised command sequences. Its eight track renderers consume input in batches
and resume where they stopped, and they are not here yet. Asking for one raises,
because a command that quietly produced nothing would be indistinguishable from a
road with no segments in it, which is a real answer this chip can give.

Only `dsp2` is in the catalogue, because only `dsp2` has a corpus behind it. A
model with nothing behind it would make its fidelity a claim rather than a
measurement, and listing one would be worse than the gap.

> [!NOTE]
> The DSP-1 and DSP-3 each carry a thousand-entry table masked into the silicon.
> That is chip content rather than a description of behaviour, so modelling
> either one raises a question about redistribution that the DSP-2 and DSP-4 do
> not. It is named here rather than discovered later.

## Project structure

```
snesdsp/
  __init__.py     the package, and the model chosen at construction
  chip.py         the port protocol, and nothing else
  commands.py     what each command computes, as functions of their input
  memory.py       parameter RAM that holds what it held
  models.py       what each part is
  version.py      rewritten by the release job and by nothing else
conformance/
  corpus.py       replays a recording you captured yourself
  capture.py      turns a recording into shapes, and never into payload
  ref/            the driver around the four reference implementations
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
| Corpus harness | [`conformance/corpus.test.py`](conformance/corpus.test.py) | Replay, comparison, reporting, the command line |

Coverage is enforced at 100% of statements and branches by [`pyproject.toml`](pyproject.toml), so a new branch without a test fails the build rather than quietly lowering the number.

## Development

| Command | Description |
|:--------|:------------|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage run -a <file>` | Run one test file under coverage |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 conformance/corpus.py <file>` | Replay a recording |

## Project conventions

| Convention | Source |
|:-----------|:-------|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Releases | [semantic-release](https://semantic-release.gitbook.io/), driven by [`.releaserc.json`](.releaserc.json) |
| Lint and format | [Ruff](https://docs.astral.sh/ruff/), configured in [`pyproject.toml`](pyproject.toml) |
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

No. This models the DSP-2 at its port: the commands the cartridge sends and the bytes that come back. Emulating the uPD77C25 core and running Nintendo's microcode on it would need that microcode, which is copyrighted and not distributable, so it would not be a package anyone could use.

</details>

## License

[MIT](LICENSE)
