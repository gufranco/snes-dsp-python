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

## The images, and how to know you have the right one

Every image is checked by name **and** by content before it is used. `sha256`
decides; the other three are confirmed too rather than published and ignored,
because a file can be the right length under the right name and still be a bad
dump. The digests live in the processor's manifest, which is what does the
checking, and are printed here so you can confirm a copy before you supply it.

| Part | Revision | Bytes | crc32 | md5 |
|------|----------|------:|-------|-----|
| dsp1 | DSP-1 | 8192 | `27124599` | `4865ac61cd758b0f9383fe3d4d3b8694` |
| dsp1b | DSP-1B | 8192 | `588279b4` | `c8bfb983703a96e1c3d4683105112bc0` |
| dsp2 | DSP-2 | 8192 | `f0221c90` | `e500ec7f6005e78cb935eea5289c8cc4` |
| dsp3 | DSP-3 | 8192 | `e3b54e6a` | `c037185c8bbef6313226200dbe5fd07f` |
| dsp4 | DSP-4 | 8192 | `ca09e176` | `fe85065a7023551b0d84941a094435ba` |
| st010 | ST010 | 53248 | `8d136190` | `a1728c31df22b93e4bdae73718ba27a2` |
| st011 | ST011 | 53248 | `750c6012` | `2c56baddba22c6649c95c4c3b13adce3` |

| Part | sha1 | sha256 |
|------|------|--------|
| dsp1 | `4870e3b1636938c85347e20c56a81284fdfaf46e` | `5f2e5ed06b362be023b978b5978813ecb9a07c76592454b45c2a1ed17a0de349` |
| dsp1b | `1e0112ba3b130c770dab342f6cfe47ac53b278f0` | `4d42db0f36faef263d6b93f508e8c1c4ae8fc2605fd35e3390ecc02905cd420c` |
| dsp2 | `9179f61b8823b4e9a4130e1fb732424a2f6daa1a` | `5efbdf96ed0652790855225964f3e90e6a4d466cfa64df25b110933c6cf94ea1` |
| dsp3 | `0386ffaa041a5798c4568c5f5dc17fe66bb09d24` | `2e635f72e4d4681148bc35429421c9b946e4f407590e74e31b93b8987b63ba90` |
| dsp4 | `9a5392879cee4bac7907159f281d9e5681dfa66a` | `63ede17322541c191ed1fdf683872554a0a57306496afc43c59de7c01a6e764a` |
| st010 | `75a3e5b5564ea251060dd35bff3dc468d4429e77` | `55c697e864562445621cdf8a7bf6e84ae91361e393d382a3704e9aa55559041e` |
| st011 | `b2fdfa3edf08f76dbd30a0a4d3d0ef1e3d3f6905` | `651b82a1e26c4fa8dd549e91e7f923012ed2ca54c1d9fd858655ab30679c2f0e` |

Check a copy before supplying it:

```bash
shasum -a 256 dsp1.bin
```

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
