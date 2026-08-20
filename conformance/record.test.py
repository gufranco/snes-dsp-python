import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import record


class Complaint(Exception):
    pass


def an_identity(
    name: str = "Made Up (World).sfc", part: str = "dsp1", title: str = "MADE UP"
) -> dict[str, Any]:
    return {
        "name": name,
        "title": title,
        "part": part,
        "why": "made up",
        "bytes": 524288,
        "crc32": "aaaaaaaa",
        "md5": "b" * 32,
        "sha1": "c" * 40,
        "sha256": "d" * 64,
    }


def a_manifest(*entries: Any) -> dict[str, Any]:
    return {"note": "made up", "canonical": {}, "cartridges": list(entries)}


class GroupingTest(unittest.TestCase):
    """Which shapes belong to which part, and where each one came from."""

    def test_a_cartridge_contributes_its_shapes_to_its_own_part(self) -> None:
        found = record.gather(
            a_manifest(an_identity(part="dsp2")),
            lambda _name: ("lorom", {"write1 read1": 3}),
        )

        self.assertEqual(sorted(found), ["dsp2"])
        self.assertEqual(found["dsp2"].counted["write1 read1"], 3)

    def test_two_cartridges_for_one_part_have_their_counts_added(self) -> None:
        found = record.gather(
            a_manifest(an_identity(name="one.sfc"), an_identity(name="two.sfc")),
            lambda _name: ("hirom", {"write1 read1": 2}),
        )

        self.assertEqual(found["dsp1"].counted["write1 read1"], 4)

    def test_and_the_shape_records_how_many_cartridges_used_it(self) -> None:
        found = record.gather(
            a_manifest(an_identity(name="one.sfc"), an_identity(name="two.sfc")),
            lambda _name: ("hirom", {"write1 read1": 2}),
        )

        self.assertEqual(found["dsp1"].cartridges["write1 read1"], 2)

    def test_a_shape_only_one_cartridge_uses_says_so(self) -> None:
        def reading(name: str) -> Any:
            return ("hirom", {"write1 read1": 1} if name == "one.sfc" else {"read1": 1})

        found = record.gather(
            a_manifest(an_identity(name="one.sfc"), an_identity(name="two.sfc")), reading
        )

        self.assertEqual(found["dsp1"].cartridges["write1 read1"], 1)

    def test_every_cartridge_read_is_named_with_what_it_contributed(self) -> None:
        found = record.gather(
            a_manifest(an_identity(name="one.sfc")), lambda _name: ("hirom", {"read1": 1})
        )

        self.assertEqual(found["dsp1"].sources[0]["name"], "one.sfc")
        self.assertEqual(found["dsp1"].sources[0]["shapes"], 1)

    def test_and_carries_the_digests_that_identify_it(self) -> None:
        found = record.gather(
            a_manifest(an_identity(name="one.sfc")), lambda _name: ("hirom", {"read1": 1})
        )

        self.assertEqual(found["dsp1"].sources[0]["sha256"], "d" * 64)

    def test_a_cartridge_that_is_not_here_is_passed_over(self) -> None:
        def absent(_name: str) -> None:
            return None

        self.assertEqual(record.gather(a_manifest(an_identity()), absent), {})

    def test_a_cartridge_that_says_nothing_to_its_part_is_a_finding(self) -> None:
        found = record.gather(
            a_manifest(an_identity()), lambda _name: ("hirom", {}), keep_silent=True
        )

        self.assertEqual(found["dsp1"].silent, ["Made Up (World).sfc"])

    def test_and_is_left_out_of_the_sources_by_default(self) -> None:
        found = record.gather(a_manifest(an_identity()), lambda _name: ("hirom", {}))

        self.assertEqual(found, {})

    def test_the_layout_a_cartridge_declares_travels_with_it(self) -> None:
        found = record.gather(a_manifest(an_identity()), lambda _name: ("lorom", {"read1": 1}))

        self.assertEqual(found["dsp1"].sources[0]["layout"], "lorom")


class PrintingTest(unittest.TestCase):
    def test_what_was_recorded_prints_as_what_it_holds(self) -> None:
        found = record.gather(
            a_manifest(an_identity()), lambda _name: ("hirom", {"write1 read1": 2})
        )

        self.assertIn("dsp1", repr(found["dsp1"]))
        self.assertIn("1 shapes", repr(found["dsp1"]))


class OrderTest(unittest.TestCase):
    """The order shapes are written in, which decides what a cut sweep spends on."""

    def test_the_longest_shape_comes_first(self) -> None:
        found = record.gather(
            a_manifest(an_identity()),
            lambda _name: ("hirom", {"read1": 90, "write1 write1 read1": 1}),
        )

        self.assertEqual(found["dsp1"].ordered()[0]["shape"], "write1 write1 read1")

    def test_and_the_busier_of_two_equal_lengths_comes_first(self) -> None:
        found = record.gather(
            a_manifest(an_identity()), lambda _name: ("hirom", {"read1": 1, "write1": 9})
        )

        self.assertEqual(found["dsp1"].ordered()[0]["shape"], "write1")

    def test_every_shape_survives_the_ordering(self) -> None:
        found = record.gather(
            a_manifest(an_identity()),
            lambda _name: ("hirom", {"read1": 1, "write1": 2, "poll1 read2": 3}),
        )

        self.assertEqual(len(found["dsp1"].ordered()), 3)


