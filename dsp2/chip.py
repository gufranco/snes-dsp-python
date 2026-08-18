"""The DSP-2 as the cartridge talks to it: one port in, one port out.

The chip has no address bus. Everything arrives through a single byte wide port
as a command, then any lengths that command needs, then its data, and results
leave the same way. So the protocol is a small state machine over a stream, and
this module is that machine and nothing else. What each command computes lives in
`commands`, as functions of their input, which is what allows them to be proved
rather than merely exercised.

Nothing here starts clean. The parameter RAM is the chip's own memory and the
chip never clears it, so it holds whatever the previous command left. That is not
a detail: the rescale reads past the data it was given, straight into whatever is
sitting there.
"""

from . import commands
from .memory import UNSET_SEED, parameter_ram, scramble

IDLE_BYTE = 0xFF

COMMAND_TILE = 0x01
COMMAND_TRANSPARENT = 0x03
COMMAND_MERGE = 0x05
COMMAND_MIRROR = 0x06
COMMAND_MULTIPLY = 0x09
COMMAND_SCALE = 0x0D
COMMAND_SYNC = 0x0F

_FIXED_INPUT = {
    COMMAND_TILE: commands.TILE_BYTES,
    COMMAND_TRANSPARENT: 1,
    COMMAND_MULTIPLY: commands.MULTIPLY_BYTES,
}

_PRODUCES_OUTPUT = frozenset(
    {COMMAND_TILE, COMMAND_MERGE, COMMAND_MIRROR, COMMAND_MULTIPLY, COMMAND_SCALE}
)

_LENGTH_COUNT = {
    COMMAND_MERGE: 1,
    COMMAND_MIRROR: 1,
    COMMAND_SCALE: 2,
}

_PAYLOAD_SIZE = {
    COMMAND_MERGE: lambda lengths: 2 * lengths[0],
    COMMAND_MIRROR: lambda lengths: lengths[0],
    COMMAND_SCALE: lambda lengths: (lengths[0] + 1) >> 1,
}

LARGEST_LENGTH = 0xFF

LARGEST_PAYLOAD = max(size([LARGEST_LENGTH, LARGEST_LENGTH]) for size in _PAYLOAD_SIZE.values())
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
        self.transparent = scramble(1, seed)[0] & 0x0F if fill is None else 0x00
        self._reset()

    def _reset(self):
        self.command = None
        self.lengths = []
        self.in_index = 0
        self.payload_length = 0
        self.output = b""
        self.output_count = 0
        self.output_index = 0
        self._wanted_lengths = 0
        self._wanted_parameters = 0

    @property
    def payload(self):
        """The bytes the current command was given, without the RAM behind them."""
        return bytes(self.parameter_ram[: self.payload_length])

    @property
    def pending_output(self):
        return max(0, self.output_count - self.output_index)

    def write(self, value):
        """Take one byte from the cartridge, and run the command once it is whole."""
        value &= 0xFF

        if self.command is None:
            self.command = value
            self.lengths = []
            self.in_index = 0
            self.payload_length = 0
            self._wanted_lengths = _LENGTH_COUNT.get(value, 0)
            self._wanted_parameters = _FIXED_INPUT.get(value, 0)
            if self._wanted_lengths == 0 and self._wanted_parameters == 0:
                self._run()
            return

        if self._wanted_lengths > 0:
            self.lengths.append(value)
            self._wanted_lengths -= 1
            if self._wanted_lengths == 0:
                self._wanted_parameters = self._payload_size()
                self.in_index = 0
                self.payload_length = 0
                if self._wanted_parameters == 0:
                    self._run()
            return

        self.parameter_ram[self.in_index] = value
        self.in_index += 1
        self.payload_length = self.in_index
        self._wanted_parameters -= 1
        if self._wanted_parameters == 0:
            self._run()

    def _payload_size(self):
        """How many bytes the command still wants, once its lengths have arrived.

        This is never larger than the parameter RAM, and that is a property of the
        protocol rather than luck. A length arrives as a single byte, so the
        largest it can be is 255, and the hungriest command is the merge at two
        runs of that, which is 510 against a RAM of 512. So the write above needs
        no bounds check; `LARGEST_PAYLOAD` states the bound and a test pins it.
        """
        return _PAYLOAD_SIZE[self.command](self.lengths)

    def _run(self):
        payload = self.payload
        command = self.command
        self.command = None
        self.output_index = 0

        if command == COMMAND_TILE:
            self.output = commands.tile(payload)
        elif command == COMMAND_TRANSPARENT:
            self.transparent = payload[0] & 0x0F
        elif command == COMMAND_MERGE:
            self.output = commands.merge(self.transparent, payload, self.lengths[0])
        elif command == COMMAND_MIRROR:
            self.output = commands.mirror(payload, self.lengths[0])
        elif command == COMMAND_MULTIPLY:
            self.output = commands.multiply(payload)
        elif command == COMMAND_SCALE:
            self.output = commands.scale(self.parameter_ram, self.lengths[0], self.lengths[1])

        if command in _PRODUCES_OUTPUT:
            self.output_count = len(self.output)

    def read(self):
        """The next byte of the finished result, or the idle byte.

        A result is spent once it has been read out, and only then. A command that
        produces nothing, which is the transparent colour, a sync, and anything the
        chip does not recognise, rewinds the cursor without clearing the count, so
        a result read only in part can be read again from its start. That is what
        the hardware does, and it is visible behaviour rather than an accident.
        """
        if self.output_count == 0:
            return IDLE_BYTE
        value = self.output[self.output_index]
        self.output_index += 1
        if self.output_index == self.output_count:
            self.output_count = 0
        return value
