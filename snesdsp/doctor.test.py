import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import doctor


class Complaint(Exception):
    pass


def a_finding(name="something", ok=True, detail="detail", advice=None):
    return doctor.Finding(name, ok, detail, advice)


class FindingTest(unittest.TestCase):
    def test_a_finding_says_what_was_checked(self):
        self.assertEqual(a_finding(name="the image").name, "the image")

    def test_and_whether_it_was_well(self):
        self.assertTrue(a_finding(ok=True).ok)
        self.assertFalse(a_finding(ok=False).ok)

    def test_a_healthy_finding_prints_with_a_mark_that_says_so(self):
        self.assertIn("ok", a_finding(ok=True).line)

    def test_and_an_unhealthy_one_prints_differently(self):
        self.assertNotIn("ok", a_finding(ok=False).line)

    def test_every_finding_carries_what_it_actually_saw(self):
        self.assertIn("53248 bytes", a_finding(detail="53248 bytes").line)

    def test_an_unhealthy_finding_says_what_to_do_about_it(self):
        found = a_finding(ok=False, advice="put a copy in firmware/")

        self.assertIn("put a copy in firmware/", found.report)

    def test_a_healthy_one_has_nothing_to_advise(self):
        self.assertEqual(
            a_finding(ok=True, advice="x").report,
            a_finding(ok=True).report.replace("detail", "detail"),
        )

    def test_a_finding_prints_as_itself(self):
        self.assertIn("something", repr(a_finding()))


class RunTest(unittest.TestCase):
    def test_the_examination_produces_findings(self):
        self.assertTrue(doctor.examine())

    def test_it_reports_the_python_it_is_running_on(self):
        names = [one.name for one in doctor.examine()]

        self.assertIn("python", names)

    def test_and_the_version_of_this_package(self):
        self.assertIn("snesdsp", [one.name for one in doctor.examine()])

    def test_and_whether_the_processor_is_checked_out(self):
        self.assertIn("processor", [one.name for one in doctor.examine()])

    def test_and_one_finding_per_part_it_covers(self):
        from snesdsp import models

        names = [one.name for one in doctor.examine()]

        for part in models.MODELS:
            self.assertIn(part, names, part)

    def test_and_whether_the_cartridge_exchanges_are_there(self):
        self.assertIn("exchanges", [one.name for one in doctor.examine()])

    def test_every_finding_carries_a_detail(self):
        for one in doctor.examine():
            self.assertTrue(one.detail, one.name)

    def test_a_part_with_no_image_is_reported_rather_than_hidden(self):
        found = doctor.examine(images={})

        parts = [one for one in found if one.name.startswith("dsp")]
        self.assertTrue(parts)
        self.assertFalse(any(one.ok for one in parts))

    def test_and_says_where_to_put_one(self):
        found = doctor.examine(images={})

        for one in found:
            if one.name.startswith("dsp") and not one.ok:
                self.assertIn("firmware", one.report)


class PresentImageTest(unittest.TestCase):
    """That a part which starts is examined on machines holding no microcode.

    Nobody who does not already own these parts can put one on a machine, so the
    build holds nothing and most machines that ever run this report hold nothing
    either. Leaving the started-part checks to whatever happens to be lying
    around means they run where it is convenient and nowhere else, and a check
    that only runs on one laptop is not a check.
    """

    def _made_up(self):
        import tempfile

        where = Path(tempfile.mkdtemp()) / "made-up.bin"
        where.write_bytes(b"nothing anybody owns")
        return where

    def _held(self, where):
        from snesdsp import models

        return dict.fromkeys(models.MODELS, ("identity", where))

    def _nameless(self, _part, _images):
        return SimpleNamespace(identity=None)

    def _named(self, _part, _images):
        return SimpleNamespace(identity=SimpleNamespace(part="dsp1b"))

    def test_a_part_that_starts_is_reported_as_running_something(self):
        found = doctor.examine(images=self._held(self._made_up()), build=self._nameless)

        parts = [one for one in found if one.name.startswith("dsp")]
        self.assertTrue(all(one.ok for one in parts))

    def test_and_says_which_image_it_is_running(self):
        found = doctor.examine(images=self._held(self._made_up()), build=self._named)

        for one in found:
            if one.name == "dsp1":
                self.assertIn("dsp1b", one.detail)

    def test_a_part_whose_chip_will_not_name_itself_falls_back_to_the_one_asked_for(self):
        found = doctor.examine(images=self._held(self._made_up()), build=self._nameless)

        for one in found:
            if one.name == "dsp1a":
                self.assertIn("dsp1", one.detail)

    def test_and_carries_the_digest_of_the_file_it_ran(self):
        import hashlib

        found = doctor.examine(images=self._held(self._made_up()), build=self._nameless)

        digest = hashlib.sha256(b"nothing anybody owns").hexdigest()
        self.assertIn(digest, " ".join(one.detail for one in found))

    def test_the_build_it_uses_by_default_is_the_one_that_runs_the_microcode(self):
        with self.assertRaises(doctor.silicon.NoFirmware):
            doctor._default_build("dsp1", {})


