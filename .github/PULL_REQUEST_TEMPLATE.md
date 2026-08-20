## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text
```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] `python3 -m snesdsp.doctor` reports nothing on this machine
- [ ] Where an image is present, `conformance/against_cartridges.py` was run for every part it touches

## If this changes what a part answers

The microcode is the authority. A change to what a part gives back has to say
which part, which command, and what was measured against, because a value that
came from somewhere other than the part is a value nobody can act on.

## What it does not carry

- [ ] No microcode, no cartridge, and no bytes from either
- [ ] Nothing that says where to obtain them
