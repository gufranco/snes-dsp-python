# Firmware goes here

Nothing in this directory is committed, and nothing in it ships.

The models in this repository are behavioural: each command is written down as a
function of its arguments, and they are settled against another implementation of
those same commands. That is good evidence and it has a ceiling, because two
readings of a part can be wrong together.

A copy of the microcode removes the ceiling. The `processor` submodule models the
processor these parts are built on, settled instruction by instruction on its own,
and it will run the program the cartridge actually carries. Feed both sides the
same bytes and either they agree or one of them is wrong about the part.

## What belongs here

| Part | Bytes | Names it is usually saved under |
|:-----|------:|:--------------------------------|
| DSP-1 | 8,192 | `dsp1.rom`, `dsp1.bin` |
| DSP-1B | 8,192 | `dsp1b.rom`, `dsp1b.bin` |
| DSP-2 | 8,192 | `dsp2.rom`, `dsp2.bin` |
| DSP-3 | 8,192 | `dsp3.rom`, `dsp3.bin` |
| DSP-4 | 8,192 | `dsp4.rom`, `dsp4.bin` |

Every file is identified by digest before it is run, against the manifest in the
`processor` submodule. A file that does not match is diagnosed rather than
refused.

## How to use it

```bash
git submodule update --init
python3 conformance/against_firmware.py
```

With nothing here, every check that needs an image reports as skipped rather than
as passed.
