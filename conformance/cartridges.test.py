import hashlib
import json
import os
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conformance import cartridges

PRESENT = cartridges.present()


def a_cartridge(filler: int = 0xAB, size: int = 64) -> bytes:
    return bytes([filler]) * size


def a_catalogue(image: bytes, name: str = "made-up.sfc", **overrides: Any) -> dict[str, Any]:
    entry = {
        "name": name,
        "title": "MADE UP",
        "bytes": len(image),
        "chipset": "0x03",
        "crc32": f"{zlib.crc32(image) & 0xFFFFFFFF:08x}",
        "md5": hashlib.md5(image).hexdigest(),
        "sha1": hashlib.sha1(image).hexdigest(),
        "sha256": hashlib.sha256(image).hexdigest(),
    }
    entry.update(overrides)
    return {"cartridges": [entry]}


class ProvenanceTest(unittest.TestCase):
    """Where each published digest came from, which a digest alone does not say."""

    def test_every_cartridge_says_where_its_digests_came_from(self) -> None:
        for one in cartridges.manifest()["cartridges"]:
            self.assertIn("provenance", one, one["name"])

    def test_and_names_a_kind_the_manifest_explains(self) -> None:
        held = cartridges.manifest()
        kinds = held["provenance"]["kinds"]

        for one in held["cartridges"]:
            self.assertIn(one["provenance"]["kind"], kinds, one["name"])

    def test_the_weakest_kind_says_that_it_is_the_weakest(self) -> None:
        self.assertIn("weakest", cartridges.manifest()["provenance"]["kinds"]["localCopy"])

    def test_the_manifest_says_only_retail_dumps_are_listed(self) -> None:
        self.assertIn("retail", cartridges.manifest()["provenance"]["onlyRetailDumps"])


class ManifestTest(unittest.TestCase):
    def test_the_manifest_describes_cartridges(self) -> None:
        self.assertTrue(cartridges.manifest()["cartridges"])

    def test_every_cartridge_carries_all_four_digests(self) -> None:
        for entry in cartridges.manifest()["cartridges"]:
            for name in cartridges.DIGESTS:
                self.assertIn(name, entry, (entry["name"], name))

    def test_each_digest_is_the_length_that_kind_of_digest_has(self) -> None:
        for entry in cartridges.manifest()["cartridges"]:
            for name, width in cartridges.DIGEST_WIDTHS.items():
                self.assertEqual(len(entry[name]), width, (entry["name"], name))

    def test_every_cartridge_names_a_file_and_a_length(self) -> None:
        for entry in cartridges.manifest()["cartridges"]:
            self.assertTrue(entry["name"])
            self.assertGreater(entry["bytes"], 0)

    def test_no_two_cartridges_share_a_deciding_digest(self) -> None:
        seen = [entry["sha256"] for entry in cartridges.manifest()["cartridges"]]

        self.assertEqual(len(seen), len(set(seen)))

    def test_the_manifest_carries_no_run_of_bytes_longer_than_a_digest(self) -> None:
        longest = max(cartridges.DIGEST_WIDTHS.values())
        written = json.dumps(cartridges.manifest())
        runs = [
            piece
            for piece in written.replace('"', " ").split()
            if len(piece) > longest and all(letter in "0123456789abcdef" for letter in piece)
        ]

        self.assertEqual(runs, [])

    def test_a_manifest_can_be_read_from_somewhere_else(self) -> None:
        where = Path(tempfile.mkdtemp()) / "other.json"
        where.write_text(json.dumps({"cartridges": []}))

        self.assertEqual(cartridges.manifest(where)["cartridges"], [])


class IdentifyTest(unittest.TestCase):
    def test_a_cartridge_the_manifest_knows_is_named(self) -> None:
        image = a_cartridge()

        self.assertEqual(cartridges.identify(image, a_catalogue(image)).name, "made-up.sfc")

    def test_and_carries_the_title_its_header_declared(self) -> None:
        image = a_cartridge()

        self.assertEqual(cartridges.identify(image, a_catalogue(image)).title, "MADE UP")

    def test_a_cartridge_of_the_right_length_and_wrong_content_says_so(self) -> None:
        image = a_cartridge()
        catalogue = a_catalogue(image, sha256="0" * 64)

        with self.assertRaises(cartridges.Unrecognised) as raised:
            cartridges.identify(image, catalogue)

        self.assertIn("altered", str(raised.exception))

    def test_a_cartridge_of_no_length_the_manifest_knows_says_that(self) -> None:
        with self.assertRaises(cartridges.Unrecognised) as raised:
            cartridges.identify(b"\x00" * 7, {"cartridges": []})

        self.assertIn("7", str(raised.exception))

    def test_the_report_always_carries_the_digest_that_was_computed(self) -> None:
        with self.assertRaises(cartridges.Unrecognised) as raised:
            cartridges.identify(b"\x00" * 7, {"cartridges": []})

        self.assertIn(hashlib.sha256(b"\x00" * 7).hexdigest(), str(raised.exception))


