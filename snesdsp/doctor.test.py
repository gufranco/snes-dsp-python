import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402
from snesdsp import doctor  # noqa: E402

PROCESSOR = str(ROOT / "nec-upd7725-96050-python")

OWNED = b"nothing anybody owns"


class Complaint(Exception):
    pass


def a_finding(
    name: str = "something",
    ok: bool = True,
    detail: str = "detail",
    advice: str | None = None,
) -> doctor.Finding:
    return doctor.Finding(name, ok, detail, advice)


def advice_from(found: doctor.Finding) -> str:
    assert found.advice is not None, f"{found.name} failed without saying what to do"
    return found.advice


def a_file() -> Path:
    where = Path(tempfile.mkdtemp()) / "made-up.bin"
    where.write_bytes(OWNED)
    return where


def every_part_held(where: Path) -> dict[str, tuple[object, Path]]:
    return dict.fromkeys(snesdsp.MODELS, ("identity", where))


def nameless(_part: str, _images: object) -> doctor.Restartable:
    return SimpleNamespace(identity=None, reset=lambda: None)


def named(_part: str, _images: object) -> doctor.Restartable:
    return SimpleNamespace(identity=SimpleNamespace(part="dsp1b"), reset=lambda: None)


def will_not_reset(_part: str, _images: object) -> doctor.Restartable:
    def refuse() -> NoReturn:
        raise RuntimeError("the pin did nothing")

    return SimpleNamespace(identity=None, reset=refuse)


def explodes(_part: str, _images: object) -> NoReturn:
    raise Complaint("the part exploded")


def parts_in(found: list[doctor.Finding]) -> dict[str, doctor.Finding]:
    return {one.name: one for one in found if one.name in snesdsp.MODELS}


def a_folder(**files: str) -> Path:
    where = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (where / name).write_text(text)
    return where


class FindingTest(unittest.TestCase):
    def test_a_healthy_finding_prints_its_mark_its_name_and_what_it_saw(self) -> None:
        # Arrange
        found = a_finding(name="the image", detail="53248 bytes")

        # Act
        line = found.line

        # Assert
        self.assertEqual(line, "  ok    the image: 53248 bytes")

    def test_and_an_unhealthy_one_prints_a_different_mark(self) -> None:
        # Arrange
        found = a_finding(name="the image", ok=False, detail="missing")

        # Act
        line = found.line

        # Assert
        self.assertEqual(line, "     !  the image: missing")

    def test_an_unhealthy_finding_says_what_to_do_about_it(self) -> None:
        # Arrange
        found = a_finding(ok=False, advice="put a copy in firmware/")

        # Act
        report = found.report

        # Assert
        self.assertEqual(report, f"{found.line}\n         put a copy in firmware/")

    def test_a_healthy_one_has_nothing_to_advise(self) -> None:
        # Arrange
        found = a_finding(ok=True, advice="x")

        # Act
        report = found.report

        # Assert
        self.assertEqual(report, found.line)

    def test_a_finding_prints_as_itself(self) -> None:
        # Arrange
        found = a_finding(ok=False)

        # Act
        printed = repr(found)

        # Assert
        self.assertEqual(printed, "<Finding something not ok>")


class RunTest(unittest.TestCase):
    def test_the_examination_names_every_check_it_makes(self) -> None:
        # Arrange
        expected = {"python", "snesdsp", "processor", "timing", "exchanges", *snesdsp.MODELS}

        # Act
        names = {one.name for one in doctor.examine()}

        # Assert
        self.assertEqual(expected - names, set())

    def test_every_finding_carries_a_detail(self) -> None:
        # Arrange
        found = doctor.examine()

        # Act
        bare = [one.name for one in found if not one.detail]

        # Assert
        self.assertEqual(bare, [])

    def test_a_part_with_no_image_is_reported_with_where_to_put_one(self) -> None:
        # Arrange
        nothing: dict[str, tuple[object, Path]] = {}

        # Act
        found = parts_in(doctor.examine(images=nothing))

        # Assert
        self.assertEqual(sorted(found), sorted(snesdsp.MODELS))
        self.assertEqual([name for name, one in found.items() if one.ok], [])
        self.assertIn("SNES_DSP_FIRMWARE_DIR", found["dsp2"].report)

    def test_a_part_that_shares_an_image_is_reported_by_the_image_it_needs(self) -> None:
        # Arrange
        nothing: dict[str, tuple[object, Path]] = {}

        # Act
        found = parts_in(doctor.examine(images=nothing))

        # Assert
        self.assertEqual(found["dsp1a"].detail, "no image for dsp1")


