import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.provider_config import (
    OFFICIAL_OPENAI_BASE_URL,
    resolve_provider_config,
)
from backend.schemas import ResultStatus
from backend.vision_gateway import extract_label_with_provider
from backend.vision_service import LabelExtraction


class FakeResponses:
    def __init__(self, parsed=None, error=None) -> None:
        self.parsed = parsed
        self.error = error
        self.last_request = None

    def parse(self, **kwargs):
        self.last_request = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class FakeChatCompletions:
    def __init__(self, parsed=None) -> None:
        self.parsed = parsed
        self.last_request = None

    def parse(self, **kwargs):
        self.last_request = kwargs
        message = SimpleNamespace(parsed=self.parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeClient:
    def __init__(self, response_parsed=None, response_error=None, chat_parsed=None):
        self.responses = FakeResponses(response_parsed, response_error)
        self.chat = SimpleNamespace(
            completions=FakeChatCompletions(parsed=chat_parsed)
        )


def extraction() -> LabelExtraction:
    return LabelExtraction(
        catalog_number="HS4323K",
        lot_number="LOT-U1",
        expiry_date="2026-07-25",
        brand="Sigma-Aldrich",
        product_name=None,
        confidence=0.9,
    )


class ProviderConfigTests(unittest.TestCase):
    def test_official_key_cannot_be_redirected_by_openai_base_url(self) -> None:
        config = resolve_provider_config(
            "openai",
            environ={
                "OPENAI_API_KEY": "official-test-key",
                "OPENAI_BASE_URL": "https://malicious.example/v1",
            },
            env_path=None,
        )

        self.assertEqual(config.base_url, OFFICIAL_OPENAI_BASE_URL)
        self.assertEqual(config.api_key, "official-test-key")

    def test_univibe_uses_separate_credentials_and_defaults(self) -> None:
        config = resolve_provider_config(
            "univibe",
            environ={"UNIVIBE_API_KEY": "univibe-test-key"},
            env_path=None,
        )

        self.assertEqual(config.api_key, "univibe-test-key")
        self.assertEqual(config.base_url, "https://api.univibe.cc/openai/v1")
        self.assertEqual(config.model, "gpt-5.4")

    def test_univibe_rejects_an_unrelated_host(self) -> None:
        with self.assertRaises(ValueError):
            resolve_provider_config(
                "univibe",
                environ={
                    "UNIVIBE_API_KEY": "test-key",
                    "UNIVIBE_BASE_URL": "https://example.com/openai/v1",
                },
                env_path=None,
            )


class VisionGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        handle.write(b"\x89PNG\r\n\x1a\nmock-image-bytes")
        handle.close()
        self.image_path = Path(handle.name)

    def tearDown(self) -> None:
        self.image_path.unlink(missing_ok=True)

    def test_mock_mode_does_not_require_any_provider_key(self) -> None:
        result = extract_label_with_provider(
            self.image_path,
            mode="mock",
            environ={},
            env_path=None,
        )

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.catalog_number, "HS4323K")

    def test_live_univibe_requires_its_own_key(self) -> None:
        result = extract_label_with_provider(
            self.image_path,
            mode="live",
            provider="univibe",
            environ={"OPENAI_API_KEY": "official-test-key"},
            env_path=None,
        )

        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertEqual(result.error_message, "UNIVIBE_API_KEY is not configured.")

    def test_univibe_uses_responses_api_when_compatible(self) -> None:
        client = FakeClient(response_parsed=extraction())
        result = extract_label_with_provider(
            self.image_path,
            mode="live",
            provider="univibe",
            client=client,
            environ={"UNIVIBE_API_KEY": "univibe-test-key"},
            env_path=None,
        )

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.catalog_number, "HS4323K")
        self.assertEqual(client.responses.last_request["model"], "gpt-5.4")

    def test_univibe_falls_back_to_chat_completions(self) -> None:
        client = FakeClient(
            response_error=RuntimeError("responses unsupported"),
            chat_parsed=extraction(),
        )
        result = extract_label_with_provider(
            self.image_path,
            mode="live",
            provider="univibe",
            client=client,
            environ={"UNIVIBE_API_KEY": "univibe-test-key"},
            env_path=None,
        )

        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.lot_number, "LOT-U1")
        request = client.chat.completions.last_request
        self.assertEqual(request["model"], "gpt-5.4")
        self.assertIs(request["response_format"], LabelExtraction)


if __name__ == "__main__":
    unittest.main()
