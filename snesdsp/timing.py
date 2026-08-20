"""How long the part runs for, in the console's terms rather than in guesses.

A part is only half of an exchange. The other half is when the console next
speaks to it, and that is not a number anybody here gets to choose: it follows
from two oscillators and from what a cartridge access costs the console.

The part runs one instruction per clock. So counting instructions is counting
cycles, and the only thing that was missing was the rate to count them at.

Three numbers decide everything below, and each is a property of the hardware:

    the part's oscillator          7,600,000 Hz for this whole family
    the console's master clock     six times its colour carrier
    what one cartridge access costs eight master clocks, or six on a fast board

The access alone is not the whole cost, and taking it for the whole cost is the
mistake this file exists to avoid making. A console does not touch a port out of
nowhere: it executes an instruction that touches it, and that instruction spends
several cycles of its own, each one costing what a cartridge access costs. A
store to a long address takes five, so the part gets around fourteen instructions
before the console can possibly speak again.

That is the floor rather than the usual case. A real driver was read to check:
Super Mario Kart puts between one and twelve of its own instructions between
consecutive accesses to the part, so in practice the part gets rather more. The
floor is what belongs here, because a default that assumed the usual case would
be quietly generous in exactly the situation where a game depends on catching the
part before it has finished.
"""

from .models import describe

NTSC_COLOURBURST = 3579545.4545454545
"""The colour carrier an NTSC console is built around, in hertz."""

PAL_COLOURBURST = 4433618.75

MASTER_CLOCK = round(NTSC_COLOURBURST * 6)
"""What an NTSC console counts in: six times its colour carrier."""

PAL_MASTER_CLOCK = round(PAL_COLOURBURST * 4.8)

SLOW_ACCESS = 8
"""Master clocks one cartridge access costs, which is what a coprocessor is."""

FAST_ACCESS = 6
"""The same on a board wired for it, in the half of the address space that allows it."""

DSP_CLOCK = 7_600_000
"""The oscillator every part in this family runs from.

One rate for all of them, because they are one piece of silicon with different
programs masked into it and the cartridge that carries one carries the same
crystal whichever it is.
"""


def clock_of(part: str) -> int:
    """The rate that part's oscillator runs at, refusing a name nobody answers to."""
    describe(part)
    return DSP_CLOCK


LONG_STORE_CYCLES = 5
"""Cycles a 65816 store to a long address takes, which is how a port is written.

The narrowest thing a console can do to a coprocessor. Every cycle of it reaches
memory and costs what an access costs, so this is what sets the floor below.
"""


def steps_for(master_clocks: int, clock: int = DSP_CLOCK, master: int = MASTER_CLOCK) -> int:
    """How many instructions the part gets while the console spends that long.

    Rounded down, because a part that is halfway through an instruction when the
    console speaks has not finished it, and crediting it with the whole one would
    let the model answer sooner than the hardware can.
    """
    return master_clocks * clock // master


GAP = steps_for(LONG_STORE_CYCLES * SLOW_ACCESS)
"""The least a console can leave the part between two accesses.

One store, five cycles, each costing a cartridge access, converted at the two
oscillators above. It comes out at fourteen instructions. Derived rather than
chosen, and a floor rather than a guess: a caller who knows how long their
console actually spent passes that instead.
"""
