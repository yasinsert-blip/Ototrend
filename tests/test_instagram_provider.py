import unittest
from unittest.mock import patch

from app.ai.provider import instagram_chat


class InstagramProviderTests(unittest.TestCase):
    def test_ollama_instagram_requests_json_format(self):
        with patch("app.ai.provider._active_provider", return_value="ollama"), patch(
            "app.ai.provider.client.chat"
        ) as chat:
            chat.return_value = {"message": {"content": "{}"}}

            self.assertEqual(instagram_chat("taslak"), "{}")

        self.assertEqual(chat.call_args.kwargs["format"], "json")


if __name__ == "__main__":
    unittest.main()
