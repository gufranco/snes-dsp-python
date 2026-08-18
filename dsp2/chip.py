"""The DSP-2 as the cartridge talks to it: one port in, one port out.

The chip has no address bus. Everything arrives through a single byte wide port
as a command, then any lengths that command needs, then its data, and results
leave the same way. So the protocol is a small state machine over a stream, and
this module is that machine and nothing else. What each command computes lives in
`commands`, as functions of their input, which is what allows them to be proved
rather than merely exercised.

The state machine is modelled the way the hardware carries it rather than the way
it reads best, because the two differ in a place that matters. Three of the
commands take a length before their data, and the chip remembers between calls
that a length has already been given. It also decides whether to expect data at
all by looking at the length byte itself: a length of zero leaves the chip
waiting for a command instead, with that memory still set. So a zero length does
not cancel a command, it arms one, and the next byte on the port is read as a new
command rather than as data. A model that resets on a zero length looks tidier
and answers differently.

Nothing here starts clean either. The parameter RAM is the chip's own memory and
the chip never clears it, so it holds whatever the previous command left. That is
not a detail: the rescale reads past the data it was given, straight into
whatever is sitting there.
"""

from . import commands
from .memory import PARAMETER_BYTES, UNSET_SEED, parameter_ram, scramble

IDLE_BYTE = 0xFF

COMMAND_TILE = 0x01
COMMAND_TRANSPARENT = 0x03
COMMAND_MERGE = 0x05
COMMAND_MIRROR = 0x06
COMMAND_MULTIPLY = 0x09
COMMAND_SCALE = 0x0D
COMMAND_SYNC = 0x0F

HEADER_INPUT = {
    COMMAND_TILE: commands.TILE_BYTES,
    COMMAND_TRANSPARENT: 1,
    COMMAND_MERGE: 1,
    COMMAND_MIRROR: 1,
    COMMAND_MULTIPLY: commands.MULTIPLY_BYTES,
    COMMAND_SCALE: 2,
}
"""How many bytes each command wants before it first acts, lengths included."""

LARGEST_LENGTH = 0xFF

LARGEST_PAYLOAD = 2 * LARGEST_LENGTH
"""The most bytes any command can ask for, which the parameter RAM must hold."""


class Chip:
    """A DSP-2 holding whatever it was holding, which is how one powers up.

    `fill` decides what the parameter RAM starts as: a byte, an image, or None
    for a scrambled pattern that is reproducible from the seed and obviously not
    clean. A caller that wants zeroes asks for zero, and that becomes a decision
    recorded in the code rather than a default nobody chose.
    """

    def __init__(self, fill=None, seed=UNSET_SEED):
        self.parameter_ram = parameter_ram(fill=fill, seed=seed)
        self.transparent = scramble(1, seed)[0] if fill is None else 0x00
        self.output = b""

        self.waiting_for_command = True
        self.command = 0x00
        self.in_count = 0
        self.in_index = 0
        self.out_count = 0
        self.out_index = 0

        self.merge_armed = False
        self.merge_length = 0
        self.mirror_armed = False
        self.mirror_length = 0
        self.scale_armed = False
        self.scale_in_length = 0
        self.scale_out_length = 0

    @property
    def pending_output(self):
        return max(0, self.out_count - self.out_index)

    def write(self, value):
        """Take one byte from the cartridge, and act once the chip has enough."""
        value &= 0xFF

        if self.waiting_for_command:
            self.command = value
            self.in_index = 0
            self.waiting_for_command = False
            self.in_count = HEADER_INPUT.get(value, 0)
        else:
            if self.in_index < PARAMETER_BYTES:
                self.parameter_ram[self.in_index] = value
            self.in_index += 1

        if self.in_count == self.in_index:
            self.waiting_for_command = True
            self.out_index = 0
            self._act(value)

    def _arm(self, name, wanted, value):
        """Record the lengths, then decide whether data follows them.

        A non zero length means data comes next. A zero length leaves the chip
        waiting for a command, and the arming stays set, so the next appearance
        of this command runs it immediately with the length it was given.
        """
        setattr(self, f"{name}_armed", True)
        self.in_index = 0
        self.in_count = wanted
        if value:
            self.waiting_for_command = False

    def _act(self, value):
        command = self.command

        if command == COMMAND_TILE:
            self.out_count = commands.TILE_BYTES
            self.output = commands.tile(bytes(self.parameter_ram[: commands.TILE_BYTES]))

        elif command == COMMAND_TRANSPARENT:
            self.transparent = self.parameter_ram[0]

        elif command == COMMAND_MULTIPLY:
            self.out_count = commands.MULTIPLY_BYTES
            self.output = commands.multiply(bytes(self.parameter_ram[: commands.MULTIPLY_BYTES]))

        elif command == COMMAND_MERGE:
            if self.merge_armed:
                self.merge_armed = False
                self.out_count = self.merge_length
                self.output = commands.merge(
                    self.transparent,
                    bytes(self.parameter_ram[: 2 * self.merge_length]),
                    self.merge_length,
                )
            else:
                self.merge_length = self.parameter_ram[0]
                self._arm("merge", 2 * self.merge_length, value)

        elif command == COMMAND_MIRROR:
            if self.mirror_armed:
                self.mirror_armed = False
                self.out_count = self.mirror_length
                self.output = commands.mirror(
                    bytes(self.parameter_ram[: self.mirror_length]), self.mirror_length
                )
            else:
                self.mirror_length = self.parameter_ram[0]
                self._arm("mirror", self.mirror_length, value)

        elif command == COMMAND_SCALE:
            if self.scale_armed:
                self.scale_armed = False
                self.out_count = self.scale_out_length
                self.output = commands.scale(
                    self.parameter_ram, self.scale_in_length, self.scale_out_length
                )
            else:
                self.scale_in_length = self.parameter_ram[0]
                self.scale_out_length = self.parameter_ram[1]
                self._arm("scale", (self.scale_in_length + 1) >> 1, value)

    def read(self):
        """The next byte of the finished result, or the idle byte.

        A result is spent once it has been read out, and only then. A command that
        produces nothing, which is the transparent colour, a sync, and anything the
        chip does not recognise, rewinds the cursor without clearing the count, so
        a result read only in part can be read again from its start. That is what
        the hardware does, and it is visible behaviour rather than an accident.
        """
        if self.out_count == 0:
            return IDLE_BYTE
        value = self.output[self.out_index]
        self.out_index += 1
        if self.out_index == self.out_count:
            self.out_count = 0
        return value
