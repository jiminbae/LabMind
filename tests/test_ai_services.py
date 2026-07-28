from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.classification_service import (
    ChemicalClassification,
    classify_cas_with_gemini,
)
from backend.provider_config import resolve_gemini_config
from backend.query_translation_service import (
    ChemicalQueryTranslation,
    translate_chemical_question,
)
from backend.vision_service import LabelExtraction, extract_label_fields


SINGLE_PIXEL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010804000000b51c0c02"
    "0000000b4944415478da6364f80f00010501012718e3660000000049454e44ae426082"
)


class FakeModels:
    def __init__(self, parsed: object) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(dict(kwargs))
        return SimpleNamespace(parsed=self.parsed)


class AIServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "inventory.db"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_provider_defaults_to_safe_manual_mode(self) -> None:
        config = resolve_gemini_config(environ={}, env_path=None)

        self.assertEqual(config.mode, "manual")
        self.assertEqual(config.provider, "gemini")
        self.assertIsNone(config.api_key)

    def test_manual_vision_never_returns_fake_label_values(self) -> None:
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "manual"},
            env_path=None,
        )

        self.assertEqual(result.status, "manual")
        self.assertEqual(result.fields, {"confidence": 0})
        self.assertIn("not configured", result.message)

    def test_live_vision_parses_only_the_allowed_fields(self) -> None:
        models = FakeModels(
            LabelExtraction(
                cas_number=" 64-17-5 ",
                specification=" HPLC grade ",
                batch_number=" LOT-42 ",
                manufacturer=" Sigma-Aldrich ",
                confidence=0.92,
            )
        )
        client = SimpleNamespace(models=models)

        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={
                "LABMIND_VISION_MODE": "live",
                "GEMINI_API_KEY": "test-key",
                "GEMINI_MODEL": "test-model",
            },
            env_path=None,
            client=client,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(
            result.fields,
            {
                "specification": "HPLC grade",
                "batch_number": "LOT-42",
                "manufacturer": "Sigma-Aldrich",
                "confidence": 92,
                "cas_number": "64-17-5",
            },
        )
        self.assertEqual(models.calls[0]["model"], "test-model")

    def test_invalid_vision_cas_is_not_prefilled(self) -> None:
        models = FakeModels(
            LabelExtraction(cas_number="64-17-6", confidence=0.9)
        )
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
            client=SimpleNamespace(models=models),
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.fields["cas_number"], "")
        self.assertIn("check digit failed", result.message)

    def test_unsupported_image_fails_without_provider_call(self) -> None:
        result = extract_label_fields(
            b"not-an-image",
            "label.pdf",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("Unsupported image format", result.message)

    def test_classification_requires_a_valid_cas_and_live_configuration(self) -> None:
        invalid = classify_cas_with_gemini(
            "64-17-6",
            db_path=self.database_path,
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
        )
        manual = classify_cas_with_gemini(
            "64-17-5",
            db_path=self.database_path,
            environ={"LABMIND_VISION_MODE": "manual"},
            env_path=None,
        )

        self.assertEqual(invalid.status, "manual")
        self.assertEqual(manual.status, "manual")
        self.assertEqual(manual.classification["labels"], [])
        self.assertNotIn("location", manual.classification)

    def test_classification_is_cached_by_cas_and_never_selects_storage(self) -> None:
        models = FakeModels(
            ChemicalClassification(
                labels=["Chiral ligand", "Phosphine ligand"],
                constraints=["Ambient temperature", "Keep away from oxidizers"],
                confidence=0.87,
                rationale="A chiral phosphine ligand.",
            )
        )
        environment = {"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"}
        client = SimpleNamespace(models=models)

        first = classify_cas_with_gemini(
            "76189-55-4",
            chemical_name="(R)-BINAP",
            db_path=self.database_path,
            environ=environment,
            env_path=None,
            client=client,
        )
        second = classify_cas_with_gemini(
            "76189-55-4",
            chemical_name="(R)-BINAP",
            db_path=self.database_path,
            environ=environment,
            env_path=None,
            client=client,
        )

        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "cached")
        self.assertEqual(len(models.calls), 1)
        self.assertEqual(first.classification["labels"], ["Chiral ligand", "Phosphine ligand"])
        self.assertNotIn("location", first.classification)

    def test_query_translation_returns_only_a_search_plan(self) -> None:
        models = FakeModels(
            ChemicalQueryTranslation(
                concept="Aldehyde-containing reagent",
                patterns=["[CH]=O"],
                required_labels=["Organic compound", "not allowed"],
                explanation="A carbonyl carbon bearing hydrogen.",
            )
        )

        result = translate_chemical_question(
            "Do we have an aldehyde reagent?",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
            client=SimpleNamespace(models=models),
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(result.translation["patterns"], ["[CH]=O"])
        self.assertEqual(result.translation["required_labels"], ["Organic compound"])
        self.assertNotIn("availability", result.translation)

    def test_query_translation_fails_closed_without_a_live_provider(self) -> None:
        result = translate_chemical_question(
            "Find a nonstandard ligand family.",
            environ={"LABMIND_VISION_MODE": "manual"},
            env_path=None,
        )

        self.assertEqual(result.status, "manual")
        self.assertIsNone(result.translation)


if __name__ == "__main__":
    unittest.main()
