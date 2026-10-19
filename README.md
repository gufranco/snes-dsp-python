# SNES DSP

The Nintendo DSP-1, DSP-1A, DSP-1B, DSP-2, DSP-3 and DSP-4 in Python: one NEC uPD77C25 running the microcode you supply, held to the exchanges retail cartridges make with it.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/snes-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/snes-dsp-python)](https://github.com/gufranco/snes-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**6** parts on **5** microcode images, **121** exchanges read out of **36** retail cartridges, **62** of them played at the part, **0** failures, **0** commands described by hand, **993** tests, **100%** statement and branch coverage, no dependencies

```python
import snesdsp

part = snesdsp.Chip("dsp2")
part.write(0x09)
for byte in (0x02, 0x00, 0x03, 0x00):
    part.write(byte)
print([part.read() for _ in range(4)])
print(part, part.model, part.identity.part)
```

```
[6, 0, 0, 0]
<Chip dsp2 on upd7725> dsp2 dsp2
```

The example builds a DSP-2, which loads the DSP-2 microcode into a uPD77C25 and boots it. Command `0x09` multiplies two 16-bit words sent low byte first. The answer is 2 times 3 in the first word, and the program in the image computed it. No line of this package says what command `0x09` does.

## Install

| Requirement | Version                                                                                                          |
| :---------- | :--------------------------------------------------------------------------------------------------------------- |
| Python      | 3.12 or newer                                                                                                    |
| git         | Any, to fetch the submodules                                                                                     |
| Microcode   | A copy you own of each image you want to run, listed under [The microcode you supply](#the-microcode-you-supply) |

```bash
git clone --recurse-submodules https://github.com/gufranco/snes-dsp-python.git
cd snes-dsp-python
python3 snesdsp/doctor.py
```

The package imports nothing outside the standard library. The processor is the `nec-upd7725-96050-python` submodule at the repository root, and nothing runs without it. The `snes-driver-python` submodule is used only to re-read cartridges. A source archive from the download-zip link carries neither submodule, so there every part refuses to build and says why.

The doctor checks the machine, the checkout, every part and the processor underneath, and ends with one line. Paste its whole output into any bug report. With all five images present it ends:

```
  17 checks, nothing to report
```

Without an image, the line for each part that needs it says where a copy goes.

Releases follow [Semantic Versioning](https://semver.org/) and are cut from the commit history by semantic-release. Every release is tagged and listed on the [releases page](https://github.com/gufranco/snes-dsp-python/releases).

## The interface

`snesdsp.Chip(model, **options)` builds one part and boots it. `model` is required and is matched without regard to case, hyphens or underscores. A part is built only when its image is present: there is no fallback, and a part that cannot be built raises `NoFirmware`.

| Option     | Default  | Meaning                                                                             |
| :--------- | :------- | :---------------------------------------------------------------------------------- |
| `gap`      | `14`     | Instructions the part runs after each access, the least a console can leave it      |
| `patience` | `400000` | Instructions a read waits for the part to ask before reading anyway                 |
| `boot`     | `20000`  | Instructions run after loading, before the first access                             |
| `fill`     | `0`      | The value the processor's memories hold before the image is loaded                  |
| `image`    | none     | The image bytes, handed in so no directory is searched. Needs `identity`            |
| `identity` | none     | What `image` is, as `snesdsp.identify(image)` returns it                            |
| `images`   | none     | A mapping of part name to `(identity, path)`, used in place of the directory search |

### Models

| Model   | Aliases                                    | Runs the image of | What the program does                                                                             |
| :------ | :----------------------------------------- | :---------------- | :------------------------------------------------------------------------------------------------ |
| `dsp1`  | `dsp-1`, `upd77c25dsp1`, `nintendodsp1`    | `dsp1`            | 31 commands of fixed-point 3D maths: a camera, three attitude matrices, projections and rotations |
| `dsp1a` | `dsp-1a`, `upd77c25dsp1a`, `nintendodsp1a` | `dsp1`            | The DSP-1 program and data ROM on a smaller die                                                   |
| `dsp1b` | `dsp-1b`, `upd77c25dsp1b`, `nintendodsp1b` | `dsp1b`           | The last DSP-1 mask, 31 commands, with an arithmetic fault corrected                              |
| `dsp2`  | `dsp-2`, `upd77c25dsp2`, `nintendodsp2`    | `dsp2`            | 6 commands: tile conversion, transparent colour, merge, mirror, multiply and rescale              |
| `dsp3`  | `dsp-3`, `upd77c25dsp3`, `nintendodsp3`    | `dsp3`            | 13 commands: a decompressor, a bit plane converter and a search across a hex grid                 |
| `dsp4`  | `dsp-4`, `upd77c25dsp4`, `nintendodsp4`    | `dsp4`            | 15 commands, 7 of them road renderers that suspend part way through and resume                    |

### Calls

| Call                        | Effect                                                                                                                   |
| :-------------------------- | :----------------------------------------------------------------------------------------------------------------------- |
| `write(value)`              | One byte into the data port, then `gap` instructions                                                                     |
| `read()`                    | Waits up to `patience` instructions for the part to ask, reads one byte from the data port, then runs `gap` instructions |
| `read_status()`             | The status register. Bit 7 is RQM, set while the part asks for the next byte                                             |
| `write_bus(address, value)` | `write(value)` when bit 0 of `address` is 0, a write to the status port when it is 1. Returns the part                   |
| `read_bus(address)`         | `read()` when bit 0 of `address` is 0, `read_status()` when it is 1                                                      |
| `step(count=None)`          | Runs `count` instructions, or `gap` when `count` is left out                                                             |
| `elapsed(master_clocks)`    | Runs as many instructions as the part executes in that many console master clocks. Returns the part                      |
| `waited()`                  | Steps until the part asks, up to `patience` instructions. True when it asked                                             |
| `settle()`                  | `waited()`, raising `NeverReady` when the part never asked                                                               |
| `reset()`                   | Rebuilds the processor, reloads the same image bytes and boots again. Returns the part                                   |

### State

| Attribute         | Meaning                                                                                |
| :---------------- | :------------------------------------------------------------------------------------- |
| `model`, `part`   | The canonical model name                                                               |
| `identity`        | The image's `Identity`: `part`, `processor`, `revision`, `program_words`, `data_words` |
| `processor`       | The processor the image runs on, `upd7725` for every part here                         |
| `asking`          | True while RQM is set                                                                  |
| `pending_output`  | 1 while the part asks, else 0                                                          |
| `clock`           | The part's clock in Hz                                                                 |
| `gap`, `patience` | The two options above, writable                                                        |
| `core`            | The `upd7725` processor running the image                                              |
| `console`         | The processor's host port the calls above go through                                   |

### Module contents

| Name                                                                     | Content                                                                                                                                                                  |
| :----------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `snesdsp.MODELS`                                                         | The six `Model` records, keyed by canonical name. Each has `name`, `aliases`, `summary` and `image`                                                                      |
| `snesdsp.Model`                                                          | The type of those records                                                                                                                                                |
| `snesdsp.SHARES_MICROCODE`                                               | `{"dsp1a": "dsp1"}`, the one part that runs another part's image                                                                                                         |
| `snesdsp.available(held=None)`                                           | The parts whose image is on this machine, as a mapping of part name to `(identity, path)`. Given `held`, a mapping of the same shape, it reads that instead of searching |
| `snesdsp.why_not(held=None)`                                             | `None` when at least one part can be built, otherwise the sentence saying why none can. Takes the same `held`                                                            |
| `snesdsp.MASTER_CLOCK`                                                   | `21477273`, the console's master clock in Hz, six times the NTSC colour carrier                                                                                          |
| `snesdsp.DSP_CLOCK`                                                      | `7600000`, the part's clock in Hz, one instruction per clock                                                                                                             |
| `snesdsp.GAP`                                                            | `14`, the default `gap`                                                                                                                                                  |
| `snesdsp.clock_of(model)`                                                | The clock of that model in Hz. Raises `UnknownModelError` for an unknown name                                                                                            |
| `snesdsp.steps_for(master_clocks, clock=DSP_CLOCK, master=MASTER_CLOCK)` | Instructions run in that many master clocks, rounded down                                                                                                                |
| `snesdsp.__version__`                                                    | The installed version                                                                                                                                                    |
| `snesdsp.identify(image, catalogue=None)`                                | The image's `Identity`, found by SHA-256 in the manifest or in `catalogue`, a mapping of the manifest's shape. Raises `Unrecognised` or `Corrupt`                        |
| `snesdsp.digests_of(image)`                                              | The image's CRC32, MD5, SHA-1 and SHA-256, as lowercase hex keyed `crc32`, `md5`, `sha1` and `sha256`                                                                    |
| `snesdsp.directories(environment=None)`                                  | The directories the search reads, in order, from `environment` or the process environment                                                                                |
| `snesdsp.search(places=None, catalogue=None)`                            | Every image found in `places`, or in `directories()`, as `(identity, path)` pairs, the first file found for a part winning                                               |

```python
import snesdsp

for name, model in snesdsp.MODELS.items():
    print(name, model.image, model.aliases)

print(snesdsp.SHARES_MICROCODE)
print(snesdsp.MASTER_CLOCK, snesdsp.DSP_CLOCK, snesdsp.GAP, snesdsp.clock_of("DSP-1"))
print(snesdsp.steps_for(snesdsp.MASTER_CLOCK // 60))

for wrong in ("dsp5", None):
    try:
        snesdsp.Chip(wrong)
    except snesdsp.UnknownModelError as error:
        print(error)
```

```
dsp1 dsp1 ('dsp-1', 'upd77c25dsp1', 'nintendodsp1')
dsp1a dsp1 ('dsp-1a', 'upd77c25dsp1a', 'nintendodsp1a')
dsp1b dsp1b ('dsp-1b', 'upd77c25dsp1b', 'nintendodsp1b')
dsp2 dsp2 ('dsp-2', 'upd77c25dsp2', 'nintendodsp2')
dsp3 dsp3 ('dsp-3', 'upd77c25dsp3', 'nintendodsp3')
dsp4 dsp4 ('dsp-4', 'upd77c25dsp4', 'nintendodsp4')
{'dsp1a': 'dsp1'}
21477273 7600000 14 7600000
126666
dsp5 is not a part this package covers; it has dsp1, dsp1a, dsp1b, dsp2, dsp3, dsp4
no model was named, and this package will not choose one for you. Name one of: dsp1, dsp1a, dsp1b, dsp2, dsp3, dsp4
```

A sixtieth of a second of master clocks is 126,666 instructions of the part.

### Errors

| Error               | Raised when                                                                                                                  |
| :------------------ | :--------------------------------------------------------------------------------------------------------------------------- |
| `UnknownModelError` | The model name is missing or no model goes by it. The message lists every model                                              |
| `NoFirmware`        | The processor submodule is not checked out, no image for the part was found, or `image` was passed without `identity`        |
| `NeverReady`        | `settle()` ran `patience` instructions and the part never asked                                                              |
| `Unrecognised`      | `snesdsp.identify` was given bytes whose SHA-256 no image in the manifest has. The message says what the file most likely is |
| `Corrupt`           | An image matched on SHA-256 and disagreed on another digest the manifest records                                             |
| `WrongShape`        | `image` is not the length its `identity` needs: 3 bytes per program word and 2 per data word                                 |

```python
from pathlib import Path

import snesdsp

if snesdsp.why_not():
    raise snesdsp.NoFirmware(snesdsp.why_not())

identity, where = snesdsp.available()["dsp1b"]
held = Path(where).read_bytes()
print(snesdsp.identify(held), identity.program_words, identity.data_words, len(held))

part = snesdsp.Chip("dsp1b", image=held, identity=identity)
print(part.identity.part, part.processor)

for wrong in (held[:-2], held[::-1]):
    try:
        snesdsp.identify(wrong)
    except snesdsp.Unrecognised as error:
        print(str(error)[:72])
try:
    snesdsp.Chip("dsp1b", image=held[:-2], identity=identity)
except snesdsp.WrongShape as error:
    print(error)

slow = snesdsp.Chip("dsp1", patience=0)
slow.write(0x00)
try:
    slow.settle()
except snesdsp.NeverReady as error:
    print(error)
```

```
<Identity dsp1b DSP-1B on upd7725> 2048 1024 8192
dsp1b upd7725
this is 8190 bytes, and the manifest knows no part of that length (it kn
this is 8192 bytes, the length of dsp1, dsp1b, dsp2, dsp3, dsp4, but its
a upd7725 takes 8192 bytes of firmware and this is 8190
dsp1 did not ask for attention within 0 instructions
```

The example hands an image straight in, so no directory is searched. Every image is 2,048 program words and 1,024 data words. A file two bytes short is refused by length, and the same bytes reversed are refused by content.

## The microcode you supply

The microcode is not carried here, not downloaded and not linked to. Every image is identified by SHA-256 before a byte of it runs. [`snesdsp/artifacts.manifest.json`](snesdsp/artifacts.manifest.json) holds the digests.

| Image   | Parts that run it | Bytes | CRC32      | SHA-256                                                            |
| :------ | :---------------- | ----: | :--------- | :----------------------------------------------------------------- |
| `dsp1`  | `dsp1`, `dsp1a`   | 8,192 | `27124599` | `5f2e5ed06b362be023b978b5978813ecb9a07c76592454b45c2a1ed17a0de349` |
| `dsp1b` | `dsp1b`           | 8,192 | `588279b4` | `4d42db0f36faef263d6b93f508e8c1c4ae8fc2605fd35e3390ecc02905cd420c` |
| `dsp2`  | `dsp2`            | 8,192 | `f0221c90` | `5efbdf96ed0652790855225964f3e90e6a4d466cfa64df25b110933c6cf94ea1` |
| `dsp3`  | `dsp3`            | 8,192 | `e3b54e6a` | `2e635f72e4d4681148bc35429421c9b946e4f407590e74e31b93b8987b63ba90` |
| `dsp4`  | `dsp4`            | 8,192 | `ca09e176` | `63ede17322541c191ed1fdf683872554a0a57306496afc43c59de7c01a6e764a` |

The search reads files ending `.bin` or `.rom` from these directories, in order, and the first file found for a part wins:

1. Every directory in `SNES_DSP_FIRMWARE_DIR`, separated the way the operating system separates `PATH`.
2. Every directory in `UPD7725_FIRMWARE_DIR`, the name this member once shared with snes-st-python.
3. [`firmware/`](firmware/README.md) in the directory that holds this checkout, for when it is a submodule of another project.
4. [`firmware/`](firmware/README.md) in this checkout.

A file whose SHA-256 is not in the manifest is skipped by the search. Handed to `snesdsp.identify`, it is refused with a diagnosis: a copier header, a byte-swapped dump and a known bad dump are each recognised and named.

Confirm a copy you hold:

```bash
shasum -a 256 firmware/dsp1.bin                 # macOS
sha256sum firmware/dsp1.bin                     # Linux
certutil -hashfile firmware\dsp1.bin SHA256     # Windows
```

## Driving it the way a console does

A console reaches the part through an address. Bit 0 of that address picks the port: 0 is the data port and 1 is the status register. No higher bit is decoded, so one part answers across a whole address window.

The part runs one instruction per clock at 7,600,000 Hz. The console counts master clocks at 21,477,273 Hz and spends 8 of them on a slow cartridge access. A 65816 store to a long address takes 5 cycles, so the least a console can leave the part between two accesses is 40 master clocks, which is 14 instructions. That is the default `gap`. A console that spent longer says so with `elapsed`.

```python
import snesdsp

part = snesdsp.Chip("dsp1")
print(f"{part.read_bus(0x3F8001):#04x}", part.asking)

part.write_bus(0x3F8000, 0x00)
for word in (0x4000, 0x2000):
    part.write_bus(0x3F8000, word & 0xFF)
    part.write_bus(0x3F8000, word >> 8)
low, high = part.read_bus(0x3F8000), part.read_bus(0x3F8000)
print(hex(low | high << 8), f"{part.read_status():#04x}")
print(part.gap, part.patience, part.clock)
print(part.elapsed(snesdsp.MASTER_CLOCK // 60) is part, part.reset() is part)
```

```
0x84 True
0x1000 0x84
14 400000 7600000
True True
```

The odd address reads the status register, with RQM set after boot. The even address carries DSP-1 command `0x00`, a multiply, and its two arguments. `0x4000 * 0x2000 >> 15` is `0x1000`.

## Driving every part

Each output below is what the part's own microcode answered. [`conformance/documented.py`](conformance/documented.py) runs the same exchanges against the parts on every pipeline run that has the images.

### DSP-1

A command byte, then little-endian argument words, then the answer the same way. Command `0x00` multiplies two fixed-point words.

```python
from snesdsp import Chip

part = Chip("dsp1")
part.write(0x00)
for value in (0x4000, 0x2000):
    part.write(value & 0xFF)
    part.write(value >> 8)
low, high = part.read(), part.read()
print(hex(low | (high << 8)))
```

```
0x1000
```

### DSP-1A

There is no DSP-1A image. Building one runs the DSP-1's.

```python
from snesdsp import Chip

part = Chip("dsp1a")
print(part.model, part.identity.part)
```

```
dsp1a dsp1
```

### DSP-1B

The DSP-1B runs its own image. Its correction is not in the multiply, which gives `0x1000` here too. Where the correction is lies under [Is it right](#is-it-right).

```python
from snesdsp import Chip

part = Chip("dsp1b")
part.write(0x00)
for value in (0x4000, 0x2000):
    part.write(value & 0xFF)
    part.write(value >> 8)
low, high = part.read(), part.read()
print(part.identity.part, hex(low | (high << 8)))
```

```
dsp1b 0x1000
```

### DSP-2

Command `0x09` is an integer multiply rather than a fixed-point one.

```python
from snesdsp import Chip

part = Chip("dsp2")
part.write(0x09)
for value in (0x0002, 0x0003):
    part.write(value & 0xFF)
    part.write(value >> 8)
print([hex(part.read()) for _ in range(4)])
```

```
['0x6', '0x0', '0x0', '0x0']
```

### DSP-3

The DSP-3 takes a word at a time. Command `0x001c` answers with the last word written, for as long as anything reads.

```python
from snesdsp import Chip

part = Chip("dsp3")
for byte in (0x1C, 0x00):
    part.write(byte)
for byte in (0x34, 0x12, 0x78, 0x56):
    part.write(byte)
print(" ".join(f"{part.read():02x}" for _ in range(8)))
```

```
78 56 78 56 78 56 78 56
```

snes9x's DSP-3 code answers this command with two zero words. [`conformance/divergences.json`](conformance/divergences.json) records the disagreement, and [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) says what would settle whether any game sends it.

### DSP-4

The DSP-4 takes a command word and parameters, then answers in batches.

```python
from snesdsp import Chip

part = Chip("dsp4")
part.write(0x01)
part.write(0x00)
for value in (0x0001, 0x0002, 0x0003, 0x0004):
    part.write(value & 0xFF)
    part.write(value >> 8)
print([hex(part.read()) for _ in range(6)])
```

```
['0x4', '0x0', '0x4', '0x0', '0x4', '0x0']
```

## Is it right

What a command computes is the program's answer, so the checks here hold everything around the program: the port, the pacing, the identity of each image, and the exchanges real games make.

| Check                                                                   | Command                                                                             | Needs images |
| :---------------------------------------------------------------------- | :---------------------------------------------------------------------------------- | :----------: |
| The processor, instruction by instruction                               | In [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python) |      No      |
| The port, the pacing, the status register and the bus decode            | The unit tests beside each module                                                   |      No      |
| Every model, alias and image, and that each image has a deciding digest | The unit tests beside each module                                                   |      No      |
| Every exchange a cartridge makes gets an answer                         | `python3 -m conformance.against_cartridges <part>`                                  |     Yes      |
| Every part still answers what it answered when the corpus was taken     | `python3 -m conformance.answers`                                                    |     Yes      |
| The DSP-1 and DSP-1B images still disagree where they were found to     | `python3 -m conformance.masks`                                                      |     Yes      |
| No shipped microcode drives the return stack past 4 levels              | `python3 -m conformance.stack`                                                      |     Yes      |
| Every README example prints what it says                                | `python3 -m conformance.documented`                                                 |     Yes      |
| Stepping stays above 150,000 instructions per second                    | `python3 -m conformance.speed`                                                      |     Yes      |

Each tool that needs an image exits 2 and says what is missing when none is present, rather than passing.

### The exchanges

What a game sends is read out of the cartridge by [snes-driver-python](https://github.com/gufranco/snes-driver-python), which disassembles the routine that drives the part. Each result is a shape: the order and width of the accesses, with no payload. [`cartridges.manifest.json`](cartridges.manifest.json) names every cartridge by digest, and no byte of any cartridge is stored.

| Part  | Cartridges | Shapes | Played at the part | Access sites |
| :---- | ---------: | -----: | -----------------: | -----------: |
| DSP-1 |         29 |     50 |                 22 |        1,384 |
| DSP-2 |          3 |     13 |                  1 |          270 |
| DSP-3 |          1 |     20 |                 10 |          182 |
| DSP-4 |          3 |     38 |                 29 |          910 |

The DSP-1 rows come from 29 different drivers. The DSP-3 rows come from one cartridge, the only one that carries the part.

A shape carries no payload, so its bytes are generated from a fixed seed. A shape the part answers with silence is played again under each of the 256 command bytes, and counts as silent only when all 256 are. Four shapes, one on the DSP-1, two on the DSP-3 and one on the DSP-4, read before they write: on a console they read what an earlier exchange left, so they are reported apart rather than counted as silence. Every other shape gets an answer.

```bash
python3 -m conformance.against_cartridges dsp1
python3 -m conformance.answers --take dsp1
python3 -m conformance.answers
python3 -m conformance.record
```

`against_cartridges` takes one part, `dsp3` when none is named, and exits 1 when any exchange stays silent. The DSP-1A and DSP-1B are played the DSP-1 shapes, since no dump shows which mask a DSP-1 board carries and all three take the same commands. `answers` takes part names, all of them by default, exits 1 on a changed answer, and exits 2 when the image on this machine is not the one the corpus was taken from. It exits 1 with no image present when a part has no corpus, or when the corpus was not taken over the shapes swept today in the same order: every payload comes from one seeded stream, so a moved shape changes the payload of every shape after it. `--take` records answers instead of checking them. `record` re-reads every cartridge in [`cartridges/`](cartridges) or `SNES_CARTRIDGE_DIR` and exits 2 when none is present.

### The DSP-1B correction

The DSP-1B corrected an arithmetic fault, so some input must make the two masks disagree. `python3 -m conformance.masks --sweep` runs both images over 256 command bytes and 16 argument sets of 6 words each. It found 6 command bytes, `0x04`, `0x0b`, `0x1b`, `0x24`, `0x2b` and `0x3b`, that differ on one argument set, from the third word of the answer on. Nothing else in that space differs. `python3 -m conformance.masks` re-derives those 6 and exits 1 when any of them changes or turns into agreement.

### Where the evidence comes from

| Evidence                                         | What it settles                                               | What it cannot                                                                                      |
| :----------------------------------------------- | :------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------- |
| NEC's data sheet, through the processor's record | Widths, memory sizes, a 4-level stack, clocks per instruction | Behaviour NEC did not print                                                                         |
| The microcode, run on that processor             | What every command computes                                   | Whether the port hands it the right bytes at the right moment                                       |
| Exchanges read out of cartridges                 | That the part answers what a shipped game asks                | Anything no game asks                                                                               |
| A behavioural model of the same part             | Nothing: it is never followed                                 | Recorded only where it disagrees, in [`conformance/divergences.json`](conformance/divergences.json) |

Nintendo published nothing about these parts. The pacing, the boot length and the decode above bit 0 are bounds, and [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) lists each with the measurement that would settle it. [`conformance/hardware.json`](conformance/hardware.json) records the authority order and what this member is compared against.

## Working on it

| Need                                                            | Where                                                                                         |
| :-------------------------------------------------------------- | :-------------------------------------------------------------------------------------------- |
| Every gate and the order to run them                            | [CONTRIBUTING.md](CONTRIBUTING.md)                                                            |
| The same material for a coding agent                            | [AGENTS.md](AGENTS.md)                                                                        |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md)                                                                        |
| Bug reports and wrong answers                                   | [GitHub Issues](https://github.com/gufranco/snes-dsp-python/issues), with the doctor's output |
| Security reports                                                | [SECURITY.md](SECURITY.md)                                                                    |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 --with types-setuptools==84.0.0.20260812 mypy==1.14.1
pnpm run format:check
cov=(uvx --python 3.12 --from coverage==7.6.10 --with setuptools==84.0.0 coverage)
"${cov[@]}" erase
for file in $(find snesdsp conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$file"
done
"${cov[@]}" report
python3 -m conformance.speed
```

Each module has a test file beside it, named `<module>.test.py`, and each runs on its own. Coverage is a hard gate at 100% statement and branch. The throughput floor runs outside the coverage step. Never attach microcode or a cartridge to a report: a SHA-256 identifies either.

## References

- NEC, _uPD7725/uPD96050 Digital Signal Processor_ data sheet. Every fact taken from it is recorded, with its page, in [nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python), which this repository carries as a submodule. It is not redistributable and is not in this repository.
- snes9x, `dsp3.cpp` at commit `2971061cf07fdc6fc7d18883edf4e648eb16a6d2`, https://github.com/snes9xgit/snes9x, read only to state the one recorded disagreement. Nothing here follows it.
- [snes-driver-python](https://github.com/gufranco/snes-driver-python), for reading what a cartridge's own code sends to its coprocessor.
- Retail cartridges the reader owns, each confirmed by digest against [`cartridges.manifest.json`](cartridges.manifest.json) before it is read.

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version.

## License

MIT. See [LICENSE](LICENSE).
