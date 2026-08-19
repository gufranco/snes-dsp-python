"""The DSP-1, which does fixed point three dimensional maths for a flight model.

This is the microcode that shipped in the most cartridges, and the only one in
the family whose commands are recognisably arithmetic: rotate a vector, project a
point onto a screen, work out where a screen position lands in the world, take
the length of something. A handful of commands set up a camera and the rest ask
questions of it.

The arithmetic is the interesting part, and it is not floating point. Every value
is a sixteen bit coefficient with a separate exponent, and the chip carries its
own normalise, its own reciprocal and its own truncation to move between them.
Each of those has edge cases that a straightforward implementation does not have:
the reciprocal has a special case at exactly one half, the normalisation of a
wide value has a second pass for exponents past fifteen, and truncation
saturates rather than wrapping.

Several commands answer to more than one byte. The chip masks the command it was
given rather than comparing it, so a projection can be asked for as any of four
bytes and the extra bits mean nothing. Two of them do not merely alias: the
raster command keeps answering after its output has been read, producing the next
scanline's matrix without being asked again, and a write while it still has
output is swallowed as an acknowledgement rather than starting anything.

The mask ROM this chip carries is not here. What the arithmetic reads out of it
is in `dsp1tables`, as the formulas that produce those numbers rather than as a
copy of the table. The one command that hands the whole table back needs the
whole table, so it answers from one the caller supplies or refuses to answer.
"""

from .dsp1tables import (
    HORIZON,
    INTERPOLATION,
    MAX_ZENITH,
    SINE,
    newton_seed,
    node,
    round_up,
    shift_down,
    shift_up,
    spread,
)
from .memory import PARAMETER_BYTES, UNSET_SEED, parameter_ram

IDLE = 0x80

OUTPUT_BYTES = DATA_ROM_BYTES = 2048
"""Room for the whole mask ROM, which is the only answer that needs more than a word.

The reference keeps five hundred and twelve bytes here and sets a count of two
thousand and forty eight for that one command, so it reads past its own buffer
and then past its own table. That command is therefore not comparable, and is the
one command this model does not put in front of the reference.
"""

DATA_ROM_WORDS = 1024

SATURATED = 0x7FFF

QUARTER_TURN = 0x40

DIVIDED_BY_ZERO_EXPONENT = 0x2F

NEWTON_ROUNDS = 2

FIRST_MASK = "dsp1"

CORRECTED_MASK = "dsp1b"

MASKS = (FIRST_MASK, CORRECTED_MASK)

VERSION_WORD = {
    FIRST_MASK: 0x0100,
    CORRECTED_MASK: 0x0101,
}
"""What each mask answers when asked command 0x2F, which names itself.

Measured rather than assumed. Both images were run on the processor they are
masked into and asked the same question ten times over: the first mask answers
0x0100 every time and the later one answers 0x0101 every time. It is a version
word, and it is the one difference between the two that is fully pinned down
here. There is at least one more, in the vector length at command 0x28, and it
is deliberately not modelled until it can be read as reliably as this one.
"""

MEMORY_SIZE = VERSION_WORD[FIRST_MASK]

RASTER_COMMANDS = (0x0A, 0x1A)

DUMP_DATA_ROM = 0x1F

WORDS_WANTED = {
    0x00: 2,
    0x01: 4,
    0x02: 7,
    0x03: 3,
    0x04: 2,
    0x06: 3,
    0x08: 3,
    0x0A: 1,
    0x0B: 3,
    0x0C: 3,
    0x0D: 3,
    0x0E: 2,
    0x0F: 1,
    0x10: 2,
    0x11: 4,
    0x13: 3,
    0x14: 6,
    0x18: 4,
    0x1A: 1,
    0x1B: 3,
    0x1C: 6,
    0x1D: 3,
    0x1F: 1,
    0x20: 2,
    0x21: 4,
    0x23: 3,
    0x28: 3,
    0x2B: 3,
    0x2D: 3,
    0x2F: 1,
    0x38: 4,
}
"""How many words each command takes. The chip counts bytes, so these are doubled."""

