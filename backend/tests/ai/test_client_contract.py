import os

import pytest

from ai_dating.ai.client import extract_chat_completion
from ai_dating.config import Settings


@pytest.mark.integration
def test_openai_compatible_provider_returns_schema_shaped_json():
    if not os.environ.get("DSLAB_API_KEY"):
        pytest.skip("DSLAB_API_KEY is not set")
    settings = Settings()
    result = extract_chat_completion(
        settings, "self_about", "Long walks and dumplings on weekends."
    )
    assert isinstance(result.payload, dict)
    assert "facts" in result.payload
