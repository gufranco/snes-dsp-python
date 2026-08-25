"""Run the part's own microcode instead of modelling what it computes.

The models beside this were derived by working out what each command does and
writing that down. That can be checked but it can never be finished: you only
learn about the commands somebody thought to try, and the measured disagreements
are exactly the commands nobody had reason to look at.

This takes the other route. The part is a processor and a mask ROM, so given the
ROM there is nothing left to derive: run the program and whatever it answers is
what the part answers, including the corners nobody has characterised. Fidelity
stops being something to argue about and becomes a property of the arrangement.

What it costs is the ROM. That belongs to whoever made the part, so it is never
carried here and this backend exists only when its owner supplies one. The models
are what the package can do without.

Nothing here knows how many bytes a command answers with, and that is deliberate.
The console does not know either: it writes bytes and watches one bit that says
whether the part wants attention. A table of answer lengths would be one more
thing derived by hand, which is the very thing this exists to avoid.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from snesdsp.errors import NeverReady, NoFirmware

if TYPE_CHECKING:  # pragma: no cover
    from types import ModuleType

from . import timing

ROOT = Path(__file__).resolve().parent.parent

PROCESSOR = ROOT / "nec-upd7725-python"

BOOT_STEPS = 20000
"""Instructions to run before the part is spoken to.

An image starts by setting up its own state and only then waits. Speaking to it
first is speaking over the top of that, and the answers come back plausible and
wrong rather than obviously broken.
"""

GAP = timing.GAP
"""Instructions to run between one console access and the next.

Not a number chosen here. It is what the console's own clocks leave the part
while it performs the narrowest access it can make, which is one store to a long
address. A caller who knows how long their console actually spent says so with
`elapsed` instead.
"""

STATUS_BIT = 0
"""The address bit that decides whether an access is the port or the register.

Even is the data port and odd is the status register. Nothing about the address
above that bit matters, which is why a coprocessor answers across a whole window
rather than at one address.
"""

SETTLE_LIMIT = 400000
"""How long to wait for the part to ask for attention before giving up."""

WHY_NOT_PROCESSOR = (
    "the processor is not here: this backend runs the part's own microcode on"
    " the NEC uPD7725, which sits beside this package as a submodule, so it has"
    " to be checked out with git submodule update --init --recursive"
)

WHY_NOT_FIRMWARE = (
    "no firmware image was found: this backend runs the part's own microcode, and"
    " that microcode belongs to whoever made the part, so a copy you already own"
    " goes in the firmware directory or wherever UPD7725_FIRMWARE_DIR points"
)


SHARES_IMAGE = {"dsp1a": "dsp1"}
"""Parts that run somebody else's image because they are the same program.

The DSP-1A is a die shrink of the DSP-1 and carries the same program and data
ROM, so there is no DSP-1A image to find and none of the dumps in circulation
has one. It is still a distinct part with its own die, and it is answered here as
one, but the microcode it runs is the DSP-1's.

