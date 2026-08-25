import hashlib
import json
import os
import sys
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from snesdsp import chip, errors, firmware, models  # noqa: F401

sys.path.append(str(chip.PROCESSOR))

from upd7725 import models as upd_models


def an_image(program_words: int = 2048, data_words: int = 1024, filler: int = 0xAB) -> bytes:
    return bytes([filler]) * (program_words * 3 + data_words * 2)


class ShippedManifestTest(unittest.TestCase):
    """That the manifest travels with the package rather than beside it.

    `identify` is the whole of the public reading interface and it cannot answer
    anything without the manifest. Kept at the top of the repository the file is
    not part of the distribution, so every install had an `identify` that raised
    FileNotFoundError instead of naming the image, and the readme example that
    calls it could not run for anybody who installed the package the way the
    readme says to.

    A test on the path is what catches that. Running `identify` from a checkout
    passes either way, because from a checkout the file is there.
    """

    def test_the_manifest_lives_inside_the_package(self) -> None:
        package = Path(firmware.__file__).resolve().parent

        self.assertEqual(Path(firmware.MANIFEST).resolve().parent, package)

    def test_and_the_packaging_declares_it_as_package_data(self) -> None:
        pyproject = (Path(firmware.__file__).resolve().parent.parent / "pyproject.toml").read_text()

        self.assertIn('snesdsp = ["artifacts.manifest.json"]', pyproject)

    def test_and_identify_needs_nothing_outside_the_package(self) -> None:
        package = Path(firmware.__file__).resolve().parent

        reached = Path(firmware.MANIFEST).resolve()

        self.assertTrue(reached.is_relative_to(package))
        self.assertTrue(reached.exists())


class ManifestTest(unittest.TestCase):
    def test_the_manifest_names_every_part_the_package_can_run(self) -> None:
        named = {entry["part"] for entry in firmware.manifest()["artifacts"]}

        self.assertIn("st011", named)
        self.assertIn("dsp1", named)

    def test_each_part_names_the_processor_it_runs_on(self) -> None:
        for entry in firmware.manifest()["artifacts"]:
            self.assertIn(entry["processor"], upd_models.MODELS, entry["part"])

    def test_each_part_names_a_size_its_two_stores_add_up_to(self) -> None:
        for entry in firmware.manifest()["artifacts"]:
            self.assertEqual(
                entry["programWords"] * 3 + entry["dataWords"] * 2, entry["bytes"], entry["part"]
            )

    def test_each_part_carries_at_least_one_digest(self) -> None:
        for entry in firmware.manifest()["artifacts"]:
            self.assertTrue(entry["accepted"], entry["part"])

    def test_every_accepted_image_carries_all_four_digests(self) -> None:
        for entry in firmware.manifest()["artifacts"]:
            for accepted in entry["accepted"]:
                for name in firmware.DIGESTS:
                    self.assertIn(name, accepted, (entry["part"], name))

    def test_each_digest_is_the_length_that_kind_of_digest_has(self) -> None:
        for entry in firmware.manifest()["artifacts"]:
            for accepted in entry["accepted"]:
                for name, width in firmware.DIGEST_WIDTHS.items():
                    self.assertEqual(len(accepted[name]), width, (entry["part"], name))

    def test_every_digest_is_a_whole_sha256(self) -> None:
        for entry in firmware.manifest()["artifacts"]:
            for accepted in entry["accepted"]:
                self.assertEqual(len(accepted["sha256"]), 64, entry["part"])

    def test_the_manifest_carries_no_run_of_bytes_longer_than_a_digest(self) -> None:
        def strings(held: object) -> Iterator[str]:
            if isinstance(held, str):
                yield held
            elif isinstance(held, dict):
                for value in held.values():
                    yield from strings(value)
            elif isinstance(held, list):
                for value in held:
                    yield from strings(value)

        runs = [
            text.strip()
            for text in strings(firmware.manifest())
            if len(text.strip()) > 64
            and all(letter in "0123456789abcdefABCDEF" for letter in text.strip())
        ]

        self.assertEqual(runs, [])

    def test_a_manifest_can_be_read_from_somewhere_else(self) -> None:
        where = Path(tempfile.mkdtemp()) / "other.json"
        where.write_text(json.dumps({"artifacts": []}))

        self.assertEqual(firmware.manifest(where)["artifacts"], [])


