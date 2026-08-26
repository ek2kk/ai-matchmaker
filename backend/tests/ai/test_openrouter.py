from ai_dating.ai.client import (
    _payload_from_content,
    extraction_model_version,
)
from ai_dating.config import Settings


def test_openrouter_key_selects_free_router_model():
    settings = Settings(_env_file=None, openrouter_api_key="sk-or-test")
    assert extraction_model_version(settings) == "openrouter/free"


def test_dslab_key_wins_over_openrouter():
    settings = Settings(
        _env_file=None,
        dslab_api_key="sk-dslab-test",
        openrouter_api_key="sk-or-test",
    )
    assert extraction_model_version(settings) == "gemini-2.5-flash-lite"


def test_yandex_folder_prefix_without_openrouter():
    settings = Settings(
        _env_file=None,
        yandex_ai_folder_id="folder",
        yandex_ai_model="yandexgpt-lite/latest",
    )
    assert extraction_model_version(settings) == "gpt://folder/yandexgpt-lite/latest"


def test_payload_strips_markdown_fence():
    payload = _payload_from_content('```json\n{"facts":[]}\n```')
    assert payload == {"facts": []}
