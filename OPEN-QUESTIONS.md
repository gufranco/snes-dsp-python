# Open questions

What this project does not know for certain, and what it would take to find out.

Most of the list is short for a reason that is worth stating first: the part is
not modelled here at all. Four coprocessors and one processor underneath them,
and the processor is
[nec-upd7725-96050-python](https://github.com/gufranco/nec-upd7725-96050-python),
which carries its own record, its own divergences and its own open questions.
Everything NEC printed is settled there, and repeating any of it here would
create a second copy free to disagree with the first.

What is left for this repository is everything Nintendo put around that
processor: the port decode, the pacing, the boot handshake and which image each
part runs. Nintendo published nothing about any of it.

Every entry is also in
[`conformance/divergences.json`](conformance/divergences.json) with its status
and severity, so a program can read what a person reads here.

## Why running the microcode closes most of it

The strongest thing here is that the part is not described. A command's answer is
not written down anywhere in this repository: the program a reader supplies is
run, and what it computes is what comes out. That removes a whole class of
question, because a reimplementation of a masked program is a reimplementation of
somebody's reading of it, and there is no reading here to be wrong.

What it cannot remove is everything around the program. The port decode, the
pacing, the read semantics and the boot handshake are this repository's, and the
microcode says nothing about them.

## What would settle almost all of them

A logic analyser on a cartridge edge connector while a game runs, or one page of
a Nintendo document that nobody has published. Neither is available here, so the
entries below stay open and say so rather than being closed by an agreeable
number.

## Where no document exists at all

### How long a console leaves the part between two accesses.

**The document says.** Nothing. No Nintendo document on this machine names a
figure, and the NEC data sheet describes the part rather than the board it sits
on.

**What this project follows.** A floor derived from what one store to a long
address costs on the console's processor, which is the shortest gap a driver
could produce even if it tried.

**Why.** It is a bound rather than a measurement, and a bound is the honest shape
for a figure nobody printed. A driver that leaves more time than the floor is
served correctly by it; one that leaves less does not exist, because the
instruction that writes the port takes at least that long.

**What would settle or reopen it.** A capture of a real cartridge's accesses with
timestamps, or a Nintendo document naming a minimum.

### How long an image spends booting before it will answer.

**The document says.** Nothing. This is a property of each program rather than of
the silicon.

**What this project follows.** A step count large enough that every image on this
machine has settled, used as a limit rather than as a figure.

**Why.** The alternative is asking the part whether it is ready, which is what
the status register is for and which the model already does. The count exists so
a program that never becomes ready fails loudly instead of hanging.

**What would settle or reopen it.** Nothing published would. Measuring each
image's own settling time on hardware would.

### What the port decodes above its lowest bit.

**The document says.** Nothing.

**What this project follows.** That the lowest bit of the address chooses between
the data port and the status register, and that nothing above it is examined.

**Why.** It follows from the only bit any driver varies. Every exchange read out
of thirty six cartridges touches one of two addresses that differ in that bit
alone, so the decode above it is unconstrained by anything observed rather than
established as absent.

**What would settle or reopen it.** A driver that addresses the part somewhere
else, or a board schematic.

## Where a source disagrees and neither can be promoted

### What a DSP-3 answers to command `0x1c`.

**The document says.** Nothing. There is no document.

**What this project follows.** The microcode, which is the part.

**Why.** A behavioural model of the same chip answers differently, and it is
recorded in [`conformance/divergences.json`](conformance/divergences.json)
rather than followed. A model only has to be right about what the one cartridge
carrying a DSP-3 actually asks, and nothing establishes that this command is
among them.

**What would settle or reopen it.** Finding the command in SD Gundam GX's own
code, which would make the disagreement matter, or establishing that it is never
sent, which would make it moot.

**Why that is not a matter of looking.** It was tried on 2026-08-27. The
cartridge is here and
[snes-driver-python](https://github.com/gufranco/snes-driver-python) finds 282
places in it that reach the part, so the sites are not the problem. What that
package records is the shape of each conversation, the widths and the order of
reads, writes and polls, and never the value a write carries: a `Step` holds
what, width, address and bank. So it can say that this routine writes nine bytes
and reads eight, and it cannot say which command those bytes are.

Settling this therefore needs that package to report written values, which means
tracking the immediate an instruction loaded before the store that reaches the
window. That is a feature of the reader rather than a fact about this part, and
it is worth naming here so the next reader does not spend an afternoon expecting
to grep for it. Scanning the image for a load of `0x1c` near a store to the port
is not the same thing and would not be evidence.

## Where coverage is uneven rather than absent

### What the parts answer to commands no shipped game sends.

**The document says.** Nothing.

**What this project follows.** The microcode, for every command, including the
ones no cartridge issues.

**Why.** The program is run rather than described, so an unasked command is
answered by the same mechanism as an asked one. What is uneven is the
confirmation: the DSP-1 is exercised by many cartridges and the DSP-3 by one.

**What would settle or reopen it.** More cartridges, which raises confirmation
without changing what the model does.

## What is not in question

So the boundary is visible rather than implied:

- **What each command computes.** The program decides, and the program is run.
  Nothing here describes a command.
- **Which image each part runs.** Recorded with a deciding digest, so a supplied
  file is confirmed rather than trusted.
- **That the pacing follows from the two oscillators.** Derived rather than
  chosen, and a test asserts the derivation rather than the number.
- **Everything about the processor.** Settled in the member that models it,
  against NEC's own data sheet.

## What is deliberately not modelled

Absent rather than unknown, and absent on purpose:

- **The processor.** It has a repository. Modelling it twice is how two models
  start disagreeing.
- **Any microcode.** Nintendo's programs are not carried, not linked to and not
  reconstructible from anything here. Everything published is a digest.
- **The cartridge board.** Where the part sits in the memory map is
  [snes-mapper-python](https://github.com/gufranco/snes-mapper-python).
