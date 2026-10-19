from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from snesdsp.errors import NeverReady, NoFirmware, NotDecoded

from . import firmware

if TYPE_CHECKING:  # pragma: no cover
    from types import ModuleType

from . import timing

ROOT = Path(__file__).resolve().parent.parent

PROCESSOR = ROOT / "nec-upd7725-96050-python"

BOOT_STEPS = 20000

GAP = timing.GAP

BANK_MIRROR = 0x7F

MODE_20 = (range(0x30, 0x40), 0x8000, 0xFFFF, 14)

MODE_21 = (range(0x00, 0x10), 0x6000, 0x7FFF, 12)

DECODED = (MODE_20, MODE_21)

SETTLE_LIMIT = 400000

WHY_NOT_PROCESSOR = (
    "the processor is not here: this backend runs the part's own microcode on"
    " the NEC uPD7725, which sits beside this package as a submodule, so it has"
    " to be checked out with git submodule update --init --recursive"
)

WHY_NOT_FIRMWARE = (
    "no firmware image was found: this backend runs the part's own microcode, and"
    " that microcode belongs to whoever made the part, so a copy you already own"
    " goes in the firmware directory or wherever SNES_DSP_FIRMWARE_DIR points"
)


SHARES_IMAGE = {"dsp1a": "dsp1"}


def _processor() -> tuple[ModuleType, ModuleType] | None:
    if str(PROCESSOR) not in sys.path:
        sys.path.append(str(PROCESSOR))
    try:
        from upd7725 import models, ports
    except ImportError:
        return None
    return models, ports


def selects_status(address: int) -> bool:
    bank = address >> 16 & BANK_MIRROR
    page = address & 0xFFFF
    for banks, low, high, line in DECODED:
        if bank in banks and low <= page <= high:
            return bool(page >> line & 1)
    raise NotDecoded(
        f"{address:06X} is in neither window the board decodes for the part: banks"
        " 30-3F and B0-BF at 8000-FFFF under Mode 20, or banks 00-0F and 80-8F at"
        " 6000-7FFF under Mode 21"
    )


def available(held: dict[str, tuple[Any, Path]] | None = None) -> dict[str, tuple[Any, Path]]:
    if held is None:
        found = _processor()
        if found is None:
            return {}
        held = {identity.part: (identity, path) for identity, path in firmware.search()}
    held = dict(held)
    for part, shared in SHARES_IMAGE.items():
        if shared in held:
            held.setdefault(part, held[shared])
    return held


def why_not(held: dict[str, tuple[Any, Path]] | None = None) -> str | None:
    if _processor() is None:
        return WHY_NOT_PROCESSOR
    if not available(held):
        return WHY_NOT_FIRMWARE
    return None


class Chip:
    __slots__ = (
        "_boot",
        "_fill",
        "_image",
        "_models",
        "_ports",
        "bus_cycle",
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

        models, ports = found

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
        self.bus_cycle = timing.BUS_CYCLE

        self._ports = ports
        self._models = models
        self._fill = fill
        self._image = image
        self._boot = boot
        self._start()

    def _start(self) -> None:
        identity = self.identity
        self.core = self._models.lookup(identity.processor).build(fill=self._fill)
        firmware.load(self.core, self._image, identity)
        self.core.reset()
        self.console = self._ports.Host(self.core)
        self.step(self._boot)

    def reset(self) -> Chip:
        self._start()
        return self

    @property
    def clock(self) -> int:
        return timing.DSP_CLOCK

    def step(self, count: int | None = None) -> None:
        for _ in range(self.gap if count is None else count):
            self.core.step()

    def elapsed(self, master_clocks: int) -> Chip:
        self.step(timing.steps_for(master_clocks, self.clock))
        return self

    def read_bus(self, address: int) -> int:
        if selects_status(address):
            return self.read_status()
        return self.read()

    def write_bus(self, address: int, value: int) -> Chip:
        if selects_status(address):
            self.console.write(self._ports.STATUS, value & 0xFF)
            self.step()
            return self
        self.write(value)
        return self

    @property
    def asking(self) -> bool:
        return bool(self.core.registers.sr.rqm)

    @property
    def pending_output(self) -> int:
        return 1 if self.asking else 0

    def waited(self) -> bool:
        for _ in range(self.patience):
            if self.asking:
                return True
            self.core.step()
        return False

    def settle(self) -> None:
        if not self.waited():
            raise NeverReady(
                f"{self.part} did not ask for attention within {self.patience} instructions"
            )

    def write(self, value: int) -> None:
        self.console.write(self._ports.DATA, value & 0xFF)
        self.step()

    def read_status(self) -> int:
        found: int = self.console.read(self._ports.STATUS)
        return found

    def read(self) -> int:
        value: int = self.console.read(self._ports.DATA)
        self.step()
        return value

    def write_word(self, word: int) -> None:
        self.console.write(self._ports.DATA, word & 0xFF)
        self.step(self.bus_cycle)
        self.write(word >> 8)

    def read_word(self) -> int:
        low: int = self.console.read(self._ports.DATA)
        self.step(self.bus_cycle)
        return low | self.read() << 8

    @override
    def __repr__(self) -> str:
        return f"<Chip {self.part} on {self.processor}>"