class PresentImageTest(unittest.TestCase):
    def test_a_part_that_starts_is_reported_as_running_something(self) -> None:
        # Arrange
        held = every_part_held(a_file())

        # Act
        found = parts_in(doctor.examine(images=held, build=nameless))

        # Assert
        self.assertEqual([name for name, one in found.items() if not one.ok], [])

    def test_a_part_that_starts_and_will_not_reset_is_reported_as_broken(self) -> None:
        # Arrange
        held = every_part_held(a_file())

        # Act
        found = parts_in(doctor.examine(images=held, build=will_not_reset))

        # Assert
        self.assertEqual([name for name, one in found.items() if one.ok], [])
        self.assertIn("RuntimeError: the pin did nothing", found["dsp1"].detail)

    def test_and_says_which_image_it_is_running(self) -> None:
        # Arrange
        held = every_part_held(a_file())

        # Act
        found = parts_in(doctor.examine(images=held, build=named))

        # Assert
        self.assertTrue(found["dsp1"].detail.startswith("runs and resets the dsp1b image"))

    def test_a_part_that_will_not_name_itself_falls_back_to_the_image_asked_for(self) -> None:
        # Arrange
        held = every_part_held(a_file())

        # Act
        found = parts_in(doctor.examine(images=held, build=nameless))

        # Assert
        self.assertTrue(found["dsp1a"].detail.startswith("runs and resets the dsp1 image"))

    def test_and_carries_the_digest_of_the_file_it_ran(self) -> None:
        # Arrange
        held = every_part_held(a_file())

        # Act
        found = parts_in(doctor.examine(images=held, build=nameless))

        # Assert
        self.assertTrue(found["dsp2"].detail.endswith(hashlib.sha256(OWNED).hexdigest()))

    def test_the_build_it_uses_by_default_is_the_one_that_runs_the_microcode(self) -> None:
        # Arrange
        nothing: dict[str, tuple[object, Path]] = {}

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            doctor.default_build("dsp1", nothing)

        # Assert
        self.assertIn("dsp1", str(refused.exception))


class ExplodingTest(unittest.TestCase):
    def test_a_check_that_raises_becomes_an_unhealthy_finding_naming_the_failure(self) -> None:
        # Arrange
        held = {"dsp1": ("identity", Path("dsp1.bin"))}

        # Act
        found = parts_in(doctor.examine(images=held, build=explodes))

        # Assert
        self.assertFalse(found["dsp1"].ok)
        self.assertEqual(found["dsp1"].detail, "Complaint: the part exploded")


class DigestTest(unittest.TestCase):
    def test_a_part_whose_file_is_here_reports_its_digest(self) -> None:
        # Arrange
        held = {"dsp1": ("identity", a_file())}

        # Act
        found = doctor.digest_of("dsp1", held)

        # Assert
        self.assertEqual(found, f", sha256 {hashlib.sha256(OWNED).hexdigest()}")

    def test_a_file_that_cannot_be_read_says_so_rather_than_going_quiet(self) -> None:
        # Arrange
        held = {"dsp1": ("identity", Path(tempfile.mkdtemp()) / "absent.bin")}

        # Act
        found = doctor.digest_of("dsp1", held)

        # Assert
        self.assertTrue(found.startswith(", but its file could not be read: "))

    def test_a_catalogue_without_the_part_reports_no_digest(self) -> None:
        # Arrange
        held: dict[str, tuple[object, Path]] = {}

        # Act
        found = doctor.digest_of("dsp1", held)

        # Assert
        self.assertEqual(found, "")

    def test_and_a_catalogue_that_is_not_one_at_all_does_the_same(self) -> None:
        # Arrange
        held = None

        # Act
        found = doctor.digest_of("dsp1", held)

        # Assert
        self.assertEqual(found, "")


