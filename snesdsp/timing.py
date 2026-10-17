from . import models

NTSC_COLOURBURST = 3579545.4545454545

MASTER_CLOCK = round(NTSC_COLOURBURST * 6)

SLOW_ACCESS = 8

DSP_CLOCK = 7_600_000


def clock_of(part: str) -> int:
    models.lookup(part)
    return DSP_CLOCK


LONG_STORE_CYCLES = 5


def steps_for(master_clocks: int, clock: int = DSP_CLOCK, master: int = MASTER_CLOCK) -> int:
    return master_clocks * clock // master


GAP = steps_for(LONG_STORE_CYCLES * SLOW_ACCESS)