class IdentifyTest(unittest.TestCase):
    def test_an_image_the_manifest_knows_is_named(self) -> None:
        image = an_image()
        digest = hashlib.sha256(image).hexdigest()
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": digest}],
                }
            ]
        }

        self.assertEqual(firmware.identify(image, catalogue).part, "made-up")

    def test_and_the_revision_it_turned_out_to_be(self) -> None:
        image = an_image()
        digest = hashlib.sha256(image).hexdigest()
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": digest}],
                }
            ]
        }

        self.assertEqual(firmware.identify(image, catalogue).revision, "one")

    def test_an_image_of_the_right_size_and_the_wrong_content_says_so(self) -> None:
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": 8192,
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": "0" * 64}],
                }
            ]
        }

        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(an_image(), catalogue)

        self.assertIn("altered", str(raised.exception))

    def test_an_image_of_no_size_the_manifest_knows_says_that_instead(self) -> None:
        catalogue: dict[str, list[object]] = {"artifacts": []}

        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(b"\x00" * 7, catalogue)

        self.assertIn("7", str(raised.exception))

    def test_the_report_always_carries_the_digest_that_was_computed(self) -> None:
        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(b"\x00" * 7, {"artifacts": []})

        self.assertIn(hashlib.sha256(b"\x00" * 7).hexdigest(), str(raised.exception))


def a_catalogue(image: bytes, part: str = "made-up", **extra: object) -> dict[str, Any]:
    """A manifest holding one artifact, which is that image."""
    return {
        "artifacts": [
            {
                "part": part,
                "processor": "upd7725",
                "bytes": len(image),
                "programWords": 2048,
                "dataWords": 1024,
                "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                **extra,
            }
        ]
    }


class RepairTest(unittest.TestCase):
    """What can be done to a file the user already has.

    Nothing here is ever suggested on a hunch. A transform is applied, its result
    is hashed, and it is only named when the hash matches something published. So
    a repair that is offered is a repair that works, and a file nothing helps gets
    told that instead of being given a list of things to try.
    """

    def test_a_file_carrying_a_copier_header_is_told_to_strip_it(self) -> None:
        image = an_image()

        found = firmware.repairs(b"H" * 512 + image, a_catalogue(image)["artifacts"])

        self.assertEqual(len(found), 1)
        self.assertIn("512", found[0][0])

    def test_and_told_which_part_it_would_become(self) -> None:
        image = an_image()

        found = firmware.repairs(b"H" * 512 + image, a_catalogue(image, "dsp9")["artifacts"])

        self.assertEqual(found[0][1], "dsp9")

    def test_a_file_with_its_bytes_in_the_wrong_order_is_told_to_swap_them(self) -> None:
        image = bytes(range(256)) * 32
        swapped = bytes(image[at ^ 1] for at in range(len(image)))

        found = firmware.repairs(swapped, a_catalogue(image)["artifacts"])

        self.assertTrue(any("swap" in how for how, _part in found), found)

    def test_a_file_that_is_already_right_needs_nothing(self) -> None:
        image = an_image()

        self.assertEqual(firmware.repairs(image, a_catalogue(image)["artifacts"]), [])

    def test_a_file_nothing_helps_is_offered_nothing(self) -> None:
        image = an_image()

        found = firmware.repairs(b"Z" * len(image), a_catalogue(image)["artifacts"])

        self.assertEqual(found, [])

    def test_a_file_too_short_to_strip_is_offered_nothing(self) -> None:
        image = an_image()

        self.assertEqual(firmware.repairs(b"Z" * 8, a_catalogue(image)["artifacts"]), [])

    def test_the_diagnosis_names_the_repair_rather_than_the_length(self) -> None:
        image = an_image()

        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(b"H" * 512 + image, a_catalogue(image))

        self.assertIn("512", str(raised.exception))
        self.assertIn("checked rather than guessed", str(raised.exception))


class BadDumpTest(unittest.TestCase):
    """A damaged copy, told apart from a copy of the wrong thing.

    Two different problems: a wrong file means go and find the right one, and a
    damaged file means that copy is broken. The manifest carries no bad dumps
    today because nobody has sent one, so what is pinned here is the mechanism
    that will name one when somebody does.
    """

    def test_a_declared_bad_dump_is_named_as_damaged(self) -> None:
        image = an_image()
        broken = an_image(filler=0x00)
        catalogue = a_catalogue(
            image,
            badDumps=[{"sha256": hashlib.sha256(broken).hexdigest(), "why": "truncated"}],
        )

        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(broken, catalogue)

        self.assertIn("known bad dump", str(raised.exception))

    def test_and_names_the_part_it_is_a_bad_dump_of(self) -> None:
        image = an_image()
        broken = an_image(filler=0x00)
        catalogue = a_catalogue(
            image,
            part="dsp9",
            badDumps=[{"sha256": hashlib.sha256(broken).hexdigest()}],
        )

        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(broken, catalogue)

        self.assertIn("dsp9", str(raised.exception))

    def test_an_undeclared_file_is_not_called_a_bad_dump(self) -> None:
        image = an_image()

        with self.assertRaises(errors.Unrecognised) as raised:
            firmware.identify(an_image(filler=0x00), a_catalogue(image))

        self.assertNotIn("known bad dump", str(raised.exception))

    def test_the_manifest_that_ships_declares_the_list_for_every_part(self) -> None:
        for artifact in firmware.manifest()["artifacts"]:
            self.assertIn("badDumps", artifact, artifact["part"])


