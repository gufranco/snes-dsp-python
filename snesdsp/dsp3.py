"""The DSP-3, which is three unrelated chips sharing one port.

It decompresses tile data, it converts a bitmap into bit planes, and it walks a
hex grid working out what a unit can reach and what each step there costs. The
three have nothing to do with each other beyond arriving through the same two
registers, and the chip decides which one is running by remembering the last
command it was given.

That memory is the whole design. There is no length, no framing and no way to ask
the chip what it is doing. A command sets the state machine's next step, and
every word that arrives afterwards is handed to whatever step is current, which
sets the next one. So a word means nothing on its own: it means whatever the step
holding it decides, and the step is state that outlives the word.

The port carries sixteen bit words through an eight bit hole, and which half
arrives is a bit in the status register rather than a count. Reading toggles it
too, so an odd number of reads leaves the next write landing in the wrong half.
That is not a mistake to be smoothed over: a driver that loses count of its own
halves is what the register is for.

One status bit changes the rule entirely. With it set, every single byte runs the
current step rather than every second one.

The mask ROM this chip carries is not here. Only one part of it is reachable by
anything other than the command that dumps it: six pairs naming the neighbours of
a cell on a hex grid, which are the grid's own geometry rather than content. Those
are here. The dump command needs the rest, and the rest is not ours to ship, so
that command answers from a table the caller supplies or refuses to answer at all.
"""

RESET_DATA = 0x0080

RESET_STATUS = 0x0084

READY = 0x0080

BUSY = 0x00C0

BYTE_AT_A_TIME = 0x0004

HALF_WORD = 0x0010

MORE_INPUT = 0x0040

END_OF_LIST = 0xFFFF

DATA_ROM_WORDS = 1024

GRID_CELLS = 0x2000

TILE_BYTES = 8

CODE_WORDS = 512

BASE_CODES = 8

IMPASSABLE = 0xFF

SHORT_RUN = 8

LONG_RUN = 12

TURNS = 6

NEIGHBOURS = (
    (-1, 0),
    (-1, 1),
    (0, 1),
    (1, 0),
    (0, -1),
    (-1, -1),
)
"""The six neighbours of a hex cell, as the chip's own table gives them.

Each pair is in the order the lookup reads it: the row step first, then the
column step. The chip reads them from its mask ROM at a computed offset, and the
offset wraps, so a move beyond the sixth comes back round to the first.
"""

STRAY_MOVES = {
    12: (0, 0),
    13: (0, 68),
    14: (136, 204),
    15: (272, 340),
}
"""What the chip finds past the two copies of the direction table.

These are not neighbours. They are whatever the next words of the mask ROM happen
to be, read as a pair because the code that reads them cannot tell. A move of
sixteen or more lands on the unprogrammed tail, where every pair is minus one.
"""

STRAY_TAIL = (-1, -1)

MOVE_TABLE_BASE = 0x03B2

TABLE_WORDS = 0x0400

HI_ADD_EVEN = (0x00, 0xFF, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00)

HI_ADD_ODD = (0x00, 0xFF, 0xFF, 0x00, 0x01, 0x00, 0xFF, 0x00)

LO_ADD = (0x00, 0x00, 0x01, 0x01, 0x00, 0xFF, 0xFF, 0x00)


class DataRomMissing(Exception):
    pass


class TableOverrun(Exception):
    pass


def signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def low(value):
    return value & 0xFF


def high(value):
    return (value >> 8) & 0xFF


def move_of(index):
    """The pair the chip finds for a move, wrapped the way its lookup wraps.

    The lookup takes a word offset and masks it to the table, so the six
    directions appear twice before anything else does. Nothing checks the range.
    """
    at = ((index << 1) + MOVE_TABLE_BASE) & (TABLE_WORDS - 1)
    step = ((at - MOVE_TABLE_BASE) % TABLE_WORDS) >> 1
    if step < 2 * TURNS:
        return NEIGHBOURS[step % TURNS]
    return STRAY_MOVES.get(step, STRAY_TAIL)


