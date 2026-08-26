# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

## What this project is, in one paragraph

The DSP-1, DSP-2, DSP-3 and DSP-4: four Nintendo cartridge coprocessors that are
one NEC uPD77C25 carrying four different programs. Nothing here describes what a
command computes, because the program is run rather than read: a reader supplies
the microcode they already own, its digest is confirmed, and the processor
executes it. What this repository models is everything Nintendo put around that
processor, which is the port decode, the pacing, the status register and the boot
handshake. The processor itself is
[nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python),
consumed as a submodule at the repository root. No Nintendo document about any of
these four parts is known to exist.

## The interface a caller drives

The part answers accesses. The cycles are spent inside the processor it composes,
and that member is the one that reports them, so none of the family's clocked
interface appears here.

`Chip(model, **options)` builds one. The model comes first, which is the argument
every member of the family takes first, and the name is the kind rather than the
chip so a traceback says what sort of thing it was.

| Call | What it does |
|:--|:--|
| `write(byte)` | One byte into the data port |
| `read()` | One byte out of the data port |
| `read_status()` | The status register, whose top bit is whether the part is asking |
| `write_bus(address, byte)`, `read_bus(address)` | The same two, addressed the way a console addresses them |
| `elapsed(master_clocks)` | Run the part for as long as the console spent |
| `step(count)` | Run the part for a number of its own steps |
| `reset()` | Back to power on with the same program, handed back for chaining |

## The authority ladder

1. **The microcode**, which is the part. The program masked into the silicon is
   what decides what a command answers, and it is run rather than described.
2. **What a manufacturer printed**, reached through the sibling that read it.
   Every fact about the uPD77C25 lives in that member's record, not in this one.
3. **Exchanges read out of retail cartridges**, 112 of them across 36 images,
   each confirmed by digest before a byte of it is disassembled.
4. **A behavioural model of the same part**, recorded in
   [`conformance/divergences.json`](conformance/divergences.json) where it
   answers differently, and never followed.

A rung above beats a rung below. That is why the return stack in this family is
four deep and not sixteen: NEC printed four.

## What is settled and what is not

**Not settled: 5 things**, each in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with the measurement that would close it.
The short version is that Nintendo published nothing, so the pacing, the boot
handshake and the port decode above its lowest bit are bounds and inferences
rather than printed figures, and they say so.

Settled: what every command computes, because the program is run; which image
each part runs, because each is pinned by digest; and everything about the
processor, because a sibling read the data sheet.

## The microcode is never carried

Not committed, not vendored, not linked to, not baked into an image, and not
reconstructible from anything here. Every image is named by digest and nothing
else. A digest updated to make a check pass is the failure the whole standard
exists to prevent.

## The four parts are five images

`SHARES_MICROCODE` is why the catalogue has six entries and the disk has five
images: the DSP-1, DSP-1A and DSP-1B are one part at three mask revisions, and
two of the three run the same program. Only the DSP-1B changed it, correcting a
fault in one of the maths routines, and that is the divergence the mask sweep
pins.

## Every gate, in the order to run them

```bash
ruff format --check .
ruff check .
mypy
pnpm run format:check
python3 -m coverage erase
for file in $(find snesdsp conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the model does:

```bash
python3 -m conformance.speed
```

The runs that need a reader's own files, which report what they could not check
rather than passing quietly:

```bash
python3 snesdsp/doctor.py
python3 -m conformance.against_cartridges dsp1
python3 -m conformance.quotes
```

Everything under `conformance/` runs as a module. Run as a script, its own
directory goes on the import path and a file there shadows any standard library
module of the same name. `doctor.py` is the exception and runs as a file on
purpose, so that it still runs when the package itself will not import, which is
the case it exists for.

## Conventions that are not negotiable

- Python only, standard library only, no dependencies.
- No comments in source. Reasoning goes in docstrings, and a step that would need
  a comment is a step that should be a named function.
- Tests sit beside the module they cover as `<module>.test.py`. Arrange, blank
  line, one act, blank line, assert, with no section labels.
- 100% statement and branch coverage, enforced. `mypy` at strict, with every
  optional error class on.
- Everything a caller can catch is defined once, in `snesdsp/errors.py`, and
  imported from there.
- A check nobody has seen fail is not known to work. Drive every new check
  against input that should fail it before keeping it.

## Layout

```text
snesdsp/
  __init__.py     the package, and the part chosen at construction
  models.py       which parts exist, what they answer to, which image each runs
  chip.py         loading an image and driving the part it belongs to
  timing.py       the two oscillators, and how long the console leaves the part
  errors.py       everything this package raises, in one place
  doctor.py       what is actually on this machine, printed for a bug report
  version.py      rewritten by the release job and by nothing else
conformance/
  family.test.py  the family standard, held to this repository
  against_cartridges.py  drives a part with the exchanges a real cartridge makes
  shapes.py       reads and replays those exchanges
  cartridges.py   finds and confirms the cartridges they were read from
  record.py       re-reads every cartridge on this machine and pools the shapes
  answers.py      what each part answered, and whether it still answers that
  masks.py        where the three masks of the DSP-1 disagree
  stack.py        how deep the shipped microcode drives the return stack
  quotes.py       looks for every quoted sentence in the document it cites
  speed.py        the throughput floor
  documented.py   every example the readme prints, run against the parts
nec-upd7725-96050-python/  the processor all of these are, as a submodule at the root
```

## Things that will bite you

- **The directory variable is `SNES_DSP_FIRMWARE_DIR`, and the old shared one
  still works.** `UPD7725_FIRMWARE_DIR` named this member's images and
  snes-st-python's at once, so a caller holding both sets could point at only
  one of them. It is now read after this member's own name rather than instead
  of it. A test pins both halves: the old name still finds a directory, and the
  new one wins when both are set.
- **The search order lives in three members and nothing holds them together.**
  `directories` in `firmware.py` is byte-identical here, in the other microcode
  member and in `sony-s-smp-python`, because no package is a dependency of all
  three. The recipe for diffing a copy against a sibling is in that function's
  own docstring. Change one and change the other two in the same task.
- **The submodule is not optional.** Without it nothing here can run, and the
  refusal says so rather than falling back to a guess.
- **A part cannot be built without an image.** `Chip("dsp1")` raises `NoFirmware`
  on a machine that has none, which is most machines. `why_not()` is the sentence
  to print, and it is what the family's own checks read before skipping.
- **`.core` is the processor, `.part` is the model name.** Two attributes one
  letter apart in meaning, and reaching for the wrong one gets a string where a
  processor was expected.
- **A reset rebuilds the processor.** It reloads the same image, because the
  image is what the mask holds. It does not re-read the file.
- **The doctor runs as a file.** Running it with `-m` imports the package first,
  which is exactly what fails on the machines the doctor exists to diagnose.

## Before calling anything finished

Every gate above, green, with output shown. A claim without a run behind it is
not evidence. If a check was skipped because a file is not on this machine, say
which check and why rather than reporting a pass.

## What a change is expected to leave behind

A test that fails without the change and passes with it. An entry in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) if it turned a settled thing into an open
one, or removed one. A record entry with the sentence and the page if it added a
fact from a document. Nothing in `firmware/` or `cartridges/` under version
control, ever.