class ProvenanceTest(unittest.TestCase):
    """Where each published digest came from, which a digest alone does not say."""

    def test_every_accepted_revision_says_where_its_digest_came_from(self) -> None:
        for artifact in firmware.manifest()["artifacts"]:
            for accepted in artifact["accepted"]:
                self.assertIn("provenance", accepted, artifact["part"])

    def test_and_names_a_kind_the_manifest_explains(self) -> None:
        held = firmware.manifest()
        kinds = held["provenance"]["kinds"]

        for artifact in held["artifacts"]:
            for accepted in artifact["accepted"]:
                self.assertIn(accepted["provenance"]["kind"], kinds, artifact["part"])

    def test_and_the_date_it_was_checked_on(self) -> None:
        for artifact in firmware.manifest()["artifacts"]:
            for accepted in artifact["accepted"]:
                self.assertIn("verifiedOn", accepted["provenance"], artifact["part"])

    def test_the_weakest_kind_says_that_it_is_the_weakest(self) -> None:
        kinds = firmware.manifest()["provenance"]["kinds"]

        self.assertIn("weakest", kinds["localCopy"])


class CrossCheckTest(unittest.TestCase):
    def test_an_image_whose_other_digests_disagree_is_refused(self) -> None:
        image = an_image()
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [
                        {
                            "revision": "one",
                            "sha256": hashlib.sha256(image).hexdigest(),
                            "crc32": "00000000",
                            "md5": "0" * 32,
                            "sha1": "0" * 40,
                        }
                    ],
                }
            ]
        }

        with self.assertRaises(errors.Corrupt) as raised:
            firmware.identify(image, catalogue)

        self.assertIn("crc32", str(raised.exception))

    def test_a_cross_check_that_passes_every_digest_accepts_the_image(self) -> None:
        image = an_image()
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", **firmware.digests_of(image)}],
                }
            ]
        }

        self.assertEqual(firmware.identify(image, catalogue).revision, "one")

    def test_every_kind_of_disagreement_is_caught(self) -> None:
        image = an_image()
        for name, wrong in (("crc32", "0" * 8), ("md5", "0" * 32), ("sha1", "0" * 40)):
            catalogue = {
                "artifacts": [
                    {
                        "part": "made-up",
                        "processor": "upd7725",
                        "bytes": len(image),
                        "programWords": 2048,
                        "dataWords": 1024,
                        "accepted": [
                            {"revision": "one", **firmware.digests_of(image), name: wrong}
                        ],
                    }
                ]
            }

            with self.assertRaises(errors.Corrupt):
                firmware.identify(image, catalogue)

    def test_an_image_the_manifest_only_partly_describes_is_still_accepted(self) -> None:
        image = an_image()
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                }
            ]
        }

        self.assertEqual(firmware.identify(image, catalogue).part, "made-up")


class IdentityTest(unittest.TestCase):
    def test_an_identity_prints_as_the_part_it_names(self) -> None:
        found = firmware.Identity("dsp1", "upd7725", "DSP-1", 2048, 1024)

        self.assertIn("dsp1", repr(found))
        self.assertIn("DSP-1", repr(found))


class LoadTest(unittest.TestCase):
    def test_a_loaded_image_fills_the_program_store(self) -> None:
        chip = upd_models.describe("upd7725").build(fill=0)
        image = bytes(range(256)) * 32 + bytes(2048)

        firmware.load(chip, image[: 2048 * 3] + image[: 1024 * 2])

        self.assertEqual(chip.stores.program[0], 0x000102)

    def test_and_the_table_after_it(self) -> None:
        chip = upd_models.describe("upd7725").build(fill=0)
        program = bytes(2048 * 3)
        table = bytes([0xAA, 0xBB]) * 1024

        firmware.load(chip, program + table)

        self.assertEqual(chip.stores.table[0], 0xAABB)

    def test_an_image_that_does_not_match_the_processor_is_refused(self) -> None:
        chip = upd_models.describe("upd7725").build(fill=0)

        with self.assertRaises(errors.WrongShape):
            firmware.load(chip, bytes(53248))