class ExplodingTest(unittest.TestCase):
    """That a check which itself goes wrong is shown rather than swallowed."""

    def test_a_check_that_raises_becomes_an_unhealthy_finding(self):
        def boom(_part, _images):
            raise Complaint("the part exploded")

        found = doctor.examine(images={"dsp1": object()}, build=boom)

        self.assertTrue(any(not one.ok for one in found))

    def test_and_the_report_carries_what_it_said(self):
        def boom(_part, _images):
            raise Complaint("the part exploded")

        found = doctor.examine(images={"dsp1": object()}, build=boom)

        self.assertIn("the part exploded", "\n".join(one.report for one in found))

    def test_and_names_the_kind_of_failure_it_was(self):
        def boom(_part, _images):
            raise Complaint("the part exploded")

        found = doctor.examine(images={"dsp1": object()}, build=boom)

        self.assertIn("Complaint", "\n".join(one.report for one in found))


class DigestTest(unittest.TestCase):
    """The line that settles which file somebody actually has."""

    def _catalogue(self, where):
        import sys as system

        system.path.insert(0, str(doctor.silicon.PROCESSOR))
        from upd7725 import firmware

        return {"dsp1": (firmware.Identity("dsp1", "upd7725", "MADE UP", 8, 8), where)}

    def test_a_part_whose_file_is_here_reports_its_digest(self):
        import hashlib
        import tempfile

        where = Path(tempfile.mkdtemp()) / "made-up.bin"
        where.write_bytes(b"nothing anybody owns")

        found = doctor._digest_of("dsp1", self._catalogue(where))

        self.assertIn(hashlib.sha256(b"nothing anybody owns").hexdigest(), found)

    def test_a_file_that_cannot_be_read_says_so_rather_than_going_quiet(self):
        found = doctor._digest_of("dsp1", self._catalogue(Path("/nowhere/at/all.bin")))

        self.assertIn("could not be read", found)

    def test_a_catalogue_with_nothing_in_it_reports_no_digest(self):
        self.assertEqual(doctor._digest_of("dsp1", {}), "")

    def test_and_a_catalogue_that_is_not_one_at_all_does_the_same(self):
        self.assertEqual(doctor._digest_of("dsp1", None), "")


class BeneathTest(unittest.TestCase):
    """That what this is built on is examined too, and under its own name.

    A package can be entirely well while the thing underneath it is missing,
    stale, or holding a different file. A doctor that looks only at its own
    project reports that everything is fine on exactly the machine where it is
    not, which is the failure this is here to prevent.
    """

    def test_the_processor_underneath_is_examined_as_well(self):
        names = [one.name for one in doctor.examine()]

        self.assertTrue(any(name.startswith(doctor.PROCESSOR_NAME) for name in names))

    def test_its_findings_are_named_after_the_project_they_came_from(self):
        def beneath():
            return [doctor.Finding("python", True, "some version")]

        for one in doctor.examine(beneath=beneath):
            if one.name.startswith(doctor.PROCESSOR_NAME):
                self.assertIn("/", one.name)

    def test_a_stale_project_underneath_is_reported_like_an_absent_one(self):
        def beneath():
            raise ImportError("cannot import name 'doctor'")

        found = doctor.examine(beneath=beneath)

        for one in found:
            if not one.ok and one.name == doctor.PROCESSOR_NAME:
                self.assertIn("older than this package expects", one.report)

    def test_an_unwell_finding_beneath_makes_this_run_unwell_too(self):
        def beneath():
            return [doctor.Finding("something", False, "not well", "go and look")]

        found = doctor.examine(beneath=beneath)

        self.assertTrue(any(not one.ok for one in found))

    def test_a_project_underneath_that_cannot_be_asked_says_so(self):
        def beneath():
            raise Complaint("no doctor down there")

        found = doctor.examine(beneath=beneath)

        text = "\n".join(one.report for one in found)
        self.assertIn("no doctor down there", text)
        self.assertIn("Complaint", text)

    def test_what_comes_back_keeps_the_detail_it_was_given(self):
        def beneath():
            return [doctor.Finding("image dsp1", True, "sha256 abc")]

        found = doctor.examine(beneath=beneath)

        self.assertIn("sha256 abc", "\n".join(one.detail for one in found))

    def test_nothing_underneath_at_all_is_not_a_failure(self):
        found = doctor.examine(beneath=list)

        self.assertTrue(all(one.ok for one in found if "/" in one.name))