class Dsp3:
    """One DSP-3, holding a step, a window, and whichever of its three jobs is running."""

    def __init__(self, data_rom=None):
        self.data_rom = data_rom
        self.reset()

    def reset(self):
        self.data = RESET_DATA
        self.status = RESET_STATUS
        self.step = self._command
        self.index = 0
        self.window_low = 0
        self.window_high = 0
        self.add_low = 0
        self.add_high = 0
        self.x = 0
        self.y = 0
        self.memory_index = 0
        self._clear_tiles()
        self._clear_decoder()
        self._clear_grid()
        return self

    def _clear_tiles(self):
        self.bitmap = bytearray(TILE_BYTES)
        self.bitplane = bytearray(TILE_BYTES)
        self.bitmap_index = 0
        self.bitplane_index = 0
        self.count = 0

    def _clear_decoder(self):
        self.codewords = 0
        self.outwords = 0
        self.symbol = 0
        self.bit_count = 0
        self.bits_left = 0
        self.request_bits = 0
        self.request_data = 0
        self.bit_command = END_OF_LIST
        self.base_length = 0
        self.base_codes = 0
        self.base_code = END_OF_LIST
        self.codes = [0] * CODE_WORDS
        self.code_lengths = [0] * BASE_CODES
        self.code_offsets = [0] * BASE_CODES
        self.lz_code = 0
        self.lz_length = 0

    def _clear_grid(self):
        self.origin_x = 0
        self.origin_y = 0
        self.terrain = bytearray(GRID_CELLS)
        self.cost = bytearray(GRID_CELLS)
        self.weight = bytearray(GRID_CELLS)
        self.cell = 0
        self.turn = 0
        self.walk_x = 0
        self.walk_y = 0
        self.min_radius = 0
        self.max_radius = 0
        self.max_search_radius = 0
        self.max_path_radius = 0
        self.lcv_radius = 0
        self.lcv_steps = 0
        self.lcv_turns = 0

    def write(self, byte):
        """One byte in, which is half a word unless the chip says otherwise."""
        byte &= 0xFF
        if self.status & BYTE_AT_A_TIME:
            self.data = (self.data & 0xFF00) | byte
            self.step()
            return

        self.status ^= HALF_WORD
        if self.status & HALF_WORD:
            self.data = (self.data & 0xFF00) | byte
        else:
            self.data = (self.data & 0x00FF) | (byte << 8)
            self.step()

    def read(self):
        """One byte out, which advances the same state machine that writing does."""
        if self.status & BYTE_AT_A_TIME:
            found = low(self.data)
            self.step()
            return found

        self.status ^= HALF_WORD
        if self.status & HALF_WORD:
            return low(self.data)
        found = high(self.data)
        self.step()
        return found

    @property
    def pending_output(self):
        """Whether a byte would be read as data rather than taken as a command.

        One or nothing, never a count, because this part is clocked a byte at a
        time and holds no notion of how much is left. That is the shape the
        microcode backend has too, and for the same reason.
        """
        return 0 if self.idle else 1

    @property
    def idle(self):
        """Whether the next byte would be read as a command rather than as data."""
        return self.step == self._command

    def read_status(self):
        """The status register, which is what an address outside the data window gives."""
        return self.status & 0xFF

    def _restart(self):
        self.data = RESET_DATA
        self.status = RESET_STATUS
        self.step = self._command

    def _command(self):
        found = {
            0x02: self._coordinate,
            0x03: self._cell_of,
            0x06: self._set_window,
            0x07: self._step_from,
            0x0C: self._absorb_one,
            0x0F: self._test_memory,
            0x10: self._absorb_until_end,
            0x18: self._convert,
            0x1C: self._absorb_two_answer_two,
            0x1E: self._search_reachable,
            0x1F: self._dump_data_rom,
            0x38: self._decode,
            0x3E: self._set_origin,
        }.get(self.data)
        if self.data >= 0x40 or found is None:
            return
        self.step = found
        if found == self._step_from:
            return
        self.status = READY
        self.index = 0

    def _test_memory(self):
        self.data = 0x0000
        self._restart()

    def _dump_data_rom(self):
        """The mask ROM, word by word, which needs a mask ROM to give.

        The chip has one and this package does not, so a caller that wants this
        command supplies the table and takes responsibility for having it. There
        is no partial answer: a table that is absent is not a table of zeroes.
        """
        if self.data_rom is None:
            raise DataRomMissing(
                "command 0x1f hands back this chip's mask ROM word by word, which is "
                "content rather than behaviour and is not shipped here; construct the "
                "chip with data_rom= to answer it"
            )
        self.memory_index = 0
        self.step = self._dump_next_word
        self._dump_next_word()

    def _dump_next_word(self):
        self.data = self.data_rom[self.memory_index]
        self.memory_index += 1
        if self.memory_index == DATA_ROM_WORDS:
            self._restart()

    def _set_window(self):
        """How wide and how tall the grid is, which every cell lookup wraps against."""
        self.window_low = low(self.data)
        self.window_high = high(self.data)
        self._restart()

    def _cell_of(self):
        """Where a coordinate pair lands in the grid arrays."""
        self.data = self._cell_for(low(self.data), high(self.data))
        self.step = self._restart

    def _cell_for(self, x, y):
        return signed16((self.window_low * y << 1) + (x << 1)) >> 1

    def _coordinate(self):
        """A pair handed in and handed straight back, one word at a time."""
        self.index += 1
        if self.index == 3:
            if self.data == END_OF_LIST:
                self._restart()
        elif self.index == 4:
            self.x = self.data
        elif self.index == 5:
            self.y = self.data
            self.data = 1
        elif self.index == 6:
            self.data = self.x
        elif self.index == 7:
            self.data = self.y
            self.index = 0

    def _step_from(self):
        """One move across the grid, from the pair the mask ROM holds for it.

        This is the one command the chip accepts without also saying it is busy,
        so the byte naming the move arrives on its own rather than as half of a
        word. Nothing about the command says so; it is what the dispatcher skips.
        """
        self.add_high, self.add_low = move_of(self.data)
        self.step = self._step_wrap
        self.status = READY

    def _step_wrap(self):
        """Add the caller's own offset to the move, and wrap it into the window."""
        offset_low = low(self.data)
        offset_high = high(self.data)
        if offset_low & 1:
            offset_high += self.add_low & 1

        self.add_low += offset_low
        self.add_high += offset_high
        self._wrap_into_window()

        self.data = (self.add_low | (self.add_high << 8) | ((self.add_high >> 8) & 0xFF)) & 0xFFFF
        self.step = self._step_answer

    def _wrap_into_window(self):
        if self.add_low < 0:
            self.add_low += self.window_low
        elif self.add_low >= self.window_low:
            self.add_low -= self.window_low

        if self.add_high < 0:
            self.add_high += self.window_high
        elif self.add_high >= self.window_high:
            self.add_high -= self.window_high

    def _step_answer(self):
        self.data = self._cell_for(self.add_low, self.add_high)
        self.step = self._restart

    def _absorb_one(self):
        self.data = 0
        self.step = self._restart

    def _absorb_until_end(self):
        if self.data == END_OF_LIST:
            self._restart()

    def _absorb_two_answer_two(self):
        """Two words in and two zeroes out, which is all anything ever saw it do.

        Four steps for two words and two answers, because the chip counts the
        words it has been given rather than the bytes, and zeroes the answer only
        once both have arrived. A model that zeroes it a step early hands back the
        second word instead of the first zero, and nothing else about it differs.
        """
        self.step = self._absorb_second_word

    def _absorb_second_word(self):
        self.step = self._answer_zero

    def _answer_zero(self):
        self.data = 0
        self.step = self._answer_zero_again

    def _answer_zero_again(self):
        self.data = 0
        self.step = self._restart

    def _convert(self):
        """Eight bytes of bitmap in, eight bytes of bit plane out, repeatedly."""
        self.count = self.data
        self.bitmap_index = 0
        self.step = self._convert_next

    def _convert_next(self):
        if self.bitmap_index < TILE_BYTES:
            self.bitmap[self.bitmap_index] = low(self.data)
            self.bitmap[self.bitmap_index + 1] = high(self.data)
            self.bitmap_index += 2
            if self.bitmap_index == TILE_BYTES:
                self._transpose()

        if self.bitmap_index != TILE_BYTES:
            return
        if self.bitplane_index == TILE_BYTES:
            if not self.count:
                self._restart()
            self.bitmap_index = 0
            return
        self.data = self.bitplane[self.bitplane_index] | (
            self.bitplane[self.bitplane_index + 1] << 8
        )
        self.bitplane_index += 2

    def _transpose(self):
        """Turn eight rows of pixels into eight planes of one bit each."""
        for row in range(TILE_BYTES):
            for plane in range(TILE_BYTES):
                self.bitplane[plane] = (
                    (self.bitplane[plane] << 1) | ((self.bitmap[row] >> plane) & 1)
                ) & 0xFF
        self.bitplane_index = 0
        self.count = (self.count - 1) & 0xFFFF

    def _decode(self):
        self.codewords = self.data
        self.step = self._decode_length

    def _decode_length(self):
        self.outwords = self.data
        self.step = self._decode_symbols
        self.bit_count = 0
        self.bits_left = 0
        self.symbol = 0
        self.index = 0
        self.bit_command = END_OF_LIST
        self.status = BUSY

    def _take_bits(self, count):
        """Pull that many bits out of the stream, or say there are not enough yet.

        The count is remembered rather than restarted, so a request that runs out
        of stream half way through resumes on the next word with the bits it
        already has. Saying so is the only way the caller learns to send more.
        """
        if not self.bits_left:
            self.bits_left = count
            self.request_bits = 0

        while True:
            if not self.bit_count:
                self.status = BUSY
                return False
            self.request_bits = ((self.request_bits << 1) & 0xFFFF) | (
                1 if self.request_data & 0x8000 else 0
            )
            self.request_data = (self.request_data << 1) & 0xFFFF
            self.bit_count -= 1
            self.bits_left -= 1
            if not self.bits_left:
                return True

    def _take_one_bit(self):
        """One bit off the stream, which is always there when this is asked for.

        Every other request can run out half way and has to be resumed on the
        next word. This one cannot: the step that reaches it has already turned
        back once for want of a whole word, so a word of bits is in hand.
        """
        self.request_bits = 1 if self.request_data & 0x8000 else 0
        self.request_data = (self.request_data << 1) & 0xFFFF
        self.bit_count -= 1
        return self.request_bits

    def _decode_symbols(self):
        """The symbol table, written as differences from the symbol before it."""
        self.request_data = self.data
        self.bit_count += 16

        while True:
            if self.bit_command == END_OF_LIST:
                if not self._take_bits(2):
                    return
                self.bit_command = self.request_bits

            if not self._take_symbol():
                return

            self.bit_command = END_OF_LIST
            self.codes[self.index] = self.symbol
            self.index += 1
            self.codewords = (self.codewords - 1) & 0xFFFF
            if not self.codewords:
                break

        self.index = 0
        self.symbol = 0
        self.base_codes = 0
        self.step = self._decode_tree
        if self.bit_count:
            self._decode_tree()

    def _take_symbol(self):
        """One entry of the table, as an absolute value or a step from the last."""
        if self.bit_command == 0:
            if not self._take_bits(9):
                return False
            self.symbol = self.request_bits
        elif self.bit_command == 1:
            self.symbol = (self.symbol + 1) & 0xFFFF
        elif self.bit_command == 2:
            if not self._take_bits(1):
                return False
            self.symbol = (self.symbol + 2 + self.request_bits) & 0xFFFF
        else:
            if not self._take_bits(4):
                return False
            self.symbol = (self.symbol + 4 + self.request_bits) & 0xFFFF
        return True

    def _decode_tree(self):
        """How long each code is, and where in the symbol table its block starts."""
        if not self.bit_count:
            self.request_data = self.data
            self.bit_count += 16

        if not self.base_codes:
            self._take_bits(1)
            if self.request_bits:
                self.base_length = 3
                self.base_codes = 8
            else:
                self.base_length = 2
                self.base_codes = 4

        while self.base_codes:
            if not self._take_bits(3):
                return
            self.request_bits = (self.request_bits + 1) & 0xFFFF
            self.code_lengths[self.index] = self.request_bits & 0xFF
            self.code_offsets[self.index] = self.symbol
            self.index += 1
            self.symbol = (self.symbol + (1 << self.request_bits)) & 0xFFFF
            self.base_codes -= 1

        self.base_code = END_OF_LIST
        self.lz_code = 0
        self.step = self._decode_data
        if self.bit_count:
            self._decode_data()

    def _decode_data(self):
        """One output word per call, which is either a symbol or a run of them."""
        if not self.bit_count:
            if not self.status & MORE_INPUT:
                self.status = BUSY
                return
            self.request_data = self.data
            self.bit_count += 16

        if self.lz_code == 1:
            self.lz_length = LONG_RUN if self._take_one_bit() else SHORT_RUN
            self.lz_code += 1

        if self.lz_code == 2:
            if not self._take_bits(self.lz_length):
                return
            self.lz_code = 0
            self._one_word_out()
            self.status = READY
            self.data = self.request_bits
            return

        if self.base_code == END_OF_LIST:
            if not self._take_bits(self.base_length):
                return
            self.base_code = self.request_bits

        if not self._take_bits(self.code_lengths[self.base_code]):
            return

        at = self.code_offsets[self.base_code] + self.request_bits
        if at >= CODE_WORDS:
            raise TableOverrun(
                f"this stream asks for symbol {at} of a table that holds {CODE_WORDS}; "
                "what the chip does past the end is not something this model knows, "
                "and the reference reads whatever its own memory happens to hold there"
            )
        self.symbol = self.codes[at]
        self.base_code = END_OF_LIST

        if self.symbol & 0xFF00:
            self.symbol = (self.symbol + 0x7F02) & 0xFFFF
            self.lz_code += 1
        else:
            self._one_word_out()

        self.status = READY
        self.data = self.symbol

    def _one_word_out(self):
        self.outwords = (self.outwords - 1) & 0xFFFF
        if not self.outwords:
            self.step = self._restart

    def _set_origin(self):
        """Where the search starts, and the state it wipes to start it."""
        self.origin_x = low(self.data)
        self.origin_y = high(self.data)
        self._cell_of()

        self.terrain[self.data] = 0x00
        self.cost[self.data] = IMPASSABLE
        self.weight[self.data] = 0
        self.max_search_radius = 0
        self.max_path_radius = 0

    def _search_reachable(self):
        """Walk the ring of cells at each radius, asking the caller about each one.

        The chip does not hold the map. It names a cell, the caller answers with
        that cell's terrain and its cost, and the chip records both and names the
        next. Only when the rings run out does it work out what anything costs to
        reach, and it does that without being asked anything further.
        """
        self._take_radius_range(walked=self.max_search_radius)
        self.max_search_radius = max(self.max_search_radius, self.max_radius)
        self._start_ring()
        self._offer_cell(self._record_terrain, self._weigh_paths)

    def _take_radius_range(self, walked):
        self.min_radius = low(self.data)
        self.max_radius = high(self.data)
        if self.min_radius == 0:
            self.min_radius += 1
        if walked >= self.min_radius:
            self.min_radius = walked + 1

    def _start_ring(self):
        self.lcv_radius = self.min_radius
        self.lcv_steps = self.min_radius
        self.lcv_turns = TURNS
        self.turn = 0
        self._walk_out(self.min_radius)

    def _walk_out(self, distance):
        self.walk_x = self.origin_x
        self.walk_y = self.origin_y
        for _ in range(distance):
            self.walk_x, self.walk_y = self._moved(self.turn, self.walk_x, self.walk_y)

    def _moved(self, move, x, y):
        """One step from the mask ROM's move table, wrapped into the window."""
        self.add_high, self.add_low = move_of(move)
        offset_low = low(x)
        offset_high = low(y)
        if offset_low & 1:
            offset_high += self.add_low & 1
        self.add_low += offset_low
        self.add_high += offset_high
        self._wrap_into_window()
        return self.add_low, self.add_high

    def _stepped(self, move, x, y):
        """The same step from the table the chip carries in microcode rather than ROM."""
        self.add_high = HI_ADD_ODD[move & 7] if low(x) & 1 else HI_ADD_EVEN[move & 7]
        self.add_low = LO_ADD[move & 7]
        offset_low = low(x)
        offset_high = low(y)
        if offset_low & 1:
            offset_high += self.add_low & 1
        self.add_low += offset_low
        self.add_high += offset_high
        return signed16(self.add_low), signed16(self.add_high)

    def _offer_cell(self, answer_with, when_done):
        """Name the next cell of the ring, or say the rings have run out."""
        if self.lcv_steps == 0:
            self.lcv_radius += 1
            self.lcv_steps = self.lcv_radius
            self._walk_out(self.lcv_radius)

        if self.lcv_radius > self.max_radius:
            self.turn += 1
            self.lcv_turns -= 1
            self.lcv_radius = self.min_radius
            self.lcv_steps = self.min_radius
            self._walk_out(self.min_radius)

        if self.lcv_turns == 0:
            self.data = END_OF_LIST
            self.status = READY
            self.step = when_done
            return

        self.data = (low(self.walk_x) | (low(self.walk_y) << 8)) & 0xFFFF
        self._cell_of()
        self.cell = self.data
        self.status = READY
        self.step = answer_with

    def _record_terrain(self):
        self.status = RESET_STATUS
        self.step = self._record_terrain_value

    def _record_terrain_value(self):
        self.terrain[self.cell] = low(self.data)
        self.status = RESET_STATUS
        self.step = self._record_cost

    def _record_cost(self):
        self.cost[self.cell] = low(self.data)
        if self.lcv_radius == 1:
            self.weight[self.cell] = (
                IMPASSABLE if self.terrain[self.cell] & 1 else self.cost[self.cell]
            )
        else:
            self.weight[self.cell] = IMPASSABLE

        self.walk_x, self.walk_y = self._moved(self.turn + 2, self.walk_x, self.walk_y)
        self.lcv_steps -= 1
        self.status = READY
        self._offer_cell(self._record_terrain, self._weigh_paths)

    def _weigh_paths(self):
        """Grow the cheapest route outwards from the origin, one ring at a time."""
        self.walk_x = self.origin_x
        self.walk_y = self.origin_y
        self.lcv_radius = 1
        self._spread_cost()
        self.step = self._report_weights

    def _spread_cost(self):
        while self.lcv_radius < self.max_radius:
            self.walk_y -= 1
            self.lcv_turns = TURNS
            self.turn = 5
            while self.lcv_turns:
                self.lcv_steps = self.lcv_radius
                while self.lcv_steps:
                    self.walk_x, self.walk_y = self._stepped(self.turn, self.walk_x, self.walk_y)
                    self._maybe_relax()
                    self.lcv_steps -= 1
                self.turn -= 1
                if self.turn == 0:
                    self.turn = TURNS
                self.lcv_turns -= 1
            self.lcv_radius += 1

    def _inside(self, x, y):
        return 0 <= y < self.window_high and 0 <= x < self.window_low

    def _maybe_relax(self):
        if not self._inside(self.walk_x, self.walk_y):
            return
        self.data = (low(self.walk_x) | (low(self.walk_y) << 8)) & 0xFFFF
        self._cell_of()
        self.cell = self.data
        if self.cost[self.cell] < 0x80 and self.terrain[self.cell] < 0x40:
            self._relax_from_neighbours()

    def _relax_from_neighbours(self):
        """The cheapest neighbour, plus what this cell costs to enter."""
        best = IMPASSABLE
        for turns in range(TURNS, 0, -1):
            x, y = self._stepped(turns, self.walk_x, self.walk_y)
            self.data = (low(x) | (low(y) << 8)) & 0xFFFF
            self._cell_of()
            neighbour = self.data
            if not self._inside(x, y):
                continue
            if self.terrain[neighbour] < 0x80 or self.weight[neighbour] == 0:
                best = min(best, self.weight[neighbour])

        if best != IMPASSABLE:
            self.weight[self.cell] = (best + self.cost[self.cell]) & 0xFF

    def _report_weights(self):
        """Name each cell of each ring again, this time answering what it cost."""
        self._take_radius_range(walked=self.max_path_radius)
        self.max_path_radius = max(self.max_path_radius, self.max_radius)
        self._start_ring()
        self._offer_cell(self._answer_weight, self._restart)

    def _answer_weight(self):
        self.data = self.weight[self.cell]
        self.walk_x, self.walk_y = self._moved(self.turn + 2, self.walk_x, self.walk_y)
        self.lcv_steps -= 1
        self.status = RESET_STATUS
        self.step = self._offer_next_weight

    def _offer_next_weight(self):
        self._offer_cell(self._answer_weight, self._restart)

    def __repr__(self):
        return f"<DSP-3 status {self.status:#06x} data {self.data:#06x}>"