class BeneathTest(unittest.TestCase):
    def test_the_processor_underneath_is_examined_as_well(self) -> None:
        # Arrange
        prefix = f"{doctor.PROCESSOR_NAME} / "

        # Act
        names = [one.name for one in doctor.examine()]

        # Assert
        self.assertIn(f"{prefix}python", names)

    def test_its_findings_keep_their_verdict_and_detail_under_its_name(self) -> None:
        # Arrange
        def beneath() -> list[doctor.Finding]:
            return [doctor.Finding("image dsp1", False, "sha256 abc", "go and look")]

        # Act
        found = doctor.examine(beneath=beneath)[-1]

        # Assert
        self.assertEqual(
            (found.name, found.ok, found.detail, found.advice),
            (f"{doctor.PROCESSOR_NAME} / image dsp1", False, "sha256 abc", "go and look"),
        )

    def test_a_project_underneath_that_cannot_be_asked_says_so(self) -> None:
        # Arrange
        def beneath() -> list[doctor.Finding]:
            raise Complaint("no doctor down there")

        # Act
        found = doctor.examine(beneath=beneath)[-1]

        # Assert
        self.assertEqual((found.name, found.ok), (doctor.PROCESSOR_NAME, False))
        self.assertEqual(found.detail, "Complaint: no doctor down there")
        self.assertIn("older than this package expects", advice_from(found))

    def test_nothing_underneath_at_all_adds_no_finding(self) -> None:
        # Arrange
        prefix = doctor.PROCESSOR_NAME

        # Act
        found = doctor.examine(beneath=list)

        # Assert
        self.assertEqual([one.name for one in found if one.name.startswith(prefix)], [])


class ReachTest(unittest.TestCase):
    def test_a_path_without_the_processor_gains_it_first(self) -> None:
        # Arrange
        path = ["somewhere else"]

        # Act
        found = doctor.reach_processor(path)

        # Assert
        self.assertEqual(found, [PROCESSOR, "somewhere else"])

    def test_a_path_that_already_has_it_is_left_alone(self) -> None:
        # Arrange
        path = ["somewhere else", PROCESSOR]

        # Act
        found = doctor.reach_processor(path)

        # Assert
        self.assertEqual(found, ["somewhere else", PROCESSOR])

    def test_by_default_it_works_on_the_real_one(self) -> None:
        # Arrange
        expected = sys.path

        # Act
        found = doctor.reach_processor()

        # Assert
        self.assertIs(found, expected)
        self.assertIn(PROCESSOR, sys.path)