Only the DSP-1B changed the program, correcting a fault in one of the maths
routines. That is the difference the two images already measured disagree on.
"""


def _processor() -> tuple[ModuleType, ModuleType, ModuleType] | None:
    """The processor package, or nothing when the submodule is absent."""
    if str(PROCESSOR) not in sys.path:
        sys.path.insert(0, str(PROCESSOR))
    try:
        from upd7725 import firmware, models, ports
    except ImportError:
        return None
    return firmware, models, ports


def available(held: dict[str, tuple[Any, Path]] | None = None) -> dict[str, tuple[Any, Path]]:
    """Every part there is an image for, by the name the part is known as.

    `held` is what was found on disk, passed in so the sharing below can be
    exercised without an image for every part being present.
    """
    if held is None:
        found = _processor()
        if found is None:
            return {}
        held = {identity.part: (identity, path) for identity, path in found[0].search()}
    held = dict(held)
    for part, shared in SHARES_IMAGE.items():
        if shared in held:
            held.setdefault(part, held[shared])
    return held


def why_not(held: dict[str, tuple[Any, Path]] | None = None) -> str | None:
    """Why this backend cannot run, or nothing when it can.

    `held` is passed through to `available` for the same reason it exists there:
    so the answer can be checked on a machine that has no image at all.
    """
    if _processor() is None:
        return WHY_NOT_PROCESSOR
    if not available(held):
        return WHY_NOT_FIRMWARE
    return None


class Chip:
    """A part driven by running the program inside it.

    An image can be supplied rather than found on disk. That is what a caller with
    the bytes already in hand wants, and it is also what lets this class be driven
    in a test by a program nobody owns, on a machine where no real microcode is
    present. `images` replaces the search instead of the image, for a caller that
    knows where the files are but wants them read the usual way.

    The interface is the one the models offer, so a caller swaps backends without
    knowing which it holds. What differs is `pending_output`, which the hardware
    cannot answer with a count: the status register carries one bit saying the
    part wants attention, and how many bytes sit behind it is not something the
    console is ever told.
    """

    __slots__ = (
        "_boot",
        "_fill",
        "_firmware",
        "_image",
        "_models",
        "_ports",
        "console",
        "core",
        "gap",
        "identity",
        "model",
        "part",
        "patience",
        "processor",
    )

    def __init__(
        self,
        part: str,
        fill: int = 0,
        patience: int = SETTLE_LIMIT,
        boot: int = BOOT_STEPS,
        gap: int = GAP,
        image: bytes | None = None,
        identity: Any | None = None,
        images: dict[str, tuple[Any, Path]] | None = None,
    ) -> None:
        found = _processor()
        if found is None:
            raise NoFirmware(WHY_NOT_PROCESSOR)

        firmware, models, ports = found

        if image is None:
            images = available(images)
            wanted = SHARES_IMAGE.get(part, part)
            if wanted not in images:
                raise NoFirmware(
                    f"there is no firmware image for {part}, so its microcode cannot be"
                    f" run. {WHY_NOT_FIRMWARE}"
                )
            identity, path = images[wanted]
            image = path.read_bytes()
        elif identity is None:
            raise NoFirmware(
                "an image was supplied without saying what it is, and the processor"
                " has to be told how much of it is program and how much is table"
            )

        self.part = part
        self.model = part
        self.processor = identity.processor
        self.identity = identity
        self.patience = patience
        self.gap = gap

        self._ports = ports
        self._firmware = firmware
        self._models = models
        self._fill = fill
        self._image = image
        self._boot = boot
        self._start()

    def _start(self) -> None:
        """Build the processor, load the program into it, and boot it.

        Separate from the constructor because a reset does exactly this and
        nothing else: the part comes back up holding what a part holds at power
        on, with the same program in it.
        """
        identity = self.identity
        self.core = self._models.describe(identity.processor).build(fill=self._fill)
        self._firmware.load(self.core, self._image, identity)
        self.console = self._ports.Console(self.core)
        self.step(self._boot)

    def reset(self) -> Chip:
        """Take the part back to where the console's reset line leaves it.

        The processor restarts at address zero with its program intact, which is
        what the reset pin does on the part underneath: the microcode is masked
        in, so nothing a reset does can reach it. The part is handed back so a
        caller can build and reset in one expression.
        """
        self._start()
        return self

    @property
    def clock(self) -> int:
        """The rate this part's oscillator runs at.

        One rate for the whole family, so a part built from an image that names
        no catalogue entry still runs at the rate the cartridge crystal supplies.
        """
        return timing.DSP_CLOCK

    def step(self, count: int | None = None) -> None:
        """Run the part for a while, which is what the console's silence is."""
        for _ in range(self.gap if count is None else count):
            self.core.step()

    def elapsed(self, master_clocks: int) -> Chip:
        """Run the part for as long as the console spent, in the console's clocks.

        What an emulator calls instead of guessing. The conversion is the two
        oscillators, so a caller who knows how many master clocks went by does
        not have to know anything about how fast this part runs.
        """
        self.step(timing.steps_for(master_clocks, self.clock))
        return self

    def read_bus(self, address: int) -> int:
        """One byte, from wherever on the bus the console reached for it."""
        if address >> STATUS_BIT & 1:
            return self.read_status()
        return self.read()

    def write_bus(self, address: int, value: int) -> Chip:
        """One byte in, to whichever side of the part the address names."""
        if address >> STATUS_BIT & 1:
            self.console.write(self._ports.STATUS, value & 0xFF)
            self.step()
            return self
        self.write(value)
        return self

    @property
    def asking(self) -> bool:
        """Whether the part is waiting on the console rather than working."""
        return bool(self.core.registers.sr.rqm)

    @property
    def pending_output(self) -> int:
        """Whether the part has something to say, as far as the console can tell.

        One, never a count. The models can say how many bytes remain because they
        computed them; the part cannot, and answering with a number would put a
        hand-derived figure back into the one path that has none.
        """
        return 1 if self.asking else 0

    def waited(self) -> bool:
        """Run until the part asks for attention, reporting whether it ever did."""
        for _ in range(self.patience):
            if self.asking:
                return True
            self.core.step()
        return False

    def settle(self) -> None:
        """Wait for the part to ask, and refuse to continue if it never does.

        For a caller who wants to know. Reading does not go through this, because
        a console cannot refuse to continue.
        """
        if not self.waited():
            raise NeverReady(
                f"{self.part} did not ask for attention within {self.patience} instructions"
            )

    def write(self, value: int) -> None:
        """Give the part one byte, then leave it room to act on it."""
        self.console.write(self._ports.DATA, value & 0xFF)
        self.step()

    def read_status(self) -> int:
        """The status register, which is what the console watches rather than a count.

        Taken without waiting and without disturbing anything, because that is
        what the console does: the register is readable at any moment and reading
        it is how a part that is clocked a word at a time is driven at all.
        """
        found: int = self.console.read(self._ports.STATUS)
        return found

    def read(self) -> int:
        """Give the part a chance to answer, take the port, and leave it room again.

        A chance rather than a guarantee, because that is the console's position.
        It cannot hang waiting: it reads the port and takes whatever is latched
        there, and a part that never raises its attention bit is read anyway.

        The difference matters between parts. One that answers a command by
        raising that bit is read after it does. One that is clocked a word at a
        time keeps it raised except in the instant after a read, and a read that
        insisted on seeing it raised would wait forever for a part that is
        already answering.
        """
        self.waited()
        value: int = self.console.read(self._ports.DATA)
        self.step()
        return value

    @override
    def __repr__(self) -> str:
        return f"<Chip {self.part} on {self.processor}>"
