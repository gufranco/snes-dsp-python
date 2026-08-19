"""The DSP-4, which draws a road rather than answering questions.

The other microcodes in this family take a few numbers and hand back a few
numbers. This one is a renderer. A command hands it a viewpoint and a stretch of
track, and it walks that track outwards from the viewer producing scanline
segments and sprite entries until it runs out of either. Several commands cannot
finish in one go: they consume a batch of input, produce output, and then wait
for the next batch, resuming exactly where they stopped.

The reference implements that by jumping back into the middle of a function. Here
each such command is a generator, which resumes where it yielded for the same
reason and without the jump. What matters is that the resumption point is state:
a command half way through a track is not the same chip as one that has just
started, and a model that restarts the command produces plausible output that
drifts.

Two details in the port protocol look like bugs and are the hardware.

Writing a byte to the output writes a whole word and then advances by one, so
consecutive byte writes overlap and the second one overwrites the top half of the
first. The sprite packer relies on it.

And the output length is cleared when the last byte is read rather than when the
next command arrives, so a program that reads one byte too many gets the idle
value instead of wrapping round to the start.

The arithmetic is fixed point in three formats, and which one a field is in is
not recoverable from the field. It is written down here in the names.

What is here and what is not. The port protocol is complete, and so are the seven
commands that finish in one go: the multiply, the horizontal mapping, the angle
lookup, the three that manage the sprite table, and the one that places a sprite.
Each is compared against the chip's own reference.

The eight track renderers are not here yet, and asking for one raises rather than
returning nothing. A command that quietly produced no output would be
indistinguishable from a road with no segments in it, which is a real answer this
chip can give, so silence is the one response this module must not make.
"""

PARAMETER_BYTES = 512

OUTPUT_BYTES = 512

OUTPUT_MASK = OUTPUT_BYTES - 1

IDLE = 0xFF

OAM_ENTRIES = 16

OAM_ROWS = 32

SCREEN_WIDTH = 0x0155

INPUT_COUNTS = {
    0x0000: 4,
    0x0001: 44,
    0x0003: 0,
    0x0005: 0,
    0x0006: 0,
    0x0007: 34,
    0x0008: 90,
    0x0009: 14,
    0x000A: 6,
    0x000B: 6,
    0x000D: 42,
    0x000E: 0,
    0x000F: 46,
    0x0010: 36,
    0x0011: 8,
}

ANGLES = (
    0x0000,
    0x0030,
    0x0060,
    0x0090,
    0x00C0,
    0x00F0,
    0x0120,
    0x0150,
    0xFE80,
    0xFEB0,
    0xFEE0,
    0xFF10,
    0xFF40,
    0xFF70,
    0xFFA0,
    0xFFD0,
)

SPRITE_LIMIT = 128

VISIBLE_BELOW = 0x00EB


class Unimplemented(Exception):
    pass


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def signed32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def multiply(multiplicand, multiplier):
    """The chip's multiply, which drops the bottom bit of its own product."""
    return signed32((signed16(multiplicand) * signed16(multiplier) << 1) >> 1)


