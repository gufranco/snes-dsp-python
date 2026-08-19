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
commands that finish in one go and the single-player track projection, which is
the first of the renderers. Each is compared against the chip's own reference.

The remaining renderers are not here yet, and asking for one raises rather than
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

INVERSE = (
    0x0000,
    0x8000,
    0x4000,
    0x2AAA,
    0x2000,
    0x1999,
    0x1555,
    0x1249,
    0x1000,
    0x0E38,
    0x0CCC,
    0x0BA2,
    0x0AAA,
    0x09D8,
    0x0924,
    0x0888,
    0x0800,
    0x0787,
    0x071C,
    0x06BC,
    0x0666,
    0x0618,
    0x05D1,
    0x0590,
    0x0555,
    0x051E,
    0x04EC,
    0x04BD,
    0x0492,
    0x0469,
    0x0444,
    0x0421,
    0x0400,
    0x03E0,
    0x03C3,
    0x03A8,
    0x038E,
    0x0375,
    0x035E,
    0x0348,
    0x0333,
    0x031F,
    0x030C,
    0x02FA,
    0x02E8,
    0x02D8,
    0x02C8,
    0x02B9,
    0x02AA,
    0x029C,
    0x028F,
    0x0282,
    0x0276,
    0x026A,
    0x025E,
    0x0253,
    0x0249,
    0x023E,
    0x0234,
    0x022B,
    0x0222,
    0x0219,
    0x0210,
    0x0208,
)

END_OF_TRACK = -0x8000

TURNOFF = 0x8001

VISIBLE_BELOW = 0x00EB


class Unimplemented(Exception):
    pass


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def signed32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def inverse(value):
    """One over a small number, from the table the chip carries.

    The table is sixty four entries and the argument is clamped into it rather
    than checked, so a run of segments longer than the table quietly reuses the
    last entry instead of dividing by the number it was given.
    """
    return INVERSE[min(max(value, 0), 63)]


def sign_extend_low(value):
    """A one point seven point eight value widened to one point fifteen point sixteen."""
    return signed32(signed16(value) << 8)


