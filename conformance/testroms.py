from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import snesdsp
from conformance import answers
from snesdsp import chip, firmware

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Sequence

HERE = Path(__file__).resolve().parent

RECORD = HERE / "testroms.json"

MEASURED = HERE / "testroms_measured.json"

RECORDING = "--record"

RUN = "run"

Measures = dict[str, dict[str, Any]]


def _default_check(part: str, identity: Any, path: Path) -> Any:  # pragma: no cover
    held = chip.available({identity.part: (identity, path)})
    run = firmware.canonical(path.read_bytes(), identity)
    corpus = answers.load(part)
    assert corpus is not None, f"no answers are recorded for {part}"
    return answers.check(
        corpus,
        lambda one: snesdsp.Chip(one, images=held),
        digest=lambda _one: hashlib.sha256(run).hexdigest(),
    )


def parts_running(image: str) -> list[str]:
    return sorted(name for name, model in snesdsp.MODELS.items() if model.image == image)


def measure(image: bytes, identity: Any, path: Path, check: Any) -> dict[str, Any]:
    found = {part: check(part, identity, path) for part in parts_running(identity.part)}
    return {
        "part": identity.part,
        "order": identity.order,
        "canonicalSha256": hashlib.sha256(firmware.canonical(image, identity)).hexdigest(),
        "checked": {part: one.checked for part, one in found.items()},
        "disagreements": sum(len(one.disagreements) for one in found.values()),
    }


def runnable(record: Path) -> dict[str, dict[str, Any]]:
    held = json.loads(record.read_text())["cartridges"]
    return {one["sha256"]: one for one in held if one["outcome"] == RUN}


def measured_in(folder: Path, record: Path, identify: Any, check: Any) -> Measures:
    listed = runnable(record)
    found: Measures = {}
    if not folder.is_dir():
        return found
    for path in sorted(one for one in folder.iterdir() if one.is_file()):
        image = path.read_bytes()
        entry = listed.get(hashlib.sha256(image).hexdigest())
        if entry is not None:
            found[entry["id"]] = measure(image, identify(image), path, check)
    return found


def main(
    argv: Sequence[str],
    say: Callable[[str], object] = print,
    record: Path = RECORD,
    measured: Path = MEASURED,
    identify: Any = snesdsp.identify,
    check: Any = _default_check,
) -> int:
    told = [one for one in argv if one != RECORDING]
    total = len(runnable(record))
    if not told:
        say(f"  0 of {total} runnable images run: no folder was named")
        return 2
    found = measured_in(Path(told[0]), record, identify, check)
    say(f"  {len(found)} of {total} runnable images run")
    if not found:
        return 2
    if RECORDING in argv:
        measured.write_text(json.dumps(found, indent=2, sort_keys=True) + "\n")
        return 0
    held = json.loads(measured.read_text())
    moved = [name for name, one in sorted(found.items()) if held.get(name) != one]
    for name in moved:
        say(f"  ! {name}: measured {found[name]}, recorded {held.get(name)}")
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