ALIASES = {
    0x05: 0x01,
    0x07: 0x0F,
    0x09: 0x0D,
    0x12: 0x02,
    0x15: 0x11,
    0x16: 0x06,
    0x17: 0x1F,
    0x19: 0x1D,
    0x22: 0x02,
    0x24: 0x04,
    0x25: 0x21,
    0x26: 0x06,
    0x27: 0x2F,
    0x29: 0x2D,
    0x2A: 0x1A,
    0x2C: 0x0C,
    0x2E: 0x0E,
    0x30: 0x10,
    0x31: 0x01,
    0x32: 0x02,
    0x33: 0x03,
    0x34: 0x14,
    0x35: 0x01,
    0x36: 0x06,
    0x37: 0x1F,
    0x39: 0x0D,
    0x3A: 0x1A,
    0x3B: 0x0B,
    0x3C: 0x1C,
    0x3D: 0x0D,
    0x3E: 0x0E,
    0x3F: 0x1F,
}
"""The bytes that mean the same thing as another byte, which is most of them.

The chip does not compare the command it was given, it masks it, so the bits
these differ in mean nothing. Two of the aliases are load bearing rather than
decorative: the raster command answers to four bytes and the model has to record
which of them it was, because that decides whether the next read produces another
matrix or nothing at all.
"""


class UnknownMask(Exception):
    pass


class DataRomMissing(Exception):
    pass


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def signed32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def scaled(first, second):
    """A product narrowed back into a word, which is every multiply this chip does."""
    return signed16((signed16(first) * signed16(second)) >> 15)


def leading_zeroes(value):
    """How far a word can be shifted left before its sign bit would move.

    A negative value is counted on its complement, so the answer is the run of
    bits that match the sign rather than the run of zeroes. A value with no run
    at all answers fifteen, which is the whole word.
    """
    found = ~value if value < 0 else value
    found &= 0x7FFF
    if found == 0:
        return 15
    shift = 0
    probe = 0x4000
    while not found & probe:
        probe >>= 1
        shift += 1
    return shift


def sine(angle):
    """The sine of an angle, interpolated between two steps of a table of 256."""
    if angle < 0:
        if angle == -0x8000:
            return 0
        return -sine(-angle)
    step = angle >> 8
    found = SINE[step] + ((INTERPOLATION[angle & 0xFF] * SINE[QUARTER_TURN + step]) >> 15)
    return min(found, SATURATED)


def cosine(angle):
    """The cosine of the same angle, from the same table a quarter turn along."""
    if angle < 0:
        if angle == -0x8000:
            return -0x8000
        angle = -angle
    step = angle >> 8
    found = SINE[QUARTER_TURN + step] - ((INTERPOLATION[angle & 0xFF] * SINE[step]) >> 15)
    return max(found, -SATURATED)


def narrowed(coefficient, exponent):
    """A value brought back to a plain word, saturating rather than wrapping."""
    if exponent > 0:
        if coefficient > 0:
            return SATURATED
        if coefficient < 0:
            return -SATURATED
        return coefficient
    if exponent < 0:
        return scaled(coefficient, shift_down(exponent))
    return coefficient


def halved_if_unnegatable(coefficient, exponent):
    """The one value a word cannot negate, moved to one it can.

    Negating the smallest word gives the smallest word again, so the horizon
    would come back on the wrong side of the screen. Halving it first costs a bit
    of the answer and keeps the sign. Nothing driving the chip through its port
    has been seen to reach this, and the chip carries the guard anyway.
    """
    if coefficient == -0x8000:
        return coefficient >> 1, exponent + 1
    return coefficient, exponent


def shifted_right(coefficient, exponent):
    """The same scaling without the saturation, which the projection uses."""
    return scaled(coefficient, shift_down(exponent))


