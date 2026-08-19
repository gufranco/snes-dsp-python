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

Three details look like bugs and are the hardware.

Writing a byte to the output writes a whole word and then advances by one, so
consecutive byte writes overlap and the second one overwrites the top half of the
first. The sprite packer relies on it.

The output length is cleared when the last byte is read rather than when the next
command arrives, so a program that reads one byte too many gets the idle value
instead of wrapping round to the start.

And one over one does not fit the reciprocal table, which holds it as a value the
lookup hands back signed, so a run of a single scanline steps the wrong way.
Every caller then negates that step again, so the two mistakes cancel where they
meet and neither is visible on its own.

The arithmetic is fixed point in three formats, and which one a field is in is
not recoverable from the field. It is written down here in the names.

Every command the chip answers is here: the eight that finish in one go and the
seven renderers that do not. Each is compared against the chip's own reference,
which is what settles the places where the two could differ.

A command the chip does not know is refused when it arrives rather than when it
runs, which is what the hardware does. A command that quietly produced no output
would be indistinguishable from a road with no segments in it, which is a real
answer this chip can give, so silence is the one response this module must not
make.

And nothing starts clean here either. The parameter RAM and the output buffer are
the chip's own memory and it never clears them, so by default they hold the
scrambled pattern the rest of this package uses rather than zeroes. A caller that
wants zeroes asks for them.
"""

from .memory import PARAMETER_BYTES, UNSET_SEED, parameter_ram

OUTPUT_BYTES = PARAMETER_BYTES

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

LIGHTING_COLOURS = 4

VEHICLE = 0x9000

NO_SPRITE = 0x0000

CLIPPING_TILE = 0x00EE

OFFSCREEN_ROW = 0x0100

SPRITE_HEADERS = (0x20, 0x2E, 0x40, 0x60, 0xA0, 0xC0, 0xE0)

FORK_LEFT = 0xC001

FORK_RIGHT = 0x3FFF


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

    One over one is the entry that does not fit. The table holds it as 0x8000 and
    the lookup hands back a signed word, so the reciprocal of one comes back
    negative and a run of a single line steps the wrong way. Every caller then
    negates that step again, which is why it is only a single line that is
    affected and why the two mistakes are not visible as one.
    """
    return signed16(INVERSE[min(max(value, 0), 63)])


