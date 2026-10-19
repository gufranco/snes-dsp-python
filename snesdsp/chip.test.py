import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, override
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024

BLANK = bytes(PROGRAM_WORDS * 3 + TABLE_WORDS * 2)

BOOT = 64

COUNTING = bytes(range(256)) * 24 + bytes(TABLE_WORDS * 2)


def an_identity(part: str = "dsp1") -> SimpleNamespace:
    return SimpleNamespace(
        part=part,
        processor="upd7725",
        revision="MADE UP",
        program_words=PROGRAM_WORDS,
        data_words=TABLE_WORDS,
    )


def a_part(model: str = "dsp1", **options: Any) -> Any:
    return snesdsp.Chip(model, image=BLANK, identity=an_identity(), boot=BOOT, **options)


def on_disk() -> dict[str, tuple[object, Path]]:
    where = Path(tempfile.mkdtemp()) / "made-up.bin"
    where.write_bytes(COUNTING)
    return {"dsp1": (an_identity(), where)}


class WithoutTheProcessorTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        hidden = mock.patch.dict(sys.modules, {"upd7725": None})
        hidden.start()
        self.addCleanup(hidden.stop)

    def test_with_no_processor_it_offers_nothing(self) -> None:
        # Arrange
        expected: dict[str, object] = {}

        # Act
        found = snesdsp.available()

        # Assert
        self.assertEqual(found, expected)

    def test_and_says_the_submodule_is_missing(self) -> None:
        # Arrange
        wanted = "submodule"

        # Act
        reason = snesdsp.why_not()

        # Assert
        self.assertIn(wanted, str(reason))

    def test_and_refuses_to_build_a_part(self) -> None:
        # Arrange
        model = "dsp1"

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            snesdsp.Chip(model)

        # Assert
        self.assertIn("submodule", str(refused.exception))


class WithoutAnImageTest(unittest.TestCase):
    def test_with_a_processor_but_no_image_it_names_where_one_goes(self) -> None:
        # Arrange
        held: dict[str, tuple[object, Path]] = {}

        # Act
        reason = snesdsp.why_not(held)

        # Assert
        self.assertIn("SNES_DSP_FIRMWARE_DIR", str(reason))

    def test_a_part_sharing_an_image_that_is_absent_is_refused(self) -> None:
        # Arrange
        held: dict[str, tuple[object, Path]] = {}

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            snesdsp.Chip("dsp1a", images=held)

        # Assert
        self.assertIn("dsp1a", str(refused.exception))


class SharingTest(unittest.TestCase):
    def test_a_part_that_shares_an_image_is_offered_when_the_image_is(self) -> None:
        # Arrange
        held = {"dsp1": ("identity", Path("dsp1.bin"))}

        # Act
        found = snesdsp.available(held)

        # Assert
        self.assertEqual(found["dsp1a"], held["dsp1"])

    def test_and_is_not_offered_when_it_is_not(self) -> None:
        # Arrange
        held = {"dsp2": ("identity", Path("dsp2.bin"))}

        # Act
        found = snesdsp.available(held)

        # Assert
        self.assertEqual(sorted(found), ["dsp2"])

    def test_what_was_found_is_left_as_it_was(self) -> None:
        # Arrange
        held = {"dsp1": ("identity", Path("dsp1.bin"))}

        # Act
        snesdsp.available(held)

        # Assert
        self.assertEqual(sorted(held), ["dsp1"])


class AvailabilityTest(unittest.TestCase):
    def test_every_part_offered_is_one_the_catalogue_names(self) -> None:
        # Arrange
        catalogue = set(snesdsp.MODELS)

        # Act
        found = set(snesdsp.available())

        # Assert
        self.assertEqual(found - catalogue, set())

    def test_asking_for_a_part_it_cannot_run_is_refused(self) -> None:
        # Arrange
        held: dict[str, tuple[object, Path]] = {"dsp2": (an_identity("dsp2"), Path("x"))}

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            snesdsp.Chip("dsp4", images=held)

        # Assert
        self.assertIn("microcode", str(refused.exception))

    def test_the_refusal_says_what_is_missing_and_where_it_goes(self) -> None:
        # Arrange
        held: dict[str, tuple[object, Path]] = {}

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            snesdsp.Chip("dsp4", images=held)

        # Assert
        self.assertIn("dsp4", str(refused.exception))
        self.assertIn("SNES_DSP_FIRMWARE_DIR", str(refused.exception))