class Dsp4:
    """One DSP-4, holding a command, its inputs, and a road part way drawn."""

    def __init__(self):
        self.parameters = bytearray(PARAMETER_BYTES)
        self.output = bytearray(OUTPUT_BYTES)
        self.reset()

    def reset(self):
        self.waiting = True
        self.half_command = False
        self.command = 0
        self.in_count = 0
        self.in_index = 0
        self.out_count = 0
        self.out_index = 0
        self.running = None
        self.oam_attr = [0] * OAM_ENTRIES
        self.oam_index = 0
        self.oam_bits = 0
        self.oam_row_max = 0
        self.oam_row = bytearray(OAM_ROWS)
        self.sprite_count = 0
        return self

    def take_word(self):
        at = self.in_index
        self.in_index += 2
        return signed16(self.parameters[at] | (self.parameters[at + 1] << 8))

    def clear_output(self):
        self.out_count = 0
        self.out_index = 0

    def put_word(self, value):
        """A word into the output, which advances by the two bytes it wrote."""
        value &= 0xFFFF
        self.output[self.out_count & OUTPUT_MASK] = value & 0xFF
        self.output[(self.out_count + 1) & OUTPUT_MASK] = value >> 8
        self.out_count += 2

    def put_byte(self, value):
        """A word into the output that advances by one byte rather than two.

        This is not a narrower write. It writes both bytes and then steps a single
        place, so the next write lands on the high half of this one and overwrites
        it. The sprite packer depends on the overlap.
        """
        value &= 0xFFFF
        self.output[self.out_count & OUTPUT_MASK] = value & 0xFF
        self.output[(self.out_count + 1) & OUTPUT_MASK] = value >> 8
        self.out_count += 1

    def put_oam_table(self):
        for value in self.oam_attr:
            self.put_word(value)

    def read(self):
        """One byte of whatever the last command produced."""
        if not self.out_count:
            return IDLE
        value = self.output[self.out_index & OUTPUT_MASK]
        self.out_index += 1
        if self.out_count == self.out_index:
            self.out_count = 0
        return value

    def write(self, value):
        """One byte in, which is a command, a parameter, or a read acknowledgement."""
        value &= 0xFF
        if self.out_index < self.out_count:
            self.out_index += 1
            return

        if self.waiting:
            self._accept_command(value)
        else:
            self.parameters[self.in_index] = value
            self.in_index += 1

        if not self.waiting and self.in_count == self.in_index:
            self.waiting = True
            self.out_index = 0
            self.in_index = 0
            self._execute()

    def _accept_command(self, value):
        if not self.half_command:
            self.command = value
            self.half_command = True
            return
        self.command |= value << 8
        self.in_index = 0
        self.waiting = False
        self.half_command = False
        self.out_count = 0
        self.out_index = 0
        self.running = None
        found = INPUT_COUNTS.get(self.command)
        if found is None:
            self.waiting = True
            return
        self.in_count = found

    def _execute(self):
        handler = self._handlers().get(self.command)
        if handler is None:
            raise Unimplemented(
                f"command {self.command:#06x} is one of this chip's track renderers, "
                "which this model does not carry yet"
            )
        handler()

    def _handlers(self):
        return {
            0x0000: self._multiply,
            0x0003: self._select,
            0x0005: self._clear_sprites,
            0x0006: self._transfer_sprites,
            0x000A: self._angles,
            0x000B: self._set_sprite,
            0x0011: self._map_across,
        }

    def _multiply(self):
        multiplier = self.take_word()
        multiplicand = self.take_word()
        product = multiply(multiplicand, multiplier)
        self.clear_output()
        self.put_word(product)
        self.put_word(product >> 16)

    def _select(self):
        self.oam_row_max = 33
        self.oam_row = bytearray(OAM_ROWS)

    def _clear_sprites(self):
        self.oam_index = 0
        self.oam_bits = 0
        self.oam_attr = [0] * OAM_ENTRIES
        self.sprite_count = 0

    def _transfer_sprites(self):
        self.clear_output()
        self.put_oam_table()

    def _angles(self):
        """Four nibbles, each looked up, handed back in an order nobody would guess.

        The four results do not come out in nibble order. The lookup fills them in
        one order and the caller reads them in another, so the second nibble is
        answered first and the lowest is answered third. There is no reading of
        the table that predicts it; it is what the two of them do together.
        """
        self.take_word()
        packed = self.take_word() & 0xFFFF
        self.take_word()
        self.clear_output()
        for shift in (8, 12, 0, 4):
            self.put_word(ANGLES[(packed >> shift) & 0x0F])

    def _set_sprite(self):
        sprite_x = self.take_word()
        sprite_y = self.take_word()
        attributes = self.take_word()
        self.clear_output()
        self._place_sprite(sprite_x, sprite_y, attributes)

    def _place_sprite(self, sprite_x, sprite_y, attributes):
        """One sprite, if the row it lands on still has room for it.

        The chip also has a double-height form, which only the track renderers
        ask for. It is not here because they are not here.
        """
        row = (sprite_y >> 3) & 0x1F

        draw = True
        if not (sprite_y < 0 or (sprite_y & 0x01FF) < VISIBLE_BELOW):
            draw = False
        if self.oam_row[row] >= self.oam_row_max:
            draw = False
        if self.sprite_count >= SPRITE_LIMIT:
            draw = False

        if not draw:
            self.put_word(0)
            return

        self.oam_row[row] += 1
        self.put_word(1)
        self.put_byte(sprite_x & 0xFF)
        self.put_byte(sprite_y & 0xFF)
        self.put_word(attributes)
        self.sprite_count += 1

        offscreen = 1 if sprite_x < 0 or sprite_x > 255 else 0
        self.oam_attr[self.oam_index] |= offscreen << self.oam_bits
        self.oam_bits += 2
        if self.oam_bits == 16:
            self.oam_bits = 0
            self.oam_index += 1

    def _map_across(self):
        fourth = self.take_word()
        third = self.take_word()
        second = self.take_word()
        first = self.take_word()
        packed = (
            ((first * SCREEN_WIDTH >> 2) & 0xF000)
            | ((second * SCREEN_WIDTH >> 6) & 0x0F00)
            | ((third * SCREEN_WIDTH >> 10) & 0x00F0)
            | ((fourth * SCREEN_WIDTH >> 14) & 0x000F)
        )
        self.clear_output()
        self.put_word(packed)

    def __repr__(self):
        return f"<DSP-4 command {self.command:#06x} waiting {self.waiting}>"