class ReachTest(unittest.TestCase):
    """That the project underneath is made importable, and only once."""

    def test_a_path_without_it_gains_it(self):
        found = doctor._reach([])

        self.assertEqual(found, [str(doctor.silicon.PROCESSOR)])

    def test_a_path_that_already_has_it_is_left_alone(self):
        found = doctor._reach([str(doctor.silicon.PROCESSOR), "somewhere else"])

        self.assertEqual(len(found), 2)

    def test_by_default_it_works_on_the_real_one(self):
        self.assertIn(str(doctor.silicon.PROCESSOR), doctor._reach())


class CorpusTest(unittest.TestCase):
    """The three corpora this package is settled against, reported as what is here."""

    def _empty(self):
        import tempfile

        return Path(tempfile.mkdtemp())

    def _damaged(self, name):
        where = self._empty()
        (where / name).write_text("{ not json at all")
        return where

    def test_the_shapes_say_how_many_cartridges_each_part_was_read_from(self):
        for one in doctor.examine():
            if one.name == "exchanges":
                self.assertIn("cartridge", one.detail)

    def test_a_shapes_file_that_is_damaged_is_reported_as_damaged(self):
        found = doctor._exchanges(self._damaged("dsp1shapes.json"))

        self.assertIn("damaged", found.detail)

    def test_no_shapes_at_all_is_a_failure_that_says_where_they_go(self):
        found = doctor._exchanges(self._empty())

        self.assertFalse(found.ok)
        self.assertIn("conformance", found.advice)

    def test_the_recorded_answers_are_named_by_part(self):
        for one in doctor.examine():
            if one.name == "recorded answers":
                self.assertIn("dsp1", one.detail)

    def test_no_recorded_answers_says_how_to_take_them(self):
        found = doctor._answers(self._empty())

        self.assertFalse(found.ok)
        self.assertIn("--take", found.advice)

    def test_the_mask_divergence_says_how_wide_the_sweep_was(self):
        for one in doctor.examine():
            if one.name == "mask divergence":
                self.assertIn("commands", one.detail)

    def test_a_sweep_that_was_never_run_says_how_to_run_it(self):
        found = doctor._masks(self._empty())

        self.assertFalse(found.ok)
        self.assertIn("--sweep", found.advice)

    def test_a_swept_file_that_is_damaged_is_reported_as_damaged(self):
        found = doctor._masks(self._damaged("dsp1masks.json"))

        self.assertFalse(found.ok)
        self.assertIn("damaged", found.detail)

    def test_a_sweep_that_found_no_divergence_is_a_failure(self):
        import json

        where = self._empty()
        (where / "dsp1masks.json").write_text(json.dumps({"divergences": [], "swept": {}}))

        found = doctor._masks(where)

        self.assertFalse(found.ok)
        self.assertIn("one image under two names", found.advice)


class ReportTest(unittest.TestCase):
    def test_the_report_has_a_line_for_every_finding(self):
        found = doctor.examine()

        lines = doctor.report(found)

        self.assertGreaterEqual(len(lines), len(found))

    def test_it_opens_with_something_that_says_what_it_is(self):
        self.assertIn("snesdsp", doctor.report(doctor.examine())[0])

    def test_it_can_be_pasted_into_an_issue_as_it_stands(self):
        text = "\n".join(doctor.report(doctor.examine()))

        self.assertTrue(text.strip())
        self.assertNotIn("\t", text)

    def test_an_unhealthy_run_says_so_at_the_end(self):
        found = [a_finding(ok=False, advice="do the thing")]

        self.assertIn("1", " ".join(doctor.report(found)))

    def test_a_healthy_run_says_that_instead(self):
        found = [a_finding(ok=True)]

        self.assertIn("nothing to report", " ".join(doctor.report(found)))


class EntryTest(unittest.TestCase):
    def test_a_healthy_run_reports_success(self):
        self.assertEqual(
            doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=lambda _: None), 0
        )

    def test_an_unhealthy_one_reports_failure(self):
        self.assertEqual(
            doctor.main([], examine=lambda **_: [a_finding(ok=False)], say=lambda _: None), 1
        )

    def test_the_report_is_printed_rather_than_kept(self):
        said = []

        doctor.main([], examine=lambda **_: [a_finding(ok=True)], say=said.append)

        self.assertTrue(said)

    def test_a_real_run_says_something_about_this_machine(self):
        said = []

        doctor.main([], say=said.append)

        self.assertIn("snesdsp", " ".join(said))


if __name__ == "__main__":
    unittest.main()