class FoundOnDiskTest(unittest.TestCase):
    def test_an_image_the_search_found_is_read_from_its_file(self) -> None:
        # Arrange
        held = on_disk()

        # Act
        part = snesdsp.Chip("dsp1", images=held, boot=BOOT)

        # Assert
        self.assertEqual(part.core.stores.program[0], 0x000102)

    def test_a_part_sharing_another_part_image_is_built_from_it(self) -> None:
        # Arrange
        held = on_disk()

        # Act
        part = snesdsp.Chip("dsp1a", images=held, boot=BOOT)

        # Assert
        self.assertEqual((part.part, part.identity.part), ("dsp1a", "dsp1"))

    def test_a_dump_storing_words_low_byte_first_is_run_in_the_published_order(self) -> None:
        # Arrange
        identity, where = on_disk()["dsp1"]
        held = {"dsp1": (SimpleNamespace(**vars(identity), order=snesdsp.LOW_BYTE_FIRST), where)}

        # Act
        part = snesdsp.Chip("dsp1", images=held, boot=BOOT)

        # Assert
        self.assertEqual(part.core.stores.program[0], 0x020100)

    def test_with_an_image_present_there_is_no_reason_it_cannot_run(self) -> None:
        # Arrange
        held = on_disk()

        # Act
        reason = snesdsp.why_not(held)

        # Assert
        self.assertIsNone(reason)


class SuppliedImageTest(unittest.TestCase):
    def test_a_supplied_image_is_run_without_one_on_disk(self) -> None:
        # Arrange
        identity = an_identity()

        # Act
        part = snesdsp.Chip("dsp2", image=BLANK, identity=identity, boot=BOOT)

        # Assert
        self.assertIs(part.identity, identity)

    def test_it_names_the_processor_the_image_says_it_runs_on(self) -> None:
        # Arrange
        identity = an_identity()

        # Act
        part = snesdsp.Chip("dsp1", image=BLANK, identity=identity, boot=BOOT)

        # Assert
        self.assertEqual(part.processor, "upd7725")

    def test_an_alias_builds_the_part_under_its_canonical_name(self) -> None:
        # Arrange
        alias = "DSP-1"

        # Act
        part = a_part(alias)

        # Assert
        self.assertEqual((part.model, part.part), ("dsp1", "dsp1"))

    def test_a_reset_hands_the_part_back(self) -> None:
        # Arrange
        part = a_part()

        # Act
        handed = part.reset()

        # Assert
        self.assertIs(handed, part)

    def test_and_leaves_it_where_a_fresh_one_starts_with_the_same_identity(self) -> None:
        # Arrange
        part = a_part()
        part.step(200)
        before = part.identity
        fresh = a_part()

        # Act
        part.reset()

        # Assert
        self.assertIs(part.identity, before)
        self.assertEqual(part.core.registers.pc, fresh.core.registers.pc)
        self.assertEqual(part.core.cycles, fresh.core.cycles)

    def test_it_prints_as_the_part_and_the_processor_it_runs_on(self) -> None:
        # Arrange
        part = a_part("dsp3")

        # Act
        printed = repr(part)

        # Assert
        self.assertEqual(printed, "<Chip dsp3 on upd7725>")

    def test_an_image_supplied_without_saying_what_it_is_is_refused(self) -> None:
        # Arrange
        image = bytes(64)

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            snesdsp.Chip("dsp1", image=image)

        # Assert
        self.assertIn("program", str(refused.exception))


if __name__ == "__main__":
    unittest.main()