class CrossCheckTest(unittest.TestCase):
    def test_a_cartridge_whose_other_digests_disagree_is_refused(self) -> None:
        image = a_cartridge()
        catalogue = a_catalogue(image, crc32="00000000")

        with self.assertRaises(cartridges.Corrupt) as raised:
            cartridges.identify(image, catalogue)

        self.assertIn("crc32", str(raised.exception))

    def test_every_kind_of_disagreement_is_caught(self) -> None:
        image = a_cartridge()
        for name, wrong in (("md5", "0" * 32), ("sha1", "0" * 40), ("crc32", "0" * 8)):
            with self.assertRaises(cartridges.Corrupt):
                cartridges.identify(image, a_catalogue(image, **{name: wrong}))

    def test_a_manifest_that_only_names_the_deciding_digest_is_still_accepted(self) -> None:
        image = a_cartridge()
        catalogue = a_catalogue(image)
        for name in ("crc32", "md5", "sha1"):
            del catalogue["cartridges"][0][name]

        self.assertEqual(cartridges.identify(image, catalogue).name, "made-up.sfc")


class PrintingTest(unittest.TestCase):
    def test_a_cartridge_prints_as_the_file_and_the_title_it_carries(self) -> None:
        printed = repr(cartridges.Identity("a.sfc", "A GAME", 512, "0x03", "0" * 64))

        self.assertIn("a.sfc", printed)
        self.assertIn("A GAME", printed)


class DirectoryTest(unittest.TestCase):
    def test_the_directory_comes_from_the_environment_when_one_is_named(self) -> None:
        self.assertEqual(cartridges.directory({"SNES_CARTRIDGE_DIR": "/x"}), Path("/x"))

    def test_and_from_the_repository_when_none_is(self) -> None:
        self.assertEqual(cartridges.directory({}).name, "cartridges")

    def test_the_project_this_sits_inside_is_looked_at_too(self) -> None:
        self.assertIn(cartridges.ALONGSIDE, cartridges.directories({}))

    def test_a_named_directory_comes_before_either_of_them(self) -> None:
        found = cartridges.directories({cartridges.DIRECTORY_VARIABLE: "/x"})

        self.assertEqual(found[0], Path("/x"))

    def test_the_first_place_that_is_actually_there_is_the_one_used(self) -> None:
        import tempfile

        here = Path(tempfile.mkdtemp())

        self.assertEqual(cartridges.directory({}, places=[Path("/nowhere"), here]), here)

    def test_and_when_no_place_is_there_the_folder_here_is_named(self) -> None:
        chosen = cartridges.directory({}, places=[Path("/nowhere"), Path("/nor/here")])

        self.assertEqual(chosen, cartridges.DEFAULT_DIRECTORY)

    def test_a_named_directory_wins_even_when_it_is_not_there(self) -> None:
        chosen = cartridges.directory({cartridges.DIRECTORY_VARIABLE: "/nowhere"})

        self.assertEqual(chosen, Path("/nowhere"))

    def test_a_directory_that_is_not_there_yields_nothing(self) -> None:
        self.assertEqual(list(cartridges.found(Path("/nowhere/at/all"))), [])

    def test_a_file_the_manifest_does_not_know_is_passed_over(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "nonsense.sfc").write_bytes(b"\x00" * 99)

        self.assertEqual(list(cartridges.found(where, {"cartridges": []})), [])