class FoundTest(unittest.TestCase):
    def test_a_directory_with_nothing_in_it_yields_nothing(self) -> None:
        self.assertEqual(list(firmware.found(Path(tempfile.mkdtemp()))), [])

    def test_a_directory_that_is_not_there_yields_nothing_either(self) -> None:
        self.assertEqual(list(firmware.found(Path("/nowhere/at/all"))), [])

    def test_a_file_the_manifest_knows_is_yielded_with_its_name(self) -> None:
        where = Path(tempfile.mkdtemp())
        image = an_image()
        (where / "made-up.bin").write_bytes(image)
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                }
            ]
        }

        found = list(firmware.found(where, catalogue))

        self.assertEqual(found[0][0].part, "made-up")

    def test_a_file_that_is_not_an_image_at_all_is_passed_over(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "README.md").write_text("notes, not an image")
        (where / "notes.txt").write_text("also not one")

        self.assertEqual(list(firmware.found(where, {"artifacts": []})), [])

    def test_a_file_the_manifest_does_not_know_is_passed_over(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "nonsense.bin").write_bytes(b"\x00" * 99)

        self.assertEqual(list(firmware.found(where, {"artifacts": []})), [])

    def test_the_directory_comes_from_the_environment_when_one_is_named(self) -> None:
        self.assertEqual(firmware.directory({"UPD7725_FIRMWARE_DIR": "/x"}), Path("/x"))

    def test_and_from_the_repository_when_none_is(self) -> None:
        self.assertEqual(firmware.directory({}).name, "firmware")


class SearchPathTest(unittest.TestCase):
    def test_the_package_always_looks_in_its_own_directory(self) -> None:
        self.assertIn(firmware.DEFAULT_DIRECTORY, firmware.directories({}))

    def test_and_in_the_project_that_carries_it_as_a_submodule(self) -> None:
        self.assertIn(firmware.ALONGSIDE, firmware.directories({}))

    def test_the_project_above_is_looked_at_before_the_package_itself(self) -> None:
        found = firmware.directories({})

        self.assertLess(found.index(firmware.ALONGSIDE), found.index(firmware.DEFAULT_DIRECTORY))

    def test_a_named_directory_is_looked_at_before_either(self) -> None:
        found = firmware.directories({"UPD7725_FIRMWARE_DIR": "/x"})

        self.assertEqual(found[0], Path("/x"))

    def test_more_than_one_can_be_named_at_once(self) -> None:
        found = firmware.directories({"UPD7725_FIRMWARE_DIR": f"/x{os.pathsep}/y"})

        self.assertEqual(found[:2], (Path("/x"), Path("/y")))

    def test_an_empty_entry_between_two_names_is_passed_over(self) -> None:
        found = firmware.directories({"UPD7725_FIRMWARE_DIR": f"/x{os.pathsep}{os.pathsep}/y"})

        self.assertEqual(found[:2], (Path("/x"), Path("/y")))

    def test_no_directory_appears_twice(self) -> None:
        found = firmware.directories({"UPD7725_FIRMWARE_DIR": str(firmware.DEFAULT_DIRECTORY)})

        self.assertEqual(len(found), len(set(found)))

    def test_searching_finds_an_image_in_any_of_them(self) -> None:
        first = Path(tempfile.mkdtemp())
        second = Path(tempfile.mkdtemp())
        image = an_image()
        (second / "made-up.bin").write_bytes(image)
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                }
            ]
        }

        found = list(firmware.search((first, second), catalogue))

        self.assertEqual(found[0][0].part, "made-up")

    def test_the_first_directory_holding_a_part_is_the_one_that_answers(self) -> None:
        first = Path(tempfile.mkdtemp())
        second = Path(tempfile.mkdtemp())
        image = an_image()
        (first / "from-first.bin").write_bytes(image)
        (second / "from-second.bin").write_bytes(image)
        catalogue = {
            "artifacts": [
                {
                    "part": "made-up",
                    "processor": "upd7725",
                    "bytes": len(image),
                    "programWords": 2048,
                    "dataWords": 1024,
                    "accepted": [{"revision": "one", "sha256": hashlib.sha256(image).hexdigest()}],
                }
            ]
        }

        found = list(firmware.search((first, second), catalogue))

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][1].name, "from-first.bin")


if __name__ == "__main__":
    unittest.main()