class WritingTest(unittest.TestCase):
    def _written(self, **held: Any) -> Any:
        where = Path(tempfile.mkdtemp())
        found = record.gather(
            a_manifest(an_identity(**held)), lambda _name: ("hirom", {"write1 read1": 2})
        )
        record.write(found, where)
        part = held.get("part", "dsp1")
        return json.loads((where / f"{part}shapes.json").read_text())

    def test_the_file_is_named_after_the_part_it_holds(self) -> None:
        self.assertEqual(self._written()["part"], "dsp1")

    def test_it_names_the_tool_that_read_the_cartridges(self) -> None:
        self.assertIn("snes-driver-python", self._written()["producedBy"])

    def test_and_every_cartridge_it_was_read_from(self) -> None:
        self.assertEqual(len(self._written()["readFrom"]), 1)

    def test_and_the_shapes_themselves(self) -> None:
        self.assertEqual(self._written()["shapes"][0]["shape"], "write1 read1")

    def test_no_byte_of_a_cartridge_reaches_the_file(self) -> None:
        written = json.dumps(self._written())

        self.assertNotIn("payload", written)
        self.assertNotIn("bytes:", written)

    def test_a_part_that_only_went_silent_writes_no_file(self) -> None:
        where = Path(tempfile.mkdtemp())
        found = record.gather(
            a_manifest(an_identity()), lambda _name: ("hirom", {}), keep_silent=True
        )

        self.assertEqual(record.write(found, where), [])
        self.assertEqual(list(where.iterdir()), [])

    def test_a_part_with_nothing_recorded_writes_no_file(self) -> None:
        where = Path(tempfile.mkdtemp())

        record.write({}, where)

        self.assertEqual(list(where.iterdir()), [])


class ReadingTest(unittest.TestCase):
    """The step that opens a cartridge, which is the only reason one is opened."""

    def test_a_cartridge_that_is_not_on_this_machine_reads_as_nothing(self) -> None:
        self.assertIsNone(record.reading("nowhere.sfc", Path("/nowhere/at/all")))

    def test_a_cartridge_that_is_here_is_confirmed_before_it_is_read(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "made-up.sfc").write_bytes(b"\x00" * 64)
        confirmed: list[bytes] = []

        record.reading(
            "made-up.sfc",
            where,
            confirm=confirmed.append,
            layout_of=lambda _image: "hirom",
            shapes_of=lambda _image, _window: {},
        )

        self.assertEqual(len(confirmed), 1)

    def test_and_what_it_says_comes_back_with_its_layout(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "made-up.sfc").write_bytes(b"\x00" * 64)

        found = record.reading(
            "made-up.sfc",
            where,
            confirm=lambda _image: None,
            layout_of=lambda _image: "lorom",
            shapes_of=lambda _image, _window: {"read1": 1},
        )

        self.assertEqual(found, ("lorom", {"read1": 1}))

    def test_a_cartridge_that_is_not_the_one_named_is_refused(self) -> None:
        where = Path(tempfile.mkdtemp())
        (where / "made-up.sfc").write_bytes(b"\x00" * 64)

        def refuse(_image: bytes) -> None:
            raise Complaint("that is not the file this names")

        with self.assertRaises(Complaint):
            record.reading("made-up.sfc", where, confirm=refuse)


class EntryTest(unittest.TestCase):
    def test_told_no_manifest_it_reads_the_one_that_ships(self) -> None:
        said: list[str] = []

        code = record.main([], reading=lambda _name: None, say=said.append)

        self.assertEqual(code, 2)
        self.assertIn("nothing to read", " ".join(said))

    def test_a_machine_with_no_cartridge_says_so_rather_than_writing_nothing(self) -> None:
        said: list[str] = []

        code = record.main(
            [],
            manifest=a_manifest(an_identity()),
            reading=lambda _name: None,
            say=said.append,
        )

        self.assertEqual(code, 2)
        self.assertIn("nothing to read", " ".join(said))

    def test_a_run_that_reads_something_reports_what_it_wrote(self) -> None:
        where = Path(tempfile.mkdtemp())
        said: list[str] = []

        code = record.main(
            [],
            manifest=a_manifest(an_identity()),
            reading=lambda _name: ("hirom", {"write1 read1": 2}),
            where=where,
            say=said.append,
        )

        self.assertEqual(code, 0)
        self.assertTrue((where / "dsp1shapes.json").exists())
        self.assertIn("dsp1", " ".join(said))

    def test_and_names_every_cartridge_that_said_nothing(self) -> None:
        said: list[str] = []

        record.main(
            [],
            manifest=a_manifest(an_identity(name="quiet.sfc"), an_identity(name="loud.sfc")),
            reading=lambda name: ("hirom", {} if name == "quiet.sfc" else {"write1 read1": 1}),
            where=Path(tempfile.mkdtemp()),
            say=said.append,
        )

        self.assertIn("quiet.sfc", " ".join(said))


if __name__ == "__main__":
    unittest.main()