def sign_extend_whole(value):
    """A whole number widened into the same fixed point format."""
    return signed32(signed16(value) << 16)


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
        self._clear_projection()
        return self

    def _clear_projection(self):
        """Everything the road renderers carry between one batch and the next."""
        self.world_x = 0
        self.world_y = 0
        self.world_dx = 0
        self.world_dy = 0
        self.world_ddx = 0
        self.world_ddy = 0
        self.world_xenv = 0
        self.world_yofs = 0
        self.view_x1 = 0
        self.view_y1 = 0
        self.view_x2 = 0
        self.view_y2 = 0
        self.view_xofs1 = 0
        self.view_yofs1 = 0
        self.view_xofs2 = 0
        self.view_yofs2 = 0
        self.view_yofsenv = 0
        self.view_dx = 0
        self.view_dy = 0
        self.view_turnoff_x = 0
        self.view_turnoff_dx = 0
        self.viewport_bottom = 0
        self.distance = 0
        self.segments = 0
        self.poly_bottom = 0
        self.poly_top = 0
        self.poly_cx_left = 0
        self.poly_cx_right = 0
        self.poly_ptr = 0
        self.poly_raster = 0

    def take_dword(self):
        at = self.in_index
        self.in_index += 4
        return signed32(
            self.parameters[at]
            | (self.parameters[at + 1] << 8)
            | (self.parameters[at + 2] << 16)
            | (self.parameters[at + 3] << 24)
        )

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
        if self.running is not None:
            self._advance()
            return
        handler = self._handlers().get(self.command)
        if handler is None:
            raise Unimplemented(
                f"command {self.command:#06x} is one of this chip's track renderers, "
                "which this model does not carry yet"
            )
        found = handler()
        if found is None:
            return
        self.running = found
        self._advance()

    def _advance(self):
        """Run a suspended command until it asks for more input or finishes.

        A renderer that yields is asking for that many bytes and will carry on
        from where it stopped. One that returns is done, and the chip goes back to
        waiting for a command.
        """
        try:
            self.in_count = next(self.running)
        except StopIteration:
            self.running = None
            self.waiting = True
            return
        self.in_index = 0
        self.waiting = False

    def _handlers(self):
        return {
            0x0000: self._multiply,
            0x0003: self._select,
            0x0005: self._clear_sprites,
            0x0006: self._transfer_sprites,
            0x000A: self._angles,
            0x000B: self._set_sprite,
            0x0001: self._project_track,
            0x0007: self._project_turnoff,
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

    def _project_track(self):
        """The single-player road, drawn outwards from the viewer.

        This is the command that cannot finish in one go. It projects the track
        as far as the input it has describes, hands back the scanline segments it
        produced, and then asks for the next stretch. The caller keeps feeding it
        until it says the track has ended.

        Three places it suspends, and they are not interchangeable. After each
        stretch it wants two bytes, which are either the next distance or a
        marker. If that marker says the road forks it wants six more describing
        the fork, and then two again. Otherwise it wants six describing the next
        stretch's curvature. Resuming at the wrong one reads the fork's numbers
        as curvature and bends the road.
        """
        self.world_y = self.take_dword()
        self.poly_bottom = self.take_word()
        self.poly_top = self.take_word()
        self.poly_cx_right = self.take_word()
        self.viewport_bottom = self.take_word()
        self.world_x = self.take_dword()
        self.poly_cx_left = self.take_word()
        self.poly_ptr = self.take_word()
        self.world_yofs = self.take_word()
        self.world_dy = self.take_dword()
        self.world_dx = self.take_dword()
        self.distance = self.take_word()
        self.take_word()
        self.world_xenv = self.take_dword()
        self.world_ddy = self.take_word()
        self.world_ddx = self.take_word()
        self.view_yofsenv = self.take_word()

        self.view_x1 = signed16(signed32(self.world_x + self.world_xenv) >> 16)
        self.view_y1 = signed16(self.world_y >> 16)
        self.view_xofs1 = signed16(self.world_x >> 16)
        self.view_yofs1 = self.world_yofs
        self.view_turnoff_x = 0
        self.view_turnoff_dx = 0
        self.poly_raster = self.poly_bottom

        while True:
            self._project_one_stretch()

            yield 2
            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                return

            if (self.distance & 0xFFFF) == TURNOFF:
                yield 6
                self.distance = self.take_word()
                self.view_turnoff_x = self.take_word()
                self.view_turnoff_dx = self.take_word()
                shift = signed16((self.view_turnoff_x * self.distance) >> 15)
                self.view_x1 = signed16(self.view_x1 + shift)
                self.view_xofs1 = signed16(self.view_xofs1 + shift)
                self.view_turnoff_x = signed16(self.view_turnoff_x + self.view_turnoff_dx)
                yield 2

            yield 6
            self.world_ddy = self.take_word()
            self.world_ddx = self.take_word()
            self.view_yofsenv = self.take_word()
            self.world_xenv = 0

    def _project_one_stretch(self):
        """One stretch of road: where it lands on screen, and the lines it fills."""
        far_x = signed32(self.world_x + self.world_xenv) >> 16
        self.view_x2 = signed16(
            ((far_x * self.distance) >> 15) + ((self.view_turnoff_x * self.distance) >> 15)
        )
        self.view_y2 = signed16(((self.world_y >> 16) * self.distance) >> 15)
        self.view_xofs2 = self.view_x2
        self.view_yofs2 = signed16(
            ((self.world_yofs * self.distance) >> 15) + self.poly_bottom - self.view_y2
        )

        self.clear_output()
        self.put_word(far_x)
        self.put_word(self.view_x2)
        self.put_word(self.world_y >> 16)
        self.put_word(self.view_y2)

        self.segments = signed16(self.poly_raster - self.view_y2)
        if self.view_y2 >= self.poly_raster:
            self.segments = 0
        else:
            self.poly_raster = self.view_y2

        if self.view_y2 < self.poly_top:
            self.segments = 0
            if self.view_y1 >= self.poly_top:
                self.segments = signed16(self.view_y1 - self.poly_top)

        self.put_word(self.segments)

        if self.segments:
            self._rasterise()

        self.view_x1 = self.view_x2
        self.view_y1 = self.view_y2
        self.view_xofs1 = self.view_xofs2
        self.view_yofs1 = self.view_yofs2

        self.world_dx = signed32(self.world_dx + sign_extend_low(self.world_ddx))
        self.world_dy = signed32(self.world_dy + sign_extend_low(self.world_ddy))
        self.world_x = signed32(self.world_x + self.world_dx + self.world_xenv)
        self.world_y = signed32(self.world_y + self.world_dy)
        self.view_turnoff_x = signed16(self.view_turnoff_x + self.view_turnoff_dx)

    def _rasterise(self):
        """Walk between two projected points, one scanline at a time."""
        step_x = signed32((self.view_xofs2 - self.view_xofs1) * inverse(self.segments) << 1)
        step_y = signed32((self.view_yofs2 - self.view_yofs1) * inverse(self.segments) << 1)
        scroll_x = sign_extend_whole(self.poly_cx_left + self.view_xofs1)
        scroll_y = sign_extend_whole(
            -self.viewport_bottom
            + self.view_yofs1
            + self.view_yofsenv
            + self.poly_cx_right
            - self.world_yofs
        )

        for _ in range(self.segments):
            self.put_word(self.poly_ptr)
            self.put_word(signed32(scroll_y + 0x8000) >> 16)
            self.put_word(signed32(scroll_x + 0x8000) >> 16)
            self.poly_ptr = signed16(self.poly_ptr - 4)
            scroll_x = signed32(scroll_x + step_x)
            scroll_y = signed32(scroll_y + step_y)

    def _project_turnoff(self):
        """The road that leaves the road, drawn the same way and steered differently.

        Where the main projection works out its own path from a world position
        and a curvature, this one is told where the branch is on screen and how
        fast it moves, and simply walks it. So it carries a step rather than a
        velocity, and the step is scaled by the distance once when it arrives
        rather than every stretch.
        """
        self.world_y = self.take_dword()
        self.poly_bottom = self.take_word()
        self.poly_top = self.take_word()
        self.poly_cx_right = self.take_word()
        self.viewport_bottom = self.take_word()
        self.world_x = self.take_dword()
        self.poly_cx_left = self.take_word()
        self.poly_ptr = self.take_word()
        self.world_yofs = self.take_word()
        self.distance = self.take_word()
        self._take_branch_shape()

        self.view_x1 = signed16(self.world_x >> 16)
        self.view_y1 = signed16(self.world_y >> 16)
        self.view_xofs1 = self.view_x1
        self.view_yofs1 = self.world_yofs
        self.poly_raster = self.poly_bottom

        while True:
            self._turnoff_one_stretch()

            yield 2
            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                return

            yield 10
            self._take_branch_shape()

    def _take_branch_shape(self):
        """Where the branch sits on screen and how fast it moves across it."""
        self.view_y2 = self.take_word()
        self.view_dy = signed16((self.take_word() * self.distance) >> 15)
        self.view_x2 = self.take_word()
        self.view_dx = signed16((self.take_word() * self.distance) >> 15)
        self.view_yofsenv = self.take_word()

    def _turnoff_one_stretch(self):
        """One stretch of the branch, and the lines it fills."""
        self.view_x2 = signed16(self.view_x2 + self.view_dx)
        self.view_y2 = signed16(self.view_y2 + self.view_dy)
        self.view_xofs2 = self.view_x2
        self.view_yofs2 = signed16(
            ((self.world_yofs * self.distance) >> 15) + self.poly_bottom - self.view_y2
        )

        self.clear_output()
        self.put_word(self.view_x2)
        self.put_word(self.view_y2)

        self.segments = signed16(self.view_y1 - self.view_y2)
        if self.view_y2 >= self.poly_raster:
            self.segments = 0
        else:
            self.poly_raster = self.view_y2

        if self.view_y2 < self.poly_top:
            self.segments = 0
            if self.view_y1 >= self.poly_top:
                self.segments = signed16(self.view_y1 - self.poly_top)

        self.put_word(self.segments)

        if self.segments:
            self._rasterise()

        self.view_x1 = self.view_x2
        self.view_y1 = self.view_y2
        self.view_xofs1 = self.view_xofs2
        self.view_yofs1 = self.view_yofs2

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
