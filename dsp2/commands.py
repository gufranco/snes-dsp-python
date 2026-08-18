"""What each DSP-2 command computes, as a function of its input alone.

Five of the chip's commands transform data and one only sets a colour. Each of
the five is written here as a plain function, separately from the register
protocol that feeds it, because that is what makes them checkable: a permutation
can be proved exhaustively, a product can be checked against arithmetic, and a
per-nibble rule can be run over every input it accepts. The protocol in `chip`
decides when these run; nothing here knows that a protocol exists.

The scale is the one that does not fit the pattern, and the comment on it says
why: its walk is not bounded by the data it was given.
"""

TILE_BYTES = 32
MULTIPLY_BYTES = 4

UNIT = 0x10000
PARAMETER_BYTES = 512

_LOW_PLANE_SHIFTS = (
    ((0x10, 3), (0x01, 6), (0x10, 1), (0x01, 4), (0x10, -1), (0x01, 2), (0x10, -3), (0x01, 0)),
    ((0x20, 2), (0x02, 5), (0x20, 0), (0x02, 3), (0x20, -2), (0x02, 1), (0x20, -4), (0x02, -1)),
)

_HIGH_PLANE_SHIFTS = (
    ((0x40, 1), (0x04, 4), (0x40, -1), (0x04, 2), (0x40, -3), (0x04, 0), (0x40, -5), (0x04, -2)),
    ((0x80, 0), (0x08, 3), (0x80, -2), (0x08, 1), (0x80, -4), (0x08, -1), (0x80, -6), (0x08, -3)),
)


def _shift(value, places):
    return (value << places) if places >= 0 else (value >> -places)


def _pack_ordered(ordered, pattern):
    out = 0
    for value, (mask, places) in zip(ordered, pattern, strict=True):
        out |= _shift(value & mask, places)
    return out & 0xFF


def tile(payload):
    """Rearrange a tile from packed pixels into the console's bit planes.

    Every output bit is one input bit moved, so the whole command is a
    permutation of the 256 bits it is given. That is what makes it provable
    rather than merely tested: 256 single bit inputs pin the destination of
    every bit, and nothing else can be hiding.
    """
    if len(payload) != TILE_BYTES:
        raise ValueError(f"a tile conversion takes {TILE_BYTES} bytes, got {len(payload)}")

    low = bytearray()
    high = bytearray()
    for group in range(8):
        quad = payload[group * 4 : group * 4 + 4]
        ordered = (quad[0], quad[0], quad[1], quad[1], quad[2], quad[2], quad[3], quad[3])
        for pattern in _LOW_PLANE_SHIFTS:
            low.append(_pack_ordered(ordered, pattern))
        for pattern in _HIGH_PLANE_SHIFTS:
            high.append(_pack_ordered(ordered, pattern))
    return bytes(low + high)


def merge(transparent, payload, length):
    """Lay one run of pixels over another, letting one colour show through.

    Each nibble is decided on its own, so a byte can take its high pixel from
    the overlay and its low pixel from what is underneath.
    """
    if len(payload) != 2 * length:
        raise ValueError(f"a merge of {length} takes {2 * length} bytes, got {len(payload)}")

    colour = transparent & 0x0F
    under = payload[:length]
    over = payload[length:]
    out = bytearray(length)
    for index in range(length):
        below = under[index]
        above = over[index]
        high = below & 0xF0 if (above >> 4) == colour else above & 0xF0
        low = below & 0x0F if (above & 0x0F) == colour else above & 0x0F
        out[index] = high | low
    return bytes(out)


def mirror(payload, length):
    """Flip a run of pixels end to end, which swaps each byte's two pixels too."""
    if len(payload) < length:
        raise ValueError(f"a mirror of {length} takes {length} bytes, got {len(payload)}")

    out = bytearray(length)
    for index in range(length):
        value = payload[index]
        out[length - 1 - index] = ((value << 4) | (value >> 4)) & 0xFF
    return bytes(out)


def multiply(payload):
    """Multiply two sixteen bit values into a thirty two bit product."""
    if len(payload) != MULTIPLY_BYTES:
        raise ValueError(f"a multiply takes {MULTIPLY_BYTES} bytes, got {len(payload)}")

    first = payload[0] | (payload[1] << 8)
    second = payload[2] | (payload[3] << 8)
    return (first * second).to_bytes(4, "little")


def ratio(in_length, out_length):
    """The fixed point step that walks the input while the output advances by one."""
    return (in_length << 17) // ((out_length << 1) + 1)


def scale(parameters, in_length, out_length):
    """Rescale a run of nibbles, reading the chip's parameter RAM rather than a payload.

    The walk is not bounded by the data that was sent. With the step at one unit,
    which is every case where the input is no longer than the output, it reads
    out_length bytes while the payload holds only half the input length, and the
    cartridge's own calls read a hundred and twenty bytes from a sixty byte
    payload. What it finds past the payload is whatever the previous command left
    in the parameter RAM, which the chip never clears, so the whole RAM is what
    gets passed here rather than the payload alone.

    An earlier version padded with zeroes and agreed with the recorded runs
    anyway, because in those runs the reads past the payload happened to land on
    bytes that were still zero. It disagreed everywhere else.
    """
    if len(parameters) < PARAMETER_BYTES:
        raise ValueError(f"the parameter RAM is {PARAMETER_BYTES} bytes, got {len(parameters)}")

    step = UNIT if in_length <= out_length else ratio(in_length, out_length)

    nibbles = []
    position = 0
    for _ in range(out_length * 2):
        index = position >> 16
        byte = parameters[(index >> 1) & (PARAMETER_BYTES - 1)]
        nibbles.append(byte & 0x0F if index & 1 else (byte & 0xF0) >> 4)
        position += step

    out = bytearray(out_length)
    for index in range(out_length):
        out[index] = (nibbles[index * 2] << 4) | nibbles[index * 2 + 1]
    return bytes(out)