def inverse(coefficient, exponent):
    """One over a value, by table lookup and two rounds of Newton's method.

    Three things here are not arithmetic. Zero answers a saturated word with an
    exponent that means nothing anything else produces, so a caller can tell the
    difference. Exactly one half is special-cased, and negative one half comes
    back with a different exponent from positive one half. And the seed table is
    read at a step of one hundred and twenty eight, so the two iterations start
    from within a part in two hundred and fifty six either way.
    """
    if coefficient == 0:
        return SATURATED, DIVIDED_BY_ZERO_EXPONENT

    sign = 1
    if coefficient < 0:
        coefficient = max(coefficient, -SATURATED)
        coefficient = -coefficient
        sign = -1

    shift = leading_zeroes(coefficient)
    coefficient <<= shift
    exponent -= shift

    if coefficient == 0x4000:
        if sign == 1:
            return SATURATED, 1 - exponent
        return -0x4000, 1 - (exponent - 1)

    found = newton_seed((coefficient - 0x4000) >> 7)
    for _ in range(NEWTON_ROUNDS):
        product = (coefficient * found) >> 15
        found = signed16((found + ((-found * product) >> 15)) << 1)
    return signed16(found * sign), 1 - exponent


def normalise(value, exponent):
    """A word shifted up until its top bit is significant, and by how much."""
    shift = leading_zeroes(value)
    if shift > 0:
        return signed16((value * shift_up(shift)) << 1), exponent - shift
    return value, exponent - shift


def normalise_wide(product):
    """The same for a value wider than a word, which has a second pass.

    The low half is folded back in once the high half has been shifted, and when
    the high half was nothing at all the shift starts again on the low half. That
    second pass reads a different ladder, and the ladder has a step that holds
    one where every step either side of it holds a power of two.
    """
    low = product & 0x7FFF
    high = signed16(product >> 15)
    shift = leading_zeroes(high)

    if shift == 0:
        return high, 0

    coefficient = signed16((high * shift_up(shift)) << 1)
    if shift < 15:
        return signed16(coefficient + ((low * round_up(shift)) >> 15)), shift

    tail = ~signed16(low | 0x8000) if high < 0 else low
    shift += leading_zeroes(tail)
    if shift > 15:
        return signed16((low * spread(shift)) << 1), shift
    return signed16(coefficient + low), shift


