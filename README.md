# SNES DSP Family

The NEC uPD77C25 as Nintendo shipped it, running the microcode you supply rather than a description of it.

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)

**6** parts across **5** microcodes, **0** commands described by hand, **112** exchanges read out of **36** real cartridges compared, **0** failures, **874** tests, **100%** statement and branch coverage, no dependencies

```python
from snesdsp import Chip

chip = Chip("dsp2")

chip.write(0x09)
for byte in (0x02, 0x00, 0x03, 0x00):
    chip.write(byte)

[chip.read() for _ in range(4)]

# [6, 0, 0, 0]
```


## Install
```bash
git clone --recurse-submodules https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
```

Python 3.12 or newer, and the submodule. Nothing else.

The submodule sits at the repository root as
[`nec-upd7725-96050-python/`](https://github.com/gufranco/nec-upd7725-96050-python), named
after itself rather than buried under a generic folder, because it is the
processor every one of these parts is built on and anybody browsing this should
see that immediately. Without it nothing here can run at all.

The microcode is a separate matter and is not carried here. Where to put a copy
you already own is under [the microcode you supply](#the-microcode-you-supply).

## The interface
Everything a caller touches. Nothing else is public.

| Name | What it is |
|:--|:--|
| `Chip(model, **options)` | A part of that model, running its own microcode |
| `Chip(model, image=...)` | The same, with the bytes handed straight in and no directory searched |
| `MODELS` | Every part this package covers, by the name it goes by |
| `Model` | One entry of that catalogue: its name, its aliases and what it is |
| `SHARES_MICROCODE` | Which parts run the same program as which other part |
| `available()` | Every part there is an image for on this machine |
| `why_not()` | Why the backend cannot run, or nothing when it can |
| `MASTER_CLOCK`, `DSP_CLOCK` | The console's oscillator and the part's own |
| `clock_of(model)`, `steps_for(model, ticks)` | The rate a part runs at, and how far a span of console time carries it |
| `GAP` | How long the console leaves the part between accesses |
| `UnknownModelError` | No part goes by that name |
| `NoFirmware` | The microcode this part runs was not supplied |
| `NeverReady` | The part was asked for an answer and never produced one |

`Chip` takes the model first, which is the argument every member of the family
takes first. The name is the kind rather than the chip, so a traceback says what
sort of thing it was rather than which of four parts happened to raise.

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

A copy you already own goes in `firmware/` in this project, or in the `firmware/`
of the project this one sits inside when it is checked out as a submodule, or in
any directory named by `SNES_DSP_FIRMWARE_DIR`. That variable is read first and
may name more than one directory at once, separated the way the operating system
separates a path. `UPD7725_FIRMWARE_DIR` is read after it and still works: this
member and [snes-st-python](https://github.com/gufranco/snes-st-python) shared
that one name until somebody wanted to point them at two different sets. Nothing
is downloaded.

A caller who already holds the bytes hands them straight over as
`Chip("dsp1", image=...)`, and then no directory is searched at all and no
variable is read.

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
from snesdsp import Chip, MASTER_CLOCK

chip = Chip("dsp1")
chip.elapsed(MASTER_CLOCK // 60)
```

### The bus

A console does not call a method on a coprocessor. It reads and writes an
address, and the part decides from the lowest bit of that address whether the
access was the data port or the status register.

```python
from snesdsp import Chip

chip = Chip("dsp1")
chip.write_bus(0x3F8000, 0x09)
chip.read_bus(0x3F8001)
```

An even address is the data port. An odd one is the status register.

Nothing above that bit matters, which is why one of these answers across a whole
window rather than at a single address. The decode lives here rather than in
whoever calls this, because every caller that reimplements it is a caller that
can get it the wrong way round.

## Driving every part
Six parts, two ways of being spoken to, and one example each. Every output below
was taken from a run against the part's own microcode rather than written down
from a document.

### DSP-1

A command byte, then its arguments as little endian words, then the answer the
same way. This is the multiply, and it is the one command whose result can be
checked without knowing anything about the part.

```python
from snesdsp import Chip

chip = Chip("dsp1")
chip.write(0x00)
for value in (0x4000, 0x2000):
    chip.write(value & 0xFF)
    chip.write(value >> 8)
low, high = chip.read(), chip.read()
hex(low | (high << 8))
```

Gives `'0x1000'`, which is `0x4000 * 0x2000 >> 15`.

### DSP-1A

The same part on a smaller die, carrying the same program. Ask for it by name and
it runs the DSP-1's image, which is the only image there is.

```python
from snesdsp import Chip

chip = Chip("dsp1a")
chip.identity.part
```

Gives `'dsp1'`. The same multiply gives the same `0x1000`, because it is the same
program.

### DSP-1B

The last mask, which corrected an arithmetic fault. It carries its own image, and
this one really is a different file.

```python
from snesdsp import Chip

chip = Chip("dsp1b")
chip.identity.part
```

Gives `'dsp1b'`. The multiply above still gives `0x1000`: the correction is not in
that command, and a package that answered differently here would be inventing a
difference rather than running one.

### DSP-2

Same shape of exchange, a different program. Command `0x09` multiplies, and this
one is plain integer rather than fixed point.

```python
from snesdsp import Chip

chip = Chip("dsp2")
chip.write(0x09)
for value in (0x0002, 0x0003):
    chip.write(value & 0xFF)
    chip.write(value >> 8)
[hex(chip.read()) for _ in range(4)]
```

Gives `['0x6', '0x0', '0x0', '0x0']`. Two times three, in the first word.

### DSP-3

Driven a word at a time rather than a command and a burst, and it keeps its
attention bit raised between words. Command `0x001c` is worth showing on its own:
having been given a word, the part answers with it, and goes on answering with it
for as long as anybody keeps reading.

```python
from snesdsp import Chip

chip = Chip("dsp3")
for byte in (0x1C, 0x00):
    chip.write(byte)
for byte in (0x34, 0x12, 0x78, 0x56):
    chip.write(byte)
" ".join(f"{chip.read():02x}" for _ in range(8))
```

Gives `'78 56 78 56 78 56 78 56'`, the last word echoed without end. Emulators
that model this command by hand answer zeroes instead. Neither of those numbers
was chosen here; the program decides, and the program is what runs.

### DSP-4

A road renderer, driven as a stream: a command word, then parameters, then it
answers a batch at a time rather than once.

```python
from snesdsp import Chip

chip = Chip("dsp4")
chip.write(0x01)
chip.write(0x00)
for value in (0x0001, 0x0002, 0x0003, 0x0004):
    chip.write(value & 0xFF)
    chip.write(value >> 8)
[hex(chip.read()) for _ in range(6)]
```

Gives `['0x4', '0x0', '0x4', '0x0', '0x4', '0x0']`. Read it for longer and it
keeps answering, which is what a part that draws one scanline batch after another
does.

## The family
| Part | What it does | Image it runs |
|:--|:--|:--|
| DSP-1 | Fixed-point three dimensional maths, in more cartridges than the rest together | its own |
| DSP-1A | A die shrink of the DSP-1, same program and data ROM | the DSP-1's |
| DSP-1B | The last mask, which corrected an arithmetic fault | its own |
| DSP-2 | Tile conversion, scaling and a multiply | its own |
| DSP-3 | Decompression and a search across a hex grid | its own |
| DSP-4 | Draws a road, one scanline batch at a time | its own |

Each answers to more than one name, so a caller writing what a manual or a board
silkscreen calls the part gets the part rather than a refusal:

| Name | Also answers to |
|:--|:--|
| `dsp1` | `dsp-1`, `upd77c25dsp1`, `nintendodsp1` |
| `dsp1a` | `dsp-1a`, `upd77c25dsp1a`, `nintendodsp1a` |
| `dsp1b` | `dsp-1b`, `upd77c25dsp1b`, `nintendodsp1b` |
| `dsp2` | `dsp-2`, `upd77c25dsp2`, `nintendodsp2` |
| `dsp3` | `dsp-3`, `upd77c25dsp3`, `nintendodsp3` |
| `dsp4` | `dsp-4`, `upd77c25dsp4`, `nintendodsp4` |

Three of those are one part masked three times. Two programs, three parts: the
DSP-1A carries the DSP-1's program, so no DSP-1A image exists to find and none is
needed. It is still a part in its own right and is answered as one.

## Is it right
A machine holding no microcode still checks everything this package can get
wrong, because the part-specific knowledge is no longer in the code.

| Layer | What is checked | Needs an image |
|:--|:--|:--:|
| The processor | Every instruction, in [`nec-upd7725-96050-python`](https://github.com/gufranco/nec-upd7725-96050-python) | No |
| The port | The handshake, the pacing, the status register and the bus decode, driven by a program of zeroes | No |
| Timing | That the pacing follows from the two oscillators rather than from a chosen number | No |
| Identity | That every part names an image with a deciding digest, so a supplied file is confirmed rather than trusted | No |
| The catalogue | Every part, every name it answers to, and which image each runs | No |
| Every annotation | `mypy` at strict, plus every optional error class the version has | No |
| The documented widths | Every width, size and depth against the manufacturer's own datasheet, in the processor's [`conformance/hardware.json`](https://github.com/gufranco/nec-upd7725-96050-python/blob/main/conformance/hardware.json) | No |
| The parts | Driven through the exchanges a real cartridge makes with them | Yes |
| What each part answers | Re-derived and compared against what it answered when the corpus was taken | Yes |
| The DSP-1B correction | The pinned divergences between the two masks, re-derived | Yes |
| The return stack | That no shipped microcode drives it past the depth NEC gives the part | Yes |
| Recorded divergences | That where this and a behavioural model disagree, this still answers what was recorded | Yes |

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

One cartridge per part is not enough, and the DSP-1 is why. It shipped in more
than twenty games and each one drives it differently: one takes a command and a
burst, another polls between words, a third writes three words before it reads
one. A part settled against one of those is settled against one driver rather
than against the part, so every cartridge present is read and the shapes are
pooled.

| Part | Cartridges read | Shapes | That drive the part | Sites | How strong that is |
|:--|--:|--:|--:|--:|:--|
| DSP-1 | 29 | 44 | 21 | 1,404 | Strong. Twenty-nine drivers, so a shape most of them share is the protocol rather than one studio's habit |
| DSP-2 | 3 | 13 | 1 | 273 | Weak. Three regional releases of one game, and one exchange that drives the part |
| DSP-3 | 1 | 17 | 8 | 182 | Weak, and cannot improve. One cartridge carries a DSP-3 and that is all there ever was |
| DSP-4 | 3 | 38 | 29 | 919 | Moderate. Two games across three releases, but twenty-nine exchanges between them |

The last column is the point of the table. A single total across the four would
read as though the DSP-1 and the DSP-3 were checked alike, and they are not: one
is corroborated by twenty-nine independent drivers and the other by one, with no
second cartridge in existence to add. Both are driven by what a real game sends,
which is the claim being made. Only one of them is corroborated.

Each shape records how many cartridges used it. A shape two dozen games agree on
is the part's protocol; a shape one game uses is that game's corner, which is
exactly where a model is likely to be wrong.

A shape carries no payload, so the bytes filling it are generated, and the first
of them is a command the part may not have. Most of the 256 possible bytes are not
commands on these parts, and a part answering nothing to one of those has not been
shown to answer nothing: it has been asked a question it does not have. So a shape
that says nothing is asked again under every command byte in turn, and is reported
as silent only when all 256 leave it silent.

A shape whose first read comes before its first write is separate again. On a
console that read follows an earlier exchange and is answered by what that
exchange left behind; played on its own at a part that has just booted there is
nothing behind it, and no command can change that because the read happens first.
Three of the 59 shapes that both give and take are like this, and they are
reported as asked out of order rather than counted as silence.

Every other exchange, on all four parts, gets an answer.

```bash
python3 -m conformance.against_cartridges dsp1
python3 -m conformance.record            # re-read every cartridge on this machine
```

### What each part answered, kept

A run that drives a part proves it answers. It does not prove it answers the same
thing it answered last month. So what each part says to each exchange is recorded,
keyed to the digest of the image that said it and to the payload seed that
produced it:

```bash
python3 -m conformance.answers --take    # record what every part answers now
python3 -m conformance.answers           # check that it still answers that
```

| Part | Exchanges recorded |
|:--|--:|
| DSP-1 | 21 |
| DSP-2 | 1 |
| DSP-3 | 8 |
| DSP-4 | 29 |

A corpus is refused rather than failed when the image on this machine is not the
one it was taken from. Two different images are entitled to answer differently, so
there is nothing to compare and saying so is the honest answer.

### The correction in the DSP-1B, found rather than described

Nintendo shipped the same program on three parts. The DSP-1A is a die shrink and
carries the DSP-1's image byte for byte, so it cannot answer differently. The
DSP-1B is a later mask that corrected an arithmetic fault, and that is a claim
with a consequence: somewhere there is an input where the two disagree, and if
there is not, one of the two images is not what it says.

Running both programs makes the values right without knowing where that is. So
every command byte is swept across sixteen argument sets, six words each, and
every case where the two part company is pinned:

```bash
python3 -m conformance.masks --sweep     # find them
python3 -m conformance.masks             # re-derive the ones pinned
```

Across 256 commands and 16 argument sets it found one command, reached through six
of its encodings, where the third word out differs. Nothing else in that space
differs at all, which is what a corrected fault should look like rather than a
different program. A case that quietly becomes agreement fails as loudly as one
that changes value: two images agreeing everywhere are one image under two names.

### What each piece of evidence is worth

Not all of it is worth the same, and a project that lists its checks without
saying so invites a reader to assume the strongest applies to everything.

| Evidence | Rung | What it settles | What it cannot |
|:--|:--|:--|:--|
| The manufacturer's datasheet, pinned fact by fact with the sentence it came from | Highest | Widths, memory sizes, stack depth, clocks per instruction. Anything NEC printed | Anything NEC did not print, which includes almost all behaviour |
| The microcode itself, run on a model of the documented processor | Second | What a command does, because the program is what decides | Whether the surrounding layers hand it the right bytes at the right moment |
| Exchanges read out of real cartridges | Second | That the part answers what a shipped game actually asks | Anything no game asks. Coverage is uneven per part, as the table above says |
| Measurements of the real microcode, such as how deep it drives the stack | Second | What the shipped programs need | What the silicon does beyond what they need |
| Recordings from an independent implementation, in the processor's corpus | Third | Instruction-level behaviour nobody documented | Nothing about silicon. It is a reimplementation, however careful |
| Agreement between the two implementations in the processor repository | Third | That neither has drifted | Nothing about silicon: one author wrote both |

Where a rung disagrees with a lower one, the higher wins. That is not a
preference. It is why the return stack in this family is four deep here and
sixteen deep almost everywhere else: NEC printed four, and an implementation
carrying sixteen is a widely copied mistake rather than a second opinion.

The short form: the manufacturer decides what the part is, the part's own program
decides what it does, and an emulator decides neither.

**Open questions** are listed with the measurement that would close each one: [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). Where two sources part, both are kept in [`conformance/divergences.json`](conformance/divergences.json) with what would settle it.

## Working on it
```bash
python -m coverage erase
for file in $(find snesdsp conformance -name '*.test.py' | sort); do
  python -m coverage run -a "$file"
done
python -m coverage report
```

`python3 snesdsp/doctor.py` says what is actually on this machine: the parts, which image each wants, and whether the microcode this repository cannot carry is present and whole. It is run as a file rather than with `-m` so that it still runs when the package itself will not import, which is the case it exists for.

[`AGENTS.md`](AGENTS.md) is the document for an agent working here. [`FAMILY.md`](FAMILY.md) is the standard this repository shares with the rest of the family, kept identical in every member.

### Project structure

```text
snesdsp/
  __init__.py     the package, and the part chosen at construction
  models.py       which parts exist, what they answer to, which image each runs
  chip.py         loading an image and driving the part it belongs to
  timing.py       the two oscillators, and how long the console leaves the part
  doctor.py       what is actually on this machine, printed for a bug report
  version.py      rewritten by the release job and by nothing else
conformance/
  against_cartridges.py  drives a part with the exchanges a real cartridge makes
  documented.py   every example this README prints, run against the parts
  shapes.py       reads and replays those exchanges
  cartridges.py   finds and confirms the cartridges they were read from
  record.py       re-reads every cartridge on this machine and pools the shapes
  answers.py      what each part answered, and whether it still answers that
  masks.py        where the three masks of the DSP-1 disagree
  stack.py        how deep the shipped microcode drives the return stack
  divergences.json where this and a behavioural model answer differently
  driven.py       what these runs need a part to be, which is less than a part is
nec-upd7725-96050-python/  the processor all of these are, as a submodule at the root
```

Each module has its tests beside it as `<module>.test.py`, so a module and the
cases that pin its behaviour are read together.

### Tests

```bash
for f in snesdsp/*.test.py conformance/*.test.py; do python3 "$f"; done
```

| Area | File | What it pins |
|:--|:--|:--|
| The catalogue | [`snesdsp/models.test.py`](snesdsp/models.test.py) | Every part, its names, its image, and that the image is declared with a digest |
| The part | [`snesdsp/chip.test.py`](snesdsp/chip.test.py) | Loading, the handshake, the pacing, the bus decode, reading, refusing |
| Timing | [`snesdsp/timing.test.py`](snesdsp/timing.test.py) | The clocks, the conversion, and that the gap is derived rather than chosen |
| The doctor | [`snesdsp/doctor.test.py`](snesdsp/doctor.test.py) | Every check it makes, and that a check which throws is reported rather than swallowed |
| Cartridge exchanges | [`conformance/shapes.test.py`](conformance/shapes.test.py) | Reading a driver's accesses, replaying them, the payloads they are filled with |
| Driving a part | [`conformance/against_cartridges.test.py`](conformance/against_cartridges.test.py) | Playing every recorded exchange, and what silence means |
| Recording exchanges | [`conformance/record.test.py`](conformance/record.test.py) | Reading every cartridge present, pooling per part, confirming digests before disassembly |
| Recorded answers | [`conformance/answers.test.py`](conformance/answers.test.py) | Taking a corpus, comparing one, and refusing when the image differs |
| The mask divergence | [`conformance/masks.test.py`](conformance/masks.test.py) | Sweeping for disagreement, pinning it, and failing when it converges |
| The return stack | [`conformance/stack.test.py`](conformance/stack.test.py) | Following the pointer while a part is driven, and whether what it reaches fits the documented depth |
| Recorded divergences | [`conformance/divergences.test.py`](conformance/divergences.test.py) | That a recorded disagreement still says enough to check, and still holds |
| What a part must be | [`conformance/driven.test.py`](conformance/driven.test.py) | The contract these runs hold a part to, and the stand-ins that satisfy it |
| This document | [`conformance/documented.test.py`](conformance/documented.test.py) | That every example printed above still gives the answer printed beside it |

Coverage is enforced at 100% of statements and branches by
[`pyproject.toml`](pyproject.toml), so a new branch without a test fails the
build rather than quietly lowering the number.

### Development

| Command | Description |
|:--|:--|
| `ruff format .` | Format |
| `ruff check .` | Lint |
| `python3 -m coverage run -a <file>` | Run one test file under coverage |
| `python3 -m coverage report` | Coverage, which fails below 100% |
| `python3 -m snesdsp.doctor` | Say what is on this machine, for a bug report |
| `python3 -m conformance.against_cartridges <part>` | Drive a part with real cartridge exchanges |
| `mypy` | Types, at strict, with every optional error class on |
| `python3 -m conformance.documented` | Run every example in this README against the parts |
| `python3 -m conformance.record` | Re-read every cartridge on this machine |
| `python3 -m conformance.answers` | Check every part still answers what it answered |
| `python3 -m conformance.masks` | Re-derive where the DSP-1 masks disagree |
| `python3 -m conformance.stack` | Measure how deep the microcode drives the stack, about twenty minutes |
| `pnpm install` | Install the JSON formatter |
| `pnpm run format:check` | Check that every JSON file is formatted, which CI also does |

### Project conventions

| Convention | Source |
|:--|:--|
| Commit format | [Conventional Commits](https://www.conventionalcommits.org/) |
| Formatting and lint | [ruff](https://docs.astral.sh/ruff/), pinned in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Versioning | [semantic-release](https://semantic-release.gitbook.io/), from the commit history |
| Tests | Beside the module, named `<module>.test.py` |
| Types | [mypy](https://mypy.readthedocs.io/) at strict, configured in [`pyproject.toml`](pyproject.toml) |

### Reporting something

| Need | Where |
|:--|:--|
| Something is wrong | [Open an issue](https://github.com/gufranco/snes-dsp-python/issues/new/choose), with the doctor output |
| A part answers the wrong thing | The same, using the fidelity template |
| A change | [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) says what a change has to show |

Never attach microcode or a cartridge to a report, and never link to somewhere
either can be downloaded. A SHA-256 identifies both, and it is all anybody needs.

### Versioning

This project follows [Semantic Versioning](https://semver.org/). Every release is
tagged. See [releases](https://github.com/gufranco/snes-dsp-python/releases) for
the changelog and upgrade notes.

### FAQ

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

### Contributing

Measurements first. If you have a part, a cartridge, or a machine this has not
been run against, the most useful thing you can send is a run and what it found,
especially a disagreement. [CONTRIBUTING.md](CONTRIBUTING.md) has the gates a
change is expected to pass, [SECURITY.md](SECURITY.md) says what belongs in a
private report, and the [Code of Conduct](CODE_OF_CONDUCT.md) applies wherever
this project is discussed.

Never attach a copyrighted image or a game, and never link to somewhere one can
be downloaded. A digest identifies a file without carrying it.

## References
This repository carries no documents and no microcode. Every claim is traced to
something published elsewhere, listed here so a reader can fetch the same file
and check the same page. Each row gives the page count and the first sixteen
characters of the file's SHA-256, because vendor links move and a link that has
rotted into a different revision is easy to follow without noticing. Compute the
full digest with `shasum -a 256 <file>`.

Every manufacturer document below is copyrighted and not redistributable, which
is why none is in this repository. Individual sentences are quoted in
[`conformance/hardware.json`](conformance/hardware.json) with the page they came
from.

| Document | Date | Pages | SHA-256 | Redistributable |
|:---------|:-----|------:|:--------|:----------------|
| NEC, *uPD7725/uPD96050 Digital Signal Processor* data sheet | undated | 44 | see [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python) | No |

The processor underneath every part here has its own repository, and every fact
about it is recorded there rather than repeated here. Repeating it is how two
copies of one fact start disagreeing.

| Source | Used for |
|:-------|:---------|
| [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python) | The processor itself: its data sheet, its record, its divergences and its corpus |
| [snes-driver-python](https://github.com/gufranco/snes-driver-python) | Reading a cartridge's own code to find what it says to its coprocessor |
| Retail cartridges a reader already owns | The exchanges in [`conformance/dsp*answers.json`](conformance), each confirmed by digest before a byte of it is read |

## Citing this
[CITATION.cff](CITATION.cff) is kept in step with the released version by the
same script that stamps the package, so the version it names is the version that
shipped. GitHub renders it as a Cite this repository button.

## License
[MIT](LICENSE)
