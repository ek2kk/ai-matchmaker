import os

import pytest

from ai_dating.ai.client import extract_chat_completion
from ai_dating.config import Settings


@pytest.mark.integration
def test_openai_compatible_provider_returns_schema_shaped_json():
    if os.environ.get("DSLAB_API_KEY"):
        settings = Settings()
    elif os.environ.get("OPENROUTER_API_KEY"):
        settings = Settings()
    elif os.environ.get("YANDEX_AI_BASE_URL") and os.environ.get("YANDEX_AI_API_KEY"):
        settings = Settings()
    else:
        pytest.skip("DS Lab, OpenRouter or Yandex AI credentials are not set")
    result = extract_chat_completion(
        settings, "self_about", "Long walks and dumplings on weekends."
    )
    assert isinstance(result.payload, dict)
    assert "facts" in result.payload