class Dsp1:
    """One DSP-1, holding a camera, three attitude matrices, and a command."""

    def __init__(self, fill=None, seed=UNSET_SEED, data_rom=None, revision=FIRST_MASK):
        if revision not in VERSION_WORD:
            raise UnknownMask(f"{revision} is not a mask of this chip; it has {', '.join(MASKS)}")
        self.revision = revision
        self.parameters = parameter_ram(fill=fill, seed=seed)
        self.output = bytearray(OUTPUT_BYTES)
        self.output[:PARAMETER_BYTES] = parameter_ram(fill=fill, seed=seed)
        self.data_rom = data_rom
        self.reset()

    def reset(self):
        self.waiting = True
        self.first_parameter = True
        self.command = 0
        self.in_count = 0
        self.in_index = 0
        self.out_count = 0
        self.out_index = 0
        self._clear_camera()
        self._clear_matrices()
        return self

    def _clear_camera(self):
        self.sin_azimuth = 0
        self.cos_azimuth = 0
        self.sin_zenith = 0
        self.cos_zenith = 0
        self.normal_x = 0
        self.normal_y = 0
        self.normal_z = 0
        self.centre_x = 0
        self.centre_y = 0
        self.eye_x = 0
        self.eye_y = 0
        self.eye_z = 0
        self.screen_coefficient = 0
        self.screen_exponent = 0
        self.screen_distance = 0
        self.plane_coefficient = 0
        self.plane_exponent = 0
        self.sin_clipped = 0
        self.cos_clipped = 0
        self.secant_c1 = 0
        self.secant_e1 = 0
        self.secant_c2 = 0
        self.secant_e2 = 0
        self.vertical_offset = 0
        self.raster_line = 0

    def _clear_matrices(self):
        self.matrices = [[[0, 0, 0] for _ in range(3)] for _ in range(3)]
        self.polar = [0, 0, 0]

    def write(self, byte):
        """One byte in, which is a command, a parameter, or an acknowledgement."""
        byte &= 0xFF
        if self.command in RASTER_COMMANDS and self.out_count:
            self.out_count -= 1
            self.out_index += 1
            return

        if self.waiting:
            self._accept_command(byte)
        else:
            self.parameters[self.in_index] = byte
            self.first_parameter = False
            self.in_index += 1

        if self.waiting:
            self.first_parameter = False
            return
        if self.first_parameter:
            return

        self.in_count -= 1
        if self.in_count == 0:
            self.waiting = True
            self.out_index = 0
            self._execute()

    def _accept_command(self, byte):
        self.command = ALIASES.get(byte, byte)
        self.in_index = 0
        self.waiting = False
        self.first_parameter = True
        found = WORDS_WANTED.get(self.command)
        if found is None:
            self.command = byte
            self.in_count = 0
            self.waiting = True
            return
        self.in_count = found << 1

    def read(self):
        """One byte of whatever the last command produced."""
        if not self.out_count:
            return IDLE
        found = self.output[self.out_index]
        self.out_index += 1
        self.out_count -= 1
        if self.out_count == 0 and self.command in RASTER_COMMANDS:
            self._next_raster_line()
        self.waiting = True
        return found

    def take_word(self, at):
        return signed16(self.parameters[at] | (self.parameters[at + 1] << 8))

    def _put(self, values):
        self.out_count = len(values) * 2
        for at, value in enumerate(values):
            self.output[at * 2] = value & 0xFF
            self.output[at * 2 + 1] = (value >> 8) & 0xFF

    def _execute(self):
        self._handlers()[self.command]()

    def _handlers(self):
        return {
            0x00: self._multiply,
            0x01: lambda: self._set_matrix(0),
            0x02: self._set_camera,
            0x03: lambda: self._from_matrix(0),
            0x04: self._sin_and_cos,
            0x06: self._project,
            0x08: self._squared_length,
            0x0A: self._raster,
            0x0B: lambda: self._forward_component(0),
            0x0C: self._turn,
            0x0D: lambda: self._to_matrix(0),
            0x0E: self._target,
            0x0F: self._memory_test,
            0x10: self._inverse,
            0x11: lambda: self._set_matrix(1),
            0x13: lambda: self._from_matrix(1),
            0x14: self._attitude,
            0x18: self._range,
            0x1A: self._raster,
            0x1B: lambda: self._forward_component(1),
            0x1C: self._turn_in_space,
            0x1D: lambda: self._to_matrix(1),
            0x1F: self._dump_data_rom,
            0x20: self._multiply_and_add_one,
            0x21: lambda: self._set_matrix(2),
            0x23: lambda: self._from_matrix(2),
            0x28: self._length,
            0x2B: lambda: self._forward_component(2),
            0x2D: lambda: self._to_matrix(2),
            0x2F: self._memory_size,
            0x38: self._range_and_add_one,
        }

    def _multiply(self):
        self._put([scaled(self.take_word(0), self.take_word(2))])

    def _multiply_and_add_one(self):
        self._put([signed16(scaled(self.take_word(0), self.take_word(2)) + 1)])

    def _inverse(self):
        coefficient, exponent = inverse(self.take_word(0), self.take_word(2))
        self._put([coefficient, exponent])

    def _sin_and_cos(self):
        angle = self.take_word(0)
        radius = self.parameters[2] | (self.parameters[3] << 8)
        self._put([scaled(sine(angle), radius), scaled(cosine(angle), radius)])

    def _squared_length(self):
        x = self.take_word(0)
        y = self.take_word(2)
        z = self.take_word(4)
        size = signed32((x * x + y * y + z * z) << 1)
        self._put([size & 0xFFFF, (size >> 16) & 0xFFFF])

    def _range(self):
        self._put([self._range_of()])

    def _range_and_add_one(self):
        self._put([signed16(self._range_of() + 1)])

    def _range_of(self):
        x = self.take_word(0)
        y = self.take_word(2)
        z = self.take_word(4)
        radius = self.take_word(6)
        return signed16(signed32(x * x + y * y + z * z - radius * radius) >> 15)

    def _length(self):
        """How long a vector is, by interpolating between two nodes of a root curve."""
        x = self.take_word(0)
        y = self.take_word(2)
        z = self.take_word(4)
        squared = signed32(x * x + y * y + z * z)
        if squared == 0:
            self._put([0])
            return

        coefficient, exponent = normalise_wide(squared)
        if exponent & 1:
            coefficient = scaled(coefficient, 0x4000)

        step = scaled(coefficient, QUARTER_TURN)
        below = node(step)
        above = node(step + 1)
        found = (((above - below) * (coefficient & 0x1FF)) >> 9) + below
        self._put([signed16(found) >> (exponent >> 1)])

    def _turn(self):
        """A point turned about the origin, which is the plainest command here."""
        angle = self.take_word(0)
        x = self.take_word(2)
        y = self.take_word(4)
        self._put(
            [
                signed16(scaled(y, sine(angle)) + scaled(x, cosine(angle))),
                signed16(scaled(y, cosine(angle)) - scaled(x, sine(angle))),
            ]
        )

    def _turn_in_space(self):
        """The same about all three axes in turn, each from the result of the last."""
        around_z = self.take_word(0)
        around_y = self.take_word(2)
        around_x = self.take_word(4)
        x = self.take_word(6)
        y = self.take_word(8)
        z = self.take_word(10)

        x, y = (
            signed16(scaled(y, sine(around_z)) + scaled(x, cosine(around_z))),
            signed16(scaled(y, cosine(around_z)) - scaled(x, sine(around_z))),
        )
        z, turned_x = (
            signed16(scaled(x, sine(around_y)) + scaled(z, cosine(around_y))),
            signed16(scaled(x, cosine(around_y)) - scaled(z, sine(around_y))),
        )
        y, z = (
            signed16(scaled(z, sine(around_x)) + scaled(y, cosine(around_x))),
            signed16(scaled(z, cosine(around_x)) - scaled(y, sine(around_x))),
        )
        self.polar = [turned_x, y, z]
        self._put(self.polar)

    def _set_matrix(self, which):
        """One attitude matrix, from a scale and three angles."""
        scale = self.take_word(0) >> 1
        around_z = self.take_word(2)
        around_y = self.take_word(4)
        around_x = self.take_word(6)

        sin_z, cos_z = sine(around_z), cosine(around_z)
        sin_y, cos_y = sine(around_y), cosine(around_y)
        sin_x, cos_x = sine(around_x), cosine(around_x)

        self.matrices[which] = [
            [
                scaled(scaled(scale, cos_z), cos_y),
                signed16(-scaled(scaled(scale, sin_z), cos_y)),
                scaled(scale, sin_y),
            ],
            [
                signed16(
                    scaled(scaled(scale, sin_z), cos_x)
                    + scaled(scaled(scaled(scale, cos_z), sin_x), sin_y)
                ),
                signed16(
                    scaled(scaled(scale, cos_z), cos_x)
                    - scaled(scaled(scaled(scale, sin_z), sin_x), sin_y)
                ),
                signed16(-scaled(scaled(scale, sin_x), cos_y)),
            ],
            [
                signed16(
                    scaled(scaled(scale, sin_z), sin_x)
                    - scaled(scaled(scaled(scale, cos_z), cos_x), sin_y)
                ),
                signed16(
                    scaled(scaled(scale, cos_z), sin_x)
                    + scaled(scaled(scaled(scale, sin_z), cos_x), sin_y)
                ),
                scaled(scaled(scale, cos_x), cos_y),
            ],
        ]

    def _to_matrix(self, which):
        """A world vector turned into the frame one of the matrices names."""
        matrix = self.matrices[which]
        x = self.take_word(0)
        y = self.take_word(2)
        z = self.take_word(4)
        self._put(
            [signed16(scaled(x, row[0]) + scaled(y, row[1]) + scaled(z, row[2])) for row in matrix]
        )

    def _from_matrix(self, which):
        """And the same vector turned back out of that frame."""
        matrix = self.matrices[which]
        forward = self.take_word(0)
        left = self.take_word(2)
        up = self.take_word(4)
        self._put(
            [
                signed16(
                    scaled(forward, matrix[0][axis])
                    + scaled(left, matrix[1][axis])
                    + scaled(up, matrix[2][axis])
                )
                for axis in range(3)
            ]
        )

    def _forward_component(self, which):
        """How much of a vector points the way one of the matrices faces.

        This one narrows the whole sum rather than each term, so it keeps a bit
        the three-word form throws away and can answer differently from the first
        row of the same matrix applied the other way.
        """
        matrix = self.matrices[which]
        x = self.take_word(0)
        y = self.take_word(2)
        z = self.take_word(4)
        self._put([signed16((x * matrix[0][0] + y * matrix[0][1] + z * matrix[0][2]) >> 15)])

    def _memory_test(self):
        self._put([0])

    def _memory_size(self):
        self._put([VERSION_WORD[self.revision]])

    def _dump_data_rom(self):
        """The mask ROM, which needs a mask ROM to give.

        The chip has one and this package does not, so a caller that wants this
        command supplies the table and takes responsibility for having it. There
        is no partial answer: a table that is absent is not a table of zeroes.
        """
        if self.data_rom is None:
            raise DataRomMissing(
                "command 0x1f hands back this chip's mask ROM, which is content "
                "rather than behaviour and is not shipped here; construct the chip "
                "with data_rom= to answer it"
            )
        self._put(list(self.data_rom[:DATA_ROM_WORDS]))

    def _set_camera(self):
        """Where the camera is, where it looks, and what that does to the horizon."""
        focus_x = self.take_word(0)
        focus_y = self.take_word(2)
        focus_z = self.take_word(4)
        focus_length = self.take_word(6)
        screen_length = self.take_word(8)
        azimuth = self.take_word(10)
        zenith = self.take_word(12)

        self._face(azimuth, zenith)
        centre_z = self._place(focus_x, focus_y, focus_z, focus_length, screen_length)
        clipped = self._clip_zenith(zenith, centre_z)
        offset = self._horizon(zenith, clipped, screen_length)
        self._put([offset, self._vanishing_point(), self.centre_x, self.centre_y])

    def _face(self, azimuth, zenith):
        self.sin_azimuth = sine(azimuth)
        self.cos_azimuth = cosine(azimuth)
        self.sin_zenith = sine(zenith)
        self.cos_zenith = cosine(zenith)
        self.normal_x = scaled(self.sin_zenith, -self.sin_azimuth)
        self.normal_y = scaled(self.sin_zenith, self.cos_azimuth)
        self.normal_z = scaled(self.cos_zenith, SATURATED)

    def _place(self, focus_x, focus_y, focus_z, focus_length, screen_length):
        self.centre_x = signed16(focus_x + scaled(focus_length, self.normal_x))
        self.centre_y = signed16(focus_y + scaled(focus_length, self.normal_y))
        centre_z = signed16(focus_z + scaled(focus_length, self.normal_z))

        self.eye_x = signed16(self.centre_x - scaled(screen_length, self.normal_x))
        self.eye_y = signed16(self.centre_y - scaled(screen_length, self.normal_y))
        self.eye_z = signed16(centre_z - scaled(screen_length, self.normal_z))

        self.screen_coefficient, self.screen_exponent = normalise(screen_length, 0)
        self.screen_distance = screen_length
        return centre_z

    def _clip_zenith(self, zenith, centre_z):
        """How far the view may tilt before the projection stops making sense."""
        coefficient, exponent = normalise(centre_z, 0)
        self.plane_coefficient = coefficient
        self.plane_exponent = exponent

        limit = MAX_ZENITH[-exponent]
        clipped = zenith
        if clipped < 0:
            limit = -limit
            clipped = max(clipped, limit + 1)
        else:
            clipped = min(clipped, limit)

        self.sin_clipped = sine(clipped)
        self.cos_clipped = cosine(clipped)

        self.secant_c1, self.secant_e1 = inverse(self.cos_clipped, 0)
        coefficient, exponent = normalise(scaled(coefficient, self.secant_c1), exponent)
        exponent += self.secant_e1

        coefficient = scaled(narrowed(coefficient, exponent), self.sin_clipped)
        self.centre_x = signed16(self.centre_x + scaled(coefficient, self.sin_azimuth))
        self.centre_y = signed16(self.centre_y - scaled(coefficient, self.cos_azimuth))
        return clipped

    def _horizon(self, zenith, clipped, screen_length):
        """How far the horizon moves once the view has been clipped."""
        offset = 0
        limit = MAX_ZENITH[-self.plane_exponent]
        if clipped < 0:
            limit = -limit
        if zenith != clipped or zenith == limit:
            zenith = max(zenith, -SATURATED)
            over = signed16(zenith - limit)
            if over >= 0:
                over -= 1
            spread = signed16(~(over << 2))

            over = scaled(spread, HORIZON[4])
            over = signed16(scaled(over, spread) + HORIZON[3])
            offset = signed16(offset - scaled(scaled(over, spread), screen_length))

            over = scaled(spread, spread)
            spread = signed16(scaled(over, HORIZON[0]) + HORIZON[1])
            self.cos_clipped = signed16(
                self.cos_clipped + scaled(scaled(over, spread), self.cos_clipped)
            )
        self.vertical_offset = scaled(screen_length, self.cos_clipped)
        return offset

    def _vanishing_point(self):
        """Where the horizon sits on the screen, and the secant the raster reuses."""
        cosecant, exponent = inverse(self.sin_clipped, 0)
        coefficient, exponent = normalise(self.vertical_offset, exponent)
        coefficient, exponent = normalise(scaled(coefficient, cosecant), exponent)
        coefficient, exponent = halved_if_unnegatable(coefficient, exponent)
        found = narrowed(signed16(-coefficient), exponent)
        self.secant_c2, self.secant_e2 = inverse(self.cos_clipped, 0)
        return found

    def _raster(self):
        """The mode seven matrix for one scanline, and the line after it."""
        self.raster_line = self.take_word(0)
        self._put(self._raster_matrix())
        self.raster_line = signed16(self.raster_line + 1)
        self.in_index = 0

    def _next_raster_line(self):
        """The next scanline's matrix, produced by reading the last one out.

        Nothing asks for this. The command keeps answering until something else
        is asked of the chip, which is how a caller fills a whole screen from one
        command and why the model has to know which command it is holding.
        """
        self._put(self._raster_matrix())
        self.raster_line = signed16(self.raster_line + 1)
        self.out_index = 0

    def _raster_matrix(self):
        coefficient, exponent = inverse(
            signed16(scaled(self.raster_line, self.sin_zenith) + self.vertical_offset), 7
        )
        exponent += self.plane_exponent

        scale = scaled(coefficient, self.plane_coefficient)
        tilted = exponent + self.secant_e2

        coefficient, exponent = normalise(scale, exponent)
        coefficient = narrowed(coefficient, exponent)
        across = scaled(coefficient, self.cos_azimuth)
        down = scaled(coefficient, self.sin_azimuth)

        coefficient, tilted = normalise(scaled(scale, self.secant_c2), tilted)
        coefficient = narrowed(coefficient, tilted)
        return [
            across,
            scaled(coefficient, -self.sin_azimuth),
            down,
            scaled(coefficient, self.cos_azimuth),
        ]

    def _project(self):
        """Where a point in the world lands on the screen, and how big it is there."""
        x = self.take_word(0)
        y = self.take_word(2)
        z = self.take_word(4)

        px, ex = normalise_wide(signed32(x - self.eye_x))
        py, ey = normalise_wide(signed32(y - self.eye_y))
        pz, ez = normalise_wide(signed32(z - self.eye_z))
        px, ex = px >> 1, ex - 1
        py, ey = py >> 1, ey - 1
        pz, ez = pz >> 1, ez - 1

        common = min(ey, ez, ex)
        px = shifted_right(px, ex - common)
        py = shifted_right(py, ey - common)
        pz = shifted_right(pz, ez - common)

        depth = signed16(
            -scaled(px, self.normal_x) - scaled(py, self.normal_y) - scaled(pz, self.normal_z)
        )
        scale, common, plane_exponent, reach = self._perspective(depth, common)
        self._put(
            [
                self._screen_across(px, py, scale, common, plane_exponent),
                self._screen_down(px, py, pz, scale, common, plane_exponent),
                self._screen_size(scale, plane_exponent, reach),
            ]
        )

    def _perspective(self, depth, common):
        """How much a point shrinks at the depth it sits at."""
        wide = depth
        common = 16 - common
        wide = wide << common if common >= 0 else wide >> -common
        if wide == -1:
            wide = 0
        wide >>= 1

        distance = signed32((self.screen_distance & 0xFFFF) + wide)
        coefficient, exponent = normalise_wide(distance)
        exponent = 15 - exponent

        reciprocal, reach = inverse(coefficient, 0)
        return scaled(reciprocal, self.screen_coefficient), common, exponent, reach

    def _screen_across(self, px, py, scale, common, plane_exponent):
        along = signed16(
            scaled(px, scaled(self.cos_azimuth, SATURATED))
            + scaled(py, scaled(self.sin_azimuth, SATURATED))
        )
        coefficient, exponent = normalise(scaled(along, scale), 0)
        return narrowed(coefficient, self.screen_exponent - plane_exponent + common + exponent)

    def _screen_down(self, px, py, pz, scale, common, plane_exponent):
        along = signed16(
            scaled(px, scaled(self.cos_zenith, -self.sin_azimuth))
            + scaled(py, scaled(self.cos_zenith, self.cos_azimuth))
            + scaled(pz, scaled(-self.sin_zenith, SATURATED))
        )
        coefficient, exponent = normalise(scaled(along, scale), 0)
        return narrowed(coefficient, self.screen_exponent - plane_exponent + common + exponent)

    def _screen_size(self, scale, plane_exponent, reach):
        """How big a thing at that depth is, which carries the reciprocal's own exponent.

        The two screen positions start their exponent from nothing. This one does
        not: it continues from the exponent the reciprocal came back with, and a
        model that restarts it answers half of everything.
        """
        coefficient, exponent = normalise(scale, reach)
        return narrowed(coefficient, exponent + self.screen_exponent - plane_exponent - 7)

    def _target(self):
        """Where a screen position lands in the world, which is the projection undone."""
        across = self.take_word(0)
        down = self.take_word(2)

        coefficient, exponent = inverse(
            signed16(scaled(down, self.sin_zenith) + self.vertical_offset), 8
        )
        exponent += self.plane_exponent

        scale = scaled(coefficient, self.plane_coefficient)
        tilted = exponent + self.secant_e1

        coefficient, exponent = normalise(scale, exponent)
        coefficient = scaled(narrowed(coefficient, exponent), signed16(across << 8))
        x = signed16(self.centre_x + scaled(coefficient, self.cos_azimuth))
        y = signed16(self.centre_y - scaled(coefficient, self.sin_azimuth))

        coefficient, tilted = normalise(scaled(scale, self.secant_c1), tilted)
        coefficient = scaled(narrowed(coefficient, tilted), signed16(down << 8))
        self._put(
            [
                signed16(x + scaled(coefficient, -self.sin_azimuth)),
                signed16(y + scaled(coefficient, self.cos_azimuth)),
            ]
        )

    def _attitude(self):
        """Where an aircraft ends up after a moment of flying the way it is pointed."""
        around_z = self.take_word(0)
        around_x = self.take_word(2)
        around_y = self.take_word(4)
        up = self.take_word(6)
        forward = self.take_word(8)
        left = self.take_word(10)

        secant, secant_exponent = inverse(cosine(around_x), 0)

        coefficient, exponent = normalise_wide(up * cosine(around_y) - forward * sine(around_y))
        exponent = secant_exponent - exponent
        coefficient, exponent = normalise(scaled(coefficient, secant), exponent)
        turned_z = signed16(around_z + narrowed(coefficient, exponent))

        turned_x = signed16(
            around_x + scaled(up, sine(around_y)) + scaled(forward, cosine(around_y))
        )

        coefficient, exponent = normalise_wide(up * cosine(around_y) + forward * sine(around_y))
        exponent = secant_exponent - exponent
        sin_coefficient, exponent = normalise(sine(around_x), exponent)
        tangent = scaled(secant, sin_coefficient)
        coefficient, exponent = normalise(signed16(-scaled(coefficient, tangent)), exponent)
        turned_y = signed16(around_y + narrowed(coefficient, exponent) + left)

        self._put([turned_z, turned_x, turned_y])

    def __repr__(self):
        return f"<DSP-1 command {self.command:#04x} waiting {self.waiting}>"
