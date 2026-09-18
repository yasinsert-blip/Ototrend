import unittest
from unittest.mock import Mock, patch

import requests

from app.ai import provider


class OpenAIProviderTests(unittest.TestCase):
    def test_analysis_json_chat_uses_ollama_json_mode(self):
        response = {"message": {"content": '{"title_tr":"Test"}'}}

        with patch.object(provider, "AI_PROVIDER", "ollama"), patch.object(
            provider.client, "chat", return_value=response
        ) as chat:
            result = provider.json_chat("test prompt")

        self.assertEqual(result, '{"title_tr":"Test"}')
        self.assertEqual(chat.call_args.kwargs["format"], "json")
        self.assertEqual(chat.call_args.kwargs["messages"][0]["role"], "system")

    def test_instagram_chat_uses_responses_api_json_mode(self):
        api_response = Mock()
        api_response.json.return_value = {
            "output_text": '{"instagram_title":"TEST"}'
        }

        with patch.object(provider, "AI_PROVIDER", "openai"), patch.object(
            provider, "OPENAI_API_KEY", "test-key"
        ), patch.object(provider, "OPENAI_MODEL", "gpt-5.6"), patch(
            "app.ai.provider.requests.post", return_value=api_response
        ) as post:
            result = provider.instagram_chat("test prompt")

        self.assertEqual(result, '{"instagram_title":"TEST"}')
        self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/responses")
        self.assertEqual(
            post.call_args.kwargs["json"]["text"]["format"]["type"],
            "json_object",
        )
        self.assertFalse(post.call_args.kwargs["json"]["store"])

    def test_openai_provider_requires_key_when_explicitly_selected(self):
        with patch.object(provider, "AI_PROVIDER", "openai"), patch.object(
            provider, "OPENAI_API_KEY", ""
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                provider.chat("test prompt")

    def test_openai_quota_error_is_explained(self):
        api_response = Mock(status_code=429)
        api_response.raise_for_status.side_effect = requests.HTTPError(
            response=api_response
        )

        with patch.object(provider, "AI_PROVIDER", "openai"), patch.object(
            provider, "OPENAI_API_KEY", "test-key"
        ), patch(
            "app.ai.provider.requests.post", return_value=api_response
        ):
            with self.assertRaisesRegex(RuntimeError, "kotası"):
                provider.chat("test prompt")


if __name__ == "__main__":
    unittest.main()