def clamp(value, low, high):
    """A screen position pulled inside its window, low edge first.

    The order is load bearing. A window whose edges are the wrong way round
    settles on the high edge rather than on the low one.
    """
    return min(max(value, low), high)


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

    def __init__(self, fill=None, seed=UNSET_SEED):
        self.parameters = parameter_ram(fill=fill, seed=seed)
        self.output = parameter_ram(fill=fill, seed=seed)
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
        self.solid_clip_left = [[0, 0], [0, 0]]
        self.solid_clip_right = [[0, 0], [0, 0]]
        self.solid_cx = [[0, 0], [0, 0]]
        self.solid_ptr = [[0, 0], [0, 0]]
        self.solid_bottom = [[0, 0], [0, 0]]
        self.solid_top = [[0, 0], [0, 0]]
        self.solid_raster = [[0, 0], [0, 0]]
        self.solid_start = [0, 0]
        self.solid_plane = [0, 0]
        self.viewport_cx = 0
        self.viewport_cy = 0
        self.viewport_left = 0
        self.viewport_right = 0
        self.viewport_top = 0
        self.raster = 0
        self.sprite_x = 0
        self.sprite_y = 0
        self.sprite_size = 0
        self.sprite_attr = 0
        self.sprite_clipy = 0

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

    @property
    def pending_output(self):
        """How many bytes are waiting, where the model knows a count.

        Uniform across the family in meaning rather than in kind. A model that
        computed a result knows how long it is; the part does not, and neither
        does the microcode backend, which can only say whether it wants
        attention. A caller that loops while this is truthy works on both.
        """
        return max(0, self.out_count - self.out_index)

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
        found = self._handlers()[self.command]()
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
            0x0008: self._render_solid,
            0x0009: self._project_sprites,
            0x0007: self._project_turnoff,
            0x000D: self._project_shared_track,
            0x000F: self._project_lit_track,
            0x0010: self._project_lit_turnoff,
            0x000E: self._select_shared,
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

    def _select_shared(self):
        """The same, with half the room, because two players share the screen."""
        self.oam_row_max = 16
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
        self._place_sprite(True, sprite_x, sprite_y, attributes, 0, stop=True)

    def _place_sprite(self, draw, sprite_x, sprite_y, attributes, size, stop):
        """One sprite, if the rows it lands on still have room for it.

        The flag is carried in as well as out. A tile that has already been
        refused once stays refused for the rest of the sprite it belongs to, so
        the caller cannot draw the second half of something whose first half did
        not fit.

        A double-height sprite occupies two rows and counts two against each of
        them rather than one against the row it starts in.
        """
        first = (sprite_y >> 3) & 0x1F
        second = (first + 1) & 0x1F

        if not (sprite_y < 0 or (sprite_y & 0x01FF) < VISIBLE_BELOW):
            draw = False
        if size:
            if self.oam_row[first] + 1 >= self.oam_row_max:
                draw = False
            if self.oam_row[second] + 1 >= self.oam_row_max:
                draw = False
        elif self.oam_row[first] >= self.oam_row_max:
            draw = False
        if self.sprite_count >= SPRITE_LIMIT:
            draw = False

        if not draw:
            if stop:
                self.put_word(0)
            return draw

        if size:
            self.oam_row[first] += 2
            self.oam_row[second] += 2
        else:
            self.oam_row[first] += 1

        self.put_word(1)
        self.put_byte(sprite_x & 0xFF)
        self.put_byte(sprite_y & 0xFF)
        self.put_word(attributes)
        self.sprite_count += 1

        offscreen = 1 if sprite_x < 0 or sprite_x > 255 else 0
        self.oam_attr[self.oam_index] |= offscreen << self.oam_bits
        self.oam_bits += 1
        self.oam_attr[self.oam_index] |= (1 if size else 0) << self.oam_bits
        self.oam_bits += 1
        if self.oam_bits == 16:
            self.oam_bits = 0
            self.oam_index += 1
        return draw

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
            self._project_one_stretch(count_from_raster=True, follow_turnoff=True)

            finished = yield from self._take_next_distance()
            if finished:
                return

            yield 6
            self.world_ddy = self.take_word()
            self.world_ddx = self.take_word()
            self.view_yofsenv = self.take_word()
            self.world_xenv = 0

    def _take_next_distance(self):
        """The distance to the next stretch, and any forks that arrive before it.

        A fork does not merely interrupt the wait for a distance. It restarts it,
        so the two bytes that follow one are read as a distance in their own right
        and may be another fork, or the marker that ends the track. Reading them
        as the curvature that normally follows would bend the road by whatever the
        caller meant as an ending.
        """
        while True:
            yield 2
            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                return True
            if (self.distance & 0xFFFF) != TURNOFF:
                return False

            yield 6
            self.distance = self.take_word()
            self.view_turnoff_x = self.take_word()
            self.view_turnoff_dx = self.take_word()
            shift = signed16((self.view_turnoff_x * self.distance) >> 15)
            self.view_x1 = signed16(self.view_x1 + shift)
            self.view_xofs1 = signed16(self.view_xofs1 + shift)
            self.view_turnoff_x = signed16(self.view_turnoff_x + self.view_turnoff_dx)

    def _project_one_stretch(self, count_from_raster, follow_turnoff, steer_by_turnoff=True):
        """One stretch of road: where it lands on screen, and the lines it fills.

        The projections that use this differ in three places and nowhere else.
        The single-player one counts its scanlines down from the last line it
        drew; the multi-player one counts them from where the viewer was, which
        gives a different answer once a stretch has been clipped. Only the
        single-player one carries a fork, because only it can be given one. And
        the lit one does not steer by that fork even though it can be given one,
        so a fork bends its road later than it bends the unlit road.
        """
        self._stretch_header(count_from_raster, steer_by_turnoff)
        if self.segments:
            self._rasterise()
        self._advance_projection(follow_turnoff)

    def _stretch_header(self, count_from_raster, steer_by_turnoff):
        """Where the stretch lands, and how many scanlines of it are visible."""
        far_x = signed32(self.world_x + self.world_xenv) >> 16
        steer = ((self.view_turnoff_x * self.distance) >> 15) if steer_by_turnoff else 0
        self.view_x2 = signed16(((far_x * self.distance) >> 15) + steer)
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

        start = self.poly_raster if count_from_raster else self.view_y1
        self._count_segments(start)
        self.put_word(self.segments)

    def _count_segments(self, start):
        """How many scanlines this stretch covers, after clipping at both ends."""
        self.segments = signed16(start - self.view_y2)
        if self.view_y2 >= self.poly_raster:
            self.segments = 0
        else:
            self.poly_raster = self.view_y2

        if self.view_y2 < self.poly_top:
            self.segments = 0
            if self.view_y1 >= self.poly_top:
                self.segments = signed16(self.view_y1 - self.poly_top)

    def _advance_projection(self, follow_turnoff):
        """Move the viewer to the last line drawn, and bend the road onwards."""
        self.view_x1 = self.view_x2
        self.view_y1 = self.view_y2
        self.view_xofs1 = self.view_xofs2
        self.view_yofs1 = self.view_yofs2

        self.world_dx = signed32(self.world_dx + sign_extend_low(self.world_ddx))
        self.world_dy = signed32(self.world_dy + sign_extend_low(self.world_ddy))
        self.world_x = signed32(self.world_x + self.world_dx + self.world_xenv)
        self.world_y = signed32(self.world_y + self.world_dy)
        if follow_turnoff:
            self.view_turnoff_x = signed16(self.view_turnoff_x + self.view_turnoff_dx)

    def _take_lighting(self):
        """Four colours, each dimmed by how far away the thing wearing it is.

        They arrive one at a time between the stretch header and its scanlines,
        and each answer replaces the header in the output rather than following
        it. The scanlines are then appended after the fourth colour, so a caller
        that reads the output as one block reads a colour where it expects the
        first line.
        """
        for _ in range(LIGHTING_COLOURS):
            yield 4
            distance = self.take_word()
            colour = self.take_word()
            red = ((colour & 0x1F) * distance >> 15) & 0x1F
            green = (((colour >> 5) & 0x1F) * distance >> 15) & 0x1F
            blue = (((colour >> 10) & 0x1F) * distance >> 15) & 0x1F
            self.clear_output()
            self.put_word(red | (green << 5) | (blue << 10))

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

    def _take_pair_of_pairs(self, into):
        """Four words that belong to two shapes, each with a left and a right."""
        into[0][0] = self.take_word()
        into[0][1] = self.take_word()
        into[1][0] = self.take_word()
        into[1][1] = self.take_word()

    def _skip_words(self, count):
        """Input the chip is handed and does nothing with."""
        for _ in range(count):
            self.take_word()

    def _render_solid(self):
        """Two solid shapes, given as the window edges that carve them out.

        The track projections hand back scanline segments to be drawn. This one
        hands back a pair of window positions per scanline, so the shape is what
        the window leaves visible rather than anything drawn into it. Two shapes
        are carried at once because the road can be beside itself at a fork.

        Both shapes are projected from the same distance, but a shape whose
        shaping words carry either of two particular values is projected from the
        second shape's origin rather than its own. That is how the fork is drawn
        without a second command.
        """
        self._take_pair_of_pairs(self.solid_clip_right)
        self._take_pair_of_pairs(self.solid_clip_left)
        self._skip_words(8)
        self._take_pair_of_pairs(self.solid_cx)
        self._take_pair_of_pairs(self.solid_ptr)
        self._take_pair_of_pairs(self.solid_bottom)
        self._take_pair_of_pairs(self.solid_top)
        self._skip_words(4)

        self.distance = self.take_word()
        view_x, view_y, envelope = self._take_shape_guides()

        self.solid_start = [view_x[0], view_x[1]]
        self.solid_raster = [[view_y[0], view_y[0]], [view_y[1], view_y[1]]]
        self.solid_plane = [self.distance, self.distance]
        self._open_solid_window(view_x, envelope)

        while True:
            yield 2
            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                break

            yield 16
            view_x, view_y, envelope = self._take_shape_guides()
            self.clear_output()
            for polygon in (0, 1):
                self._solid_one_shape(polygon, view_x, view_y, envelope)

        self.clear_output()
        self.put_word(0)

    def _take_shape_guides(self):
        """Where each shape sits this stretch, and how its two edges are pulled."""
        view_x = [0, 0]
        view_y = [0, 0]
        envelope = [[0, 0], [0, 0]]
        view_x[0] = self.take_word()
        view_y[0] = self.take_word()
        view_x[1] = self.take_word()
        view_y[1] = self.take_word()
        self._take_pair_of_pairs(envelope)
        return view_x, view_y, envelope

    def _open_solid_window(self, view_x, envelope):
        """The window the first shape starts from, which is the only output of the opening."""
        left = clamp(
            signed16(self.solid_cx[0][0] - view_x[0] + envelope[0][0]),
            self.solid_clip_left[0][0],
            self.solid_clip_right[0][0],
        )
        right = clamp(
            signed16(self.solid_cx[0][1] - view_x[0] + envelope[0][1]),
            self.solid_clip_left[0][1],
            self.solid_clip_right[0][1],
        )

        self.clear_output()
        self.put_byte(left & 0xFF)
        self.put_byte(right & 0xFF)

    def _solid_one_shape(self, polygon, view_x, view_y, envelope):
        """How many scanlines this shape covers, and the window on each of them."""
        self.segments = signed16(self.solid_raster[polygon][0] - view_y[polygon])
        if self.segments > 0:
            self.solid_raster[polygon] = [view_y[polygon], view_y[polygon]]
        else:
            self.segments = 0

        if view_y[polygon] < self.solid_top[polygon][0]:
            self.segments = 0

        self.put_word(self.segments)

        source = polygon
        if self.segments:
            if (envelope[polygon][0] & 0xFFFF) == FORK_LEFT or envelope[polygon][1] == FORK_RIGHT:
                source = 1
            self._solid_rasterise(polygon, source, view_x, envelope)

        self.solid_start[polygon] = view_x[source]

    def _solid_rasterise(self, polygon, source, view_x, envelope):
        """Walk the two window edges down the shape, one scanline at a time."""
        near_left = signed16((envelope[polygon][0] * self.solid_plane[source]) >> 15)
        far_left = signed16((envelope[polygon][0] * self.distance) >> 15)
        near_right = signed16((envelope[polygon][1] * self.solid_plane[source]) >> 15)
        far_right = signed16((envelope[polygon][1] * self.distance) >> 15)

        step_left = self._solid_step(view_x[source], near_left, far_left, source)
        step_right = self._solid_step(view_x[source], near_right, far_right, source)
        edge_left = sign_extend_whole(
            self.solid_cx[polygon][0] - self.solid_start[source] + near_left
        )
        edge_right = sign_extend_whole(
            self.solid_cx[polygon][1] - self.solid_start[source] + near_right
        )
        self.solid_plane[polygon] = self.distance

        for _ in range(self.segments):
            edge_left = signed32(edge_left + step_left)
            edge_right = signed32(edge_right + step_right)
            left = clamp(
                signed16(edge_left >> 16),
                self.solid_clip_left[polygon][0],
                self.solid_clip_right[polygon][0],
            )
            right = clamp(
                signed16(edge_right >> 16),
                self.solid_clip_left[polygon][1],
                self.solid_clip_right[polygon][1],
            )
            self.put_word(self.solid_ptr[polygon][0])
            self.put_byte(left & 0xFF)
            self.put_byte(right & 0xFF)
            self.solid_ptr[polygon][0] = signed16(self.solid_ptr[polygon][0] - 4)
            self.solid_ptr[polygon][1] = signed16(self.solid_ptr[polygon][1] - 4)

    def _solid_step(self, near_x, near_env, far_env, source):
        """How far one edge moves per scanline, negated when there is only one.

        A single scanline takes the step backwards. It reads as a mistake and it
        is what the chip does, so a shape one line tall leans the other way.
        """
        near = signed16(near_x + near_env)
        far = signed16(self.solid_start[source] + far_env)
        step = signed32((far - near) * inverse(self.segments) << 1)
        return signed32(-step) if self.segments == 1 else step

    def _project_sprites(self):
        """Sprites placed along the road, packed into the format the screen wants.

        This is the longest-running command on the chip. It holds a viewport, a
        raster line it has drawn down to, and a sprite half unpacked, and it
        suspends in six different places. Two of them are the same batch size, so
        the resumption point cannot be recovered from what arrives next.

        A sprite is one of two kinds. A vehicle carries a collision vector and a
        lift, and its horizontal position is handed back so the caller can steer
        by it. Anything else sits on the terrain and is placed from the raster
        line rather than from the horizon.

        Then the tiles. Each is a header, a pair of offsets and an attribute
        delta, and there is no count: the run ends on a zero, on a marker, or on
        the first header the chip does not recognise. A tile that would fall
        below the line the road has already covered is drawn twice, once as a
        transparent tile that clips it and once as itself.
        """
        self.viewport_cx = self.take_word()
        self.viewport_cy = self.take_word()
        self.take_word()
        self.viewport_left = self.take_word()
        self.viewport_right = self.take_word()
        self.viewport_top = self.take_word()
        self.viewport_bottom = self.take_word()

        self.poly_bottom = signed16(self.viewport_bottom - self.viewport_cy)
        self.poly_raster = OFFSCREEN_ROW

        while True:
            yield 4
            self.raster = self.take_word()
            if self.raster < self.poly_raster:
                self.sprite_clipy = signed16(
                    self.viewport_bottom - (self.poly_bottom - self.raster)
                )
                self.poly_raster = self.raster

            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                return
            if self.distance == NO_SPRITE:
                continue

            if (self.distance & 0xFFFF) == VEHICLE:
                yield 14
                self._place_vehicle()
                yield 4
                self.sprite_y = signed16(self.sprite_y + self.take_word())
            else:
                yield 10
                self._place_terrain()

            self.sprite_size = 1
            self.sprite_attr = self.take_word()

            finished = yield from self._pack_tiles()
            if finished:
                return

    def _place_vehicle(self):
        """A car, whose position is pulled towards whatever it has just hit."""
        energy = self.take_word() & 0xFFFF
        impact_back = self.take_word()
        car_back = self.take_word()
        impact_left = self.take_word()
        car_left = self.take_word()
        self.distance = self.take_word()
        car_right = self.take_word()

        world_x = signed16(car_right - car_left - ((energy * (impact_left - car_left)) >> 16))
        world_y = signed16(car_back - ((energy * (car_back - impact_back)) >> 16))

        self.sprite_x = signed16(self.viewport_cx + signed16((world_x * self.distance) >> 15))
        self.sprite_y = signed16(
            self.viewport_bottom - (self.poly_bottom - signed16((world_y * self.distance) >> 15))
        )

        self.clear_output()
        self.put_word(world_x)

    def _place_terrain(self):
        """Anything else, placed from the raster line the road has reached."""
        self.poly_cx_left = self.take_word()
        self.take_word()
        world_x = self.take_word()
        world_y = self.take_word()

        self.segments = signed16(self.poly_bottom - self.raster)
        self.sprite_x = signed16(
            self.viewport_cx + signed16((world_x * self.distance) >> 15) - self.poly_cx_left
        )
        self.sprite_y = signed16(
            self.viewport_bottom - self.segments + signed16((world_y * self.distance) >> 15)
        )

    def _pack_tiles(self):
        """The tiles of one sprite, until something says there are no more.

        Answers whether the whole command ended rather than only this sprite,
        because the end marker can arrive in the middle of a sprite and means the
        same thing there as it does between them.
        """
        while True:
            yield 2
            self.raster = self.take_word()
            if self.raster == END_OF_TRACK:
                return True
            if self.raster == NO_SPRITE:
                if not self.sprite_size:
                    return False
                self.sprite_size = 0
                continue
            if ((self.raster & 0xFFFF) >> 8) not in SPRITE_HEADERS:
                return False

            yield 4
            self._pack_one_tile()

    def _pack_one_tile(self):
        """One tile, drawn where it belongs and again where the road clips it."""
        offset_y = self.take_word()
        offset_x = self.take_word()
        sprite_x = signed16(self.sprite_x + offset_x)
        sprite_y = signed16(self.sprite_y + offset_y)
        attributes = signed16(self.sprite_attr + self.raster)
        pixels = 15 if self.sprite_size else 7

        self.clear_output()
        draw = True
        if (
            self.sprite_clipy - pixels <= sprite_y <= self.sprite_clipy
            and self.viewport_left - pixels <= sprite_x <= self.viewport_right
            and self.viewport_top - pixels <= self.sprite_clipy <= self.viewport_bottom
        ):
            draw = self._place_sprite(
                draw, sprite_x, self.sprite_clipy, CLIPPING_TILE, self.sprite_size, stop=False
            )
        if (
            self.viewport_left - pixels <= sprite_x <= self.viewport_right
            and self.viewport_top - pixels <= sprite_y <= self.viewport_bottom
            and sprite_y <= self.sprite_clipy
        ):
            draw = self._place_sprite(
                draw, sprite_x, sprite_y, attributes, self.sprite_size, stop=False
            )
        self._place_sprite(draw, 0, OFFSCREEN_ROW, 0, 0, stop=True)

    def _project_lit_track(self):
        """The single-player road again, this time asking for the light on it.

        Everything about the projection is the road command's, with two changes.
        Between the stretch header and its scanlines it asks four times for a
        distance and a colour and answers each dimmed by that distance. And it
        does not steer by the fork it is holding, so a fork it has been given
        moves the viewer without bending the stretch it arrives on.
        """
        self.take_word()
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
            self._stretch_header(count_from_raster=True, steer_by_turnoff=False)
            if self.segments:
                yield from self._take_lighting()
                self._rasterise()
            self._advance_projection(follow_turnoff=True)

            finished = yield from self._take_next_distance()
            if finished:
                return

            yield 6
            self.world_ddy = self.take_word()
            self.world_ddx = self.take_word()
            self.view_yofsenv = self.take_word()
            self.world_xenv = 0

    def _project_lit_turnoff(self):
        """The fork again, asking for the light on it the same way.

        Its continuation asks for ten bytes and reads eight of them. The vertical
        offset that the unlit fork re-reads on every stretch is taken once at the
        start here and never again, so the two bytes carrying it are accepted and
        dropped.
        """
        self.take_word()
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
            self._turnoff_header()
            if self.segments:
                yield from self._take_lighting()
                self._rasterise()
            self._advance_turnoff()

            yield 2
            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                return

            yield 10
            self.view_y2 = self.take_word()
            self.view_dy = signed16((self.take_word() * self.distance) >> 15)
            self.view_x2 = self.take_word()
            self.view_dx = signed16((self.take_word() * self.distance) >> 15)

    def _project_shared_track(self):
        """The multi-player road, which is the single-player one without the forks.

        It also takes its horizontal shaping as one word rather than two, and
        counts its scanlines from where the viewer was rather than from the last
        line drawn. Neither difference is visible until a stretch is clipped, and
        then both are.
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
        self.world_xenv = sign_extend_low(self.take_word())
        self.world_ddy = self.take_word()
        self.world_ddx = self.take_word()
        self.view_yofsenv = self.take_word()

        self.view_x1 = signed16(signed32(self.world_x + self.world_xenv) >> 16)
        self.view_y1 = signed16(self.world_y >> 16)
        self.view_xofs1 = signed16(self.world_x >> 16)
        self.view_yofs1 = self.world_yofs
        self.poly_raster = self.poly_bottom

        while True:
            self._project_one_stretch(count_from_raster=False, follow_turnoff=False)

            yield 2
            self.distance = self.take_word()
            if self.distance == END_OF_TRACK:
                return

            yield 6
            self.world_ddy = self.take_word()
            self.world_ddx = self.take_word()
            self.view_yofsenv = self.take_word()
            self.world_xenv = 0

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
        self._turnoff_header()
        if self.segments:
            self._rasterise()
        self._advance_turnoff()

    def _turnoff_header(self):
        """Where the branch has moved to, and how much of it is visible."""
        self.view_x2 = signed16(self.view_x2 + self.view_dx)
        self.view_y2 = signed16(self.view_y2 + self.view_dy)
        self.view_xofs2 = self.view_x2
        self.view_yofs2 = signed16(
            ((self.world_yofs * self.distance) >> 15) + self.poly_bottom - self.view_y2
        )

        self.clear_output()
        self.put_word(self.view_x2)
        self.put_word(self.view_y2)

        self._count_segments(self.view_y1)
        self.put_word(self.segments)

    def _advance_turnoff(self):
        """Move the viewer to the last line of the branch that was drawn."""
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