class OnDiskAnywhereTest(unittest.TestCase):
    """Walking a directory, using files this test makes and a catalogue to match.

    None of this needs a cartridge, which is the point. The reading of a real
    directory used to be outside the coverage gate because it ran one way on a
    machine holding games and another way on a machine holding none, and no build
    could exercise both. A directory the test fills and a catalogue the test
    writes exercises both, on any machine.
    """

    def _dir(self, *files: tuple[str, bytes]) -> Path:
        where = Path(tempfile.mkdtemp())
        for name, held in files:
            (where / name).write_bytes(held)
        return where

    def test_a_directory_of_one_known_cartridge_yields_it(self) -> None:
        image = a_cartridge()
        where = self._dir(("made-up.sfc", image))

        found = cartridges.present(where, a_catalogue(image))

        self.assertEqual(len(found), 1)

    def test_and_hands_back_the_file_it_came_from(self) -> None:
        image = a_cartridge()
        where = self._dir(("made-up.sfc", image))

        found = cartridges.present(where, a_catalogue(image))

        self.assertEqual(found[0][1].name, "made-up.sfc")

    def test_a_file_the_catalogue_does_not_know_is_passed_over(self) -> None:
        image = a_cartridge()
        where = self._dir(("made-up.sfc", image), ("stranger.sfc", a_cartridge(filler=0x01)))

        found = cartridges.present(where, a_catalogue(image))

        self.assertEqual(len(found), 1)

    def test_a_file_with_a_suffix_nobody_reads_is_passed_over(self) -> None:
        image = a_cartridge()
        where = self._dir(("made-up.txt", image))

        self.assertEqual(cartridges.present(where, a_catalogue(image)), ())

    def test_a_directory_that_is_not_there_yields_nothing(self) -> None:
        image = a_cartridge()

        found = cartridges.present(Path("/nowhere/at/all"), a_catalogue(image))

        self.assertEqual(found, ())

    def test_a_directory_holding_nothing_yields_nothing(self) -> None:
        image = a_cartridge()

        self.assertEqual(cartridges.present(self._dir(), a_catalogue(image)), ())

    def test_a_subdirectory_is_not_mistaken_for_a_cartridge(self) -> None:
        image = a_cartridge()
        where = self._dir(("made-up.sfc", image))
        (where / "inner.sfc").mkdir()

        self.assertEqual(len(cartridges.present(where, a_catalogue(image))), 1)


@unittest.skipUnless(PRESENT, cartridges.WHY_NOT)
class OnDiskTest(unittest.TestCase):  # pragma: no cover
    """The cartridges this machine actually holds, if it holds any.

    Outside the coverage gate. A test whose subject is a file nobody can
    distribute runs on one machine and not another, so counting it would make the
    number mean something different depending on who ran it. The directory walk
    itself is covered above, on any machine, by a directory the test fills.
    """

    def test_every_cartridge_on_disk_matches_all_four_of_its_digests(self) -> None:
        for identity, path in PRESENT:
            self.assertTrue(identity.sha256, path)

    def test_the_manifest_describes_every_cartridge_that_is_here(self) -> None:
        named = {entry["name"] for entry in cartridges.manifest()["cartridges"]}

        for _, path in PRESENT:
            self.assertIn(path.name, named)


class SharedDirectoryRuleTest(unittest.TestCase):
    """The rule every member of this family uses to find a file it does not carry.

    Byte-identical in all of them, so these check the behaviour that identity is
    supposed to guarantee rather than the text of one copy.
    """

    def test_the_project_above_is_looked_at_before_the_package_itself(self) -> None:
        """Vendored, the parent owns the library, which is what ALONGSIDE is for."""
        found = cartridges.directories({})

        self.assertLess(
            found.index(cartridges.ALONGSIDE), found.index(cartridges.DEFAULT_DIRECTORY)
        )

    def test_a_named_directory_is_looked_at_before_either(self) -> None:
        found = cartridges.directories({cartridges.DIRECTORY_VARIABLE: "/x"})

        self.assertEqual(found[0], Path("/x"))

    def test_more_than_one_can_be_named_at_once(self) -> None:
        found = cartridges.directories({cartridges.DIRECTORY_VARIABLE: f"/x{os.pathsep}/y"})

        self.assertEqual(found[:2], (Path("/x"), Path("/y")))

    def test_an_empty_entry_between_two_names_is_passed_over(self) -> None:
        found = cartridges.directories(
            {cartridges.DIRECTORY_VARIABLE: f"/x{os.pathsep}{os.pathsep}/y"}
        )

        self.assertEqual(found[:2], (Path("/x"), Path("/y")))

    def test_no_directory_appears_twice(self) -> None:
        found = cartridges.directories(
            {cartridges.DIRECTORY_VARIABLE: str(cartridges.DEFAULT_DIRECTORY)}
        )

        self.assertEqual(len(found), len(set(found)))


class DecidingDigestTest(unittest.TestCase):
    """That the manifest tells a reader which of its four digests decides.

    The reader already knows: `DECIDES` names it and nothing else is compared
    against. A person cross-checking a copy reads the manifest rather than the
    module, so the manifest has to say it too, and this is what keeps the two
    from drifting apart.
    """

    def held(self) -> str:
        return str(cartridges.manifest()["decides"])

    def test_the_manifest_names_the_digest_that_decides(self) -> None:
        self.assertIn(cartridges.DECIDES, self.held())

    def test_and_says_the_others_decide_nothing(self) -> None:
        self.assertIn("decides anything on its own", self.held())


if __name__ == "__main__":
    unittest.main()
