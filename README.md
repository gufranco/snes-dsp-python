<div align="center">

<h1>SNES DSP Family</h1>

<strong>The NEC uPD77C25 as Nintendo shipped it, running the microcode you supply rather than a description of it.</strong>

<br>
<br>

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25%20statement%20%2B%20branch-brightgreen)](#tests)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13%20%7C%203.14-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;|&nbsp;
  <a href="#the-family">The family</a> &nbsp;|&nbsp;
  <a href="#why-there-is-no-model-here">Why there is no model</a> &nbsp;|&nbsp;
  <a href="#the-microcode-you-supply">The microcode you supply</a> &nbsp;|&nbsp;
  <a href="#driving-it-the-way-a-console-does">Driving it</a> &nbsp;|&nbsp;
  <a href="#what-is-checked-without-one">What is checked without one</a> &nbsp;|&nbsp;
  <a href="https://github.com/gufranco/snes-dsp-python/issues">Issues</a>
</p>

**6** parts across **5** microcodes · **1** processor underneath them all · **0** commands described by hand · paced at **7.6 MHz** against the console's own clock · **46** exchanges read out of four real cartridges · **209** tests · **100%** statement and branch coverage · every image confirmed by **SHA-256** before a byte of it runs

```python
from snesdsp import Dsp

chip = Dsp("dsp2")

chip.write(0x09)
for byte in (0x02, 0x00, 0x03, 0x00):
    chip.write(byte)

[chip.read() for _ in range(4)]
# [6, 0, 0, 0]
```

---

## The problem

The DSP-1, DSP-2, DSP-3 and DSP-4 are not four chips. They are one chip, a NEC
uPD77C25, with four different programs masked into it, which is why they answer
completely unrelated commands while being the same silicon underneath.

Every emulator that supports them carries a hand-written implementation of what
each command computes. Those implementations are derived: somebody worked out
what a command does and wrote it down. That can be checked and it can never be
finished, because what it covers is the commands somebody thought to look at, and
the corners nobody characterised are exactly where it is quietly wrong.

This package carried one too. Held against the parts' own microcode, four of the
five sat between 67% and 100% of the bytes their hardware answers, with 75 places
written down where they differed. Two of those differences were in a reference
implementation the whole scene works from.

## The solution

Run the program instead.

Given the microcode, there is nothing left to derive. The answer to every
command, in every state, including the ones no cartridge ever sent, is whatever
the part answers, because it is the part answering. There is no long tail to
chase and no percentage to report.

| | Running the program | Describing what it does |
|:--|:--|:--|
| Commands covered | Every one, including undocumented | The ones somebody characterised |
| Behaviour in a state nobody tried | The part's | Unknown, and silently plausible |
| What it needs | An image of the microcode | Nothing |
| How wrong it can be | Not a meaningful question | A number that moves |

The cost is real and is stated plainly: without an image this package refuses.
It does not fall back to a guess, because an answer that did not come from the
part is worse than no answer.

## Why there is no model here

This used to be roughly twelve thousand lines: four command sets, the tables they
worked from, four corpora recorded from other implementations, and a switch that
chose between running the part and describing it. All of it is gone.

What went with it is worth naming, because none of it was checking anything the
part could not answer itself. The corpora were recordings of software, and where
that software and the chip disagreed the chip was right. The command sets were
the only reason a corpus was needed at all.

What is left is the part catalogue, the port layer, and the arrangement that
loads an image and drives it.

## Quick start

### Prerequisites

| Tool | Version | Install |
|:-----|:--------|:--------|
| Python | 3.12, 3.13 or 3.14 | [python.org](https://www.python.org/downloads/) |
| Git | any | [git-scm.com](https://git-scm.com/) |

### Setup

```bash
git clone --recurse-submodules https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
```

The submodule sits at the repository root as
[`nec-upd7725-python/`](https://github.com/gufranco/nec-upd7725-python), named
after itself rather than buried under a generic folder, because it is the
processor every one of these parts is built on and anybody browsing this should
see that immediately. Without it nothing here can run at all.

### Supply the microcode

A copy of the microcode you already own goes in one of these, and the first one
that has it wins:

1. any directory named by `UPD7725_FIRMWARE_DIR`, several separated the way your
   system separates a path
2. the `firmware/` directory of the project this one sits inside, which is what a
   parent project uses when it carries this as a submodule
3. this project's own `firmware/` directory

Nothing is downloaded and nothing is shipped. The files are named below so you
can confirm the one you have is the one the part expects.

### Verify

```bash
python3 -c "import snesdsp; print(sorted(snesdsp.available()) or snesdsp.why_not())"
# ['dsp1', 'dsp1a', 'dsp1b', 'dsp2', 'dsp3', 'dsp4']
```

Without an image that prints the reason instead, naming where to put one.

### When something is wrong

```bash
python3 -m snesdsp.doctor
```

It looks at this machine and prints what is actually there: the Python it is
running on, whether the processor is checked out, which images are present and
the SHA-256 of each one, whether every part starts, and the clocks it is pacing
them at. Nothing is inferred and nothing is hidden. A check that fails says what
it saw, and a check that itself throws is reported as what it threw rather than
taking the report down with it.

It then asks the same of the project underneath, and reports what comes back
under that project's name. This package can be entirely well while the processor
it runs on is missing, stale, or holding a different file, and a report that
looked only here would come back clean on exactly the machine where it is not.

```text
snesdsp 3.0.0 on 3.13.0, Linux

  ok    python: 3.13.0 on Linux x86_64
  ok    processor: nec-upd7725-python is checked out
  ok    timing: part 7600000 Hz, console 21477273 Hz, 14 instructions between accesses
     !  dsp2: no image for dsp2
         put a copy you own in snes-dsp-python/firmware, in the firmware
         directory of the project this one sits inside, or anywhere
         UPD7725_FIRMWARE_DIR names
  ok    nec-upd7725-python / upd7725: version 1.1.0
  ok    nec-upd7725-python / image dsp1: upd7725, dsp1.bin, sha256 5f2e5ed0...

  1 of 23 checks did not pass
```

Paste all of it into an issue. Most of what gets reported here is one of three
things and they look identical from outside; that output is what tells everybody
which.

## The microcode you supply

Every image is identified before a byte of it is executed. SHA-256 decides; the
other values are there so you can cross-check against a database that keys on
them.

| Part | Bytes | CRC32 | SHA-256 |
|:--|--:|:--|:--|
| `dsp1` | 8,192 | `27124599` | `5f2e5ed06b362be023b978b5978813ecb9a07c76592454b45c2a1ed17a0de349` |
| `dsp1b` | 8,192 | `588279b4` | `4d42db0f36faef263d6b93f508e8c1c4ae8fc2605fd35e3390ecc02905cd420c` |
| `dsp2` | 8,192 | `f0221c90` | `5efbdf96ed0652790855225964f3e90e6a4d466cfa64df25b110933c6cf94ea1` |
| `dsp3` | 8,192 | `e3b54e6a` | `2e635f72e4d4681148bc35429421c9b946e4f407590e74e31b93b8987b63ba90` |
| `dsp4` | 8,192 | `ca09e176` | `63ede17322541c191ed1fdf683872554a0a57306496afc43c59de7c01a6e764a` |

Confirm one you hold:

```bash
shasum -a 256 firmware/dsp1.bin      # macOS
sha256sum firmware/dsp1.bin          # Linux
certutil -hashfile firmware\dsp1.bin SHA256   # Windows
```

A file that does not match is refused rather than run, and the refusal says what
was computed so you can search for it.

## Driving it the way a console does

A part is only half of an exchange. The other half is when the console next
speaks to it, and that is not a number this package gets to choose.

### Timing

The part runs one instruction per clock at **7,600,000 Hz**. The console counts
at six times its colour carrier, **21,477,273 Hz**, and one cartridge access
costs it **eight** of those clocks, or six on a board wired for it.

A 65816 store to a long address takes five cycles, each one reaching memory. So
the least a console can possibly leave the part between two accesses is
**14 instructions**, and that is the default here. It is a floor rather than a
guess: Super Mario Kart's driver was read to check what a real one does, and it
puts between one and twelve of its own instructions between consecutive
accesses, so in practice the part gets more.

A caller who knows how long their console actually spent says so, and the
conversion is done for them:

```python
from snesdsp import Dsp, MASTER_CLOCK

chip = Dsp("dsp1")
chip.elapsed(MASTER_CLOCK // 60)
```

### The bus

A console does not call a method on a coprocessor. It reads and writes an
address, and the part decides from the lowest bit of that address whether the
access was the data port or the status register.

```python
chip.write_bus(0x3F8000, 0x09)
chip.read_bus(0x3F8001)
```

An even address is the data port. An odd one is the status register.

Nothing above that bit matters, which is why one of these answers across a whole
window rather than at a single address. The decode lives here rather than in
whoever calls this, because every caller that reimplements it is a caller that
can get it the wrong way round.

## The family

| Part | What it does | Image it runs |
|:--|:--|:--|
| DSP-1 | Fixed-point three dimensional maths, in more cartridges than the rest together | its own |
| DSP-1A | A die shrink of the DSP-1, same program and data ROM | the DSP-1's |
| DSP-1B | The last mask, which corrected an arithmetic fault | its own |
| DSP-2 | Tile conversion, scaling and a multiply | its own |
| DSP-3 | Decompression and a search across a hex grid | its own |
| DSP-4 | Draws a road, one scanline batch at a time | its own |

Three of those are one part masked three times. Two programs, three parts: the
DSP-1A carries the DSP-1's program, so no DSP-1A image exists to find and none is
needed. It is still a part in its own right and is answered as one.

## What is checked without one

A machine holding no microcode still checks everything this package can get
wrong, because the part-specific knowledge is no longer in the code.

| Layer | What is checked | Needs an image |
|:--|:--|:--:|
| The processor | Every instruction, in [`nec-upd7725-python`](https://github.com/gufranco/nec-upd7725-python) | No |
| The port | The handshake, the pacing, the status register and the bus decode, driven by a program of zeroes | No |
| Timing | That the pacing follows from the two oscillators rather than from a chosen number | No |
| Identity | That every part names an image with a deciding digest, so a supplied file is confirmed rather than trusted | No |
| The catalogue | Every part, every name it answers to, and which image each runs | No |
| The parts | Driven through the exchanges a real cartridge makes with them | Yes |

That last one is the only check that needs an image, and it reports as skipped
rather than as passed when there is none.

### Driven by what a cartridge actually sends

These parts have no framing, so a byte means whatever the state left by the bytes
before it decides, and a sequence no game ever sent asks a question nobody has an
answer for. What a game sends is not derived here either: it is read out of the
cartridge by [`snes-driver-python`](https://github.com/gufranco/snes-driver-python),
which disassembles the routine that drives the part rather than running the game.

What comes back is a shape, the accesses a routine makes with the width of each
and no payload attached. Each file holds the digests of the game it was read from
and none of its bytes.

| Part | Read from | Shapes | That drive the part |
|:--|:--|--:|--:|
| DSP-1 | Super Mario Kart | 13 | 8 |
| DSP-2 | Dungeon Master | 13 | 1 |
| DSP-3 | SD Gundam GX | 17 | 8 |
| DSP-4 | Top Gear 3000 | 38 | 29 |

All four parts answer every exchange their own game makes.

```bash
python3 conformance/against_cartridges.py dsp1
```

## Project structure

```text
snesdsp/
  __init__.py     the package, and the part chosen at construction
  models.py       which parts exist, what they answer to, which image each runs
  silicon.py      loading an image and driving the part it belongs to
  timing.py       the two oscillators, and how long the console leaves the part
  doctor.py       what is actually on this machine, printed for a bug report
  version.py      rewritten by the release job and by nothing else
conformance/
  against_cartridges.py  drives a part with the exchanges a real cartridge makes
  shapes.py       reads and replays those exchanges
  cartridges.py   finds and confirms the cartridges they were read from
nec-upd7725-python/  the processor all of these are, as a submodule at the root
```

Each module has its tests beside it as `<module>.test.py`, so a module and the
cases that pin its behaviour are read together.

## Tests

```bash
for f in snesdsp/*.test.py conformance/*.test.py; do python3 "$f"; done
```

| Area | File | What it pins |
|:--|:--|:--|
| The catalogue | [`snesdsp/models.test.py`](snesdsp/models.test.py) | Every part, its names, its image, and that the image is declared with a digest |
| The part | [`snesdsp/silicon.test.py`](snesdsp/silicon.test.py) | Loading, the handshake, the pacing, the bus decode, reading, refusing |
| Timing | [`snesdsp/timing.test.py`](snesdsp/timing.test.py) | The clocks, the conversion, and that the gap is derived rather than chosen |
| The doctor | [`snesdsp/doctor.test.py`](snesdsp/doctor.test.py) | Every check it makes, and that a check which throws is reported rather than swallowed |
| Cartridge exchanges | [`conformance/shapes.test.py`](conformance/shapes.test.py) | Reading a driver's accesses, replaying them, the payloads they are filled with |
| Driving a part | [`conformance/against_cartridges.test.py`](conformance/against_cartridges.test.py) | Playing every recorded exchange, and what silence means |

Coverage is enforced at 100% of statements and branches by
[`pyproject.toml`](pyproject.toml), so a new branch without a test fails the
build rather than quietly lowering the number.

## Development

| Command | Description |
|:--|:--|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage run -a <file>` | Run one test file under coverage |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 -m snesdsp.doctor` | Say what is on this machine, for a bug report |
| `python3 conformance/against_cartridges.py <part>` | Drive a part with real cartridge exchanges |
| `pnpm install` | Install the JSON formatter |
| `pnpm run format:check` | Check that every JSON file is formatted, which CI also does |

## Project conventions

| Convention | Source |
|:--|:--|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Formatting and lint | [ruff](https://docs.astral.sh/ruff/), pinned in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Versioning | [semantic-release](https://semantic-release.gitbook.io/), from the commit history |
| Tests | Beside the module, named `<module>.test.py` |

## Reporting something

| Need | Where |
|:--|:--|
| Something is wrong | [Open an issue](https://github.com/gufranco/snes-dsp-python/issues/new/choose), with the doctor output |
| A part answers the wrong thing | The same, using the fidelity template |
| A change | [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) says what a change has to show |

Never attach microcode or a cartridge to a report, and never link to somewhere
either can be downloaded. A SHA-256 identifies both, and it is all anybody needs.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). Every release is
tagged. See [releases](https://github.com/gufranco/snes-dsp-python/releases) for
the changelog and upgrade notes.

## FAQ

<details>
<summary><strong>Why will it not work without a firmware image?</strong></summary>
<br>

Because what these parts do is the program masked into them, and that program
belongs to whoever made the part. A package that answered without one would be
answering from a description somebody wrote, which is the thing this exists to
stop doing.

</details>

<details>
<summary><strong>Where do I get the microcode?</strong></summary>
<br>

Not from here, and this will not tell you. Dump it from hardware you own. The
digests above let you confirm that what you have is what the part expects.

</details>

<details>
<summary><strong>What happened to the command implementations?</strong></summary>
<br>

They were removed. Held against the parts' own microcode they sat between 67% and
100% of the bytes the hardware answers, and closing that gap meant deriving
undocumented fixed-point arithmetic command by command. Running the program
closes it completely and permanently.

</details>

<details>
<summary><strong>Is the DSP-1A really the same as the DSP-1?</strong></summary>
<br>

Same program and same data ROM, on a smaller die. No DSP-1A image exists to find
and none is needed; asking for one runs the DSP-1's, which is what the part
carries. Only the DSP-1B changed the program.

</details>

## License

[MIT](LICENSE)
