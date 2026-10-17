import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import snesdsp  # noqa: E402

EVERY_PART = {"dsp1", "dsp1a", "dsp1b", "dsp2", "dsp3", "dsp4"}

LISTED = "dsp1, dsp1a, dsp1b, dsp2, dsp3, dsp4"

MANIFEST = ROOT / "snesdsp" / "artifacts.manifest.json"

PROGRAM_WORDS = 2048

TABLE_WORDS = 1024


def built(name: str) -> Any:
    identity = SimpleNamespace(
        part="dsp1",
        processor="upd7725",
        revision="MADE UP",
        program_words=PROGRAM_WORDS,
        data_words=TABLE_WORDS,
    )
    image = bytes(PROGRAM_WORDS * 3 + TABLE_WORDS * 2)
    return snesdsp.Chip(name, image=image, identity=identity, boot=0)


def declared() -> list[dict[str, Any]]:
    held = json.loads(MANIFEST.read_text())
    assert isinstance(held, dict), f"{MANIFEST} does not hold an object"
    artifacts = held["artifacts"]
    assert isinstance(artifacts, list), f"{MANIFEST} does not hold a list of images"
    return artifacts


class CatalogueTest(unittest.TestCase):
    def test_the_package_names_every_part_it_covers(self) -> None:
        # Arrange
        catalogue = snesdsp.MODELS

        # Act
        names = set(catalogue)

        # Assert
        self.assertEqual(names, EVERY_PART)

    def test_a_part_says_what_its_program_does(self) -> None:
        # Arrange
        model = snesdsp.MODELS["dsp2"]

        # Act
        summary = model.summary

        # Assert
        self.assertIn("tile conversion", summary)

    def test_and_which_image_it_runs(self) -> None:
        # Arrange
        catalogue = snesdsp.MODELS

        # Act
        images = {name: model.image for name, model in catalogue.items()}

        # Assert
        self.assertEqual(
            images,
            {
                "dsp1": "dsp1",
                "dsp1a": "dsp1",
                "dsp1b": "dsp1b",
                "dsp2": "dsp2",
                "dsp3": "dsp3",
                "dsp4": "dsp4",
            },
        )

    def test_the_one_part_that_runs_another_part_image_is_published(self) -> None:
        # Arrange
        expected = {"dsp1a": "dsp1"}

        # Act
        shared = snesdsp.SHARES_MICROCODE

        # Assert
        self.assertEqual(shared, expected)

    def test_and_is_still_a_part_in_its_own_right(self) -> None:
        # Arrange
        model = snesdsp.MODELS["dsp1a"]

        # Act
        name = model.name

        # Assert
        self.assertEqual(name, "dsp1a")

    def test_a_part_prints_as_itself_and_the_image_it_runs(self) -> None:
        # Arrange
        model = snesdsp.MODELS["dsp1a"]

        # Act
        printed = repr(model)

        # Assert
        self.assertIn("dsp1a", printed)
        self.assertIn("dsp1 image", printed)

    def test_every_part_carries_a_summary(self) -> None:
        # Arrange
        catalogue = snesdsp.MODELS

        # Act
        bare = [name for name, model in catalogue.items() if not model.summary]

        # Assert
        self.assertEqual(bare, [])

    def test_every_record_is_the_published_model_type(self) -> None:
        # Arrange
        catalogue = snesdsp.MODELS

        # Act
        kinds = {type(model) for model in catalogue.values()}

        # Assert
        self.assertEqual(kinds, {snesdsp.Model})


