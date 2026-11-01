import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from generation.client import api_key, get_client, model_name


class GenerationClientTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "LIFELOG_LLM_API_KEY": "router-key",
            "LIFELOG_LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LIFELOG_LLM_MODEL": "provider/model:free",
            "OPENAI_API_KEY": "legacy-key",
            "OPENAI_MODEL": "legacy-model",
        },
        clear=False,
    )
    def test_explicit_compatible_provider_configuration_takes_precedence(self):
        self.assertEqual(api_key(), "router-key")
        self.assertEqual(model_name(), "provider/model:free")
        openai_module = types.ModuleType("openai")
        openai_module.OpenAI = Mock()
        with patch.dict(sys.modules, {"openai": openai_module}):
            get_client()
        openai_module.OpenAI.assert_called_once_with(
            api_key="router-key",
            base_url="https://openrouter.ai/api/v1",
        )

    @patch.dict(
        os.environ,
        {
            "LIFELOG_LLM_API_KEY": "",
            "LIFELOG_LLM_MODEL": "",
            "LIFELOG_LLM_BASE_URL": "",
            "OPENAI_API_KEY": "legacy-key",
            "OPENAI_MODEL": "legacy-model",
        },
        clear=False,
    )
    def test_existing_openai_environment_remains_supported(self):
        self.assertEqual(api_key(), "legacy-key")
        self.assertEqual(model_name(), "legacy-model")


if __name__ == "__main__":
    unittest.main()