class CorpusTest(unittest.TestCase):
    def test_the_shapes_say_how_many_cartridges_each_part_was_read_from(self) -> None:
        # Arrange
        where = a_folder(
            **{
                "dsp2shapes.json": json.dumps({"readFrom": ["a", "b"]}),
                "dsp3shapes.json": json.dumps({"readFrom": "a"}),
            }
        )

        # Act
        found = doctor.check_exchanges(where)

        # Assert
        self.assertEqual(found.detail, "dsp2 from 2 cartridges, dsp3 from 1 cartridge")

    def test_a_shapes_file_that_is_damaged_is_reported_as_damaged(self) -> None:
        # Arrange
        where = a_folder(**{"dsp1shapes.json": "{ not json at all"})

        # Act
        found = doctor.check_exchanges(where)

        # Assert
        self.assertTrue(found.detail.startswith("dsp1 is damaged: "))

    def test_no_shapes_at_all_is_a_failure_that_says_where_they_go(self) -> None:
        # Arrange
        where = a_folder()

        # Act
        found = doctor.check_exchanges(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "none recorded"))
        self.assertIn("conformance/", advice_from(found))

    def test_the_recorded_answers_are_named_by_part(self) -> None:
        # Arrange
        where = a_folder(**{"dsp2answers.json": "{}", "dsp1answers.json": "{}"})

        # Act
        found = doctor.check_answers(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (True, "pinned for dsp1, dsp2"))

    def test_no_recorded_answers_says_how_to_take_them(self) -> None:
        # Arrange
        where = a_folder()

        # Act
        found = doctor.check_answers(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "none pinned"))
        self.assertIn("--take", advice_from(found))

    def test_the_mask_divergence_says_how_wide_the_sweep_was(self) -> None:
        # Arrange
        held = {"divergences": [1, 2], "swept": {"commands": 256, "argumentSets": 16}}
        where = a_folder(**{"dsp1masks.json": json.dumps(held)})

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertEqual(
            found.detail,
            "2 inputs where the DSP-1 and DSP-1B differ, found across 256 commands x 16 argument sets",
        )

    def test_a_sweep_that_was_never_run_says_how_to_run_it(self) -> None:
        # Arrange
        where = a_folder()

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertEqual((found.ok, found.detail), (False, "not swept"))
        self.assertIn("--sweep", advice_from(found))

    def test_a_swept_file_that_is_damaged_is_reported_as_damaged(self) -> None:
        # Arrange
        where = a_folder(**{"dsp1masks.json": "{ not json at all"})

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertFalse(found.ok)
        self.assertTrue(found.detail.startswith("is damaged: "))

    def test_a_sweep_that_found_no_divergence_is_a_failure(self) -> None:
        # Arrange
        where = a_folder(**{"dsp1masks.json": json.dumps({"divergences": [], "swept": {}})})

        # Act
        found = doctor.check_masks(where)

        # Assert
        self.assertFalse(found.ok)
        self.assertIn("one image under two names", advice_from(found))


class ReportTest(unittest.TestCase):
    def test_it_opens_with_the_package_and_ends_with_the_count(self) -> None:
        # Arrange
        found = [a_finding(ok=True), a_finding(ok=True)]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertTrue(lines[0].startswith(f"snesdsp {snesdsp.__version__} on "))
        self.assertEqual(lines[-1], "  2 checks, nothing to report")

    def test_it_can_be_pasted_into_an_issue_as_it_stands(self) -> None:
        # Arrange
        found = doctor.examine()

        # Act
        text = "\n".join(doctor.report(found))

        # Assert
        self.assertNotIn("\t", text)
        self.assertIn("  this package", text)

    def test_an_unhealthy_run_says_how_many_did_not_pass(self) -> None:
        # Arrange
        found = [a_finding(ok=False, advice="do the thing"), a_finding(ok=True)]

        # Act
        lines = doctor.report(found)

        # Assert
        self.assertEqual(lines[-1], "  1 of 2 checks did not pass")


class EntryTest(unittest.TestCase):
    def test_a_healthy_run_reports_success(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=said.append)

        # Assert
        self.assertEqual((code, said[-1]), (0, "  1 checks, nothing to report"))

    def test_an_unhealthy_one_reports_failure(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        code = doctor.main([], examine=lambda **_: [a_finding(ok=False)], say=said.append)

        # Assert
        self.assertEqual(code, 1)

    def test_a_real_run_says_something_about_this_machine(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        doctor.main([], say=said.append)

        # Assert
        self.assertIn("  the machine", said)

    def test_run_as_a_file_from_outside_the_repository_it_reports_rather_than_raises(
        self,
    ) -> None:
        # Arrange
        where = Path(doctor.__file__).resolve()

        # Act
        with tempfile.TemporaryDirectory() as elsewhere:
            finished = subprocess.run(
                [sys.executable, str(where)],
                capture_output=True,
                check=False,
                text=True,
                cwd=elsewhere,
                timeout=300,
            )

        # Assert
        self.assertNotIn("Traceback", finished.stderr)
        self.assertTrue(finished.stdout.startswith("snesdsp "), finished.stdout[:200])


if __name__ == "__main__":
    unittest.main()