class NamingTest(unittest.TestCase):
    def test_a_part_is_built_by_its_name(self) -> None:
        # Arrange
        name = "dsp3"

        # Act
        part = built(name)

        # Assert
        self.assertEqual(part.model, "dsp3")

    def test_the_dsp1_answers_to_the_aliases_the_readme_lists(self) -> None:
        # Arrange
        expected = ("dsp-1", "upd77c25dsp1", "nintendodsp1")

        # Act
        aliases = snesdsp.MODELS["dsp1"].aliases

        # Assert
        self.assertEqual(aliases, expected)

    def test_and_building_by_any_of_them_builds_the_dsp1(self) -> None:
        # Arrange
        aliases = snesdsp.MODELS["dsp1"].aliases

        # Act
        built_as = {built(alias).model for alias in aliases}

        # Assert
        self.assertEqual(built_as, {"dsp1"})

    def test_the_name_is_read_without_regard_to_case_hyphens_or_underscores(self) -> None:
        # Arrange
        name = "DSP_3"

        # Act
        part = built(name)

        # Assert
        self.assertEqual(part.model, "dsp3")

    def test_a_name_no_part_answers_to_is_refused_naming_what_there_is(self) -> None:
        # Arrange
        name = "dsp5"

        # Act
        with self.assertRaises(snesdsp.UnknownModelError) as refused:
            snesdsp.Chip(name)

        # Assert
        self.assertEqual(
            str(refused.exception), f"dsp5 is not a part this package covers; it has {LISTED}"
        )

    def test_no_alias_belongs_to_two_parts(self) -> None:
        # Arrange
        catalogue = snesdsp.MODELS

        # Act
        seen = [alias for model in catalogue.values() for alias in model.aliases]

        # Assert
        self.assertEqual(len(seen), len(set(seen)))


class DeclaredImageTest(unittest.TestCase):
    def test_every_part_runs_an_image_the_manifest_declares(self) -> None:
        # Arrange
        declared_images = {one["part"] for one in declared()}

        # Act
        missing = [n for n, model in snesdsp.MODELS.items() if model.image not in declared_images]

        # Assert
        self.assertEqual(missing, [])

    def test_every_declared_image_carries_a_deciding_digest(self) -> None:
        # Arrange
        images = declared()

        # Act
        widths = {len(accepted["sha256"]) for one in images for accepted in one["accepted"]}

        # Assert
        self.assertEqual(widths, {64})

    def test_every_part_of_this_family_runs_the_same_processor(self) -> None:
        # Arrange
        processors = {one["part"]: one["processor"] for one in declared()}

        # Act
        found = {processors[model.image] for model in snesdsp.MODELS.values()}

        # Assert
        self.assertEqual(found, {"upd7725"})


class BuildingTest(unittest.TestCase):
    def test_asking_for_a_part_with_no_image_asks_for_its_microcode(self) -> None:
        # Arrange
        nothing: dict[str, tuple[object, Path]] = {}

        # Act
        with self.assertRaises(snesdsp.NoFirmware) as refused:
            snesdsp.Chip("dsp2", images=nothing)

        # Assert
        self.assertIn("microcode", str(refused.exception))

    def test_a_name_no_part_answers_to_is_refused_before_any_image_is_looked_for(self) -> None:
        # Arrange
        nothing: dict[str, tuple[object, Path]] = {}

        # Act
        with self.assertRaises(snesdsp.UnknownModelError):
            snesdsp.Chip("dsp9", images=nothing)

        # Assert
        self.assertNotIn("dsp9", snesdsp.MODELS)

    def test_the_package_offers_no_way_to_ask_for_anything_but_the_part(self) -> None:
        # Arrange
        published = snesdsp.__all__

        # Act
        backends = {"backend", "MODELLED"} & set(published)

        # Assert
        self.assertEqual(backends, set())


class NamingNoneTest(unittest.TestCase):
    def test_building_without_naming_a_model_is_refused_naming_every_model(self) -> None:
        # Arrange
        expected = (
            "no model was named, and this package will not choose one for you."
            f" Name one of: {LISTED}"
        )

        # Act
        with self.assertRaises(snesdsp.UnknownModelError) as refused:
            snesdsp.Chip()

        # Assert
        self.assertEqual(str(refused.exception), expected)

    def test_nothing_named_describe_or_a_default_model_is_published(self) -> None:
        # Arrange
        names = ("describe", "DEFAULT_MODEL")

        # Act
        found = [name for name in names if hasattr(snesdsp, name)]

        # Assert
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
