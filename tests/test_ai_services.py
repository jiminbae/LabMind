from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from google import genai
from google.genai import types

from backend.classification_service import (
    ChemicalClassification,
    classify_cas_with_gemini,
)
from backend.provider_config import resolve_gemini_config
from backend.provider_errors import provider_failure_message
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
    def __init__(self, parsed: object = None, error: Exception | None = None) -> None:
        self.parsed = parsed
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        return SimpleNamespace(parsed=self.parsed)


class FakeAPIError(Exception):
    def __init__(self, code: int, status: str, raw_message: str) -> None:
        super().__init__(raw_message)
        self.code = code
        self.status = status


def label_result(**overrides: object) -> LabelExtraction:
    values: dict[str, object] = {
        "chemical_name": None,
        "cas_number": None,
        "specification": None,
        "batch_number": None,
        "manufacturer": None,
        "confidence": 0.0,
    }
    values.update(overrides)
    return LabelExtraction.model_validate(values)


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
        self.assertEqual(config.model, "gemini-3.6-flash")

    def test_provider_rejects_conflicting_key_aliases_without_exposing_them(self) -> None:
        with self.assertRaisesRegex(ValueError, "Remove the old GOOGLE_API_KEY") as raised:
            resolve_gemini_config(
                environ={
                    "LABMIND_VISION_MODE": "live",
                    "GEMINI_API_KEY": "new-secret",
                    "GOOGLE_API_KEY": "old-secret",
                },
                env_path=None,
            )

        message = str(raised.exception)
        self.assertNotIn("new-secret", message)
        self.assertNotIn("old-secret", message)

    def test_provider_accepts_one_key_or_matching_aliases(self) -> None:
        gemini_only = resolve_gemini_config(
            environ={"GEMINI_API_KEY": "same-key"}, env_path=None
        )
        matching = resolve_gemini_config(
            environ={
                "GEMINI_API_KEY": "same-key",
                "GOOGLE_API_KEY": "same-key",
            },
            env_path=None,
        )

        self.assertEqual(gemini_only.api_key, "same-key")
        self.assertEqual(matching.api_key, "same-key")

    def test_manual_vision_never_returns_fake_label_values(self) -> None:
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "manual"},
            env_path=None,
        )

        self.assertEqual(result.status, "manual")
        self.assertEqual(
            result.fields,
            {
                "chemical_name": "",
                "cas_number": "",
                "specification": "",
                "batch_number": "",
                "manufacturer": "",
                "confidence": 0,
            },
        )
        self.assertIn("not configured", result.message)

    def test_live_vision_parses_only_the_allowed_fields(self) -> None:
        models = FakeModels(
            label_result(
                chemical_name=" Ethanol ",
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
                "chemical_name": "Ethanol",
                "cas_number": "64-17-5",
                "specification": "HPLC grade",
                "batch_number": "LOT-42",
                "manufacturer": "Sigma-Aldrich",
                "confidence": 92,
            },
        )
        self.assertEqual(models.calls[0]["model"], "test-model")
        self.assertIsInstance(models.calls[0]["config"], types.GenerateContentConfig)
        self.assertIsInstance(models.calls[0]["contents"][0], types.Part)
        self.assertEqual(
            set(LabelExtraction.model_json_schema()["required"]),
            {
                "chemical_name",
                "cas_number",
                "specification",
                "batch_number",
                "manufacturer",
                "confidence",
            },
        )

    def test_google_sdk_serializes_image_schema_and_parses_response_offline(self) -> None:
        captured: dict[str, object] = {}
        payload = {
            "chemical_name": "Ethanol",
            "cas_number": "64-17-5",
            "specification": None,
            "batch_number": None,
            "manufacturer": "Example Chemicals",
            "confidence": 0.91,
        }

        def fake_request(
            method: str,
            path: str,
            request_dict: dict[str, object],
            http_options: object = None,
        ) -> types.HttpResponse:
            captured.update(method=method, path=path, body=request_dict)
            api_body = {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": json.dumps(payload)}],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ]
            }
            return types.HttpResponse(headers={}, body=json.dumps(api_body))

        client = genai.Client(api_key="offline-placeholder")
        models = client.models
        try:
            with patch.object(models._api_client, "request", side_effect=fake_request):
                result = extract_label_fields(
                    SINGLE_PIXEL_PNG,
                    "label.png",
                    environ={
                        "LABMIND_VISION_MODE": "live",
                        "GEMINI_API_KEY": "offline-placeholder",
                        "GEMINI_MODEL": "gemini-3.6-flash",
                    },
                    env_path=None,
                    client=client,
                )
        finally:
            client.close()

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.fields["chemical_name"], "Ethanol")
        self.assertEqual(captured["path"], "models/gemini-3.6-flash:generateContent")
        json.dumps(captured["body"])
        body = captured["body"]
        self.assertIsInstance(body, dict)
        schema = body["generationConfig"]["responseSchema"]
        self.assertEqual(set(schema["required"]), set(LabelExtraction.model_fields))
        self.assertTrue(schema["properties"]["chemical_name"]["nullable"])
        self.assertEqual(
            body["contents"][0]["parts"][0]["inlineData"]["mimeType"],
            "image/png",
        )

    def test_invalid_vision_cas_is_not_prefilled(self) -> None:
        models = FakeModels(
            label_result(
                chemical_name="Ethanol",
                cas_number="64-17-6",
                confidence=0.9,
            )
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
        self.assertEqual(result.fields["chemical_name"], "Ethanol")
        self.assertIn("check digit failed", result.message)

    def test_name_only_extraction_is_preserved_as_partial(self) -> None:
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
            client=SimpleNamespace(
                models=FakeModels(label_result(chemical_name="Sodium chloride", confidence=0.8))
            ),
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.fields["chemical_name"], "Sodium chloride")
        self.assertIn("CAS number", result.message)

    def test_valid_cas_with_missing_fields_is_partial(self) -> None:
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
            client=SimpleNamespace(
                models=FakeModels(label_result(cas_number="64-17-5", confidence=0.7))
            ),
        )

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.fields["cas_number"], "64-17-5")
        self.assertIn("chemical name", result.message)

    def test_empty_provider_result_requests_manual_entry(self) -> None:
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
            client=SimpleNamespace(models=FakeModels(label_result())),
        )

        self.assertEqual(result.status, "manual")
        self.assertEqual(result.provider, "gemini")
        self.assertIn("No supported label fields", result.message)

    def test_provider_error_exposes_only_safe_code_and_guidance(self) -> None:
        error = FakeAPIError(404, "NOT_FOUND", "raw secret=test-key and provider details")
        result = extract_label_fields(
            SINGLE_PIXEL_PNG,
            "label.png",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
            client=SimpleNamespace(models=FakeModels(error=error)),
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("404 NOT_FOUND", result.message)
        self.assertIn("model is not available", result.message)
        self.assertNotIn("test-key", result.message)
        self.assertNotIn("provider details", result.message)

    def test_server_error_is_reported_without_raw_details(self) -> None:
        message = provider_failure_message(
            FakeAPIError(503, "UNAVAILABLE", "internal provider response"),
            operation="Vision extraction",
            fallback="Retry later.",
        )

        self.assertIn("503 SERVER_ERROR", message)
        self.assertIn("temporarily unavailable", message)
        self.assertNotIn("internal provider response", message)

    def test_unsupported_image_fails_without_provider_call(self) -> None:
        result = extract_label_fields(
            b"not-an-image",
            "label.pdf",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("Unsupported image format", result.message)

    def test_mismatched_image_contents_fail_without_provider_call(self) -> None:
        result = extract_label_fields(
            b"not-an-image",
            "label.png",
            environ={"LABMIND_VISION_MODE": "live", "GEMINI_API_KEY": "key"},
            env_path=None,
        )

        self.assertEqual(result.status, "failed")
        self.assertIn("do not match", result.message)

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
